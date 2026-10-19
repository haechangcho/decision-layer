"""Operator-owned versioned Method drafts. Python is trusted installed code, not a sandbox."""
import asyncio
from copy import copy
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import sys
import threading
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from ..core.errors import DecisionLayerError
from .base import Method
from .skills import SkillMethod


class AssetError(DecisionLayerError):
    code = 'METHOD_ASSET_ERROR'
    http_status = 400


class AssetConflict(AssetError):
    code = 'METHOD_ASSET_CONFLICT'
    http_status = 409


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: str
    revision: str | None = None
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')
    content: str = Field(min_length=1, max_length=150_000)


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str
    reviewed: bool = False


def import_method(module_name, name, version):
    module = importlib.import_module(module_name)
    items = getattr(module, 'METHODS', None)
    if not isinstance(items, (list, tuple)) or len(items) != 1 or not isinstance(items[0], Method):
        raise ValueError('Export exactly one registered Method in METHODS')
    method = copy(items[0])
    if hasattr(method, "source_snapshot"):del method.source_snapshot
    if method.manifest.name != name or method.manifest.implementation != 'python':
        raise ValueError('The Python export must keep this Method name and implementation')
    method.manifest = method.manifest.model_copy(deep=True, update={'version': version})
    from .registry import MethodRegistry
    trial = MethodRegistry();trial.register(method)
    return method


class MethodAssets:
    def __init__(self, root, registry):
        self.root = Path(root).resolve() if root else None
        self.registry = registry
        self.lock = threading.RLock()
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
            package = self.root / 'dl_method_assets'
            package.mkdir(exist_ok=True)
            (package / '__init__.py').touch(exist_ok=True)
            if 'dl_method_assets' in sys.modules:
                paths = sys.modules['dl_method_assets'].__path__
                if str(package) not in paths:paths.append(str(package))
            if str(self.root) not in sys.path:
                sys.path.insert(0, str(self.root))
            for entry in sorted(self.history(), key=lambda item: tuple(map(int,item['version'].split('.')))):
                method = self.load(entry)
                current = self.registry._methods.get(method.manifest.name)
                if current and current.manifest.version == method.manifest.version:
                    raise AssetConflict('Installed and UI assets share a version. Review the source ownership and publish a distinct version before startup.')
                activate = current is None or tuple(map(int,method.manifest.version.split('.'))) >= tuple(map(int,current.manifest.version.split('.')))
                self.registry.register(method, activate=activate,
                    compatibility=method.manifest.name in self.registry._compatibility)

    def _write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
        os.replace(temp, path)

    def _path(self, name):
        if not self.root:
            raise AssetError('Method editing storage is not configured')
        if not re.fullmatch(r'[a-z][a-z0-9_.-]*', name):
            raise AssetError('Invalid Method name')
        return self.root / 'drafts' / (name + '.json')

    def history(self, name=None):
        path = self.root / 'published.json' if self.root else None
        values = json.loads(path.read_text()) if path and path.exists() else []
        return [v for v in values if name is None or v['name'] == name]

    def draft(self, name):
        path = self._path(name)
        value = json.loads(path.read_text()) if path.exists() else None
        return value if value and not value.get('published') else None

    def save(self, name, req, actor):
        with self.lock:
            if len(req.content.encode()) > 150_000:
                raise AssetError('Source exceeds the 150 KB limit')
            current = self.registry.get(name).manifest
            previous = self.draft(name)
            if req.base_version != current.version or req.revision != (previous['revision'] if previous else None):
                raise AssetConflict('This asset or draft changed. Reload before saving.')
            if tuple(map(int,req.version.split('.'))) <= tuple(map(int,current.version.split('.'))):
                raise AssetError('Choose a version newer than the current published version')
            value = {'name':name,'base_version':req.base_version,'version':req.version,'content':req.content,
                'implementation':current.implementation,'revision':uuid4().hex,'actor':actor,
                'updated_at':datetime.now(timezone.utc).isoformat(),'validation':None}
            self._write(self._path(name), value)
            return value

    def _same(self, name, revision):
        value = self.draft(name)
        if not value or value['revision'] != revision:
            raise AssetConflict('The draft changed. Reload it before checking or publishing.')
        if self.registry.get(name).manifest.version != value['base_version']:
            raise AssetConflict('The published asset changed. Rebase this draft explicitly.')
        return value

    def _module(self, value):
        # Version is managed registration metadata, appended visibly to the installed module.
        content = value['content'] + '\n\n' + (
            'for _dl_registered_method in METHODS:\n'
            f'    _dl_registered_method.manifest = _dl_registered_method.manifest.model_copy(update={{"version": {value["version"]!r}}})\n')
        compile(content, '<method draft>', 'exec')
        digest = sha256(content.encode()).hexdigest()
        module = 'dl_method_assets.a_' + digest
        path = self.root / 'dl_method_assets' / ('a_' + digest + '.py')
        if path.exists() and path.read_text() != content:
            raise AssetConflict('Immutable code file does not match its hash')
        if not path.exists():path.write_text(content)
        return module

    async def check(self, name, revision):
        with self.lock:
            value = self._same(name, revision).copy()
        try:
            if value['implementation'] == 'skill':
                method = SkillMethod(value['content'])
                if method.manifest.name != name or method.manifest.version != value['version']:
                    raise ValueError('Skill name/version must match the publication fields')
                for suggested in method.guide.suggested_methods:self.registry.plannable(suggested)
                manifest = method.manifest.model_dump(mode='json')
                module = None
            else:
                module = self._module(value)
                env = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','TMPDIR','TMP','TEMP','MPLCONFIGDIR'}}
                env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys([str(self.root),*sys.path]))
                process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'decision_layer.methods.asset_worker',
                    module, name, value['version'], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
                except asyncio.TimeoutError:
                    process.kill();await process.wait()
                    raise ValueError('Python registration exceeded the 15 second limit')
                if process.returncode:
                    raise ValueError('Python import/registration failed: ' + stderr.decode(errors='replace')[-700:])
                manifest = json.loads(stdout.decode().split('DL_ASSET_MANIFEST:')[-1])
            report = {'status':'pass','scope':'syntax_and_registration_only','analytical_quality_verified':False,
                      'manifest':manifest,'module':module}
        except (SyntaxError, ValueError, TypeError) as exc:
            report = {'status':'fail','scope':'syntax_and_registration_only','message':str(exc)[:1200],
                      'analytical_quality_verified':False}
        with self.lock:
            current = self._same(name, revision)
            current['validation'] = report
            self._write(self._path(name), current)
        return current

    def load(self, entry):
        if entry['implementation'] == 'skill':
            return SkillMethod(entry['content'])
        # Never accept arbitrary module names from a request or edited metadata path.
        if not re.fullmatch(r'dl_method_assets\.a_[0-9a-f]{64}', entry['module']):
            raise AssetError('Invalid managed module')
        path = self.root / 'dl_method_assets' / (entry['module'].split('.')[-1] + '.py')
        content = path.read_text()
        if sha256(content.encode()).hexdigest() != entry['module'].rsplit('_',1)[-1]:
            raise AssetError('Published source does not match its immutable hash')
        method = import_method(entry['module'], entry['name'], entry['version'])
        from .source import capture_source
        method.source_snapshot = capture_source(method)
        method.source_snapshot.origin = 'managed'
        method.source_snapshot.available = True
        from ..core.models import SourceFile
        files = method.source_snapshot.files
        if not files or files[0].name != entry['module']:
            method.source_snapshot.files = [SourceFile(name=entry['module'], content=content,
                sha256=sha256(content.encode()).hexdigest()), *files]
        method.source_snapshot.editor_content = method.source_snapshot.authoring_content or entry['content']
        return method

    def publish(self, name, req, actor):
        if not req.reviewed:
            raise AssetError('Review this source before publishing it')
        with self.lock:
            value = self._same(name, req.revision)
            if not value.get('validation') or value['validation']['status'] != 'pass':
                raise AssetError('Check this exact draft before publishing')
            entry = {**value,'module':value['validation'].get('module'), 'published_by':actor,
                     'published_at':datetime.now(timezone.utc).isoformat()}
            entries = self.history()
            if any(e['name']==name and e['version']==entry['version'] for e in entries):
                raise AssetConflict('Published versions are immutable')
            method = self.load(entry)
            entries.append(entry)
            self._write(self.root / 'published.json', entries)
            self.registry.register(method, compatibility=name in self.registry._compatibility)
            self._write(self._path(name), {**value,'published':True})
            return entry

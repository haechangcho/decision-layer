"""One project loader for local development, CLI inspection and API startup."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib
from importlib.machinery import ModuleSpec
import keyword
from pathlib import Path
import sys
from types import ModuleType

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from .methods.base import Method
from .methods.registry import InvalidBinding, MethodRegistry
from .methods.skills import SkillMethod

PROJECT_FILE = "decision-layer.yaml"
_IMPORT_ROOTS: set[str] = set()


def project_import_roots():
    """Trusted flat projects needed to restore callable imports in a worker."""
    return tuple(sorted(_IMPORT_ROOTS))


def _project_namespace(root):
    return "_dl_project_" + sha256(str(root).encode()).hexdigest()[:24]


def prepare_project_imports(roots):
    """Give each project its own package without requiring a matching folder."""
    for value in roots:
        root = Path(value).resolve()
        name = _project_namespace(root)
        if name not in sys.modules:
            package = ModuleType(name)
            package.__path__ = [str(root)]
            package.__package__ = name
            package.__spec__ = ModuleSpec(name, loader=None, is_package=True)
            sys.modules[name] = package
        elif list(getattr(sys.modules[name], "__path__", [])) != [str(root)]:
            raise ProjectError("Project import namespace points to another directory")
        _IMPORT_ROOTS.add(str(root))


class ProjectError(ValueError):
    """An invalid project or definition, with its source location."""


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    config_version: int = Field(default=1, ge=1, le=2)
    include_builtin_methods: bool = True

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if keyword.iskeyword(value) or value == "decision_layer":
            raise ValueError(
                "Choose a project name other than a Python keyword or decision_layer"
            )
        return value


@dataclass(frozen=True)
class Project:
    root: Path
    config: ProjectConfig

    @property
    def methods_dir(self):
        if self.config.config_version == 2:
            return self.root / "methods"
        return self.root / self.config.name / "methods"

    @classmethod
    def find(cls, path: str | Path | None = None, *, required=True):
        """Explicit paths name a project; otherwise search cwd and its parents."""
        start = Path(path).resolve() if path is not None else Path.cwd().resolve()
        candidates = [start] if path is not None else [start, *start.parents]
        if start.is_file():
            if start.name != PROJECT_FILE:
                raise ProjectError(f"Expected {PROJECT_FILE}: {start}")
            candidates = [start.parent]
        for root in candidates:
            config_path = root / PROJECT_FILE
            if config_path.is_file():
                try:
                    config = ProjectConfig.model_validate(
                        yaml.safe_load(config_path.read_text())
                    )
                except (ValueError, yaml.YAMLError) as exc:
                    raise ProjectError(f"{config_path}: {exc}") from exc
                project = cls(root, config)
                if not project.methods_dir.is_dir():
                    raise ProjectError(
                        f"Missing definitions directory: {project.methods_dir}"
                    )
                if not project.methods_dir.resolve().is_relative_to(root):
                    raise ProjectError(
                        f"Definitions directory must stay inside the project: {project.methods_dir}"
                    )
                return project
        if required:
            raise ProjectError(
                f"No {PROJECT_FILE} found at {start}. Run decision-layer init <directory>."
            )
        return None

    def _paths(self):
        """Only method.py and SKILL.md are entries; helper files are not scanned."""
        root = self.methods_dir
        for path in root.rglob("*"):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ProjectError(f"Definition paths must stay inside {root}: {path}")
        entries = sorted([*root.rglob("method.py"), *root.rglob("SKILL.md")])
        parents = set()
        for path in entries:
            if path.parent in parents:
                raise ProjectError(
                    f"Choose either method.py or SKILL.md in {path.parent}"
                )
            parents.add(path.parent)
        return entries

    def _import(self, path):
        parts = path.relative_to(self.root).with_suffix("").parts
        if any(not part.isidentifier() or keyword.iskeyword(part) for part in parts):
            raise ProjectError(
                f"Python definition directories must be identifiers: {path}"
            )
        importlib.invalidate_caches()
        if self.config.config_version == 2:
            prepare_project_imports([self.root])
            namespace = _project_namespace(self.root)
            module_name = ".".join([namespace, *parts])
        else:
            if str(self.root) not in sys.path:
                sys.path.insert(0, str(self.root))
            package = importlib.import_module(self.config.name)
            package_paths = {
                Path(p).resolve() for p in getattr(package, "__path__", [])
            }
            if self.root / self.config.name not in package_paths:
                raise ProjectError(
                    f"Package {self.config.name!r} is already imported from another project; use a distinct name or restart Python"
                )
            module_name = ".".join(parts)
        module = importlib.import_module(module_name)
        if Path(module.__file__).resolve() != path.resolve():
            raise ProjectError(f"Module resolves to another file: {path}")
        method = getattr(module, "METHOD", None)
        if not isinstance(method, Method):
            raise ProjectError(
                f"{path}: export METHOD = python_method(...) (or another Method object)"
            )
        if method.manifest.implementation != "python":
            raise ProjectError(
                f"{path}: Python entries must export a Python Method; use SKILL.md for Skills"
            )
        return method

    def load(self, registry: MethodRegistry):
        """Validate all entries against a copy, then register them together."""
        staged = registry.copy(
            include_builtin_methods=self.config.include_builtin_methods
        )
        methods, skills, sources = [], [], {}
        for path in self._paths():
            try:
                method = (
                    self._import(path)
                    if path.name == "method.py"
                    else SkillMethod.from_file(path)
                )
                method.definition_path = str(path)
                name = method.manifest.name
                if name in sources or any(
                    m.name == name for m in staged.manifests(include_compatibility=True)
                ):
                    raise ProjectError(f"Duplicate Method name {name!r} at {path}")
                sources[name] = path
                (methods if path.name == "method.py" else skills).append(method)
            except Exception as exc:
                raise ProjectError(f"{path}: {exc}") from exc
        for method in methods + skills:
            try:
                staged.register(method)
            except Exception as exc:
                raise ProjectError(f"{sources[method.manifest.name]}: {exc}") from exc
        for skill in skills:
            for name in skill.guide.suggested_methods:
                try:
                    target = staged.get(name)
                except InvalidBinding as exc:
                    raise ProjectError(
                        f"{sources[skill.manifest.name]}: unknown suggested Method {name!r}"
                    ) from exc
                if (
                    target.manifest.implementation != "python"
                    and not target.manifest.agent_executable
                ):
                    raise ProjectError(
                        f"{sources[skill.manifest.name]}: suggested Method {name!r} is not executable"
                    )
        registry.replace_from(staged)
        return sources

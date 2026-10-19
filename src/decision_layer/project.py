"""One project loader for local development, CLI inspection and API startup."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import keyword
from pathlib import Path
import sys

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from .methods.base import Method
from .methods.registry import InvalidBinding, MethodRegistry
from .methods.skills import SkillMethod

PROJECT_FILE = "decision-layer.yaml"


class ProjectError(ValueError):
    """An invalid project or definition, with its source location."""


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    config_version: int = Field(default=1, ge=1, le=1)

    @field_validator("name")
    @classmethod
    def valid_package(cls, value):
        if keyword.iskeyword(value) or value == "decision_layer":
            raise ValueError("Choose a project name that is a distinct Python package")
        return value


@dataclass(frozen=True)
class Project:
    root: Path
    config: ProjectConfig

    @property
    def methods_dir(self):
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
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        importlib.invalidate_caches()
        package = importlib.import_module(self.config.name)
        package_paths = {Path(p).resolve() for p in getattr(package, "__path__", [])}
        if self.root / self.config.name not in package_paths:
            raise ProjectError(
                f"Package {self.config.name!r} is already imported from another project; use a distinct name or restart Python"
            )
        module = importlib.import_module(".".join(parts))
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
        staged = registry.copy()
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
        for method in methods + skills:
            registry.register(method)
        return sources

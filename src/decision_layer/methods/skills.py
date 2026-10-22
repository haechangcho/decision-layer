"""Reviewed Markdown methods and guides; loading text never executes it."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ..core.models import MethodGuide, MethodManifest, RoleSpec, ParamSpec
from .base import Method


class SkillHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(min_length=1)
    suggested_methods: list[str] = Field(default_factory=list)
    query_execution: bool = False
    roles: dict[str, RoleSpec] = Field(default_factory=dict)
    parameters: dict[str, ParamSpec] = Field(default_factory=dict)


class SkillMethod(Method):
    def __init__(self, text: str):
        if len(text.encode()) > 100_000:
            raise ValueError("Skill exceeds the 100 KB limit")
        match = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", text, re.DOTALL)
        if not match or not match[2].strip():
            raise ValueError("Skill needs YAML frontmatter and non-empty Markdown")
        header = SkillHeader.model_validate(yaml.safe_load(match[1]))
        self.source_text = text
        self.guide = MethodGuide(name=header.name, version=header.version,
            sha256=sha256(text.encode()).hexdigest(), markdown=match[2].strip(),
            suggested_methods=header.suggested_methods)
        self.manifest = MethodManifest(name=header.name, version=header.version,
            description=header.description, implementation="skill", execution="agent_guided",
            kind="query", interpretation="association", roles=header.roles, parameters=header.parameters,
            agent_executable=header.query_execution, requires_period=header.query_execution,
            requires_capabilities=["aggregate_queries"] if header.query_execution else [],
            selection_outputs=["selected_group"] if header.query_execution else [],
            outputs=["table"] if header.query_execution else [])

    @classmethod
    def from_file(cls, path: str | Path):
        skill = cls(Path(path).read_text(encoding="utf-8"))
        skill.definition_path = str(Path(path).resolve())
        return skill

    async def run(self, ctx, bindings, params):
        from .registry import InvalidBinding
        raise InvalidBinding("Skill text is not executable. Read its guide and run registered tools on a recorded Run.")


def load_skill_directory(registry, directory: str | Path, *, builtin=False):
    """Operator-owned directory only. No HTTP upload or arbitrary request path."""
    root = Path(directory).resolve(strict=True)
    pending = []
    seen = {m.name for m in registry.manifests(include_compatibility=True)}
    for path in sorted(root.rglob("*.md")):
        if not path.resolve().is_relative_to(root):
            raise ValueError("Skill symlinks must stay inside the configured directory")
        skill = SkillMethod.from_file(path)
        if skill.manifest.name in seen:
            raise ValueError(f"Duplicate Method name: {skill.manifest.name}")
        seen.add(skill.manifest.name)
        pending.append(skill)
    pending_by_name = {skill.manifest.name: skill for skill in pending}
    for skill in pending:
        for name in skill.guide.suggested_methods:
            method = pending_by_name[name] if name in pending_by_name else registry.get(name)
            if method.manifest.implementation != "python" and not method.manifest.agent_executable:
                raise ValueError("Suggested tools must name executable Python Methods or query-executing Skills")
    for skill in pending:
        registry.register(skill, builtin=builtin)
    return registry


def core_skill_guide():
    """Shared tool protocol, snapshotted separately from the analysis procedure."""
    from importlib.resources import files
    text = (files("decision_layer") / "guides" / "analysis-core.md").read_text(encoding="utf-8")
    return MethodGuide(name="analysis-core", version="1.1.0",
        sha256=sha256(text.encode()).hexdigest(), markdown=text)


def get_authoring_guide(name: str) -> dict:
    # Fixed names; callers cannot read arbitrary repository files.
    from importlib.resources import files
    if name not in ("authoring", "cube-query", "analysis-core"):
        from .registry import InvalidBinding
        raise InvalidBinding("Unknown guide", available=["authoring", "cube-query", "analysis-core"])
    content = (files("decision_layer") / "guides" / f"{name}.md").read_text(encoding="utf-8")
    from .. import __version__
    return {"name": name, "package_version": __version__, "sha256": sha256(content.encode()).hexdigest(),
            "markdown": content, "enforcement": "advisory"}

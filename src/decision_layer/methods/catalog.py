"""Assembly of the default catalog and explicitly retained historical versions."""

from .registry import MethodRegistry
from .skills import SkillMethod


def register_builtins(target: MethodRegistry) -> MethodRegistry:
    """Install reviewed implementations in one place; modules have no registration side effects."""
    from .compatibility import register_compatibility

    register_compatibility(target)
    from .native_matching import METHODS as matching_methods
    from .native_regression import METHODS as regression_methods

    for implementation in [*matching_methods, *regression_methods]:
        target.register(implementation, builtin=True)
    from importlib.resources import files
    from .skills import load_skill_directory

    load_skill_directory(target, files("decision_layer") / "guides" / "methods", builtin=True)
    # Keep a small executable starting catalog across CLI, REST, Web and MCP.
    # Existing explicit references still resolve through the compatibility catalog.
    core_skills = {"analysis.metric_lookup", "analysis.drilldown"}
    for manifest in target.manifests():
        if manifest.implementation == "skill" and manifest.name not in core_skills:
            target.register(target.get(manifest.name), compatibility=True, builtin=True)
    # Preserve released instructions for explicitly pinned Recipes.
    for path in (files("decision_layer") / "guides" / "compatibility").iterdir():
        if path.name.endswith(".md"):
            target.register(SkillMethod.from_file(path), activate=False)
    return target

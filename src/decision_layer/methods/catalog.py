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
        target.register(implementation)
    from importlib.resources import files
    from .skills import load_skill_directory

    load_skill_directory(target, files("decision_layer") / "guides" / "methods")
    # Preserve released instructions for explicitly pinned Recipes.
    for path in (files("decision_layer") / "guides" / "compatibility").iterdir():
        if path.name.endswith(".md"):
            target.register(SkillMethod.from_file(path), activate=False)
    return target

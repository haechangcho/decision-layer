"""The same four current definitions shipped in editable projects."""
from importlib.resources import files

from .registry import MethodRegistry
from .skills import SkillMethod


def register_builtins(target: MethodRegistry) -> MethodRegistry:
    from ..starters.methods.ols.method import METHOD as regression
    from ..starters.methods.matching.method import METHOD as matching

    for implementation in (regression, matching):
        target.register(implementation, builtin=True)
    for name in ("metric_lookup", "drilldown"):
        path = files("decision_layer") / "starters" / "methods" / name / "SKILL.md"
        target.register(SkillMethod.from_file(path), builtin=True)
    return target

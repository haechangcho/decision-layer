"""Public Method authoring API and explicit built-in registration."""
from ..core.models import Artifact, DatasetSpec, Filter, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .context import ExecutionContext, NeedsInput, Refused, Scope
from .registry import InvalidBinding, MethodRegistry
from .inputs import DateRange, Dimension, Entity, Equality, Measure, TimeDimension
from .authoring import method
from .output import Estimate, Table, TimeSeries
from .calculation import InputTable, calculation
from .python import DataInput, python_method
from .skills import SkillMethod, get_authoring_guide


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


registry = register_builtins(MethodRegistry())

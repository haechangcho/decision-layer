"""Public Method authoring API and explicit built-in registration."""
from ..core.models import Artifact, DatasetSpec, Filter, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .context import ExecutionContext, NeedsInput, Refused, Scope
from .registry import InvalidBinding, MethodRegistry
from .inputs import DateRange, Dimension, Entity, Equality, Measure, TimeDimension
from .authoring import method
from .output import Estimate, Table, TimeSeries


def register_builtins(target: MethodRegistry) -> MethodRegistry:
    """Install reviewed implementations in one place; modules have no registration side effects."""
    from .aggregate import Aggregate
    from .trend import Trend
    from .drilldown import Drilldown
    from .peer_comparison import PeerComparison
    from .cem import CEM
    for implementation in (Aggregate, Trend, Drilldown):
        target.register(implementation())
    # Existing explicit Recipes still resolve optional implementations.
    # Re-register a reviewed implementation normally to offer it to new callers.
    target.register(PeerComparison(), compatibility=True)
    target.register(CEM(), compatibility=True)
    from .advanced import ols, binary_regression, linear_dml, two_period_contrast, unit_change, unit_distribution
    from .binary_matching import binary_matching
    from .regression_adjustment import regression_adjustment
    target.register(regression_adjustment)
    target.register(binary_regression, compatibility=True)
    target.register(binary_matching)
    from .legacy_advanced import adjusted_difference, dml, did
    for implementation in (ols, linear_dml, two_period_contrast,
                           unit_change, unit_distribution):
        target.register(implementation, compatibility=True)
    for implementation in (adjusted_difference, dml, did):
        target.register(implementation, compatibility=True)
    return target


registry = register_builtins(MethodRegistry())

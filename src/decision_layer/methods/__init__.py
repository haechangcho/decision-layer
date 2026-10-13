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
    for implementation in (Aggregate, Trend, Drilldown, PeerComparison, CEM):
        target.register(implementation())
    from .advanced import ols, binary_regression, linear_dml, two_period_contrast, unit_change, unit_distribution
    from .legacy_advanced import adjusted_difference, dml, did
    for implementation in (ols, binary_regression, linear_dml, two_period_contrast,
                           unit_change, unit_distribution, adjusted_difference, dml, did):
        target.register(implementation)
    return target


registry = register_builtins(MethodRegistry())

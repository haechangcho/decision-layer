"""Public Method authoring API and explicit built-in registration."""
from ..core.models import Artifact, DatasetSpec, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .context import ExecutionContext, NeedsInput, Refused, Scope
from .registry import InvalidBinding, MethodRegistry


def register_builtins(target: MethodRegistry) -> MethodRegistry:
    """Install reviewed implementations in one place; modules have no registration side effects."""
    from .aggregate import Aggregate
    from .trend import Trend
    from .drilldown import Drilldown
    from .peer_comparison import PeerComparison
    from .cem import CEM
    for implementation in (Aggregate, Trend, Drilldown, PeerComparison, CEM):
        target.register(implementation())
    return target


registry = register_builtins(MethodRegistry())

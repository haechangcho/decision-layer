"""Frozen, explicitly referenced implementations; never new catalog choices.

Keep import paths and versions for saved Recipes and managed publications. These
are not alternative authoring APIs. Removing one requires evidence that retained
Recipes and environments no longer reference it.
"""


def register_compatibility(target):
    from .aggregate import Aggregate
    from .trend import Trend
    from .drilldown import Drilldown
    from .peer_comparison import PeerComparison
    from .cem import CEM
    from .advanced import ols, binary_regression, linear_dml, two_period_contrast, unit_change, unit_distribution
    from .legacy_advanced import adjusted_difference, dml, did
    from .time_analysis import PeriodChange, SeriesDiagnostics
    from .series_diagnostics import METHODS as series_methods
    from .binary_matching import binary_matching
    from .regression_adjustment import regression_adjustment
    for implementation in (
        Aggregate(), Trend(), Drilldown(), PeerComparison(), CEM(),
        ols, binary_regression, linear_dml, two_period_contrast, unit_change, unit_distribution,
        adjusted_difference, dml, did, PeriodChange(), SeriesDiagnostics(),
        binary_matching, regression_adjustment, *series_methods,
    ):
        target.register(implementation, compatibility=True)
    return target

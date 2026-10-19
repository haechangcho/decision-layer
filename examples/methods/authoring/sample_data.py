"""Exact expected query and independent values for the first Method."""
from decision_layer.core.models import DatasetSpec, SemanticCatalog, SemanticObject, TimeScope
from decision_layer.testing import FixtureProvider, QueryFixture

METRIC = "cube://fixture/sales/revenue"
DIMENSION = "cube://fixture/sales/product"
DATE = "cube://fixture/sales/date"
DATES = ("2026-09-01", "2026-09-30")


def fixture_provider():
    catalog = SemanticCatalog(provider="cube", instance="fixture", objects=[
        SemanticObject(ref=METRIC, kind="measure", data_type="number", title="Revenue",
                       metric_kind="additive", dimension_refs=[DIMENSION, DATE], time_dimension=DATE),
        SemanticObject(ref=DIMENSION, kind="dimension", data_type="string", title="Product"),
        SemanticObject(ref=DATE, kind="time_dimension", data_type="time", title="Date"),
    ])
    spec = DatasetSpec(grain="aggregate", measures=[METRIC], dimensions=[DIMENSION],
                       time=TimeScope(dimension=DATE, date_range=DATES),
                       order=[(METRIC, "desc")], limit_rows=3)
    return FixtureProvider(catalog, [QueryFixture(spec, [[30, "A"], [20, "B"], [10, "C"]])])

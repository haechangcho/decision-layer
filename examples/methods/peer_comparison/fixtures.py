"""Independent expected semantic requests and responses for the peer example."""
from decision_layer.core.models import DatasetSpec, Filter, SemanticCatalog, SemanticObject, TimeScope
from decision_layer.testing import FixtureProvider, QueryFixture

METRIC = "cube://fixture/orders/return_rate"
COUNT = "cube://fixture/orders/count"
SELLER = "cube://fixture/orders/seller"
CATEGORY = "cube://fixture/orders/category"
DATE = "cube://fixture/orders/date"
DATES = ("2026-09-01", "2026-09-30")
BINDINGS = {"metric": METRIC}
PARAMS = {"subject": [{"member": SELLER, "value": "A"}],
          "peers": [{"member": CATEGORY, "value": "Appliances"}]}


def fixture_provider() -> FixtureProvider:
    # Declared test metadata, not new business definitions for a real source.
    catalog = SemanticCatalog(provider="cube", instance="fixture", objects=[
        SemanticObject(ref=METRIC, kind="measure", data_type="number", title="Return rate",
                       metric_kind="ratio", count_measure=COUNT, time_dimension=DATE,
                       dimension_refs=[SELLER, CATEGORY, DATE]),
        SemanticObject(ref=COUNT, kind="measure", data_type="number", title="Orders", metric_kind="count"),
        SemanticObject(ref=SELLER, kind="dimension", data_type="string", title="Seller"),
        SemanticObject(ref=CATEGORY, kind="dimension", data_type="string", title="Category"),
        SemanticObject(ref=DATE, kind="time_dimension", data_type="time", title="Order date"),
    ])
    category = Filter(member=CATEGORY, operator="equals", values=["Appliances"])
    target = Filter(member=SELLER, operator="equals", values=["A"])
    excluded = Filter(member=SELLER, operator="notEquals", values=["A"])
    # Exact independent expectations: target inside peers; benchmarks exclude A.
    filters = [[category, target], [category, excluded], [excluded]]
    values = [[12.0, 100], [8.0, 200], [6.0, 500]]
    queries = [QueryFixture(
        DatasetSpec(grain="aggregate", measures=[METRIC, COUNT], filters=conditions,
                    time=TimeScope(dimension=DATE, date_range=DATES)), [row])
        for conditions, row in zip(filters, values)]
    return FixtureProvider(catalog, queries)

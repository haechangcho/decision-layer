"""Exact query fixtures and expected answers, independent from Method query builders."""
from dataclasses import dataclass, field
import numpy as np
from decision_layer.core.models import DatasetSpec, Filter, SemanticCatalog, SemanticObject, TimeScope
from decision_layer.methods import Scope
from decision_layer.testing import FixtureProvider, QueryFixture

ROOT = "cube://practice/observations/"
M, BEFORE, RATE, UNIT, GROUP, SUBJECT, DATE, TREAT, BASELINE = [ROOT + name for name in
    ("value", "before_value", "rate", "id", "group", "subject", "date", "treated", "baseline")]
JAN_FEB = ("2026-01-01", "2026-02-28")
FEB = ("2026-02-01", "2026-02-28")
JAN = ("2026-01-01", "2026-01-31")


def catalog():
    objects = [SemanticObject(ref=ref, kind="measure", data_type="number", title=name,
        metric_kind="ratio" if ref == RATE else "additive", entity=UNIT,
        dimension_refs=[GROUP, SUBJECT, DATE, TREAT, BASELINE], time_dimension=DATE)
        for ref, name in [(M, "Value"), (BEFORE, "Baseline value"), (RATE, "Rate")]]
    objects += [SemanticObject(ref=ref, kind="dimension", data_type=kind, title=name)
                for ref, kind, name in [(UNIT, "string", "Unit"), (GROUP, "string", "Group"),
                                      (SUBJECT, "string", "Subject"), (TREAT, "number", "Treatment"),
                                      (BASELINE, "number", "Baseline")]]
    objects.append(SemanticObject(ref=DATE, kind="time_dimension", data_type="time", title="Date"))
    return SemanticCatalog(provider="cube", instance="practice", objects=objects)


@dataclass
class Scenario:
    name: str
    pattern: str
    method: str
    queries: list[QueryFixture]
    arguments: dict
    expected: dict

    def provider(self):
        return FixtureProvider(catalog(), self.queries)


def scenarios():
    # Canonical specs are spelled out here, not obtained from ctx.aggregate/entities.
    grouped = DatasetSpec(grain="aggregate", measures=[M], dimensions=[GROUP],
        time=TimeScope(dimension=DATE, date_range=FEB), order=[(M, "desc")], limit_rows=3)
    series = DatasetSpec(grain="aggregate", measures=[M],
        time=TimeScope(dimension=DATE, date_range=JAN_FEB, granularity="month"), limit_rows=50001)
    current = DatasetSpec(grain="aggregate", measures=[M],
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    baseline = DatasetSpec(grain="aggregate", measures=[M],
        time=TimeScope(dimension=DATE, date_range=JAN), limit_rows=50001)
    subject = Filter(member=SUBJECT, operator="equals", values=["A"])
    category = Filter(member=GROUP, operator="equals", values=["X"])
    exclude = Filter(member=SUBJECT, operator="notEquals", values=["A"])
    peer_specs = [DatasetSpec(grain="aggregate", measures=[RATE], filters=filters,
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
        for filters in [[category, subject], [category, exclude], [exclude]]]
    units = DatasetSpec(grain="entity", entity=UNIT, measures=[M],
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    before_units = DatasetSpec(grain="entity", entity=UNIT, measures=[M],
        time=TimeScope(dimension=DATE, date_range=JAN), limit_rows=50001)
    wide_before = DatasetSpec(grain="entity", entity=UNIT, measures=[BEFORE],
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    rng = np.random.default_rng(7)
    n = 2000
    w = rng.binomial(1, .5, n)
    t = rng.binomial(1, .25 + .5 * w)
    y = 2 * t + 3 * w + rng.normal(0, 1, n)
    statistical = DatasetSpec(grain="entity", entity=UNIT, measures=[M], dimensions=[TREAT, BASELINE],
        time=TimeScope(dimension=DATE, date_range=FEB), limit_rows=50001)
    statistical_rows = [[float(y[i]), int(t[i]), int(w[i]), str(i)] for i in range(n)]
    panel = DatasetSpec(grain="entity", entity=UNIT, measures=[M], dimensions=[TREAT],
        time=TimeScope(dimension=DATE, date_range=JAN_FEB, granularity="month"), limit_rows=50001)
    panel_pre = DatasetSpec(grain="entity", entity=UNIT, measures=[M], dimensions=[TREAT],
        time=TimeScope(dimension=DATE, date_range=JAN, granularity="month"), limit_rows=50001)
    panel_post = DatasetSpec(grain="entity", entity=UNIT, measures=[M], dimensions=[TREAT],
        time=TimeScope(dimension=DATE, date_range=FEB, granularity="month"), limit_rows=50001)
    pre_rows = [[10, 1, "A", "2026-01-01"], [8, 0, "B", "2026-01-01"]]
    post_rows = [[15, 1, "A", "2026-02-01"], [10, 0, "B", "2026-02-01"]]
    return [
        Scenario("by_group", "A", "example.group_metric", [QueryFixture(grouped, [[30, "A"], [20, "B"], [10, "C"]])],
            {"measures": {"metric": M}, "dimensions": {"group": GROUP}, "scope": Scope(FEB, DATE), "params": {"limit": 3}},
            {"column": "metric", "values": [30, 20, 10], "queries": 1}),
        Scenario("trend", "A", "example.series", [QueryFixture(series, [[20, "2026-01-01"], [30, "2026-02-01"]])],
            {"measures": {"metric": M}, "scope": Scope(JAN_FEB, DATE)}, {"series": [20, 30], "queries": 1}),
        Scenario("period", "B", "example.period_difference", [QueryFixture(current, [[30]]), QueryFixture(baseline, [[20]])],
            {"measures": {"metric": M}, "scope": Scope(FEB, DATE), "params": {"baseline": JAN}},
            {"column": "difference", "values": [10], "queries": 2}),
        Scenario("peer", "B", "example.peer", [QueryFixture(spec, [[v]]) for spec, v in zip(peer_specs, [12, 8, 6])],
            {"measures": {"metric": RATE}, "scope": Scope(FEB, DATE),
             "params": {"subject": {"member": SUBJECT, "value": "A"}, "peers": [category.model_dump()]}},
            {"column": "difference", "values": [4, 6], "queries": 3}),
        Scenario("ols", "C", "stats.ols", [QueryFixture(statistical, statistical_rows)],
            {"measures": {"outcome": M}, "dimensions": {"features": [TREAT, BASELINE]}, "entity": UNIT, "scope": Scope(FEB, DATE)},
            {"coefficients": [2, 3], "tolerance": .15, "queries": 1}),
        Scenario("dowhy", "C", "stats.binary_regression", [QueryFixture(statistical, statistical_rows)],
            {"measures": {"outcome": M}, "dimensions": {"treatment": TREAT, "confounders": [BASELINE]}, "entity": UNIT,
             "scope": Scope(FEB, DATE)}, {"value": 2, "tolerance": .15, "queries": 1}),
        Scenario("econml", "C", "stats.linear_dml", [QueryFixture(statistical, statistical_rows)],
            {"measures": {"outcome": M}, "dimensions": {"treatment": TREAT, "confounders": [BASELINE]}, "entity": UNIT,
             "scope": Scope(FEB, DATE)}, {"value": 2, "tolerance": .15, "queries": 1}),
        Scenario("unit-change", "D", "query.unit_change", [QueryFixture(units, [[5, "A"], [9, "B"]]), QueryFixture(before_units, [[2, "A"], [4, "B"]])],
            {"measures": {"outcome": M}, "entity": UNIT, "scope": Scope(FEB, DATE), "params": {"baseline": JAN}},
            {"column": "change", "values": [3, 5], "queries": 2}),
        Scenario("unit-change-wide", "D", "query.unit_change", [QueryFixture(units, [[5, "A"], [9, "B"]]), QueryFixture(wide_before, [[2, "A"], [4, "B"]])],
            {"measures": {"outcome": M, "baseline_outcome": BEFORE}, "entity": UNIT, "scope": Scope(FEB, DATE)},
            {"column": "change", "values": [3, 5], "queries": 2}),
        Scenario("did", "E", "stats.two_period_contrast", [QueryFixture(panel, [*pre_rows, *post_rows])],
            {"measures": {"outcome": M}, "dimensions": {"treated": TREAT, "time": DATE}, "entity": UNIT,
             "scope": Scope(JAN_FEB, DATE)}, {"value": 3, "tolerance": 1e-9, "queries": 1}),
        Scenario("did-split", "F", "stats.two_period_contrast", [QueryFixture(panel_pre, pre_rows), QueryFixture(panel_post, post_rows)],
            {"measures": {"outcome": M}, "dimensions": {"treated": TREAT, "time": DATE}, "entity": UNIT,
             "scope": Scope(JAN_FEB, DATE), "params": {"windows": [JAN, FEB]}},
            {"value": 3, "tolerance": 1e-9, "queries": 2}),
        Scenario("mixed", "G", "query.unit_distribution", [QueryFixture(current, [[60]]), QueryFixture(units, [[30, "A"], [20, "B"], [10, "C"]])],
            {"measures": {"outcome": M}, "entity": UNIT, "scope": Scope(FEB, DATE)},
            {"rows": [{"provider_value": 60, "unit_min": 10, "unit_max": 30, "n_units": 3}], "queries": 2}),
    ]


def verify(scenario, trial):
    result = trial.result
    if result.status != "success":
        raise AssertionError(f"{scenario.name}: {result.status}: {result.warnings}")
    if len(trial.attempts) != scenario.expected["queries"]:
        raise AssertionError("Unexpected logical query count")
    data, expected = result.primary.data, scenario.expected
    if "column" in expected:
        assert [row[expected["column"]] for row in data] == expected["values"]
    if "series" in expected:
        assert [row["metric"] for row in data["rows"]] == expected["series"]
    if "rows" in expected:
        assert data == expected["rows"]
    if "value" in expected:
        assert abs(data["value"] - expected["value"]) <= expected["tolerance"]
        assert data["causal_claim"] == "not_established"
    if "coefficients" in expected:
        values = [row["coefficient"] for row in data if row["term"] != "const"]
        assert np.allclose(values, expected["coefficients"], atol=expected["tolerance"])

"""Query Methods against an in-memory provider with known answers.

Data (orders; return = returned order):
  Q3 2026-07-01..09-30  category A: S1 100 orders / 40 returns, S2–S5 100 / 15 each, S8 5 / 5 (tiny)
                         category B: S6, S7 250 / 25 each
  Q2 2026-04-01..06-30  same, except S1 100 / 15 and no S8
"""
from datetime import date, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.errors import ProviderAccessDenied, UnknownSemanticObject
from decision_layer.core.models import Column, Dataset, DatasetSpec, ProviderCapabilities, QueryProvenance
from decision_layer.methods import registry
from decision_layer.methods import InvalidBinding
from decision_layer.methods.context import ExecutionContext, Scope
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.cube.catalog_mapper import map_meta
from decision_layer.settings import Settings
from tests.support.semantic import ref

from tests.support.semantic import RR, COUNT, RET, AMOUNT, AOV, CAT, SELLER, DT, CHANNEL, ORDER, Q3, Q2, CREDS, FakeProvider, ctx


async def test_drilldown_two_levels(provider):
    r = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT, SELLER]}, {})
    assert r.status == "success"
    table = r.primary.data
    assert [g["value"] for g in table["rows"]] == ["A", "B"]
    assert table["rows"][0]["metric"] == pytest.approx(105 / 505 * 100, abs=1e-4)  # S8 is in the category total
    first = table["next_candidates"][0]
    assert first["drill_path"] == [{"member": CAT, "value": "A"}] and first["next_dimension"] == SELLER

    r = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT, SELLER]},
                           {"drill_path": first["drill_path"]})
    table = r.primary.data
    top = table["rows"][0]
    assert (top["value"], top["metric"], top["count"]) == ("S1", 40.0, 100.0)
    assert table["excluded_small"] == 1 and table["selected_among"] == 5       # S8 (5 orders) is not ranked
    assert top["rest"] == {"metric": pytest.approx(65 / 405 * 100, abs=1e-4), "count": 405.0}
    assert top["test"]["significant"] and top["test"]["selection"]["selected_among"] == 5
    assert table["next_candidates"] == []                                      # no dimension left
    assert any("below" in w for w in r.warnings)


async def test_drilldown_refuses_when_no_dimension_left(provider):
    r = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT]},
                           {"drill_path": [{"member": CAT, "value": "A"}]})
    assert r.status == "refused"


async def test_drilldown_reports_hidden_ranked_groups(provider):
    regular = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT]},
                                 {"top_n": 1})
    assert regular.primary.data["total_groups"] == 2
    assert regular.primary.data["ranked_groups"] == 2
    assert regular.primary.data["shown_groups"] == 1
    assert any("1 of 2" in warning for warning in regular.warnings)

    compared = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT]},
                                  {"top_n": 1, "comparison": list(Q2)})
    assert compared.primary.data["shown_groups"] == 1
    assert any("1 of 2" in warning for warning in compared.warnings)





async def test_trend_with_periods_judges_the_change(provider):
    r = await registry.run("query.trend", ctx(provider, date_range=("2026-07-01", "2026-09-28")), {"metric": RR},
                           {"vs_previous": True})
    change = next(a.data for a in r.artifacts if a.type == "estimate")
    assert change["comparison_period"] == ["2026-04-02", "2026-06-30"]            # 90 days each
    assert change["test"]["ci95"][0] < change["change"] < change["test"]["ci95"][1]
    assert any(x.validator == "comparable_periods" and x.status == "pass" for x in r.validation)


async def test_trend_decomposes_a_total_and_splits_days(provider):
    r = await registry.run("query.trend", ctx(provider), {"metric": AMOUNT}, {"comparison": list(Q2)})
    change = next(a.data for a in r.artifacts if a.type == "estimate")
    [d] = change["decomposition"]["decompositions"]                               # amount = count × AOV
    assert [f["factor"] for f in d["factors"]] == ["period_days", COUNT, AOV]
    assert sum(f["contribution"] for f in d["factors"]) == pytest.approx(change["change"], abs=1e-2)
    assert change["per_day"]["current_days"] == 92 and "test" not in change      # a total gets no proportion test
    assert any(x.validator == "comparable_periods" and x.status == "warning" for x in r.validation)


async def test_trend_related_changes(provider):
    r = await registry.run("query.trend", ctx(provider), {"metric": RR, "related": [COUNT, AMOUNT]},
                           {"comparison": list(Q2)})
    change = next(a.data for a in r.artifacts if a.type == "estimate")
    rows = {x["metric"]: x for x in change["related"]}
    assert rows[COUNT]["change"] == 5 and "test" in change and "test" not in rows[AMOUNT]
    assert "decomposition" not in change                                           # a ratio is not decomposed


async def test_drilldown_period_mode_mix_rate_adds_up(provider):
    r = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT, SELLER]},
                           {"comparison": list(Q2)})
    table, change = r.primary.data, next(a.data for a in r.artifacts if a.type == "estimate")
    assert table["decomposition"] == "mix_rate"
    rows = {g["value"]: g for g in table["rows"]}
    assert rows["A"]["rate_effect"] > 0 and rows["B"]["rate_effect"] == 0
    assert sum(g["contribution"] for g in rows.values()) == pytest.approx(change["change"], abs=1e-3)
    assert table["next_candidates"][0]["drill_path"] == [{"member": CAT, "value": "A"}]


async def test_drilldown_period_mode_additive(provider):
    r = await registry.run("query.drilldown", ctx(provider), {"metric": COUNT, "dimensions": [SELLER]},
                           {"comparison": list(Q2)})
    rows = {g["value"]: g for g in r.primary.data["rows"]}
    assert r.primary.data["decomposition"] == "additive"
    assert rows["S8"]["contribution"] == 5 and rows["S8"]["share_of_change"] == 100.0





async def test_needs_input_when_time_dimension_is_ambiguous(provider):
    r = await registry.run("query.trend", ctx(provider), {"metric": ref("ecom_delivery.count")}, {})
    assert r.status == "needs_input" and r.needs_input["field"] == "time_dimension"
    assert len(r.needs_input["candidates"]) == 3 and provider.calls == 0


async def test_bindings_and_params_are_checked(provider):
    with pytest.raises(InvalidBinding):
        await registry.run("query.drilldown", ctx(provider), {"metric": CAT, "dimensions": [SELLER]}, {})
    with pytest.raises(InvalidBinding):
        await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [SELLER]}, {"rank_by": "x"})


def test_api_routes(provider):
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s", cube_service_groups=("ecommerce",), database_url="memory", allow_service_credentials=True)
    c = TestClient(create_app(s, provider))
    assert {m["name"] for m in c.get("/methods").json()} == {"query.aggregate", "query.drilldown", "query.trend", "query.peer_comparison", "causal.cem"}
    assert c.get("/methods/query.drilldown").json()["roles"]["dimensions"]["multiple"] is True
    r = c.post("/methods/query.drilldown:run", json={"bindings": {"metric": RR, "dimensions": [CAT, SELLER]},
                                                     "scope": {"date_range": list(Q3)}})
    assert r.status_code == 200 and r.json()["primary"]["data"]["rows"][0]["value"] == "A"
    assert c.post("/methods/query.nope:run", json={}).json()["error"]["code"] == "INVALID_BINDING"


async def test_peer_comparison_preserves_population_and_excludes_subject(provider):
    c = ctx(provider)
    result = await registry.run("query.peer_comparison", c, {"metric": RR}, {
        "subject": [{"member": SELLER, "value": "S1"}], "peers": [{"member": CAT, "value": "A"}],
    })
    assert result.status == "success"
    a, b, all_ = result.primary.data["rows"]
    assert a["metric"] == 40
    assert b["metric"] == pytest.approx(65 / 405 * 100, abs=1e-4)
    assert all_["metric"] == pytest.approx(115 / 905 * 100, abs=1e-4)
    assert b["difference_from_subject"] == pytest.approx(40 - 65 / 405 * 100, abs=1e-4)
    assert len(result.provenance.queries) == 3
    assert {RR, CAT, SELLER} <= set(result.provenance.semantic_refs)
    assert result.primary.data["statistical_judgement"] == "not_tested"
    assert "not an arithmetic average" in result.primary.data["comparison_basis"]
    assert "even when sample counts are available" in result.primary.data["statistical_note"]
    populations = result.primary.data["population_filters"]
    assert [(f["member"], f["operator"], f["values"]) for f in populations["subject"]] == [
        (CAT, "equals", ["A"]), (SELLER, "equals", ["S1"])]
    assert [(f["member"], f["operator"], f["values"]) for f in populations["peers"]] == [
        (CAT, "equals", ["A"]), (SELLER, "notEquals", ["S1"])]
    assert [(f["member"], f["operator"], f["values"]) for f in populations["overall"]] == [
        (SELLER, "notEquals", ["S1"])]


async def test_peer_comparison_refuses_overlapping_scope(provider):
    from decision_layer.core.models import Filter
    result = await registry.run("query.peer_comparison", ctx(provider, filters=[Filter(member=SELLER, operator="equals", values=["S1"])]),
                                {"metric": RR}, {"subject": [{"member": SELLER, "value": "S1"}]})
    assert result.status == "refused" and provider.calls == 0


async def test_peer_comparison_records_shared_filters_for_every_population(provider):
    from decision_layer.core.models import Filter
    shared = Filter(member=CAT, operator="equals", values=["A"])
    result = await registry.run("query.peer_comparison", ctx(provider, filters=[shared]), {"metric": RR},
                                {"subject": [{"member": SELLER, "value": "S1"}]})
    assert result.status == "success"
    for filters in result.primary.data["population_filters"].values():
        assert filters[0] == shared.model_dump()


async def test_peer_comparison_empty_target_and_small_sample(provider):
    for value in ("missing", "S8"):
        result = await registry.run("query.peer_comparison", ctx(provider), {"metric": RR},
                                    {"subject": [{"member": SELLER, "value": value}]})
        assert result.status == "refused"


async def test_peer_parameter_validation_is_partial_only_during_authoring(provider):
    registry.resolve_params("query.peer_comparison", {"peers": []}, partial=True)
    with pytest.raises(InvalidBinding):
        registry.resolve_params("query.peer_comparison", {"peers": []})
    with pytest.raises(InvalidBinding):
        registry.resolve_params("query.peer_comparison", {"min_count": -1}, partial=True)


async def test_declared_non_count_ratio_gets_no_units(provider):
    c = ctx(provider)
    assert c.units_measure(RR) == COUNT                       # count / count: a share of orders
    c.catalog = c.catalog.model_copy(deep=True)
    assert c.obj(AOV).ratio_parts == (AMOUNT, COUNT)
    assert c.units_measure(AOV) is None                         # amount / count: not a proportion


async def test_trend_returns_raw_series(provider):
    r = await registry.run("query.trend", ctx(provider), {"metric": RR, "related": [AMOUNT]}, {"granularity": "day"})
    assert r.status == "success" and r.interpretation == "descriptive"
    rows = r.primary.data["rows"]
    assert rows == sorted(rows, key=lambda x: x["period"]) and len(rows) == 92      # Q3, one row per day
    assert f"{RR}#units" in rows[0] and "test" not in rows[0]                       # counts given, no judgement
    assert {m["metric"] for m in r.artifacts[0].data} == {RR, AMOUNT}
    assert r.warnings                                                               # co-movement caveat

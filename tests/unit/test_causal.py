"""causal.cem on the in-memory provider, plus the pure matching pieces."""
import pytest

from decision_layer.methods import registry
from decision_layer.methods.causal import matching as m
from test_methods import CAT, CHANNEL, RR, SELLER, FakeProvider, ctx
from test_methods import AOV, COUNT, ORDER, RET
from decision_layer.methods.base import InvalidBinding

B_RATE, A_RATE = 50 / 500 * 100, 105 / 505 * 100   # Q3: B 10%, A (incl. S8) ≈ 20.79%


@pytest.fixture
def provider(cube_meta):
    return FakeProvider(cube_meta)


def test_match_weights_by_target_composition():
    s1 = m.Stratum("x", {}, {m.TARGET: m.Cell(80, 20.0), m.COMPARISON: m.Cell(10, 10.0)})
    s2 = m.Stratum("y", {}, {m.TARGET: m.Cell(20, 50.0), m.COMPARISON: m.Cell(90, 40.0)})
    s3 = m.Stratum("z", {}, {m.TARGET: m.Cell(5, 90.0)})                      # no comparison: excluded
    r = m.match([s1, s2, s3], {}, None)
    assert r["target_kpi"] == pytest.approx((80 * 20 + 20 * 50) / 100)
    assert r["comparison_kpi"] == pytest.approx((80 * 10 + 20 * 40) / 100)   # re-weighted to the target mix
    assert r["balance"]["target_retention"] == pytest.approx(100 / 105, abs=1e-4) and not r["reasons"]


def test_groups_and_ranges():
    g = m.Group.parse({"gte": 3})
    assert g.contains(3) and not g.contains(2.9) and g.complement() == m.Group(lt=3)
    assert [f.operator for f in m.Group.parse({"exclude": ["A"]}).filters(CAT)] == ["notEquals"]
    assert m.quantile_edges([(x, 1) for x in range(1, 101)], bins=4) == [25, 50, 75]
    assert m.bin_index(50, [25, 50, 75]) == 2 and m.bin_label([25, 50, 75], 0) == "< 25"



async def test_cem_category_vs_category(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                           {"target": ["A"], "comparison": ["B"]})
    assert r.status == "success" and r.interpretation == "causal_conditional"
    est = r.primary.data
    assert est["raw"]["target"] == pytest.approx(A_RATE, abs=1e-3) and est["raw"]["comparison"] == pytest.approx(B_RATE)
    assert est["matched"]["difference"] == pytest.approx(est["matched"]["target"] - est["matched"]["comparison"], abs=1e-3)
    balance = next(a.data for a in r.artifacts if a.type == "balance")
    assert balance["strata_common"] == 2 and balance["target_retention"] == 1.0
    assert est["statistical_judgement"] == "tested"
    assert any(artifact.type == "interval" for artifact in r.artifacts)
    assert RET in r.provenance.semantic_refs


async def test_cem_asks_for_groups(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]}, {})
    assert r.status == "needs_input" and r.needs_input["field"] == "target"
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": SELLER, "conditions": [CHANNEL]},
                           {"target": ["S1"]})
    assert r.status == "needs_input" and r.needs_input["field"] == "comparison"
    assert r.needs_input["candidates"][0]["value"] == {"exclude": ["S1"]}   # many values: "everyone else" first


@pytest.mark.parametrize("target,comparison", [(["A"], ["A"]), (["A"], {"exclude": ["B"]})])
async def test_cem_refuses_overlapping_explicit_groups_before_querying(provider, target, comparison):
    context = ctx(provider)
    result = await registry.run("causal.cem", context, {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": target, "comparison": comparison})
    assert result.status == "refused" and result.primary is None
    assert context.queries == []


async def test_cem_refuses_when_not_comparable(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [SELLER]},
                           {"target": ["A"], "comparison": ["B"]})      # sellers never overlap across categories
    assert r.status == "refused" and any(x.code == "NOT_COMPARABLE" for x in r.validation)



async def test_one_treatment_role(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "conditions": [CHANNEL]}, {})
    assert r.status == "refused"


async def test_average_cem_uses_verified_primary_units_without_proportion_intervals(provider):
    provider.catalog.get(AOV).metric_kind = "average"
    provider.catalog.get(AOV).ratio_parts = None
    provider.catalog.get(AOV).entity = ORDER
    provider.catalog.get(COUNT).entity = ORDER
    result = await registry.run("causal.cem", ctx(provider),
                                {"metric": AOV, "sample_count": COUNT, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": ["A"], "comparison": ["B"]})
    assert result.status == "success"
    assert result.primary.data["path"] == "average_units"
    assert result.primary.data["matched"]["difference"] == -10000
    assert result.primary.data["statistical_judgement"] == "not_tested"
    assert not any(artifact.type == "interval" for artifact in result.artifacts)
    assert COUNT in result.provenance.semantic_refs


@pytest.mark.parametrize("fault", ["missing_count", "wrong_entity", "duplicate", "null_outcome", "overlap", "private_unit"])
async def test_average_cem_fails_closed(provider, fault):
    provider.catalog.get(AOV).metric_kind = "average"
    provider.catalog.get(AOV).ratio_parts = None
    provider.catalog.get(AOV).entity = ORDER
    provider.catalog.get(COUNT).entity = ORDER if fault != "wrong_entity" else CAT
    if fault == "private_unit":
        provider.catalog.get(ORDER).public = False
    bindings = {"metric": AOV, "sample_count": COUNT, "treatment": CAT, "conditions": [CHANNEL]}
    if fault == "missing_count":
        bindings.pop("sample_count")
    if fault == "duplicate":
        provider.orders.append(dict(provider.orders[0]))
    if fault == "null_outcome":
        execute = provider.execute
        async def missing(*args, **kwargs):
            dataset = await execute(*args, **kwargs)
            index = next(i for i, col in enumerate(dataset.columns) if col.ref == AOV)
            dataset.rows[0][index] = None
            return dataset
        provider.execute = missing
    result = await registry.run("causal.cem", ctx(provider), bindings,
                                {"target": ["A"], "comparison": ["A"] if fault == "overlap" else ["B"]})
    assert result.status == "refused"
    if fault == "private_unit":
        assert provider.calls == 0 and result.primary is None


async def test_small_average_is_not_misidentified_as_percentage(provider):
    provider.catalog.get(AOV).metric_kind = "average"
    provider.catalog.get(AOV).ratio_parts = None
    provider.catalog.get(AOV).entity = ORDER
    provider.catalog.get(COUNT).entity = ORDER
    for order in provider.orders:
        order["amount"] = 25 if order[CAT] == "A" else 50
    result = await registry.run("causal.cem", ctx(provider),
                                {"metric": AOV, "sample_count": COUNT, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": ["A"], "comparison": ["B"]})
    assert result.status == "success" and result.primary.data["matched"]["difference"] == -25
    assert not any(artifact.type == "interval" for artifact in result.artifacts)


def test_matching_removes_composition_difference_without_inventing_effect():
    strata = [m.Stratum("x", {}, {m.TARGET: m.Cell(80, 10), m.COMPARISON: m.Cell(20, 10)}),
              m.Stratum("y", {}, {m.TARGET: m.Cell(20, 50), m.COMPARISON: m.Cell(80, 50)})]
    result = m.match(strata, {}, None)
    assert result["target_kpi"] == result["comparison_kpi"] == 18
    assert result["balance"]["balance_basis"] == "coarsened_strata"
    assert not result["reasons"]


@pytest.mark.parametrize("edges", [[50, 20], [20, 20], [float("nan")], [float("inf")]])
async def test_cem_rejects_invalid_edges_before_query(provider, edges):
    context = ctx(provider)
    with pytest.raises(InvalidBinding):
        await registry.run("causal.cem", context, {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                           {"target": ["A"], "comparison": ["B"], "ranges": {CHANNEL: edges}})
    assert not context.queries


async def test_cem_rejects_edges_for_non_numeric_condition(provider):
    context = ctx(provider)
    result = await registry.run("causal.cem", context, {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": ["A"], "comparison": ["B"], "ranges": {CHANNEL: [20, 50]}})
    assert result.status == "refused" and not context.queries


@pytest.mark.parametrize("fault", ["unknown_parts", "non_ratio", "amount_numerator", "fraction_scale", "wrong_count"])
async def test_cem_does_not_infer_percentage_semantics_from_numeric_values(provider, fault):
    if fault == "unknown_parts":
        provider.catalog.get(RR).ratio_parts = None
    elif fault == "non_ratio":
        provider.catalog.get(RR).metric_kind = "additive"
    elif fault == "amount_numerator":
        provider.catalog.get(RET).metric_kind = "additive"
    else:
        execute = provider.execute
        async def altered(*args, **kwargs):
            dataset = await execute(*args, **kwargs)
            index = next(i for i, col in enumerate(dataset.columns) if col.ref == (RR if fault == "fraction_scale" else RET))
            for row in dataset.rows:
                row[index] = row[index] / 100 if fault == "fraction_scale" else row[index] + 1
            return dataset
        provider.execute = altered
    result = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": ["A"], "comparison": ["B"]})
    assert result.status == "success"
    assert result.primary.data["statistical_judgement"] == "not_tested"
    assert not any(artifact.type == "interval" for artifact in result.artifacts)


async def test_failed_matching_has_no_significance_artifact(provider):
    result = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [SELLER]},
                                {"target": ["A"], "comparison": ["B"]})
    assert result.status == "refused" and result.provides == []
    assert result.primary.data["statistical_judgement"] == "not_tested"
    assert not any(artifact.type == "interval" for artifact in result.artifacts)


@pytest.mark.parametrize("target,comparison", [({"exclude": ["A"]}, {"exclude": ["B"]}),
                                               ({"exclude": ["A"]}, {"gte": 10})])
async def test_cem_rejects_ambiguous_exclusion_groups(provider, target, comparison):
    context = ctx(provider)
    result = await registry.run("causal.cem", context, {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": target, "comparison": comparison})
    assert result.status == "refused" and not context.queries


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
async def test_cem_refuses_nonfinite_outcome(provider, bad):
    execute = provider.execute
    async def corrupted(*args, **kwargs):
        dataset = await execute(*args, **kwargs)
        index = next(i for i, col in enumerate(dataset.columns) if col.ref == RR)
        for row in dataset.rows:
            row[index] = bad
        return dataset
    provider.execute = corrupted
    result = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]},
                                {"target": ["A"], "comparison": ["B"]})
    assert result.status == "refused" and result.primary is None

"""causal.cem on the in-memory provider, plus the pure matching pieces."""
import pytest

from decision_layer.methods import registry
from decision_layer.methods.causal import matching as m
from test_methods import CAT, CHANNEL, RR, SELLER, FakeProvider, ctx

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


async def test_cem_asks_for_groups(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [CHANNEL]}, {})
    assert r.status == "needs_input" and r.needs_input["field"] == "target"
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": SELLER, "conditions": [CHANNEL]},
                           {"target": ["S1"]})
    assert r.status == "needs_input" and r.needs_input["field"] == "comparison"
    assert r.needs_input["candidates"][0]["value"] == {"exclude": ["S1"]}   # many values: "everyone else" first


async def test_cem_refuses_when_not_comparable(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "treatment": CAT, "conditions": [SELLER]},
                           {"target": ["A"], "comparison": ["B"]})      # sellers never overlap across categories
    assert r.status == "refused" and any(x.code == "NOT_COMPARABLE" for x in r.validation)



async def test_one_treatment_role(provider):
    r = await registry.run("causal.cem", ctx(provider), {"metric": RR, "conditions": [CHANNEL]}, {})
    assert r.status == "refused"

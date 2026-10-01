"""Query Methods end to end against the local Cube (see test_cube_live.py for setup).

Needs the ratio parts declared in the example model (examples/ecommerce/cube/model/cubes/ecom_order.yml).
"""
import os

import pytest

from decision_layer.core.models import CallerInfo, PlanStep
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.store import MemoryRunStore
from conftest import ref
from test_cube_live import creds, provider

pytestmark = [pytest.mark.cube, pytest.mark.skipif(not os.environ.get("CUBE_API_SECRET"), reason="CUBE_API_SECRET not set")]
RR, CAT, SELLER = ref("ecom_order.return_rate"), ref("ecom_product.category_nm"), ref("ecom_order.seller_id")
YTD = {"date_range": ["2026-01-01", "2026-09-30"]}


async def run(name, bindings, params=None, scope=YTD):
    engine = RunEngine(provider(), RecipeStore("/nonexistent", "cube", "local"), MemoryRunStore())
    _, result = await engine.adhoc(creds(), CallerInfo(subject="live-test"),
                                   PlanStep(method=name, bindings=bindings, params=params or {}), scope)
    return result


async def test_drilldown_category_then_seller():
    """examples/ecommerce/EXPECTED.md: 여성의류 → S017 22.81%."""
    b = {"metric": RR, "dimensions": [CAT, SELLER]}
    r = await run("query.drilldown", b)
    top = r.primary.data["rows"][0]
    assert (top["value"], round(top["metric"], 2)) == ("여성의류", 16.73)
    path = r.primary.data["next_candidates"][0]["drill_path"]

    r = await run("query.drilldown", b, {"drill_path": path})
    top = r.primary.data["rows"][0]
    assert (top["value"], round(top["metric"], 2), top["count"]) == ("S017", 22.81, 526)
    assert top["test"]["selection"]["significant_after_selection"]


async def test_drilldown_period_mode_decomposes_declared_ratio():
    r = await run("query.drilldown", {"metric": RR, "dimensions": [CAT]}, {"vs_previous": True},
                  scope={"date_range": ["2026-07-01", "2026-09-30"]})
    change = next(a.data for a in r.artifacts if a.type == "estimate")
    assert r.primary.data["decomposition"] == "mix_rate"
    shown = sum(g["contribution"] for g in r.primary.data["rows"])
    assert shown + r.primary.data["other_contribution"] == pytest.approx(change["change"], abs=1e-3)


async def test_trend_says_q3_return_rate_change_is_noise():
    """EXPECTED.md: Q3 vs Q2 return rate +0.09 pp, 95% CI includes 0."""
    r = await run("query.trend", {"metric": RR}, {"comparison": ["2026-04-01", "2026-06-30"]},
                  scope={"date_range": ["2026-07-01", "2026-09-30"]})
    test = next(a.data for a in r.artifacts if a.type == "estimate")["test"]
    assert test["ci95"][0] < 0 < test["ci95"][1] and not test["significant"]


async def test_trend_attributes_q3_sales_growth_to_the_extra_day():
    """EXPECTED.md: +0.65% total, all of it from 92 vs 91 days."""
    r = await run("query.trend", {"metric": ref("ecom_order.total_order_amount")}, {"comparison": ["2026-04-01", "2026-06-30"]},
                  scope={"date_range": ["2026-07-01", "2026-09-30"]})
    change = next(a.data for a in r.artifacts if a.type == "estimate")
    assert change["change_pct"] == pytest.approx(0.65, abs=0.01) and change["per_day"]["change_pct"] < 0
    days = change["decomposition"]["decompositions"][0]["factors"][0]
    assert days["factor"] == "period_days" and days["share_of_change"] > 100


FULL = {"date_range": ["2026-01-01", "2026-09-30"]}
AMOUNT_RANGES = {ref("ecom_order.order_amount"): [30000, 100000, 300000]}
ORDER_CONDITIONS = [CAT, ref("ecom_order.channel"), ref("ecom_order.order_amount")]
DELIVERY_CONDITIONS = [ref("ecom_customer.region"), ref("ecom_delivery.warehouse_nm")]


def matched(r):
    assert r.status == "success", (r.warnings, r.validation)
    return r.primary.data["matched"]


async def test_cem_free_shipping():
    """examples/ecommerce/EXPECTED.md (planted effects in examples/ecommerce/data/ecom.sql)."""
    r = await run("causal.cem", {"metric": RR, "treatment": ref("ecom_order.is_free_shipping"), "conditions": ORDER_CONDITIONS},
                  {"ranges": AMOUNT_RANGES}, FULL)
    assert matched(r) == {"target": pytest.approx(11.403, abs=0.01), "comparison": pytest.approx(9.834, abs=0.01),
                          "difference": pytest.approx(1.569, abs=0.01)}
    balance = next(a.data for a in r.artifacts if a.type == "balance")
    assert (balance["strata_common"], balance["target_matched_units"]) == (182, 82601)


@pytest.mark.parametrize("carrier,diff", [("B택배", 1.962), ("C택배", 0.028)])
async def test_cem_carriers(carrier, diff):
    r = await run("causal.cem", {"metric": ref("ecom_order.late_delivery_rate"), "treatment": ref("ecom_delivery.carrier_nm"),
                                 "conditions": DELIVERY_CONDITIONS}, {"target": [carrier], "comparison": ["A택배"]}, FULL)
    assert matched(r)["difference"] == pytest.approx(diff, abs=0.01)


async def test_cem_delivery_days_unit_path():
    r = await run("causal.cem", {"metric": RR, "treatment_measure": ref("ecom_delivery.avg_delivery_days"),
                                 "conditions": ORDER_CONDITIONS}, {"ranges": AMOUNT_RANGES, "target": {"gte": 3}}, FULL)
    assert matched(r)["difference"] == pytest.approx(1.814, abs=0.01) and r.primary.data["path"] == "unit"

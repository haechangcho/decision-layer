"""Read-only real-sample scenarios, optionally recorded through the ordinary REST API."""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import asdict
import json
import math
import os

from decision_layer.dev import MethodSession
from decision_layer.methods import Filter, Scope, register_builtins
from decision_layer.semantic.credentials import ServiceCredentials
from examples.methods.scenarios.methods import AUTHORED

ROOT = "cube://journey/"


def ref(member):
    return ROOT + member.replace(".", "/")


def cases():
    receipts = ref("transaction.receipts")
    date = ref("transaction.analysis_date")
    campaign = ref("campaign_household_outcomes.campaign_id")
    start = ref("campaign_household_outcomes.campaign_start_date")
    unit = ref("campaign_household_outcomes.observation_id")
    post = ref("campaign_household_outcomes.post_sales_mean")
    pre = ref("campaign_household_outcomes.pre_sales_mean")
    target = ref("campaign_household_outcomes.is_targeted")
    month = Scope(("2001-02-01", "2001-02-28"), date)
    half_year = Scope(("2001-01-01", "2001-06-30"), date)
    campaign_filter = Filter(member=campaign, operator="equals", values=["8"])
    campaign_scope = Scope(("2001-02-15", "2001-02-15"), start, [campaign_filter])
    panel_time = ref("campaign_household_panel.period_date")
    panel_scope = Scope(("2001-01-16", "2001-02-15"), panel_time,
        [Filter(member=ref("campaign_household_panel.campaign_id"), operator="equals", values=["8"])])
    panel = {"measures": {"outcome": ref("campaign_household_panel.sales")},
             "dimensions": {"treated": ref("campaign_household_panel.is_targeted"), "time": panel_time},
             "entity": unit, "scope": panel_scope,
             "params": {"granularity": "day"}}
    return {
        "by_group": ("example.group_metric", {"measures": {"metric": receipts},
            "dimensions": {"group": ref("product.department")}, "scope": half_year, "params": {"limit": 3}}),
        "trend": ("example.series", {"measures": {"metric": receipts}, "scope": half_year}),
        "period": ("example.period_difference", {"measures": {"metric": receipts}, "scope": month,
            "params": {"baseline": ("2001-01-01", "2001-01-31")}}),
        "peer": ("example.peer", {"measures": {"metric": ref("transaction.coupon_line_rate")}, "scope": half_year,
            "params": {"subject": {"member": ref("transaction.store"), "value": "364"},
                       "peers": [{"member": ref("product.department"), "operator": "equals", "values": ["GROCERY"]}]}}),
        "ols": ("stats.ols", {"measures": {"outcome": post, "features": [pre]}, "entity": unit, "scope": campaign_scope}),
        "dowhy": ("stats.binary_regression", {"measures": {"outcome": post, "confounders": [pre]},
            "dimensions": {"treatment": target}, "entity": unit, "scope": campaign_scope}),
        "econml": ("stats.linear_dml", {"measures": {"outcome": post, "confounders": [pre]},
            "dimensions": {"treatment": target}, "entity": unit, "scope": campaign_scope}),
        "unit-change": ("query.unit_change", {"measures": {"outcome": post, "baseline_outcome": pre}, "entity": unit, "scope": campaign_scope}),
        "did": ("stats.two_period_contrast", panel),
        "did-split": ("stats.two_period_contrast", {**panel, "params": {**panel["params"],
            "windows": [("2001-01-16", "2001-01-16"), ("2001-02-15", "2001-02-15")]}}),
        "mixed": ("query.unit_distribution", {"measures": {"outcome": post}, "entity": unit, "scope": campaign_scope}),
    }


def wire(value):
    if isinstance(value, Scope):
        return wire(asdict(value))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value


def compare_sql(name, data, database):
    """Independent source SQL is a test oracle, never a Method execution path."""
    import psycopg
    with psycopg.connect(database, options="-c default_transaction_read_only=on") as connection, connection.cursor() as cursor:
        if name == "by_group":
            cursor.execute("""SELECT p.department,sum(t.sales_value::numeric) FROM journey.transaction_data t
                LEFT JOIN journey.product p ON p.product_id=t.product_id
                WHERE transaction_date BETWEEN '2001-01-01' AND '2001-06-30'
                GROUP BY p.department ORDER BY 2 DESC LIMIT 3""")
            expected = cursor.fetchall()
            assert [row["group"] for row in data] == [row[0] for row in expected]
            assert all(math.isclose(actual["metric"], float(wanted[1]), abs_tol=.01) for actual, wanted in zip(data, expected))
        elif name == "trend":
            cursor.execute("""SELECT to_char(transaction_date,'YYYY-MM'),sum(sales_value::numeric)
                FROM journey.transaction_data WHERE transaction_date BETWEEN '2001-01-01' AND '2001-06-30'
                GROUP BY 1 ORDER BY 1""")
            expected = cursor.fetchall()
            actual = sorted(data["rows"], key=lambda row: row["time"])
            assert [str(row["time"])[:7] for row in actual] == [row[0] for row in expected]
            assert all(math.isclose(a["metric"], float(b[1]), abs_tol=.01) for a, b in zip(actual, expected))
        elif name == "period":
            cursor.execute("""SELECT sum(sales_value::numeric) FILTER(WHERE transaction_date>='2001-02-01'),
                sum(sales_value::numeric) FILTER(WHERE transaction_date<'2001-02-01')
                FROM journey.transaction_data WHERE transaction_date BETWEEN '2001-01-01' AND '2001-02-28'""")
            a, b = cursor.fetchone()
            assert math.isclose(data[0]["difference"], float(a - b), abs_tol=.01)
        elif name == "peer":
            cursor.execute("""SELECT
                100.0*count(*) FILTER(WHERE p.department='GROCERY' AND t.store_id='364' AND coupon_disc::numeric<0)
                    /NULLIF(count(*) FILTER(WHERE p.department='GROCERY' AND t.store_id='364'),0),
                100.0*count(*) FILTER(WHERE p.department='GROCERY' AND t.store_id<>'364' AND coupon_disc::numeric<0)
                    /NULLIF(count(*) FILTER(WHERE p.department='GROCERY' AND t.store_id<>'364'),0),
                100.0*count(*) FILTER(WHERE t.store_id<>'364' AND coupon_disc::numeric<0)
                    /NULLIF(count(*) FILTER(WHERE t.store_id<>'364'),0)
                FROM journey.transaction_data t LEFT JOIN journey.product p ON p.product_id=t.product_id
                WHERE transaction_date BETWEEN '2001-01-01' AND '2001-06-30'""")
            a, b, c = map(float, cursor.fetchone())
            assert math.isclose(data[0]["difference"], a - b, abs_tol=1e-8)
            assert math.isclose(data[1]["difference"], a - c, abs_tol=1e-8)
        elif name == "ols":
            cursor.execute("""SELECT regr_intercept(post_sales_30d,pre_sales_30d),regr_slope(post_sales_30d,pre_sales_30d)
                FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8'""")
            a, b = cursor.fetchone()
            assert math.isclose(data[0]["coefficient"], float(a), rel_tol=1e-8, abs_tol=1e-8)
            assert math.isclose(data[1]["coefficient"], float(b), rel_tol=1e-8, abs_tol=1e-8)
        elif name == "unit-change":
            cursor.execute("""SELECT observation_id,post_sales_30d-pre_sales_30d FROM journey.campaign_household_outcomes
                WHERE eligible AND campaign_id='8'""")
            expected = dict(cursor.fetchall())
            assert len(data) == len(expected)
            assert all(math.isclose(row["change"], float(expected[row["unit"]]), abs_tol=1e-8) for row in data)
        elif name in ("did", "did-split"):
            cursor.execute("""SELECT avg(post_sales_30d-pre_sales_30d) FILTER(WHERE is_targeted)
                -avg(post_sales_30d-pre_sales_30d) FILTER(WHERE NOT is_targeted)
                FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8'""")
            assert math.isclose(data["value"], float(cursor.fetchone()[0]), rel_tol=1e-8, abs_tol=1e-8)
        elif name == "mixed":
            cursor.execute("""SELECT avg(post_sales_30d),min(post_sales_30d),max(post_sales_30d),count(*)
                FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8'""")
            expected = cursor.fetchone()
            assert all(math.isclose(data[0][key], float(value), abs_tol=1e-8)
                       for key, value in zip(["provider_value", "unit_min", "unit_max", "n_units"], expected))
        else:
            return False
    return True


async def main(args):
    entries = cases()
    selected = list(entries) if args.all else [args.case]
    if any(name not in entries for name in selected):
        raise SystemExit("Choose: " + ", ".join(entries))
    session = None
    if not args.api:
        secret = os.environ.get("DL_JOURNEY_CUBE_SECRET", "local-example-secret-change-me-0123456789")
        session = await MethodSession.cube(args.cube, ServiceCredentials(secret, ()), instance="journey")
        register_builtins(session.registry)
        for implementation in AUTHORED:
            session.register(implementation)
    try:
        for name in selected:
            method, arguments = entries[name]
            arguments = wire(arguments)
            if args.api:
                import httpx
                headers = {"Authorization": "Bearer " + os.environ["DL_TOKEN"]} if os.environ.get("DL_TOKEN") else {}
                async with httpx.AsyncClient(base_url=args.api, headers=headers, timeout=150) as client:
                    response = await client.post(f"/methods/{method}:run", json={**arguments,
                        "question": f"Complete Journey developer scenario: {name}"}, params={"wait": 120})
                    response.raise_for_status()
                    result = response.json()
                    while result.get("status") == "running":
                        await asyncio.sleep(.25)
                        response = await client.get(result["poll"])
                        response.raise_for_status()
                        result = response.json()
                    response = await client.get("/runs/" + result["run_id"])
                    response.raise_for_status()
                    recorded = response.json()
                    assert recorded["steps"][-1]["result"]["status"] == result["status"]
                    assert recorded["steps"][-1]["method"] == result["provenance"]["method"]
                    assert not recorded.get("error"), recorded.get("error")
                    attempts = len(recorded["query_attempts"])
                    if result["status"] == "success":
                        assert result["provenance"]["queries"]
                        assert "python" in result["provenance"]["runtime"]
                        assert all(attempt["status"] == "success" for attempt in recorded["query_attempts"])
            else:
                scope = arguments.pop("scope")
                trial = await session.run(method, scope=Scope(tuple(scope["date_range"]), scope["time_dimension"],
                    [Filter.model_validate(item) for item in scope["filters"]]), **arguments)
                result = trial.result.model_dump(mode="json")
                attempts = len(trial.attempts)
            expected_refusal = name in ("dowhy", "econml") and result["status"] == "refused"
            if result["status"] != "success" and not expected_refusal:
                raise AssertionError(result)
            verified = False
            data = result["primary"]["data"] if result.get("primary") else None
            if result["status"] == "success" and args.verify_sql:
                database = os.environ["DL_JOURNEY_DATABASE_URL"]
                verified = compare_sql(name, data, database)
            print(json.dumps({"case": name, "method": method, "status": result["status"], "expected_refusal": expected_refusal,
                "interpretation": result.get("interpretation"), "queries": attempts, "run_id": result.get("run_id"),
                "sql_verified": verified, "warnings": result["warnings"], "rows": len(data) if isinstance(data, list) else None,
                "preview": data[:5] if isinstance(data, list) else data}, ensure_ascii=False))
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="by_group")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--cube", default=os.environ.get("DL_JOURNEY_CUBE_URL", "http://127.0.0.1:4000/cubejs-api/v1"))
    parser.add_argument("--api", help="Record through a locally bootstrapped tutorial API")
    parser.add_argument("--verify-sql", action="store_true")
    asyncio.run(main(parser.parse_args()))

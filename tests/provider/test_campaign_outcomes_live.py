"""Opt-in source-model boundary tests against PostgreSQL; isolated schema, rolled back."""
import os
import json
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

DATABASE = os.environ.get("DL_JOURNEY_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE, reason="Set DL_JOURNEY_DATABASE_URL for isolated PostgreSQL tests")


def test_campaign_windows_population_and_zero_purchase():
    schema = "campaign_test_" + uuid4().hex
    with psycopg.connect(DATABASE) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
                cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                cursor.execute("""
                  CREATE TABLE transaction_data(household_key text, transaction_date date, sales_value text, basket_id text);
                  CREATE TABLE household(household_key text);
                  CREATE TABLE campaign_desc(campaign text, description text, start_date date, end_date date);
                  CREATE TABLE campaign_table(campaign text, household_key text);
                  CREATE TABLE hh_demographic(household_key text, classification_1 text, classification_3 text, classification_5 text);
                  INSERT INTO household VALUES ('target'), ('control'), ('future');
                  INSERT INTO campaign_desc VALUES
                    ('main','A','2001-02-01','2001-02-10'),
                    ('other','B','2001-02-02','2001-02-12'),
                    ('early','C','2001-01-01','2001-01-02'),
                    ('late','D','2001-03-04','2001-03-05');
                  INSERT INTO campaign_table VALUES ('main','target'), ('main','target'), ('other','control');
                  INSERT INTO hh_demographic VALUES ('target','a','i','c');
                  INSERT INTO transaction_data VALUES
                    ('target','2001-01-01','1000','outside-pre'),
                    ('target','2001-01-02','10','pre-boundary'),
                    ('target','2001-01-31','20','pre-last'),
                    ('target','2001-02-01','30','post-first'),
                    ('target','2001-03-02','40','post-last'),
                    ('target','2001-03-03','2000','outside-post'),
                    ('control','2001-01-31','15','control-pre'),
                    ('future','2001-02-03','500','post-only');
                """)
                statement = (Path(__file__).resolve().parents[2] / "examples/complete-journey/campaign_outcomes.sql").read_text()
                cursor.execute(statement.replace("journey.", schema + "."))
                cursor.execute("SELECT campaign_id,household_key,pre_sales_30d,pre_baskets_30d,post_sales_30d,is_targeted,eligible,overlapping_campaigns FROM campaign_household_outcomes WHERE campaign_id='main' ORDER BY household_key")
                rows = {row[1]: row for row in cursor.fetchall()}
                assert len(rows) == 3
                assert rows['target'][2:8] == (30, 2, 70, True, True, 0)
                assert rows['control'][2:8] == (15, 1, 0, False, True, 1)
                assert rows['future'][6] is False
                cursor.execute("SELECT count(*), count(DISTINCT observation_id) FROM campaign_household_outcomes")
                assert cursor.fetchone() == (12, 12)
                cursor.execute("SELECT bool_or(eligible), count(pre_sales_30d) FROM campaign_household_outcomes WHERE campaign_id='early'")
                assert cursor.fetchone() == (False, 0)
                cursor.execute("SELECT bool_or(eligible), count(post_sales_30d) FROM campaign_household_outcomes WHERE campaign_id='late'")
                assert cursor.fetchone() == (False, 0)
        finally:
            connection.rollback()


@pytest.mark.skipif(not os.environ.get("DL_JOURNEY_CUBE_URL"),
                    reason="Set Cube URL for source-model verification")
async def test_cube_cem_matches_independent_sql():
    from decision_layer.core.models import DatasetSpec, Filter, TimeScope
    from decision_layer.methods import registry
    from decision_layer.methods.context import ExecutionContext, Scope
    from decision_layer.semantic.credentials import ServiceCredentials
    from decision_layer.semantic.providers.cube.client import CubeClient
    from decision_layer.semantic.providers.cube.provider import CubeProvider

    with psycopg.connect(DATABASE) as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT is_targeted, count(*), avg(post_sales_30d)
            FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8' GROUP BY is_targeted""")
        raw = {row[0]: (row[1], float(row[2])) for row in cursor.fetchall()}
        cursor.execute("""WITH s AS (
          SELECT pre_sales_band,pre_frequency_band,
            count(*) FILTER(WHERE is_targeted) AS nt,
            count(*) FILTER(WHERE NOT is_targeted) AS nc,
            avg(post_sales_30d) FILTER(WHERE is_targeted) AS mt,
            avg(post_sales_30d) FILTER(WHERE NOT is_targeted) AS mc
          FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8'
          GROUP BY 1,2)
          SELECT sum(nt*mt)/sum(nt),sum(nt*mc)/sum(nt),sum(nt),sum(nc)
          FROM s WHERE nt>0 AND nc>0""")
        target_mean, comparison_mean, target_n, comparison_n = cursor.fetchone()
    provider = CubeProvider(CubeClient(os.environ["DL_JOURNEY_CUBE_URL"]), "journey")
    credentials = ServiceCredentials(os.environ["DL_JOURNEY_CUBE_SECRET"], ())
    metric = "cube://journey/campaign_household_outcomes/post_sales_mean"
    count = "cube://journey/campaign_household_outcomes/count"
    dimension = lambda name: "cube://journey/campaign_household_outcomes/" + name
    time = dimension("campaign_start_date")
    catalog = await provider.discover(credentials)
    assert catalog.get(metric).entity == catalog.get(count).entity and catalog.get(metric).entity
    scope = Scope(date_range=("2001-01-01", "2001-06-30"), time_dimension=time,
                  filters=[Filter(member=dimension("campaign_id"), operator="equals", values=["8"])])
    spec = DatasetSpec(grain="aggregate", measures=[metric,count], dimensions=[dimension("is_targeted")],
                       time=TimeScope(dimension=time, date_range=scope.date_range), filters=scope.filters)
    dataset = await provider.execute(spec, credentials, with_sql=True)
    for group, mean, n in dataset.rows:
        is_target = str(group).lower() in ("true", "t", "1")
        assert n == raw[is_target][0] and float(mean) == pytest.approx(raw[is_target][1])
    assert dataset.provenance[0].compiled_sql
    context = ExecutionContext(provider, credentials, catalog, scope)
    bindings = {"metric":metric,"sample_count":count,"treatment":dimension("is_targeted"),
                "conditions":[dimension("pre_sales_band"),dimension("pre_frequency_band")]}
    result = await registry.run("causal.cem", context, bindings, {"target":[True],"comparison":[False]})
    assert result.status == "success", result.warnings
    assert result.primary.data["matched"]["target"] == pytest.approx(float(target_mean), abs=0.0001)
    assert result.primary.data["matched"]["comparison"] == pytest.approx(float(comparison_mean), abs=0.0001)
    balance = next(a.data for a in result.artifacts if a.type == "balance")
    assert (balance["target_matched_units"],balance["comparison_matched_units"]) == (target_n,comparison_n)
    assert not any(a.type == "interval" for a in result.artifacts)
    assert result.primary.data["statistical_judgement"] == "not_tested"
    # The full requested demographic comparison must fail closed, not lower its threshold.
    bindings["conditions"] += [dimension("age_code"),dimension("income_code"),dimension("composition_code")]
    full = await registry.run("causal.cem", context, bindings, {"target":[True],"comparison":[False]})
    assert full.status == "refused" and any(v.code == "NOT_COMPARABLE" for v in full.validation)


@pytest.mark.skipif(not os.environ.get("DL_JOURNEY_API_URL"), reason="Set DL_JOURNEY_API_URL for MCP Run verification")
async def test_campaign_mcp_records_success_and_refusal_in_one_run():
    import httpx
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    api_url = os.environ["DL_JOURNEY_API_URL"]
    async with httpx.AsyncClient(base_url=api_url) as api:
        active = (await api.get("/sources/current")).json()["provider"]
    assert active == "cube"
    metric = "cube://journey/campaign_household_outcomes/post_sales_mean"
    count = "cube://journey/campaign_household_outcomes/count"
    dimension = lambda name: "cube://journey/campaign_household_outcomes/" + name
    time = dimension("campaign_start_date")

    def payload(response):
        assert not response.is_error, response
        value = response.structured_content or json.loads(response.content[0].text)
        assert not value.get("error"), value
        return value

    async def execute(client, args):
        value = payload(await client.call_tool("run_step", args))
        while value.get("status") == "running":
            value = payload(await client.call_tool("wait_for_run", {"run_id": args["run_id"]}))
        return value

    question = "2001년 2월 15일에 시작한 8번 캠페인의 대상 가구는 비대상보다 이후 30일 평균 판매금액이 높았어? 이전 구매금액·빈도로 맞추고, 가구 특성까지 추가하면 비교 가능한지도 확인해줘."
    server = StdioServerParameters(command=sys.executable, args=["-m", "decision_layer.mcp.server"],
                                   env={"DL_API_URL":api_url,"DL_LOCALE":"ko"})
    run_id = None
    goals = [
        {"id": "counts", "description": "Check analysis populations", "semantic_refs": [count], "required_capabilities": ["group_breakdown"]},
        {"id": "matched", "description": "Match prior purchase behavior", "semantic_refs": [metric], "required_capabilities": ["matched_comparison"]},
        {"id": "household", "description": "Also match household characteristics", "semantic_refs": [metric], "required_capabilities": ["matched_comparison"]},
    ]
    try:
        async with stdio_client(server) as (read,write), ClientSession(read,write) as client:
            await client.initialize()
            candidates = payload(await client.call_tool("find_recipes", {"question": question, "goals": goals}))
            started = payload(await client.call_tool("start_analysis", {"question":question,
                "goals": goals,
                "recipe_review": [{"recipe": item["recipe"], "decision": "skipped",
                    "reason": "This controlled integration test checks Method contracts separately from Recipe routing."}
                    for item in candidates["candidates"]],
                "date_range":["2001-02-15","2001-02-15"],"time_dimension":time,
                "filters":[{"member":dimension("campaign_id"),"operator":"equals","values":["8"]}]}))
            run_id = started["run_id"]
            first = await execute(client, {"run_id":run_id,"method":"query.drilldown","purpose":"대상·비대상 분석 가구 수 확인",
                "goal_ids": ["counts"],
                "bindings":{"metric":count,"dimensions":[dimension("is_targeted")]}})
            assert first["status"] == "success"
            bindings = {"metric":metric,"sample_count":count,"treatment":dimension("is_targeted"),
                        "conditions":[dimension("pre_sales_band"),dimension("pre_frequency_band")]}
            matched = await execute(client, {"run_id":run_id,"method":"causal.cem","purpose":"이전 구매 성향을 맞춘 이후 평균 판매금액 비교",
                "goal_ids": ["matched"],
                "bindings":bindings,"params":{"target":[True],"comparison":[False]}})
            assert matched["status"] == "success", matched
            bindings["conditions"] += [dimension("age_code"),dimension("income_code"),dimension("composition_code")]
            full = await execute(client, {"run_id":run_id,"method":"causal.cem","purpose":"가구 특성까지 맞출 때 비교 표본이 충분한지 확인",
                "goal_ids": ["household"],
                "bindings":bindings,"params":{"target":[True],"comparison":[False]}})
            assert full["status"] == "refused", full
            difference = matched["primary"]["data"]["matched"]["difference"]
            payload(await client.call_tool("complete_run", {"run_id":run_id,"conclusion":{
                "answer":f"이전 구매금액·빈도를 맞춘 대상−비대상 평균 판매금액 차이는 {difference}입니다. 가구 특성까지 맞춘 비교는 표본 부족으로 결론낼 수 없습니다.",
                "findings":[{"text":"대상·비대상 가구 수를 확인했습니다.","step_indices":[0]},
                            {"text":"이전 구매 성향을 맞춘 평균 차이를 계산했습니다.","step_indices":[1]},
                            {"text":"가구 특성을 추가한 비교는 기준을 충족하지 못했습니다.","step_indices":[2]}],
                "limitations":["평균 판매금액의 통계적 유의성은 검정하지 않았습니다.","관찰 데이터의 조건 맞춤 비교이며 인과 효과가 아닙니다.","실제 수신 시점과 가구별 관측 완전성은 확인할 수 없으며 다른 캠페인 노출이 남습니다."],
                "goal_outcomes": [
                    {"goal_id": "counts", "status": "supported", "step_indices": [0]},
                    {"goal_id": "matched", "status": "supported", "step_indices": [1]},
                    {"goal_id": "household", "status": "inconclusive", "step_indices": [2], "reason": "Insufficient matched sample", "reason_code": "data_insufficient"},
                ]}}))
        async with httpx.AsyncClient(base_url=api_url) as api:
            run = (await api.get(f"/runs/{run_id}")).json()
            assert run["status"] == "completed" and run["plan"]["question"] == question
            assert [s["result"]["status"] for s in run["steps"]] == ["success","success","refused"]
            assert run["steps"][1]["step"]["bindings"]["sample_count"] == count
            assert all(s["result"]["provenance"]["queries"] for s in run["steps"])
        print(f"CAMPAIGN_MCP_RUN_ID={run_id}")
    finally:
        if run_id and os.environ.get("DL_KEEP_TEST_RUNS") != "true":
            async with httpx.AsyncClient(base_url=api_url) as api:
                response = await api.delete(f"/runs/{run_id}")
                assert response.status_code == 204

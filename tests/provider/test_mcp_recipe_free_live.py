"""Opt-in MCP protocol smoke test against an isolated API with no Recipes."""
import json
import os
import sys

import httpx
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


API_URL = os.environ.get("DL_LIVE_EMPTY_API_URL")
pytestmark = pytest.mark.skipif(not API_URL, reason="Set DL_LIVE_EMPTY_API_URL to an isolated, Recipe-free API")
QUESTION = "2026년 6월 지급결정금액은 얼마이며 지급유형별로 어디가 가장 큰가?"


def payload(response):
    assert not response.is_error, response
    value = response.structured_content
    if value is None:
        value = json.loads(response.content[0].text)
    assert not value.get("error"), value
    return value


@pytest.mark.asyncio
async def test_mcp_question_uses_two_methods_in_one_visible_run():
    async with httpx.AsyncClient(base_url=API_URL) as api:
        recipes = (await api.get("/recipes")).json()
        assert recipes == [], "Use an isolated API; do not delete or test against existing Recipes"

    server = StdioServerParameters(command=sys.executable, args=["-m", "decision_layer.mcp.server"],
                                   env={"DL_API_URL": API_URL, "DL_LOCALE": "ko"})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        assert {"list_recipes", "search_semantic", "describe_method", "start_analysis", "run_step", "complete_run"} <= tools
        assert payload(await session.call_tool("list_recipes"))["recipes"] == []

        async def semantic(title, kind):
            objects = payload(await session.call_tool("search_semantic", {"query": title, "kind": kind}))["objects"]
            return next(item["ref"] for item in objects if item["title"] == title)

        metric = await semantic("지급결정금액 합계", "measure")
        date = await semantic("지급일자", "time_dimension")
        dimension = await semantic("지급유형", "dimension")
        for method in ("query.trend", "query.drilldown"):
            assert payload(await session.call_tool("describe_method", {"name": method}))["name"] == method

        started = payload(await session.call_tool("start_analysis", {
            "question": QUESTION, "date_range": ["2026-06-01", "2026-06-30"], "time_dimension": date,
        }))
        run_id = started["run_id"]
        assert started["status"] == "open" and started["question"] == QUESTION

        trend = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.trend", "purpose": "6월 지급결정금액 확인", "bindings": {"metric": metric},
        }))
        assert trend["status"] == "success" and trend["run_id"] == run_id
        breakdown = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown",
            "purpose": "지급유형별 최대 금액 확인",
            "bindings": {"metric": metric, "dimensions": [dimension]},
        }))
        assert breakdown["status"] == "success" and breakdown["run_id"] == run_id
        amount = trend["primary"]["data"]["rows"][0][metric]
        top = breakdown["primary"]["data"]["rows"][0]
        freshness = next(item for item in trend["validation"] if item["code"] == "DATA_STALE")
        summary = (f"2026년 6월 지급결정금액은 {amount:,.0f}원이고, 지급유형별 최대는 "
                   f"{top['value']}({top['metric']:,.0f}원)입니다. "
                   f"데이터는 {freshness['details']['latest']}까지만 있어 월말까지의 결과는 아닙니다.")
        completed = payload(await session.call_tool("complete_run", {
            "run_id": run_id, "summary": summary,
        }))
        assert completed["status"] == "completed" and len(completed["steps"]) == 2

    async with httpx.AsyncClient(base_url=API_URL) as api:
        stored = (await api.get(f"/runs/{run_id}")).json()
        assert stored["origin"] == "mcp" and stored["plan"]["question"] == QUESTION
        assert stored["recipe_snapshot"] is None
        assert stored["summary"] == summary
        assert [step["step"]["method"] for step in stored["steps"]] == ["query.trend", "query.drilldown"]
        assert [step["step"]["purpose"] for step in stored["steps"]] == ["6월 지급결정금액 확인", "지급유형별 최대 금액 확인"]
        assert all(step["result"]["provenance"]["queries"] for step in stored["steps"])
    print(f"MCP_RUN_ID={run_id}")

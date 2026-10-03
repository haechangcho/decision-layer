"""Opt-in MCP integration test for the pinned public Online Retail II example."""

import json
import os
from pathlib import Path
import sys

import httpx
import pytest
import yaml
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from decision_layer.recipes.loader import RecipeStore, parse_recipe


API_URL = os.environ.get("DL_RETAIL_API_URL")
pytestmark = pytest.mark.skipif(not API_URL, reason="Set DL_RETAIL_API_URL to the Online Retail example API")
QUESTION = "2011년 3월 영국 외 판매액은 얼마이고 어느 국가가 가장 큰가요?"


def payload(response):
    assert not response.is_error, response
    value = response.structured_content or json.loads(response.content[0].text)
    assert not value.get("error"), value
    return value


@pytest.mark.asyncio
async def test_public_dataset_recipe_free_mcp_run():
    async with httpx.AsyncClient(base_url=API_URL) as api:
        assert (await api.get("/recipes")).json() == [], "Use the fresh example before installing its optional Recipe"

    server = StdioServerParameters(command=sys.executable, args=["-m", "decision_layer.mcp.server"],
                                   env={"DL_API_URL": API_URL, "DL_LOCALE": "ko"})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert payload(await session.call_tool("list_recipes"))["recipes"] == []

        async def semantic(title, kind):
            objects = payload(await session.call_tool("search_semantic", {"query": title, "kind": kind}))["objects"]
            return next(item["ref"] for item in objects if item["title"] == title)

        metric = await semantic("Positive sale value (GBP)", "measure")
        date = await semantic("Invoice date", "time_dimension")
        country = await semantic("Customer country", "dimension")
        started = payload(await session.call_tool("start_analysis", {
            "question": QUESTION, "date_range": ["2011-03-01", "2011-03-31"], "time_dimension": date,
            "filters": [{"member": country, "operator": "notEquals", "values": ["United Kingdom"]}],
        }))
        run_id = started["run_id"]
        trend = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.trend", "purpose": "영국 외 3월 판매액 확인",
            "bindings": {"metric": metric}, "params": {"granularity": "month"},
        }))
        assert trend["status"] == "success"
        assert trend["primary"]["data"]["rows"][0][metric] == pytest.approx(131_409.08)
        breakdown = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown", "purpose": "가장 큰 국가 확인",
            "bindings": {"metric": metric, "dimensions": [country]},
        }))
        assert breakdown["status"] == "success"
        assert breakdown["primary"]["data"]["rows"][0]["value"] == "Netherlands"
        assert breakdown["primary"]["data"]["rows"][0]["metric"] == pytest.approx(22_416.49)
        completed = payload(await session.call_tool("complete_run", {
            "run_id": run_id, "summary": "영국 외 판매액은 131,409.08 GBP이며, 국가별 최대는 Netherlands(22,416.49 GBP)입니다.",
        }))
        assert completed["status"] == "completed"

    async with httpx.AsyncClient(base_url=API_URL) as api:
        stored = (await api.get(f"/runs/{run_id}")).json()
    assert stored["origin"] == "mcp" and stored["plan"]["question"] == QUESTION
    assert stored["recipe_snapshot"] is None and len(stored["steps"]) == 2
    assert [step["step"]["purpose"] for step in stored["steps"]] == ["영국 외 3월 판매액 확인", "가장 큰 국가 확인"]
    assert all(step["result"]["provenance"]["queries"] for step in stored["steps"])
    print(f"RETAIL_MCP_RUN_ID={run_id}")


@pytest.mark.asyncio
async def test_method_outputs_match_public_reference_values():
    date = "cube://online-retail/retail_line/invoice_at"
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as api:
        for measure, expected in (("cancellation_invoice_rate", 16.0363086), ("missing_customer_lines", 8926)):
            metric = f"cube://online-retail/retail_line/{measure}"
            response = await api.post("/methods/query.trend:run?wait=30", json={
                "question": f"March 2011 {measure}", "bindings": {"metric": metric},
                "params": {"granularity": "month"},
                "scope": {"date_range": ["2011-03-01", "2011-03-31"], "time_dimension": date},
            })
            response.raise_for_status()
            result = response.json()
            assert result["status"] == "success"
            assert result["primary"]["data"]["rows"][0][metric] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_optional_recipe_template_previews_without_registration():
    template = Path(__file__).resolve().parents[2] / "examples/online-retail/templates/sales-change.yaml"
    recipe = parse_recipe(yaml.safe_load(template.read_text()), "cube", "online-retail")
    RecipeStore.validate(recipe)
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as api:
        response = await api.post("/recipes:preview?wait=30", json={
            "recipe": recipe.model_dump(mode="json"), "step_index": 1,
            "scope": {"date_range": ["2011-03-01", "2011-03-31"],
                      "time_dimension": "cube://online-retail/retail_line/invoice_at"},
        })
        response.raise_for_status()
        run = response.json()
        assert run["status"] == "completed" and len(run["steps"]) == 2
        assert all(step["result"]["status"] == "success" for step in run["steps"])
        assert (await api.get("/recipes")).json() == []

"""Opt-in multi-table Cube/MCP integration with independent public reference values."""

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


API_URL = os.environ.get("DL_CHINOOK_API_URL")
pytestmark = pytest.mark.skipif(not API_URL, reason="Set DL_CHINOOK_API_URL to the Chinook example API")
QUESTION = "2023년 구매 항목 기준 판매액은 얼마이고, 어떤 장르가 가장 많이 기여했나요?"
METRIC = "cube://chinook/invoice_line/sales"
DATE = "cube://chinook/invoice/invoice_date"
GENRE = "cube://chinook/genre/genre_name"


def payload(response):
    assert not response.is_error, response
    value = response.structured_content or json.loads(response.content[0].text)
    assert not value.get("error"), value
    return value


@pytest.mark.asyncio
async def test_recipe_free_mcp_exploration_uses_governed_multitable_joins():
    async with httpx.AsyncClient(base_url=API_URL) as api:
        assert (await api.get("/recipes")).json() == [], "Run before installing the optional Recipe template"

    server = StdioServerParameters(command=sys.executable, args=["-m", "decision_layer.mcp.server"],
                                   env={"DL_API_URL": API_URL, "DL_LOCALE": "ko"})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        assert payload(await session.call_tool("list_recipes"))["recipes"] == []
        objects = payload(await session.call_tool("search_semantic", {"query": "Track sales", "kind": "measure"}))["objects"]
        assert any(item["ref"] == METRIC for item in objects)
        started = payload(await session.call_tool("start_analysis", {
            "question": QUESTION, "date_range": ["2023-01-01", "2023-12-31"], "time_dimension": DATE,
        }))
        run_id = started["run_id"]
        trend = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.trend", "purpose": "2023년 전체 판매액 확인",
            "bindings": {"metric": METRIC}, "params": {"granularity": "quarter"},
        }))
        assert trend["status"] == "success", trend
        assert sum(row[METRIC] for row in trend["primary"]["data"]["rows"]) == pytest.approx(469.58)
        breakdown = payload(await session.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown", "purpose": "판매액이 가장 큰 장르 확인",
            "bindings": {"metric": METRIC, "dimensions": [GENRE]},
        }))
        assert breakdown["status"] == "success", breakdown
        first = breakdown["primary"]["data"]["rows"][0]
        assert first["value"] == "Rock" and first["metric"] == pytest.approx(156.42)
        assert first["count"] == 158
        completed = payload(await session.call_tool("complete_run", {
            "run_id": run_id,
            "summary": "2023년 판매액은 469.58이며, 가장 큰 장르는 Rock(156.42)입니다. 통화는 원본에 명시되지 않았습니다.",
        }))
        assert completed["status"] == "completed"

    async with httpx.AsyncClient(base_url=API_URL) as api:
        stored = (await api.get(f"/runs/{run_id}")).json()
        candidate = (await api.get(f"/runs/{run_id}/recipe-candidate", params=[("indices", 0), ("indices", 1)])).json()
        assert candidate["recipe"]["status"] == "draft" and len(candidate["recipe"]["steps"]) == 2
        assert (await api.get("/recipes")).json() == []
    assert stored["origin"] == "mcp" and stored["plan"]["question"] == QUESTION
    assert stored["recipe_snapshot"] is None and len(stored["steps"]) == 2
    assert all(step["result"]["provenance"]["queries"] for step in stored["steps"])
    assert any(query["native_query"].get("_view") == "music_sales"
               for query in stored["steps"][1]["result"]["provenance"]["queries"])
    print(f"CHINOOK_MCP_RUN_ID={run_id}")


@pytest.mark.asyncio
async def test_invoice_and_line_grains_reconcile_through_cube():
    async with httpx.AsyncClient(base_url=API_URL, timeout=60) as api:
        for cube, measure, expected in (("invoice", "sales", 469.58), ("invoice", "count", 83),
                                         ("invoice_line", "sales", 469.58), ("invoice_line", "count", 442),
                                         ("invoice_line", "invoice_count", 83)):
            metric = f"cube://chinook/{cube}/{measure}"
            date = DATE
            response = await api.post("/methods/query.trend:run?wait=30", json={
                "question": f"2023 {cube}.{measure}", "bindings": {"metric": metric},
                "params": {"granularity": "quarter"},
                "scope": {"date_range": ["2023-01-01", "2023-12-31"], "time_dimension": date},
            })
            response.raise_for_status()
            result = response.json()
            assert result["status"] == "success", result
            assert sum(row[metric] for row in result["primary"]["data"]["rows"]) == pytest.approx(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("dimension,leader,value", [
    ("artist/artist_name", "U2", 26.73),
    ("employee/rep_name", "Jane Peacock", 184.34),
    ("media_type/format_name", "MPEG audio file", 361.35),
])
async def test_multihop_product_and_customer_dimensions(dimension, leader, value):
    async with httpx.AsyncClient(base_url=API_URL, timeout=60) as api:
        response = await api.post("/methods/query.drilldown:run?wait=30", json={
            "question": f"2023 track sales by {dimension}",
            "bindings": {"metric": METRIC, "dimensions": [f"cube://chinook/{dimension}"]},
            "params": {"min_count": 1},
            "scope": {"date_range": ["2023-01-01", "2023-12-31"], "time_dimension": DATE},
        })
        response.raise_for_status()
        result = response.json()
        assert result["status"] == "success", result
        first = result["primary"]["data"]["rows"][0]
        assert first["value"] == leader and first["metric"] == pytest.approx(value)


@pytest.mark.asyncio
async def test_optional_recipe_previews_without_registering_it():
    template = Path(__file__).resolve().parents[2] / "examples/chinook/templates/music-sales.yaml"
    recipe = parse_recipe(yaml.safe_load(template.read_text()), "cube", "chinook")
    RecipeStore.validate(recipe)
    async with httpx.AsyncClient(base_url=API_URL, timeout=60) as api:
        response = await api.post("/recipes:preview?wait=30", json={
            "recipe": recipe.model_dump(mode="json"), "step_index": 2,
            "scope": {"date_range": ["2023-01-01", "2023-12-31"], "time_dimension": DATE},
        })
        response.raise_for_status()
        run = response.json()
        assert run["status"] == "completed" and len(run["steps"]) == 3, run
        assert all(step["result"]["status"] == "success" for step in run["steps"])
        assert (await api.get("/recipes")).json() == []

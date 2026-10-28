"""Opt-in current-Skill execution against Complete Journey through MCP."""

import json
import os
import sys

import httpx
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

API = os.environ.get("DL_JOURNEY_API_URL")
pytestmark = pytest.mark.skipif(
    not API, reason="Set DL_JOURNEY_API_URL to the Complete Journey API"
)
PREFIX = "cube://journey/"


def data(response):
    assert not response.is_error
    payload = response.structured_content or json.loads(response.content[0].text)
    assert not payload.get("error"), payload
    return payload


async def test_mcp_current_skill_records_departments_and_selection():
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "decision_layer.mcp.server"],
        env={"DL_API_URL": API, "DL_LOCALE": "ko"},
    )
    metric, dimension, time = map(
        lambda name: PREFIX + name,
        ["transaction/receipts", "product/department", "transaction/analysis_date"],
    )
    goals = [
        {
            "id": "department",
            "description": "Compare department receipts",
            "semantic_refs": [metric, dimension],
        }
    ]
    run_id = None
    try:
        async with (
            stdio_client(server) as (read, write),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            methods = data(await client.call_tool("list_methods"))["methods"]
            assert {"analysis.metric_lookup", "analysis.drilldown"} <= {
                m["name"] for m in methods
            }
            question = "2001년 1월의 부문별 수취액을 조회해줘."
            candidates = data(
                await client.call_tool(
                    "find_recipes", {"question": question, "goals": goals}
                )
            )
            started = data(
                await client.call_tool(
                    "start_analysis",
                    {
                        "question": question,
                        "goals": goals,
                        "date_range": ["2001-01-01", "2001-01-31"],
                        "time_dimension": time,
                        "recipe_review": [
                            {
                                "recipe": r["recipe"],
                                "decision": "skipped",
                                "reason": "This test checks the current Skill directly.",
                            }
                            for r in candidates["candidates"]
                        ],
                    },
                )
            )
            run_id = started["run_id"]
            result = data(
                await client.call_tool(
                    "run_step",
                    {
                        "run_id": run_id,
                        "step_id": "departments",
                        "method": "analysis.drilldown",
                        "purpose": "Read department receipts",
                        "goal_ids": ["department"],
                        "bindings": {"metric": metric, "dimensions": [dimension]},
                    },
                )
            )
            assert result["status"] == "needs_input"
            query = data(
                await client.call_tool(
                    "run_skill_query",
                    {
                        "run_id": run_id,
                        "step_id": "departments",
                        "query_id": "groups",
                        "purpose": "Read governed department receipts",
                        "spec": {
                            "grain": "aggregate",
                            "measures": [metric],
                            "dimensions": [dimension],
                            "time": {
                                "dimension": time,
                                "date_range": ["2001-01-01", "2001-01-31"],
                            },
                            "order": [[metric, "desc"]],
                            "limit_rows": 1000,
                        },
                    },
                )
            )
            if query.get("status") == "running":
                data(await client.call_tool("wait_for_run", {"run_id": run_id}))
                query = data(
                    await client.call_tool(
                        "get_skill_query",
                        {
                            "run_id": run_id,
                            "step_id": "departments",
                            "query_id": "groups",
                        },
                    )
                )
            rows = query["result"]["primary"]["data"]
            assert rows[0][dimension] == "GROCERY"
            assert rows[0][metric] == pytest.approx(193074.59, abs=0.01)
            data(
                await client.call_tool(
                    "finish_skill_step",
                    {
                        "run_id": run_id,
                        "step_id": "departments",
                        "reason": "Compared recorded department values",
                        "selection": {
                            "query_id": "groups",
                            "row": 0,
                            "dimension": dimension,
                            "reason": "Largest returned receipts",
                        },
                    },
                )
            )
            data(
                await client.call_tool(
                    "complete_run",
                    {
                        "run_id": run_id,
                        "conclusion": {
                            "answer": "GROCERY has the highest returned January receipts.",
                            "findings": [
                                {
                                    "text": "Queried department receipts.",
                                    "step_indices": [0],
                                }
                            ],
                            "limitations": [
                                "Observed receipts do not establish profit or causality."
                            ],
                            "goal_outcomes": [
                                {
                                    "goal_id": "department",
                                    "status": "supported",
                                    "step_indices": [0],
                                }
                            ],
                        },
                    },
                )
            )
        async with httpx.AsyncClient(base_url=API) as api:
            response = await api.get(f"/runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            assert run["status"] == "completed" and len(run["query_attempts"]) == 1
            assert run["steps"][0]["step"]["method"] == "analysis.drilldown"
            assert run["steps"][0]["skill"]["guide"]["sha256"]
    finally:
        if run_id and os.environ.get("DL_KEEP_TEST_RUNS") != "true":
            async with httpx.AsyncClient(base_url=API) as api:
                assert (await api.delete(f"/runs/{run_id}")).status_code == 204

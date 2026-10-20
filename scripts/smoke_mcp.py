"""Check the installed stdio adapter, optionally against the isolated sales demo."""

import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def payload(result):
    assert not result.is_error, result
    value = result.structured_content or json.loads(result.content[0].text)
    assert not value.get("error"), value
    return value


async def verify_mcp(api_url=None, web_url=None):
    environment = {"DL_LOCALE": "ko"}
    if api_url:
        environment.update(DL_API_URL=api_url, DL_WEB_URL=web_url)
    server = StdioServerParameters(
        command=str(Path(sys.executable).parent / "decision-layer-mcp"),
        env=environment,
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert {
            "list_methods",
            "describe_method",
            "find_recipes",
            "start_run",
            "complete_run",
            "run_skill_query",
        } <= names
        if not api_url:
            print("PASS: installed MCP initialization and tool discovery.")
            return

        async def call(name, arguments=None):
            return payload(await client.call_tool(name, arguments or {}))

        methods = await call("list_methods")
        assert "analysis.drilldown" in {item["name"] for item in methods["methods"]}
        guide = await call("describe_method", {"name": "analysis.drilldown"})
        assert guide["agent_executable"] and guide["guide"]
        catalog = await call("search_semantic")
        metric = "cube://quickstart/sales/revenue"
        dimension = "cube://quickstart/sales/department"
        assert metric in {item["ref"] for item in catalog["objects"]}
        recipes = await call("list_recipes")
        recipe = next(item for item in recipes["recipes"] if item["available"])
        question = "2026년 2월 매출 1위 부문과 해당 부문의 지역별 매출을 알려줘."
        goals = [
            {
                "id": "department",
                "description": "Identify the highest-revenue department",
                "semantic_refs": [metric, dimension],
                "required_capabilities": ["group_breakdown"],
            },
            {
                "id": "regions",
                "description": "Read the leading department's regional revenue",
                "semantic_refs": [metric, dimension, "cube://quickstart/sales/region"],
                "required_capabilities": ["group_breakdown"],
            },
        ]
        await call("find_recipes", {"question": question, "goals": goals})
        run = await call(
            "start_run",
            {
                "recipe": recipe["name"],
                "question": question,
                "goals": goals,
                "date_range": ["2026-02-01", "2026-02-28"],
                "time_dimension": "cube://quickstart/sales/sold_at",
                "recipe_selection": {
                    "reason": "The sample procedure selects the current leading department and then its regions.",
                    "goal_ids": ["department", "regions"],
                },
            },
        )
        while run.get("status") == "running":
            run = await call("wait_for_run", {"run_id": run["run_id"]})
        assert len(run["steps"]) == 2, run
        first, second = [step["result"] for step in run["steps"]]
        assert first["status"] == second["status"] == "success", run
        leader = first["primary"]["data"]["rows"][0]
        assert leader["value"] == "Grocery" and leader["metric"] == 6720, leader
        assert second["primary"]["data"]["rows"][0]["metric"] == 4032
        completed = await call(
            "complete_run",
            {
                "run_id": run["run_id"],
                "conclusion": {
                    "answer": "2월 매출 1위 부문은 Grocery이며 매출은 6,720입니다. North 지역 매출은 4,032입니다.",
                    "findings": [
                        {
                            "text": "Grocery leads February revenue at 6,720.",
                            "step_indices": [0],
                        },
                        {
                            "text": "Its North region has revenue of 4,032.",
                            "step_indices": [1],
                        },
                    ],
                    "limitations": [
                        "Synthetic example data; this is a descriptive comparison."
                    ],
                    "goal_outcomes": [
                        {
                            "goal_id": "department",
                            "status": "supported",
                            "step_indices": [0],
                        },
                        {
                            "goal_id": "regions",
                            "status": "supported",
                            "step_indices": [1],
                        },
                    ],
                },
            },
        )
        assert completed["status"] == "completed", completed
        assert completed["question"] == question
        assert completed["run_url"] == web_url + "/runs/" + completed["run_id"]
        import httpx

        async with httpx.AsyncClient(base_url=api_url, trust_env=False) as api:
            stored = await api.get(f"/runs/{completed['run_id']}")
            stored.raise_for_status()
            assert stored.json()["status"] == "completed"
            assert all(
                step["result"]["provenance"]["queries"]
                for step in stored.json()["steps"]
            )
            response = await api.get(completed["run_url"])
            assert (
                response.status_code == 200
                and "text/html" in response.headers["content-type"]
            )
        # Exercise the current agent-guided Method too, not only the demo's pinned Recipe.
        question = "2026년 2월 부문별 매출을 조회해줘."
        goals = [
            {
                "id": "lookup",
                "description": "Read department revenue",
                "semantic_refs": [metric, dimension],
                "interpretation": "association",
            }
        ]
        candidates = await call("find_recipes", {"question": question, "goals": goals})
        exploration = await call(
            "start_analysis",
            {
                "question": question,
                "goals": goals,
                "date_range": ["2026-02-01", "2026-02-28"],
                "time_dimension": "cube://quickstart/sales/sold_at",
                "recipe_review": [
                    {
                        "recipe": item["recipe"],
                        "decision": "skipped",
                        "reason": "This query checks all departments directly; it does not investigate the leading department's regions.",
                    }
                    for item in candidates["candidates"]
                ],
            },
        )
        run_id = exploration["run_id"]
        await call(
            "run_step",
            {
                "run_id": run_id,
                "method": "analysis.drilldown",
                "step_id": "departments",
                "purpose": "Read February revenue for every department",
                "goal_ids": ["lookup"],
                "bindings": {"metric": metric},
            },
        )
        queried = await call(
            "run_skill_query",
            {
                "run_id": run_id,
                "step_id": "departments",
                "query_id": "revenues",
                "purpose": "Query the selected metric and department dimension for February",
                "spec": {
                    "grain": "aggregate",
                    "measures": [metric],
                    "dimensions": [dimension],
                    "time": {
                        "dimension": "cube://quickstart/sales/sold_at",
                        "date_range": ["2026-02-01", "2026-02-28"],
                    },
                    "order": [[metric, "desc"]],
                    "limit_rows": 100,
                },
            },
        )
        assert queried["status"] == "success", queried
        rows = queried["result"]["primary"]["data"]
        assert rows == [
            {dimension: "Grocery", metric: 6720.0},
            {dimension: "Home", metric: 2240.0},
        ], rows
        await call(
            "finish_skill_step",
            {
                "run_id": run_id,
                "step_id": "departments",
                "reason": "Recorded the requested department revenue rows.",
            },
        )
        stored = await call("get_run", {"run_id": run_id})
        assert stored["steps"][0]["skill"]["queries"][0]["status"] == "success"
        print(
            "PASS: current Skill Method, governed Cube query and persisted MCP query evidence."
        )
        print(
            "PASS: installed MCP discovery, live Cube analysis, conclusion, stored evidence and Web link."
        )


if __name__ == "__main__":
    asyncio.run(verify_mcp(*sys.argv[1:]))

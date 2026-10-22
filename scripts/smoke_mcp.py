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
        assert "find_methods" not in names
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
        if any(
            item["ref"].startswith("cube://journey/") for item in catalog["objects"]
        ):
            await verify_journey(call, api_url, web_url)
            return
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


async def verify_journey(call, api_url, web_url):
    """Reuse the current two-Skill Recipe through actual stdio MCP calls."""
    from decision_layer.demo.replay import METRIC, DEPARTMENT, STORE, DATE

    recipes = await call("list_recipes")
    recipe = next(item for item in recipes["recipes"] if item["available"])
    run = await call(
        "start_run",
        {
            "recipe": recipe["name"],
            "question": "Inspect department and store receipts on the example calendar in February 2001.",
            "goals": [
                {
                    "id": "departments",
                    "description": "Find the leading department",
                    "semantic_refs": [METRIC, DEPARTMENT],
                },
                {
                    "id": "stores",
                    "description": "Read stores within the selected department",
                    "semantic_refs": [METRIC, STORE],
                },
            ],
            "date_range": ["2001-02-01", "2001-02-28"],
            "time_dimension": DATE,
            "recipe_selection": {
                "reason": "Reuse the demonstrated department-to-store investigation.",
                "goal_ids": ["departments", "stores"],
            },
        },
    )
    run_id = run["run_id"]
    for step_id, dimension, expected_value, amount in [
        ("departments", DEPARTMENT, "GROCERY", 178255.38),
        ("stores", STORE, "367", 4411.16),
    ]:
        run = await call("get_run", {"run_id": run_id})
        assert run["active_skill_step"] == step_id, run
        step = next(s for s in run["steps"] if s["id"] == step_id)
        query = await call(
            "run_skill_query",
            {
                "run_id": run_id,
                "step_id": step_id,
                "query_id": "groups",
                "purpose": "Read actual receipts by the selected grouping",
                "spec": {
                    "grain": "aggregate",
                    "measures": [METRIC],
                    "dimensions": [dimension],
                    "filters": step["params"].get("filters", []),
                    "time": {
                        "dimension": DATE,
                        "date_range": ["2001-02-01", "2001-02-28"],
                    },
                    "order": [[METRIC, "desc"], [dimension, "asc"]],
                    "limit_rows": 1000,
                },
            },
        )
        while query.get("status") == "running":
            await call("wait_for_run", {"run_id": run_id})
            query = await call(
                "get_skill_query",
                {"run_id": run_id, "step_id": step_id, "query_id": "groups"},
            )
        assert query["status"] == "success", query
        row = query["result"]["primary"]["data"][0]
        assert (
            row[dimension] == expected_value
            and abs(float(row[METRIC]) - amount) < 0.005
        )
        args = {
            "run_id": run_id,
            "step_id": step_id,
            "reason": "Reviewed the recorded query rows.",
        }
        if step_id == "departments":
            args["selection"] = {
                "query_id": "groups",
                "row": 0,
                "dimension": dimension,
                "reason": "The returned department has the highest receipts.",
            }
        await call("finish_skill_step", args)
    stored = await call(
        "complete_run",
        {
            "run_id": run_id,
            "conclusion": {
                "answer": "GROCERY leads February receipts at 178,255.38; store 367 leads within it at 4,411.16.",
                "findings": [
                    {
                        "text": "GROCERY has the highest returned department receipts.",
                        "step_indices": [0],
                    },
                    {
                        "text": "Store 367 leads within the selected department.",
                        "step_indices": [1],
                    },
                ],
                "limitations": [
                    "Artificial example calendar; descriptive receipts, not causal effects or profit."
                ],
                "goal_outcomes": [
                    {
                        "goal_id": "departments",
                        "status": "supported",
                        "step_indices": [0],
                    },
                    {"goal_id": "stores", "status": "supported", "step_indices": [1]},
                ],
            },
        },
    )
    assert stored["status"] == "completed", stored
    assert stored["run_url"] == web_url + "/runs/" + run_id
    import httpx

    async with httpx.AsyncClient(base_url=api_url, trust_env=False) as api:
        response = await api.get(f"/runs/{run_id}")
        response.raise_for_status()
        run = response.json()
        assert all(s["result"]["provenance"]["queries"] for s in run["steps"])
        assert run["steps"][1]["step"]["params"]["filters"][0]["values"] == ["GROCERY"]
        response = await api.get(stored["run_url"])
        assert (
            response.status_code == 200
            and "text/html" in response.headers["content-type"]
        )
    print(
        "PASS: installed MCP, Complete Journey, current Skill Recipe replay, recorded selection filters and Web link."
    )


if __name__ == "__main__":
    asyncio.run(verify_mcp(*sys.argv[1:]))

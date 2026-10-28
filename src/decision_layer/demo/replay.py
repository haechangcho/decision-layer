"""Run the editable Skills on Complete Journey through the canonical REST API.

A scripted client drives the same recorded query/finish calls as an MCP client.
This does not test AI planning quality.
"""

from __future__ import annotations

from .client import request, settled

BASE = "cube://journey/"
METRIC = BASE + "transaction/receipts"
DEPARTMENT = BASE + "product/department"
STORE = BASE + "transaction/store"
DATE = BASE + "transaction/analysis_date"
FILTERS = "$steps.departments.selections.selected_group.evidence.filters"
PERIODS = {
    "january": (["2001-01-01", "2001-01-31"], 193074.59, "367", 5165.34),
    "february": (["2001-02-01", "2001-02-28"], 178255.38, "367", 4411.16),
}


def read_groups(client, run, step_id, dimension, *, metric=METRIC, time_dimension=DATE):
    record = next(step for step in run["steps"] if step["step"]["id"] == step_id)
    scope = run["plan"]["scope"]
    query = request(
        client,
        "POST",
        f"/runs/{run['id']}/steps/{step_id}/queries?wait=60",
        json={
            "id": "groups",
            "purpose": "Read the selected metric by observed group",
            "spec": {
                "grain": "aggregate",
                "measures": [metric],
                "dimensions": [dimension],
                "time": {"dimension": time_dimension, "date_range": scope["date_range"]},
                "filters": record["step"]["params"].get("filters", []),
                "order": [[metric, "desc"], [dimension, "asc"]],
                "limit_rows": 1000,
            },
            "author": {"client_name": "decision-layer-demo"},
        },
    )
    if query.get("status") != "success":
        # Long-running queries return a Run with HTTP 202. Read its recorded query.
        run = settled(client, run["id"])
        record = next(step for step in run["steps"] if step["step"]["id"] == step_id)
        query = record["skill"]["queries"][-1]
    if query["status"] != "success":
        raise RuntimeError(f"Sample query failed: {query.get('error')}")
    rows = query["result"]["primary"]["data"]
    if not rows or len(rows) >= 1000:
        raise RuntimeError("The sample needs a complete, nonempty group ranking.")
    return rows


def finish_groups(client, run, step_id, dimension, rows, *, select=False, metric=METRIC):
    body = {"reason": "Read all returned groups from the recorded Cube query."}
    if select:
        if len(rows) > 1 and float(rows[0][metric]) == float(rows[1][metric]):
            raise RuntimeError("Sample leaders tie; an explicit selection is required.")
        body["selection"] = {
            "query_id": "groups",
            "row": 0,
            "dimension": dimension,
            "reason": "Unique highest retailer receipts among the complete returned groups.",
        }
    request(
        client, "POST", f"/runs/{run['id']}/steps/{step_id}:finish?wait=60", json=body
    )
    return settled(client, run["id"])


def complete(client, run):
    return request(
        client,
        "POST",
        f"/runs/{run['id']}:complete",
        json={
            "conclusion": {
                "source": "execution",
                "answer": "GROCERY has the highest retailer receipts; store 367 leads within that department for this period.",
                "findings": [
                    {
                        "text": "Compared department receipts using the registered drilldown Skill.",
                        "step_indices": [0],
                    },
                    {
                        "text": "Queried stores within the department selected from this Run's results.",
                        "step_indices": [1],
                    },
                ],
                "limitations": [
                    "Source DAY values use an artificial calendar starting at 2000-01-01; these are not actual purchase dates.",
                    "Retailer receipts are not profit. Observed rankings do not establish causes.",
                    "This walkthrough uses a scripted client, not AI-generated analysis.",
                ],
            }
        },
    )


def check_run(run, department_amount, store, store_amount):
    assert run["status"] == "completed", run
    assert len(run["steps"]) == 2
    a, b = run["steps"]
    assert a["step"]["method"] == b["step"]["method"] == "analysis.drilldown"
    assert a["result"]["status"] == b["result"]["status"] == "success"
    first = a["result"]["primary"]["data"][0]
    second = b["result"]["primary"]["data"][0]
    assert (
        first[DEPARTMENT] == "GROCERY"
        and abs(float(first[METRIC]) - department_amount) < 0.005
    )
    assert second[STORE] == store and abs(float(second[METRIC]) - store_amount) < 0.005
    assert b["step"]["params"]["filters"] == [
        {"member": DEPARTMENT, "operator": "equals", "values": ["GROCERY"]}
    ]
    assert b["requested_step"]["params"]["filters"] == FILTERS
    assert a["skill"]["guide"]["sha256"] and b["skill"]["guide"]["sha256"]
    assert a["result"]["provenance"]["queries"] and b["result"]["provenance"]["queries"]


def walkthrough(client, emit=print):
    dates, *expected = PERIODS["january"]
    first = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "question": "Which department has the highest retailer receipts, and which stores lead within it?",
            "scope": {"date_range": dates, "time_dimension": DATE},
        },
    )
    for step_id, dimension, params in [
        ("departments", DEPARTMENT, {}),
        ("stores", STORE, {"filters": FILTERS}),
    ]:
        request(
            client,
            "POST",
            f"/runs/{first['id']}/steps?wait=60",
            json={
                "id": step_id,
                "method": "analysis.drilldown",
                "purpose": "Compare departments"
                if step_id == "departments"
                else "Inspect stores in the selected department",
                "bindings": {"metric": METRIC, "dimensions": [dimension]},
                "params": params,
            },
        )
        first = settled(client, first["id"])
        rows = read_groups(client, first, step_id, dimension)
        first = finish_groups(
            client, first, step_id, dimension, rows, select=step_id == "departments"
        )
    first = complete(client, first)
    check_run(first, *expected)
    emit("JANUARY  GROCERY receipts: 193,074.59. Its leading store is 367 (5,165.34).")
    recipe = request(client, "POST", f"/runs/{first['id']}/recipe", json={})
    assert recipe["status"] == "draft" and recipe.get("source_question") is None
    recipe = request(
        client,
        "POST",
        f"/recipes/{recipe['name']}/publish",
        json={"base_version": recipe["version"]},
    )
    assert recipe["steps"][1]["params"]["filters"] == FILTERS
    emit(
        "SAVED    A Recipe that selects a department from each Run's own query results."
    )
    dates, *expected = PERIODS["february"]
    second = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "recipe": recipe["name"],
            "question": "Reuse the department investigation for February.",
            "scope": {"date_range": dates, "time_dimension": DATE},
        },
    )
    for step_id, dimension in [("departments", DEPARTMENT), ("stores", STORE)]:
        second = settled(client, second["id"])
        assert second["active_skill_step"] == step_id
        rows = read_groups(client, second, step_id, dimension)
        second = finish_groups(
            client, second, step_id, dimension, rows, select=step_id == "departments"
        )
    # Recipe execution may already complete the Run after its final Skill.
    if second["status"] != "completed":
        second = complete(client, second)
    check_run(second, *expected)
    assert request(client, "GET", f"/runs/{first['id']}")["steps"] == first["steps"]
    emit("FEBRUARY GROCERY receipts: 178,255.38. Fresh store query: 367 (4,411.16).")
    return {"january": first, "recipe": recipe, "february": second}

"""Exercise the public REST API against the synthetic Cube sample; no LLM required.

This is an executable product walkthrough, not an AI quality benchmark.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import httpx

from .client import request, settled

BASE = "cube://quickstart/sales/"
METRIC, DEPARTMENT, REGION, DATE = [
    BASE + x for x in ("revenue", "department", "region", "sold_at")
]
RULE = {
    "source": "step",
    "step_id": "departments",
    "output": "ranked_groups",
    "select": "first",
    "project": "path",
}


def complete(client, run):
    rows = run["steps"][0]["result"]["primary"]["data"]["rows"]
    winner = rows[0]["value"]
    return request(
        client,
        "POST",
        f"/runs/{run['id']}:complete",
        json={
            "conclusion": {
                "source": "execution",
                "answer": f"{winner} has the highest revenue in this sample period. The next step inspects its regions.",
                "findings": [
                    {
                        "text": f"{winner} leads with {rows[0]['metric']:,.0f} example currency units.",
                        "step_indices": [0],
                    },
                    {
                        "text": "The regional breakdown uses the selected department from this run.",
                        "step_indices": [1],
                    },
                ],
                "limitations": [
                    "Synthetic tutorial data; descriptive ranking does not establish causes.",
                    "The source does not declare a sample count for revenue; inspect the recorded warnings.",
                ],
            }
        },
    )


def walkthrough(client, emit=print):
    def scope(dates):
        return {"date_range": dates, "time_dimension": DATE}

    first = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "question": "Which department leads revenue in January, and how is its revenue split by region?",
            "scope": scope(["2026-01-01", "2026-01-31"]),
        },
    )
    for step_id, params, purpose in [
        ("departments", {}, "Find the highest-revenue department in this period"),
        (
            "regions",
            {"drill_path": RULE},
            "Inspect the regions of the department selected above",
        ),
    ]:
        request(
            client,
            "POST",
            f"/runs/{first['id']}/steps?wait=60",
            json={
                "id": step_id,
                "method": "query.drilldown",
                "purpose": purpose,
                "bindings": {"metric": METRIC, "dimensions": [DEPARTMENT, REGION]},
                "params": params,
            },
        )
        settled(client, first["id"])
    first = complete(client, settled(client, first["id"]))
    check_run(first, "Home", 6200, 3720)
    emit("JANUARY  Home leads: 6,200. Its North region contributes 3,720.")
    recipe = request(client, "POST", f"/runs/{first['id']}/recipe", json={})
    assert recipe["status"] == "draft"
    assert recipe.get("source_question") is None
    recipe = request(
        client,
        "POST",
        f"/recipes/{recipe['name']}/publish",
        json={"base_version": recipe["version"]},
    )
    assert recipe["steps"][1]["params"]["drill_path"] == RULE
    assert not recipe.get("default_scope", {}).get("date_range")
    emit("SAVED    A Recipe that selects the current leader, not the word Home.")
    second = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "recipe": recipe["name"],
            "question": "Reuse the reviewed department investigation for February.",
            "scope": scope(["2026-02-01", "2026-02-28"]),
        },
    )
    second = complete(client, settled(client, second["id"]))
    check_run(second, "Grocery", 6720, 4032)
    emit("FEBRUARY Grocery now leads: 6,720. Its North region contributes 4,032.")
    # A third month has equal leaders. The same rule must not invent a winner.
    tied = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "recipe": recipe["name"],
            "question": "Reuse the procedure for March, where leaders tie.",
            "scope": scope(["2026-03-01", "2026-03-31"]),
        },
    )
    tied = settled(client, tied["id"])
    assert tied["status"] == "open"
    assert tied["steps"][-1]["result"]["status"] == "needs_input"
    assert not tied["steps"][-1]["result"]["provenance"]["queries"]
    # The January evidence remains unchanged after both replays.
    assert request(client, "GET", f"/runs/{first['id']}")["steps"] == first["steps"]
    emit("MARCH    Tie: asks for a selection before querying a regional branch.")
    return {"january": first, "recipe": recipe, "february": second, "march": tied}


def check_run(run, department, amount, north):
    assert run["status"] == "completed", run
    assert len(run["steps"]) == 2
    a, b = run["steps"]
    assert a["result"]["status"] == b["result"]["status"] == "success"
    assert a["result"]["primary"]["data"]["rows"][0]["value"] == department
    assert a["result"]["primary"]["data"]["rows"][0]["metric"] == amount
    assert b["step"]["params"]["drill_path"] == [
        {"member": DEPARTMENT, "value": department}
    ]
    assert b["requested_step"]["params"]["drill_path"] == RULE
    assert b["result"]["primary"]["data"]["rows"][0]["metric"] == north
    assert a["result"]["provenance"]["queries"] and b["result"]["provenance"]["queries"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--web", default="http://localhost:3100")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the complete synthetic execution evidence as JSON",
    )
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, timeout=150) as client:
        evidence = walkthrough(client)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    for month in ("january", "february", "march"):
        print(f"{month.title():9} {args.web}/runs/{evidence[month]['id']}")
    print(
        "PASS: live Cube queries, saved Recipe, fresh selection, tie handling, immutable prior steps."
    )
    print(
        "Scripted REST walkthrough; no model comparison or multi-user authorization test was performed."
    )


if __name__ == "__main__":
    main()

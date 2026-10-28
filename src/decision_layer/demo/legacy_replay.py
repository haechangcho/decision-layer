"""Run current query Skills against an existing synthetic demo dataset."""

import argparse
import json
from pathlib import Path
import httpx
from .client import request, settled
from .replay import read_groups, finish_groups

BASE = "cube://quickstart/sales/"
METRIC, DEPARTMENT, REGION, DATE = [
    BASE + name for name in ("revenue", "department", "region", "sold_at")
]
RULE = "$steps.departments.selections.selected_group.evidence.filters"


def complete(client, run):
    if run["status"] == "completed":
        return run
    return request(
        client,
        "POST",
        f"/runs/{run['id']}:complete",
        json={
            "summary": "Compared recorded department and regional values. Synthetic data; no causal claim."
        },
    )


def check_run(run, department, amount, north):
    assert run["status"] == "completed", run
    a, b = run["steps"]
    assert a["result"]["primary"]["data"][0][DEPARTMENT] == department
    assert a["result"]["primary"]["data"][0][METRIC] == amount
    assert b["result"]["primary"]["data"][0][METRIC] == north
    assert b["step"]["params"]["filters"] == [
        {"member": DEPARTMENT, "operator": "equals", "values": [department]}
    ]
    assert all(record["skill"] for record in run["steps"])


def walkthrough(client, emit=print):
    first = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "question": "Which department leads, and which regions lead within it?",
            "scope": {
                "date_range": ["2026-01-01", "2026-01-31"],
                "time_dimension": DATE,
            },
        },
    )
    for step_id, dimension, params in [
        ("departments", DEPARTMENT, {}),
        ("regions", REGION, {"filters": RULE}),
    ]:
        request(
            client,
            "POST",
            f"/runs/{first['id']}/steps?wait=60",
            json={
                "id": step_id,
                "method": "analysis.drilldown",
                "purpose": "Inspect the observed groups",
                "bindings": {"metric": METRIC, "dimensions": [dimension]},
                "params": params,
            },
        )
        first = settled(client, first["id"])
        rows = read_groups(
            client, first, step_id, dimension, metric=METRIC, time_dimension=DATE
        )
        first = finish_groups(
            client,
            first,
            step_id,
            dimension,
            rows,
            select=step_id == "departments",
            metric=METRIC,
        )
    first = complete(client, first)
    check_run(first, "Home", 6200, 3720)
    draft = request(client, "POST", f"/runs/{first['id']}/recipe", json={})
    recipe = request(
        client,
        "POST",
        f"/recipes/{draft['name']}/publish",
        json={"base_version": draft["version"]},
    )
    assert recipe["steps"][1]["params"]["filters"] == RULE
    second = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "recipe": recipe["name"],
            "question": "Repeat for February",
            "scope": {
                "date_range": ["2026-02-01", "2026-02-28"],
                "time_dimension": DATE,
            },
        },
    )
    for step_id, dimension in [("departments", DEPARTMENT), ("regions", REGION)]:
        rows = read_groups(
            client, second, step_id, dimension, metric=METRIC, time_dimension=DATE
        )
        second = finish_groups(
            client,
            second,
            step_id,
            dimension,
            rows,
            select=step_id == "departments",
            metric=METRIC,
        )
    second = complete(client, second)
    check_run(second, "Grocery", 6720, 4032)
    tied = request(
        client,
        "POST",
        "/runs?wait=60",
        json={
            "recipe": recipe["name"],
            "question": "Inspect March with tied leaders",
            "scope": {
                "date_range": ["2026-03-01", "2026-03-31"],
                "time_dimension": DATE,
            },
        },
    )
    rows = read_groups(
        client, tied, "departments", DEPARTMENT, metric=METRIC, time_dimension=DATE
    )
    assert len(rows) > 1 and rows[0][METRIC] == rows[1][METRIC]
    tied = settled(client, tied["id"])
    assert tied["status"] == "open" and tied["active_skill_step"] == "departments"
    assert request(client, "GET", f"/runs/{first['id']}")["steps"] == first["steps"]
    emit(
        "PASS: current Skills, saved Recipe, fresh queries and a tie awaiting explicit selection."
    )
    return {"january": first, "recipe": recipe, "february": second, "march": tied}


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

"""Bounded MCP views of stored evidence; never mutate or re-query the original."""

from __future__ import annotations
from copy import deepcopy
from typing import Any
from ..env import env
from ..i18n import _


def _running(run_id: str, running: Any) -> dict:
    return {
        "run_id": run_id,
        "status": "running",
        "running": running,
        "next": _("Still computing. Wait for the result with wait_for_run(run_id)."),
    }


def _running_or(body: Any, compact) -> Any:
    """202 bodies (still running) become a 'running' notice; anything else is compacted as usual."""
    if (
        isinstance(body, dict)
        and body.get("running")
        and (body.get("status") == "running" or "steps" in body)
    ):
        return _running(body.get("run_id") or body.get("id"), body["running"])
    return compact(body)


def _compact_result(result: Any) -> Any:
    result = deepcopy(result)
    if isinstance(result, dict):
        result["selections"] = {
            name: {
                **output,
                "candidate_count": len(output.get("candidates", [])),
                "candidates": output.get("candidates", [])[:3],
            }
            for name, output in result.get("selections", {}).items()
        }
        if result.get("step_id") and result.get("selections"):
            result["selection_sources"] = {
                name: {
                    project: {
                        "source": "step",
                        "step_id": result["step_id"],
                        "output": name,
                        "select": "first",
                        "project": project,
                    }
                    for project in ("path", "condition", "parents")
                }
                for name in result["selections"]
            }
    prov = result.get("provenance") if isinstance(result, dict) else None
    if prov:  # native queries are for audit, not for the model: keep a summary
        result["provenance"] = {
            "method": prov.get("method"),
            "semantic_refs": prov.get("semantic_refs"),
            "queries": len(prov.get("queries") or []),
            "rows_read": sum(q.get("rows", 0) for q in prov.get("queries") or []),
        }
    return result


def _compact_skill(skill: dict | None) -> dict | None:
    if not skill:
        return None
    out = {
        key: deepcopy(skill.get(key))
        for key in ("status", "completion_reason", "completed_by")
    }
    active = skill.get("status") == "awaiting_agent"
    out["guide"] = {
        key: value
        for key, value in skill["guide"].items()
        if key != "markdown" or active
    }
    if active:
        out["manifest"] = deepcopy(skill["manifest"])
    out["queries"] = [
        {
            key: deepcopy(query.get(key))
            for key in (
                "id",
                "purpose",
                "status",
                "error",
                "author",
                "started_at",
                "finished_at",
            )
        }
        | {
            "rows": len(
                (query.get("result") or {}).get("primary", {}).get("data") or []
            )
        }
        for query in skill.get("queries", [])
    ]
    out["query_detail_tool"] = "get_skill_query"
    return out


def _skill_result_summary(result: dict) -> dict:
    out = _compact_result(result)
    # Each query already has its own result. Avoid resending every table in each Run response.
    out["artifacts"] = []
    if isinstance((out.get("primary") or {}).get("data"), list):
        rows = out["primary"]["data"]
        out["primary"]["data"] = []
        out["primary_preview"] = {
            "returned": 0,
            "total": len(rows),
            "detail_tool": "get_skill_query",
            "note": "Read original query rows before selecting; selection row indices are per query, not this combined preview.",
        }
    if isinstance(out.get("needs_input"), dict):
        out["needs_input"].pop(
            "guide", None
        )  # Active frozen guide is included once under step.skill.
    return out


def _skill_query_page(query: dict, offset: int = 0, limit: int = 25) -> dict:
    out = deepcopy(query)
    if out.get("result"):
        out["result"] = _compact_result(out["result"])
        out["result"]["artifacts"] = []
        primary = out["result"].get("primary") or {}
        rows = primary.get("data")
        if isinstance(rows, list):
            total = len(rows)
            primary["data"] = rows[offset : offset + limit]
            out["page"] = {
                "offset": offset,
                "limit": limit,
                "total_rows": total,
                "next_offset": offset + limit if offset + limit < total else None,
                "selection_row_indices": "absolute query row index = page.offset + row index within this page",
            }
    out["detail_tool"] = "get_skill_query"
    return out


def _compact_run(run: dict) -> dict:
    if "id" not in run:
        return run
    recipe = run.get("recipe_snapshot") or {}
    queries = sum(
        s["result"]["provenance"].get("queries", 0)
        if isinstance(s["result"]["provenance"].get("queries"), int)
        else len(s["result"]["provenance"].get("queries") or [])
        for s in run["steps"]
    )
    queries += len(run.get("validation_queries") or [])
    queries = max(
        queries,
        (run.get("query_attempt_baseline") or 0) + len(run.get("query_attempts") or []),
    )
    out = {
        "run_id": run["id"],
        "status": run["status"],
        "recipe": run["plan"].get("recipe"),
        "run_url": env("DL_WEB_URL", "http://localhost:3000").rstrip("/")
        + "/runs/"
        + run["id"],
        "owner": run["caller"].get("subject"),
        "shared_with": run.get("shared_with") or [],
        "question": run["plan"].get("question"),
        "scope": run["plan"].get("scope"),
        "validation": run.get("validation"),
        "summary": run.get("summary"),
        "error": run.get("error"),
        "conclusion": run.get("conclusion"),
        "author": run.get("author"),
        "conclusion_author": run.get("conclusion_author"),
        "needs_input": run.get("needs_input"),
        "scope_revision": run.get("scope_revision", 0),
        "scope_resolution": run.get("scope_resolution"),
        "goals": run.get("goals", []),
        "recipe_selection": run.get("recipe_selection"),
        "remediations": run.get("remediations", []),
        "retry_of": run.get("retry_of"),
        "recipe_review": run.get("recipe_review", []),
        "recipe_invocation": run.get("recipe_invocation"),
        "method_guides": run.get("method_guides", []),
        "steps": [
            {
                "id": s["step"].get("id"),
                "purpose": s["step"].get("purpose"),
                "purpose_context": s["step"].get("purpose_context")
                or ("source_run" if recipe.get("origin_runs") else "procedure"),
                "skill": _compact_skill(s.get("skill")),
                "method": s["step"]["method"],
                "bindings": s["step"]["bindings"],
                "params": s["step"]["params"],
                "requested_step": s.get("requested_step"),
                "input_resolutions": s.get("input_resolutions", []),
                "invocation_id": s.get("invocation_id"),
                "goal_ids": s["step"].get("goal_ids", []),
                "author": s.get("author"),
                "result": _skill_result_summary(s["result"])
                if s.get("skill")
                else _compact_result(s["result"]),
            }
            for s in run["steps"]
        ],
    }
    for step in out["steps"]:
        if step.get("skill"):
            step.pop("requested_step", None)
            step.pop("input_resolutions", None)
    out["active_skill_step"] = run.get("active_skill_step")
    if run.get("active_skill_step") and not run.get("running"):
        out["next"] = {
            "tools": ["run_skill_query", "finish_skill_step"],
            "run_id": run["id"],
            "step_id": run["active_skill_step"],
            "note": "The agent must read the step Skill and execute queries; this is not a request for the user to operate tools.",
        }
    elif run.get("needs_input"):
        out["next"] = {
            "tool": "set_run_scope",
            "run_id": run["id"],
            "base_revision": run.get("scope_revision", 0),
        }
    elif run.get("running"):
        out["next"] = {"tool": "wait_for_run", "run_id": run["id"]}
    elif run["status"] == "open":
        out["next"] = {
            "tools": ["run_step", "complete_run"] if run["steps"] else ["run_step"],
            "run_id": run["id"],
        }
    if recipe:
        out["scope_note"] = (
            "The current scope defines the execution period. source_run purposes are original descriptions, not current period settings."
        )
        limits = recipe.get("limits") or {}
        out["recipe_guide"] = {
            "mode": recipe["mode"],
            "instructions": recipe.get("instructions"),
            "allowed_methods": recipe.get("allowed_methods")
            or sorted({s["method"] for s in recipe.get("steps") or []}),
            "semantic_scope": recipe["semantic_scope"],
            "steps_left": limits.get("max_steps", 12) - len(run["steps"]),
            "queries_left": limits.get("max_queries", 30) - queries,
        }
    return out

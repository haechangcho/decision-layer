"""Thin MCP server: exposes the Decision Layer REST API to MCP clients (Claude Desktop / Code).

It holds no analysis logic. Every number comes from a registered Method run on the
Decision Layer server, so the client model chooses *what* to run, never *how* to compute.

    DL_API_URL    Decision Layer API base (default http://localhost:5200)
    DL_TOKEN  optional bearer passed through to the selected semantic provider; without it the
                     server uses its service credentials (local/dev only)
    DL_LOCALE language of instructions, tool descriptions and API messages (default en)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import Context, MCPServer

from ..core.models import (
    AnalysisGoal,
    ExecutionAuthor,
    Recipe,
    RecipeReview,
    RecipeSelection,
    RunConclusion,
)
from ..core.periods import PeriodChoice
from ..service import (
    BlockedAnalysisRequest,
    RemediationCreateRequest,
    RemediationRetryRequest,
)

from .presentation import (
    _running,
    _running_or,
    _compact_result,
    _compact_skill,
    _skill_result_summary,
    _skill_query_page,
    _compact_run,
)

from ..env import env
from ..i18n import _, negotiate, set_locale

# the MCP server speaks one language per process: DL_LOCALE (e.g. ko), default en
LOCALE = negotiate(env("DL_LOCALE"))
set_locale(LOCALE)

from .instructions import DOCS, SECTIONS

# Deployment / experiment knobs (ADR-032):
#   DL_MCP_METHODS   comma list of Methods to expose (default: all)
#   DL_MCP_RECIPES   "off" hides Recipe tools, retaining question-scoped analysis
#   DL_MCP_RULES     "relaxed" (default, ADR-032): simple arithmetic allowed, judgements only from results;
#                           "strict": numbers only as returned
METHODS = {m.strip() for m in env("DL_MCP_METHODS", "").split(",") if m.strip()}
RECIPES = env("DL_MCP_RECIPES", "on").lower() != "off"
RULES = env("DL_MCP_RULES", "relaxed").lower()


def allowed(method: str) -> bool:
    return not METHODS or method in METHODS


def instructions() -> str:
    rules = (
        _(SECTIONS["rules"])
        + "\n"
        + _(SECTIONS["periods"])
        + "\n"
        + _(SECTIONS["numbers_strict" if RULES == "strict" else "numbers_relaxed"])
    )
    parts = [
        _(SECTIONS["intro"]),
        _(
            "Start one Run with the original question. Execute every Method with run_step on that run_id, supplying a purpose. Finish with complete_run and evidence-linked findings. Even a single Method needs a Run."
        ),
        *(
            [_(SECTIONS["proceed"]), _(SECTIONS["routing"]), _(SECTIONS["reuse"])]
            if RECIPES
            else []
        ),
        _(SECTIONS["record_question"]),
        _(SECTIONS["conclude"]),
        _(SECTIONS["attribution"]),
        rules,
        _(SECTIONS["method_selection"]),
    ]
    if not RECIPES:
        parts.append(
            _(
                "Recipe execution is disabled in this client profile. Use find_recipes to review candidates and record skipped recipe_review reasons before starting with registered Methods."
            )
        )
    parts.append(
        _(
            "Recording is automatic, not a user task. Before replying that an analysis cannot proceed, call report_analysis_blocked with the original question, all goals, classified outcomes and the inspected evidence. For semantic_missing include proposed requirements with unknown refs unset. If a Run already exists, finish that Run rather than starting another. Do not ask whether to record, mention internal tool names as instructions for the user, substitute a different business question, or request approval for private execution records. Return the recorded Run link with the plain-language reason. Model changes and proposal approval still require owner review. Do not claim a record was saved if the tool failed. Discovery-only catalog browsing is not an analysis question."
        )
    )
    parts.append(
        "For semantic improvements, combine goals blocked by the same missing definition in one proposal using related_goal_ids. Keep distinct definitions separate. Provide concise actions and optional model_drafts derived only from inspected APIs, with placeholders and unresolved details for unknown physical schema. Never use local project files as evidence of API-visible definitions or claim that a proposed YAML is verified or applied."
    )
    parts.append(
        "Skill Method query stages are agent-executed. Start them with run_step, or start a Recipe that pauses at its first Skill. When needs_input.reason_code is AGENT_EXECUTION_REQUIRED, read its core_guide (shared execution protocol) and guide (analysis procedure), and use run_skill_query then finish_skill_step; do not ask the user to execute tools. get_run includes the active Skill, bound inputs and per-query logs. Finish resumes the next Recipe step automatically, including Python calculations. Never start another step while a Skill is active. Export observed selections by query_id/row/dimension; preserve selected_group.evidence.filters for subsequent populations. Reading prose is not validation; only actual query checks are verified. get_method_guide provides authoring, cube-query and analysis-core references. Use list_methods for the installed Methods; removed names and versions cannot be executed."
    )
    return "\n\n".join(parts)


INSTRUCTIONS = instructions()
mcp = MCPServer(name="decision-layer", instructions=INSTRUCTIONS)
WAIT_SECONDS = 45  # per call; longer analyses continue with wait_for_run
logging.getLogger("httpx").setLevel(logging.WARNING)


def _client() -> httpx.AsyncClient:
    headers = {"Accept-Language": LOCALE, "X-Decision-Layer-Client": "mcp"}
    if token := env("DL_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        base_url=env("DL_API_URL", "http://localhost:5200"),
        headers=headers,
        timeout=120,
    )


async def _call(method: str, path: str, **kwargs: Any) -> Any:
    async with _client() as c:
        r = await c.request(method, path, **kwargs)
    body = r.json()
    if r.status_code >= 400:
        return (
            body
            if isinstance(body, dict) and "error" in body
            else {"error": {"status": r.status_code, "body": body}}
        )
    return body


@mcp.tool(description=_(DOCS["get_semantic_catalog"]))
async def get_semantic_catalog() -> dict:
    return await _call("GET", "/semantic/catalog")


@mcp.tool(description=_(DOCS["list_methods"]))
async def list_methods() -> dict:
    ms = await _call("GET", "/methods")
    if isinstance(ms, dict):
        return ms
    return {
        "methods": [
            {
                "name": m["name"],
                "description": m["description"],
                "interpretation": m["interpretation"],
                "provides": m.get("provides", []),
                "implementation": m.get("implementation", "python"),
                "roles": {
                    k: r["kind"] + ("[]" if r["multiple"] else "")
                    for k, r in m["roles"].items()
                },
            }
            for m in ms
            if allowed(m["name"])
        ]
    }


@mcp.tool(description=_(DOCS["describe_method"]))
async def describe_method(name: str) -> dict:
    if not allowed(name):
        return _not_exposed(name)
    manifest = await _call("GET", f"/methods/{name}")
    if manifest.get("implementation") == "skill":
        manifest["guide"] = await _call("GET", f"/methods/{name}/guide")
    return manifest


@mcp.tool(
    description="Read a version-matched advisory guide: authoring, cube-query or analysis-core. It never grants permissions or counts as executed validation."
)
async def get_method_guide(name: str) -> dict:
    return await _call("GET", f"/method-guides/{name}")


def _not_exposed(name: str) -> dict:
    return {
        "error": {
            "code": "METHOD_NOT_EXPOSED",
            "message": _("Method {name} is not available here", name=name),
        }
    }


@mcp.tool(
    description=_(
        "Find Recipe candidates for a question and typed goals. Structural matches do not verify natural-language relevance. No suitable Recipe is a valid outcome."
    )
)
async def find_recipes(
    question: str,
    goals: list[AnalysisGoal] | None = None,
    inputs: dict[str, Any] | None = None,
    limit: int = 5,
) -> dict:
    return await _call(
        "POST",
        "/recipes:search",
        json={
            "question": question,
            "goals": [goal.model_dump(mode="json") for goal in goals or []],
            "inputs": inputs or {},
            "limit": limit,
        },
    )


@mcp.tool(description=_(DOCS["list_recipes"]))
async def list_recipes() -> dict:
    rs = await _call("GET", "/recipes")
    if isinstance(rs, dict):
        return rs
    available = []
    for recipe in rs:
        check = await _call("POST", "/recipes:validate?live=true", json=recipe)
        available.append(
            {
                "available": check.get("valid") is True,
                "unavailable_reason": check.get("error"),
            }
        )
    return {
        "recipes": [
            {
                "name": r["name"],
                "version": r["version"],
                "mode": r["mode"],
                "description": r["description"],
                "description_role": "source_question"
                if r.get("origin_runs")
                else "procedure",
                "objective": r["routing"].get("objective")
                or ("" if r.get("origin_runs") else r["description"]),
                "source_question": r.get("source_question")
                or (r["description"] if r.get("origin_runs") else None),
                **(
                    {"reuse": await _call("GET", f"/recipes/{r['name']}/reuse")}
                    if availability["available"]
                    else {}
                ),
                "use_for": r["routing"]["use_for"],
                "do_not_use_for": r["routing"]["do_not_use_for"],
                "primary_metric": r["semantic_scope"]["primary_metric"],
                "inputs": r.get("inputs", {}),
                **availability,
            }
            for r, availability in zip(rs, available)
        ],
        "guidance": "Availability checks references only, not relevance, joins or result validity. Use find_recipes for candidates, compare their objective with the question, and never rewrite provider references automatically.",
    }


def _author(author: ExecutionAuthor | None, ctx: Context | None) -> dict | None:
    data = author.model_dump(mode="json", exclude_none=True) if author else {}
    if ctx is not None:
        params = ctx.session.client_params
        if params and params.client_info:
            data.update(
                client_name=params.client_info.name,
                client_version=params.client_info.version,
                client_source="protocol",
            )
    return data or None


@mcp.tool(description=_(DOCS["start_run"]))
async def start_run(
    recipe: str,
    question: str,
    date_range: list[str] | None = None,
    time_dimension: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
    inputs: dict[str, Any] | None = None,
    period: PeriodChoice | None = None,
    recipe_selection: RecipeSelection | None = None,
    *,
    goals: list[AnalysisGoal],
    recipe_review: list[RecipeReview] | None = None,
) -> dict:
    body = {
        "recipe": recipe,
        "question": question,
        "author": _author(author, ctx),
        "goals": [goal.model_dump(mode="json") for goal in goals or []],
        "recipe_selection": recipe_selection.model_dump(mode="json")
        if recipe_selection
        else None,
        "recipe_review": [item.model_dump(mode="json") for item in recipe_review or []],
        "scope": {
            key: value
            for key, value in {
                "date_range": date_range,
                "time_dimension": time_dimension,
                "filters": filters,
                "inputs": inputs,
                "period": period.model_dump(mode="json") if period else None,
            }.items()
            if value is not None
        },
    }
    return _running_or(
        await _call("POST", "/runs", json=body, params={"wait": WAIT_SECONDS}),
        _compact_run,
    )


@mcp.tool(
    description=_(
        "Use one pipeline Recipe inside an existing open Run. Supply the recorded goals it covers and a selection reason. Earlier query scope is preserved; conflicting shared filters require a new Run."
    )
)
async def use_recipe(
    run_id: str,
    recipe: str,
    selection: RecipeSelection,
    inputs: dict[str, Any] | None = None,
) -> dict:
    return _running_or(
        await _call(
            "POST",
            f"/runs/{run_id}:use-recipe",
            json={
                "recipe": recipe,
                "selection": selection.model_dump(mode="json"),
                "inputs": inputs or {},
            },
            params={"wait": WAIT_SECONDS},
        ),
        _compact_run,
    )


@mcp.tool(description=_(DOCS["start_analysis"]))
async def start_analysis(
    question: str,
    date_range: list[str] | None = None,
    time_dimension: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
    period: PeriodChoice | None = None,
    *,
    goals: list[AnalysisGoal],
    recipe_review: list[RecipeReview] | None = None,
    guide: str | None = None,
) -> dict:
    body = {
        "recipe": None,
        "guide": guide,
        "question": question,
        "author": _author(author, ctx),
        "goals": [goal.model_dump(mode="json") for goal in goals or []],
        "recipe_review": [item.model_dump(mode="json") for item in recipe_review or []],
        "scope": {
            "date_range": date_range,
            "time_dimension": time_dimension,
            "filters": filters or [],
            "period": period.model_dump(mode="json") if period else None,
        },
    }
    return _compact_run(await _call("POST", "/runs", json=body))


@mcp.tool(
    description="Resolve a pending analysis period and resume the same Run. Use dates supported by the user's request or conversation, a proposed relative period, or explicit all-period mode if server policy allows it. Do not claim user approval or bypass a refusal. Source labels are caller-reported evidence, not permission. If intent is unclear, ask the user. Use the base_revision returned by get_run. After execution starts, changing the period requires a new Run."
)
async def set_run_scope(
    run_id: str,
    base_revision: int,
    period: PeriodChoice,
    time_dimension: str | None = None,
) -> dict:
    scope = {"period": period.model_dump(mode="json")}
    if time_dimension is not None:
        scope["time_dimension"] = time_dimension
    return _running_or(
        await _call(
            "PUT",
            f"/runs/{run_id}/scope",
            json={"scope": scope, "base_revision": base_revision},
            params={"wait": WAIT_SECONDS},
        ),
        _compact_run,
    )


@mcp.tool(description=_(DOCS["run_step"]))
async def run_step(
    run_id: str,
    method: str,
    bindings: dict[str, str | list[str]] | None = None,
    params: dict[str, Any] | None = None,
    step_id: str | None = None,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
    exploration: bool = False,
    *,
    purpose: str,
    goal_ids: list[str],
    measures: dict[str, str | list[str]] | None = None,
    dimensions: dict[str, str | list[str]] | None = None,
    entity: str | None = None,
) -> dict:
    if not allowed(method):
        return _not_exposed(method)
    body = {
        "id": step_id,
        "method": method,
        "purpose": purpose,
        "author": _author(author, ctx),
        "bindings": bindings or {},
        "params": params or {},
        "goal_ids": goal_ids or [],
        "exploration": exploration,
        "measures": measures or {},
        "dimensions": dimensions or {},
        "entity": entity,
    }
    return _running_or(
        await _call(
            "POST", f"/runs/{run_id}/steps", json=body, params={"wait": WAIT_SECONDS}
        ),
        _compact_result,
    )


@mcp.tool(
    description="Execute one governed Cube query inside the active Skill step. This records the request, purpose, result, errors and provenance. Use the exact bound metric, Run period and inherited filters; inspect get_run for the active step. Returns at most 25 rows; use get_skill_query to read further pages before selecting an absolute query row. No SQL or Python is accepted."
)
async def run_skill_query(
    run_id: str,
    step_id: str,
    query_id: str,
    purpose: str,
    spec: dict[str, Any],
    period_role: Literal["current", "comparison"] = "current",
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
) -> dict:
    return _running_or(
        await _call(
            "POST",
            f"/runs/{run_id}/steps/{step_id}/queries",
            json={
                "id": query_id,
                "purpose": purpose,
                "spec": spec,
                "period_role": period_role,
                "author": _author(author, ctx),
            },
            params={"wait": WAIT_SECONDS},
        ),
        _skill_query_page,
    )


@mcp.tool(
    description="Read one persisted Skill query, including request, status, checks, provenance summary and a page of actual rows. This never re-executes data access. Use absolute row indices (offset plus row index) in finish_skill_step. Full native query/SQL evidence remains in the Web Run. Limit is 1 to 100 rows; default 25."
)
async def get_skill_query(
    run_id: str, step_id: str, query_id: str, offset: int = 0, limit: int = 25
) -> dict:
    if offset < 0 or not 1 <= limit <= 100:
        return {
            "error": {
                "code": "INVALID_PAGE",
                "message": "Use offset >= 0 and limit between 1 and 100.",
            }
        }
    run = await _call("GET", f"/runs/{run_id}")
    if "id" not in run:
        return run
    for step in run.get("steps", []):
        if step["step"].get("id") == step_id:
            for query in (step.get("skill") or {}).get("queries", []):
                if query["id"] == query_id:
                    return _skill_query_page(query, offset, limit)
    return {
        "error": {
            "code": "SKILL_QUERY_NOT_FOUND",
            "message": "No recorded query matches this step and query ID.",
        }
    }


@mcp.tool(
    description="Complete or refuse the active Skill stage after inspecting its query evidence. An optional selection must reference a returned query row/dimension, never an invented value. Completion resumes the next Recipe stage. If another Skill is waiting, follow its instructions; only finish the Run after all stages."
)
async def finish_skill_step(
    run_id: str,
    step_id: str,
    reason: str,
    status: Literal["completed", "refused"] = "completed",
    selection: dict[str, Any] | None = None,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
) -> dict:
    return _running_or(
        await _call(
            "POST",
            f"/runs/{run_id}/steps/{step_id}:finish",
            json={
                "status": status,
                "reason": reason,
                "selection": selection,
                "author": _author(author, ctx),
            },
            params={"wait": WAIT_SECONDS},
        ),
        _compact_run,
    )


@mcp.tool(description=_(DOCS["complete_run"]))
async def complete_run(
    run_id: str,
    conclusion: RunConclusion,
    summary: str | None = None,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
) -> dict:
    return _compact_run(
        await _call(
            "POST",
            f"/runs/{run_id}:complete",
            json={
                "summary": summary,
                "conclusion": conclusion.model_dump(mode="json")
                if conclusion
                else None,
                "author": _author(author, ctx),
            },
        )
    )


@mcp.tool(
    description=_(
        "Prepare a GitHub Method proposal draft only when the user requests it. Requires a recorded method_missing goal. Supply explicitly public, anonymized text. Returns a review link; it does not submit an issue."
    )
)
async def prepare_method_proposal(
    run_id: str, goal_id: str, title: str, public_question: str, expected_result: str
) -> dict:
    return await _call(
        "POST",
        f"/runs/{run_id}/method-proposal",
        json={
            "goal_id": goal_id,
            "title": title,
            "public_question": public_question,
            "expected_result": expected_result,
        },
    )


@mcp.tool(description=_(DOCS["share_run"]))
async def share_run(run_id: str, subjects: list[str]) -> dict:
    return _compact_run(
        await _call("POST", f"/runs/{run_id}:share", json={"subjects": subjects})
    )


@mcp.tool(
    description="Record a proposed semantic-model improvement for a recorded Run goal. Include inspected API evidence and a short actionable proposal. When possible provide model_drafts with provider, title, YAML, basis and unresolved details. Use only API-confirmed information; never assume access to local files or warehouse columns. Use placeholders for unknown columns, model names, joins or grain and list them in unresolved. YAML is an unverified external-edit draft, never applied or executed here. Never invent refs; leave unknown requirement refs null. This does not change the semantic model or approve the proposal."
)
async def record_semantic_gap(run_id: str, proposal: RemediationCreateRequest) -> dict:
    return _compact_run(
        await _call(
            "POST",
            f"/runs/{run_id}/remediations",
            json=proposal.model_dump(mode="json"),
        )
    )


@mcp.tool(
    description="Record an analysis that cannot answer all requested goals before replying to the user. No user instruction to create a Run or approve logging is needed. One call saves the original question, classified outcomes, evidence-based semantic proposals and conclusion and returns its Run link. For semantic gaps include concise actions and optional model_drafts (provider, title, YAML, basis, unresolved). Derive drafts only from inspected APIs, never local files or assumed warehouse columns. Mark unknown columns, model names, joins and grain with placeholders and unresolved details. Drafts are unverified, never executable here. Use an existing run_id for partial analyses. New records cannot claim supported answers without executed evidence. Missing definitions are caller-reported proposals, not verified facts. No queries, substitute analysis, model edits, approval or public issue submission occur."
)
async def report_analysis_blocked(
    request: BlockedAnalysisRequest,
    author: ExecutionAuthor | None = None,
    ctx: Context = None,
) -> dict:
    body = request.model_dump(mode="json", exclude_unset=True)
    body["author"] = _author(author or request.author, ctx)
    return _compact_run(await _call("POST", "/analyses:blocked", json=body))


@mcp.tool(
    description="Refresh catalog metadata and check an owner-confirmed semantic improvement. Use its current revision from get_run. A metadata pass is not an analysis result or evidence of causal validity."
)
async def recheck_semantic_gap(
    run_id: str, remediation_id: str, base_revision: int
) -> dict:
    return _compact_run(
        await _call(
            "POST",
            f"/runs/{run_id}/remediations/{remediation_id}:check",
            json={"base_revision": base_revision},
        )
    )


@mcp.tool(
    description="Start a linked new Run after owner review and a fresh catalog check. Keep the original question and goals. Select and review Recipes normally; without a Recipe, replan Methods using current data, never replay old literal selections. Existing scope is preserved unless explicitly changed. Previous conclusions remain unchanged."
)
async def retry_after_semantic_update(
    run_id: str, remediation_id: str, request: RemediationRetryRequest
) -> dict:
    if not RECIPES and request.recipe:
        return {
            "error": {
                "code": "RECIPE_NOT_EXPOSED",
                "message": "Recipes are not available in this MCP profile.",
            }
        }
    return _running_or(
        await _call(
            "POST",
            f"/runs/{run_id}/remediations/{remediation_id}:retry",
            json=request.model_dump(mode="json", exclude_unset=True),
            params={"wait": WAIT_SECONDS},
        ),
        _compact_run,
    )


@mcp.tool(description=_(DOCS["wait_for_run"]))
async def wait_for_run(run_id: str) -> dict:
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        run = await _call("GET", f"/runs/{run_id}")
        if "id" not in run:  # an API error body ({"error": …}), not a run
            return run
        if not run.get("running"):
            break
        if time.monotonic() >= deadline:
            return _running(run_id, run.get("running"))
        await asyncio.sleep(2)
    if run.get("error"):  # the job itself failed
        return {"run_id": run_id, "status": "failed", "error": run["error"]}
    return _compact_run(run)


@mcp.tool(description=_(DOCS["get_run"]))
async def get_run(run_id: str) -> dict:
    return _compact_run(await _call("GET", f"/runs/{run_id}"))


@mcp.tool(
    description="When the user asks to save their completed analysis, save its procedure as a draft. Only the Run owner with editor permission can do this. Return the draft and review its fixed values, filters, period rules and origin links with the user; questions and Run-specific prose are omitted. Saving does not publish or validate the analysis."
)
async def save_procedure(run_id: str) -> dict:
    return await _call("POST", f"/runs/{run_id}/recipe", json={})


@mcp.tool(
    description="Publish a reviewed draft only when the user asks to publish it. First inspect the entire draft returned by save_procedure, including fixed values, filters and origin links. Publication requires publisher permission and the current draft version; it creates a new immutable version. A shared Run viewer cannot promote its procedure."
)
async def publish_procedure(name: str, base_version: str) -> dict:
    from urllib.parse import quote

    return await _call(
        "POST",
        f"/recipes/{quote(name, safe='')}/publish",
        json={"base_version": base_version},
    )


if not RECIPES:
    for tool in (
        "list_recipes",
        "start_run",
        "use_recipe",
        "save_procedure",
        "publish_procedure",
    ):
        mcp.remove_tool(tool)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()

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
from typing import Any

import httpx
from mcp.server.mcpserver import Context, MCPServer

from ..core.models import ExecutionAuthor, RunConclusion

from ..env import env
from ..i18n import _, negotiate, set_locale

# the MCP server speaks one language per process: DL_LOCALE (e.g. ko), default en
LOCALE = negotiate(env("DL_LOCALE"))
set_locale(LOCALE)

SECTIONS = {
    "conclude": "After every finished analysis, call complete_run with a structured conclusion for its run_id. This also applies when run_method or a pipeline completed automatically. Do not leave the final answer only in the chat.",
    "attribution": "If your host explicitly supplies the model provider, model ID or revision, pass the known values in author on start, step and completion calls. Omit unknown values; never infer a model from the client product or claim a version from memory. Client/model attribution is informational, not an authenticated identity.",
    "intro": "Decision Layer runs registered analysis Methods on top of a semantic layer (Cube).",
    "proceed": "How to proceed\n- Look at list_recipes first. If a Recipe fits, execute it with start_run. A pipeline executes its steps automatically; an investigation guides run_step calls within its Method, metric and query limits.\n- Otherwise use start_analysis with the full original question, then run_step for registered Methods. Use run_method only for genuinely one-off execution.\n- Every finished analysis must call complete_run(run_id, conclusion), including an automatically completed pipeline or one-off Method. conclusion must contain a short answer, findings linked to recorded zero-based step indices, and plain-language limitations. Do not return only a dense summary. This stores the same format for every Method and Recipe.\n- Do not rewrite a Run that already has a caller-authored conclusion.\n- If a result is running, call wait_for_run until it finishes before concluding. Never guess unfinished results.\n- End the answer with the run_id.",
    "rules": "Rules\n- Use only refs (cube://…) found with search_semantic. Never invent names.\n- Check a Method's roles and parameters with describe_method and fill them accordingly.\n- If status is needs_input, ask the user needs_input.question with its candidates as given. Never pick for them.\n- If status is refused, explain the reasons in warnings and validation. You may suggest another approach, but\n  never work around it with your own calculation.\n- Report validation warnings (incomplete period, small sample, stale data) with the answer, but only as far as\n  the message says. Do not add guessed causes or effects. If it needs checking, run another Method (e.g. a\n  monthly comparison) and answer from that, or say clearly that it is an unverified possibility.\n- Do not present facts that are not in the results (common wisdom, how the data was made, presumed causes)\n  as conclusions.\n- Stay within the result's interpretation level. If it is descriptive, do not call anything a cause.",
    "numbers_strict": "- Quote numbers only from run_method, run_step and start_run results. Never compute or estimate ratios,\n  differences or significance yourself.",
    "numbers_relaxed": "- Numbers come from tool results. You may do simple arithmetic on them (sums, differences, ratios)\n  and say so. Judgements — whether a change or difference is significant, whether a factor is related,\n  whether data can be trusted — come only from result fields (tests, validation). Never make them yourself.",
    "changes": "Explaining changes between two periods\n- First check whether the change is real: call query.trend with current and comparison (or vs_previous) and read\n  its change test. If the change is not significant, say so and do not look for causes of it.\n- If the periods differ in length, talk about totals through the per_day values; explain a total by factors\n  (count × value per count, …) only from the decomposition field.\n- To see which groups made a change, use query.drilldown with the same periods (period mode).",
    "factors": "How a factor relates to a metric (causal.cem)\n- Questions about whether a factor (a dimension value or a numeric measure) is related to a metric are answered\n  with causal.cem, matching on conditions — not with a plain comparison.\n- If interpretation is causal_conditional, say only \"the difference remains with the conditions matched\", and\n  pass on the result's warnings that unmatched factors can remain. Never state it is the cause.\n- Put in target and comparison groups only as the user stated them. If the user did not name a comparison,\n  leave it empty so the server asks with needs_input, and relay that question. Never choose \"everyone else\"\n  or any other comparison on your own.\n- Showing the difference before (raw) and after (matched) matching shows what the conditions explained.\n- If validation comparability fails (too little overlap), do not use the comparison as a conclusion.",
    "drilldown": "Drill-down\n- query.drilldown is one level per call. Pass the drill_path of one of the result's next_candidates as the next\n  call's params.drill_path.\n- If it is unclear which candidate to follow, ask the user.\n- State the top group's significance with test.selection.significant_after_selection (corrected for picking it\n  among many groups).",
    "record_question": "When calling start_analysis, start_run or run_method, copy the user's full original question verbatim into question, including its constraints. Do not shorten, paraphrase or replace it with a Recipe description. Put step-specific intent in purpose instead.",
}

DOCS = {
    "search_semantic": "Find measures and dimensions (dimension, time_dimension). query matches title, description or ref;\nkind is measure | dimension | time_dimension. Use the returned refs in run_method bindings.",
    "list_methods": "Registered analysis Methods (name, description, roles).",
    "describe_method": "A Method's full manifest: roles (bindings) and parameters (params) with types, defaults and descriptions.",
    "run_method": "Run a registered Method.\n- bindings: role → semantic ref (e.g. {\"metric\": \"cube://…/<measure>\", \"dimensions\": [ref, ref]})\n- params: Method parameters (e.g. {\"drill_path\": [...], \"top_n\": 10})\n- date_range: [\"YYYY-MM-DD\", \"YYYY-MM-DD\"] analysis period (the current period for comparison Methods)\n- time_dimension: the date ref the period applies to (only when asked via needs_input)\n- filters: [{\"member\": ref, \"operator\": \"equals\", \"values\": [...]}] shared filters",
    "list_recipes": "The organisation's analysis procedures (Recipes). If a question matches use_for, run it with start_run.",
    "start_run": "Start a Recipe run. A pipeline returns every step's result; an investigation returns a guide (recipe_guide).\n- recipe: a name from list_recipes\n- question: the user's question as asked (for the record)\n- date_range: [\"YYYY-MM-DD\", \"YYYY-MM-DD\"] analysis period",
    "start_analysis": "Start a Recipe-free investigation for one user question. Follow with run_step for each registered Method, then complete_run.\n- question: the user's original question\n- date_range: [\"YYYY-MM-DD\", \"YYYY-MM-DD\"] analysis period\n- time_dimension: a discovered date ref when the period needs one",
    "run_step": "Run one step of an investigation. Set purpose to the specific part of the user's question this Method will address; it is recorded as intent, not evidence. A Recipe Run enforces its Method and metric scope; a Recipe-free Run accepts registered Methods with normal binding and query validation.\nThe period and shared filters of the Run apply.",
    "complete_run": "Record the conclusion of any finished analysis, including a pipeline or one-off Method that already completed execution. conclusion is required: one or two plain-language sentences answering the question, findings linked to zero-based recorded step_indices, and limitations. Include at most one essential number in answer; keep confidence intervals, settings, sample counts and diagnostics in step evidence. This is your explanation, not an independently verified finding. A caller-authored conclusion cannot be overwritten. Supply author model_id/provider/revision only when explicitly known; never guess a model version.",
    "share_run": "Only when the user asks: share a run read-only with other users. subjects: user identifiers,\n[\"*\"] = any authenticated user, [] = stop sharing. It won't open for a recipient lacking access to its metrics.",
    "wait_for_run": "Wait (about 45 s at most) for a run whose status is running. Returns the result when done (the whole run\nfor a pipeline), or running again — then call it once more.",
    "get_run": "Reopen a stored run (question, scope, step results, conclusion).",
}

# Deployment / experiment knobs (ADR-032):
#   DL_MCP_METHODS   comma list of Methods to expose (default: all)
#   DL_MCP_RECIPES   "off" hides the recipe/run tools (autonomous analysis only)
#   DL_MCP_RULES     "relaxed" (default, ADR-032): simple arithmetic allowed, judgements only from results;
#                           "strict": numbers only as returned
METHODS = {m.strip() for m in env("DL_MCP_METHODS", "").split(",") if m.strip()}
RECIPES = env("DL_MCP_RECIPES", "on").lower() != "off"
RULES = env("DL_MCP_RULES", "relaxed").lower()


def allowed(method: str) -> bool:
    return not METHODS or method in METHODS


def instructions() -> str:
    rules = _(SECTIONS["rules"]) + "\n" + _(SECTIONS["numbers_strict" if RULES == "strict" else "numbers_relaxed"])
    parts = [_(SECTIONS["intro"]), *([_(SECTIONS["proceed"])] if RECIPES else []), _(SECTIONS["record_question"]), _(SECTIONS["conclude"]), _(SECTIONS["attribution"]), rules,
             *([_(SECTIONS["changes"])] if allowed("query.trend") else []),
             *([_(SECTIONS["factors"])] if allowed("causal.cem") else []),
             *([_(SECTIONS["drilldown"])] if allowed("query.drilldown") else [])]
    return "\n\n".join(parts)


INSTRUCTIONS = instructions()
mcp = MCPServer(name="decision-layer", instructions=INSTRUCTIONS)
WAIT_SECONDS = 45   # per call; longer analyses continue with wait_for_run
logging.getLogger("httpx").setLevel(logging.WARNING)


def _client() -> httpx.AsyncClient:
    headers = {"Accept-Language": LOCALE, "X-Decision-Layer-Client": "mcp"}
    if token := env("DL_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(base_url=env("DL_API_URL", "http://localhost:5200"),
                             headers=headers, timeout=120)


async def _call(method: str, path: str, **kwargs: Any) -> Any:
    async with _client() as c:
        r = await c.request(method, path, **kwargs)
    body = r.json()
    if r.status_code >= 400:
        return body if isinstance(body, dict) and "error" in body else {"error": {"status": r.status_code, "body": body}}
    return body


@mcp.tool(description=_(DOCS["search_semantic"]))
async def search_semantic(query: str | None = None, kind: str | None = None) -> dict:
    cat = await _call("GET", "/semantic/catalog")
    if "error" in cat:
        return cat
    q = (query or "").lower()
    items = []
    for o in cat["objects"]:
        if kind and o["kind"] != kind:
            continue
        text = f"{o['ref']} {o['title']} {o.get('description') or ''}".lower()
        if q and not all(t in text for t in q.split()):
            continue
        item = {"ref": o["ref"], "kind": o["kind"], "title": o["title"]}
        if o.get("metric_kind"):
            item["metric_kind"] = o["metric_kind"]
        if o.get("ratio_parts"):
            item["ratio_parts"] = o["ratio_parts"]
        for field in ("dimension_refs", "time_dimension", "count_measure", "entity"):
            if o.get(field):
                item[field] = o[field]
        if o.get("description"):
            item["description"] = o["description"][:160]
        hints = {key: value for key, value in (o.get("metadata") or {}).items()
                 if key in ("suggestedDateRange", "calendarType")}
        if hints:
            item["metadata"] = hints
        items.append(item)
    return {"count": len(items), "objects": items}


@mcp.tool(description=_(DOCS["list_methods"]))
async def list_methods() -> dict:
    ms = await _call("GET", "/methods")
    if isinstance(ms, dict):
        return ms
    return {"methods": [{"name": m["name"], "description": m["description"], "interpretation": m["interpretation"],
                         "roles": {k: r["kind"] + ("[]" if r["multiple"] else "") for k, r in m["roles"].items()}}
                        for m in ms if allowed(m["name"])]}


@mcp.tool(description=_(DOCS["describe_method"]))
async def describe_method(name: str) -> dict:
    if not allowed(name):
        return _not_exposed(name)
    return await _call("GET", f"/methods/{name}")


@mcp.tool(description=_(DOCS["run_method"]))
async def run_method(name: str, bindings: dict[str, str | list[str]], params: dict[str, Any] | None = None,
                     date_range: list[str] | None = None, time_dimension: str | None = None,
                     filters: list[dict[str, Any]] | None = None, question: str | None = None,
                     author: ExecutionAuthor | None = None, ctx: Context = None) -> dict:
    if not allowed(name):
        return _not_exposed(name)
    body = {"question": question, "author": _author(author, ctx), "bindings": bindings, "params": params or {},
            "scope": {"date_range": date_range, "time_dimension": time_dimension, "filters": filters or []}}
    return _running_or(await _call("POST", f"/methods/{name}:run", json=body, params={"wait": WAIT_SECONDS}),
                       _compact_result)


def _not_exposed(name: str) -> dict:
    return {"error": {"code": "METHOD_NOT_EXPOSED", "message": _("Method {name} is not available here", name=name)}}


def _running(run_id: str, running: Any) -> dict:
    return {"run_id": run_id, "status": "running", "running": running,
            "next": _("Still computing. Wait for the result with wait_for_run(run_id).")}


def _running_or(body: Any, compact) -> Any:
    """202 bodies (still running) become a 'running' notice; anything else is compacted as usual."""
    if isinstance(body, dict) and body.get("running") and (body.get("status") == "running" or "steps" in body):
        return _running(body.get("run_id") or body.get("id"), body["running"])
    return compact(body)


def _compact_result(result: Any) -> Any:
    prov = result.get("provenance") if isinstance(result, dict) else None
    if prov:  # native queries are for audit, not for the model: keep a summary
        result["provenance"] = {"method": prov.get("method"), "semantic_refs": prov.get("semantic_refs"),
                                "queries": len(prov.get("queries") or []),
                                "rows_read": sum(q.get("rows", 0) for q in prov.get("queries") or [])}
    return result


def _compact_run(run: dict) -> dict:
    if "id" not in run:
        return run
    recipe = run.get("recipe_snapshot") or {}
    queries = sum(s["result"]["provenance"].get("queries", 0) if isinstance(s["result"]["provenance"].get("queries"), int)
                  else len(s["result"]["provenance"].get("queries") or []) for s in run["steps"])
    out = {"run_id": run["id"], "status": run["status"], "recipe": run["plan"].get("recipe"),
           "owner": run["caller"].get("subject"), "shared_with": run.get("shared_with") or [],
           "question": run["plan"].get("question"), "scope": run["plan"].get("scope"),
           "validation": run.get("validation"), "summary": run.get("summary"), "error": run.get("error"),
           "conclusion": run.get("conclusion"), "author": run.get("author"), "conclusion_author": run.get("conclusion_author"),
           "steps": [{"id": s["step"].get("id"), "method": s["step"]["method"], "bindings": s["step"]["bindings"],
                      "params": s["step"]["params"], "author": s.get("author"), "result": _compact_result(s["result"])} for s in run["steps"]]}
    if recipe:
        limits = recipe.get("limits") or {}
        out["recipe_guide"] = {"mode": recipe["mode"], "instructions": recipe.get("instructions"),
                               "allowed_methods": recipe.get("allowed_methods") or sorted({s["method"] for s in recipe.get("steps") or []}),
                               "semantic_scope": recipe["semantic_scope"],
                               "steps_left": limits.get("max_steps", 12) - len(run["steps"]),
                               "queries_left": limits.get("max_queries", 30) - queries}
    return out


@mcp.tool(description=_(DOCS["list_recipes"]))
async def list_recipes() -> dict:
    rs = await _call("GET", "/recipes")
    if isinstance(rs, dict):
        return rs
    available = []
    for recipe in rs:
        check = await _call("POST", "/recipes:validate?live=true", json=recipe)
        available.append({"available": check.get("valid") is True,
                          "unavailable_reason": check.get("error")})
    return {"recipes": [{"name": r["name"], "version": r["version"], "mode": r["mode"], "description": r["description"],
                         "use_for": r["routing"]["use_for"], "do_not_use_for": r["routing"]["do_not_use_for"],
                         "primary_metric": r["semantic_scope"]["primary_metric"], **availability}
                        for r, availability in zip(rs, available)],
            "guidance": "Only execute available recipes. Otherwise use registered Methods with the current semantic catalog; never rewrite provider references automatically."}


def _author(author: ExecutionAuthor | None, ctx: Context | None) -> dict | None:
    data = author.model_dump(mode="json", exclude_none=True) if author else {}
    if ctx is not None:
        params = ctx.session.client_params
        if params and params.client_info:
            data.update(client_name=params.client_info.name, client_version=params.client_info.version,
                        client_source="protocol")
    return data or None


@mcp.tool(description=_(DOCS["start_run"]))
async def start_run(recipe: str, question: str, date_range: list[str] | None = None,
                    time_dimension: str | None = None, filters: list[dict[str, Any]] | None = None,
                    author: ExecutionAuthor | None = None, ctx: Context = None) -> dict:
    body = {"recipe": recipe, "question": question, "author": _author(author, ctx),
            "scope": {key: value for key, value in {"date_range": date_range, "time_dimension": time_dimension,
                                                    "filters": filters}.items() if value is not None}}
    return _running_or(await _call("POST", "/runs", json=body, params={"wait": WAIT_SECONDS}), _compact_run)


@mcp.tool(description=_(DOCS["start_analysis"]))
async def start_analysis(question: str, date_range: list[str] | None = None,
                         time_dimension: str | None = None, filters: list[dict[str, Any]] | None = None,
                         author: ExecutionAuthor | None = None, ctx: Context = None) -> dict:
    body = {"recipe": None, "question": question, "author": _author(author, ctx),
            "scope": {"date_range": date_range, "time_dimension": time_dimension, "filters": filters or []}}
    return _compact_run(await _call("POST", "/runs", json=body))


@mcp.tool(description=_(DOCS["run_step"]))
async def run_step(run_id: str, method: str, bindings: dict[str, str | list[str]],
                   params: dict[str, Any] | None = None, step_id: str | None = None,
                   purpose: str | None = None, author: ExecutionAuthor | None = None, ctx: Context = None) -> dict:
    body = {"id": step_id, "method": method, "purpose": purpose, "author": _author(author, ctx), "bindings": bindings, "params": params or {}}
    return _running_or(await _call("POST", f"/runs/{run_id}/steps", json=body, params={"wait": WAIT_SECONDS}),
                       _compact_result)


@mcp.tool(description=_(DOCS["complete_run"]))
async def complete_run(run_id: str, conclusion: RunConclusion, summary: str | None = None,
                       author: ExecutionAuthor | None = None, ctx: Context = None) -> dict:
    return _compact_run(await _call("POST", f"/runs/{run_id}:complete", json={"summary": summary,
        "conclusion": conclusion.model_dump(mode="json") if conclusion else None, "author": _author(author, ctx)}))


@mcp.tool(description=_(DOCS["share_run"]))
async def share_run(run_id: str, subjects: list[str]) -> dict:
    return _compact_run(await _call("POST", f"/runs/{run_id}:share", json={"subjects": subjects}))


@mcp.tool(description=_(DOCS["wait_for_run"]))
async def wait_for_run(run_id: str) -> dict:
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        run = await _call("GET", f"/runs/{run_id}")
        if "id" not in run:            # an API error body ({"error": …}), not a run
            return run
        if not run.get("running"):
            break
        if time.monotonic() >= deadline:
            return _running(run_id, run.get("running"))
        await asyncio.sleep(2)
    if run.get("error"):               # the job itself failed
        return {"run_id": run_id, "status": "failed", "error": run["error"]}
    recipe = run.get("recipe_snapshot") or {}
    if recipe.get("mode") == "pipeline" and len(run["steps"]) > 1:
        return _compact_run(run)
    return _compact_result(run["steps"][-1]["result"]) if run["steps"] else _compact_run(run)


@mcp.tool(description=_(DOCS["get_run"]))
async def get_run(run_id: str) -> dict:
    return _compact_run(await _call("GET", f"/runs/{run_id}"))


if not RECIPES:
    for tool in ("list_recipes", "start_run", "start_analysis", "run_step"):
        mcp.remove_tool(tool)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()

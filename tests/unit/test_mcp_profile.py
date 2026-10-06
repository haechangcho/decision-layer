"""MCP exposure knobs (ADR-032): method allow-list, recipe tools off, relaxed number rule."""
import asyncio
import importlib


def load(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    from decision_layer.mcp import server
    return importlib.reload(server)


def test_defaults_expose_everything(monkeypatch):
    s = load(monkeypatch)
    client = s._client()
    assert client.headers["X-Decision-Layer-Client"] == "mcp"
    asyncio.run(client.aclose())
    names = {t.name for t in asyncio.run(s.mcp.list_tools())}
    assert {"start_run", "start_analysis", "run_step", "complete_run"} <= names
    assert "run_method" not in names
    assert "query.trend" in s.INSTRUCTIONS and "simple arithmetic" in s.INSTRUCTIONS    # relaxed by default (ADR-032)
    assert "verbatim" in s.INSTRUCTIONS and "Do not shorten" in s.INSTRUCTIONS
    step = next(t for t in asyncio.run(s.mcp.list_tools()) if t.name == "run_step")
    assert {"run_id", "method", "bindings", "purpose"} <= set(step.input_schema["required"])


def test_strict_rule(monkeypatch):
    s = load(monkeypatch, DL_MCP_RULES="strict")
    assert "simple arithmetic" not in s.INSTRUCTIONS and "Never compute" in s.INSTRUCTIONS
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)


def test_recipe_list_checks_current_connection_before_recommending(monkeypatch):
    s = load(monkeypatch)
    async def fake_call(method, path, **kwargs):
        if path == "/recipes":
            return [{"name": "previous-source", "version": "1.0.0", "mode": "pipeline", "description": "test",
                     "routing": {"use_for": [], "do_not_use_for": []},
                     "semantic_scope": {"primary_metric": "cube://old/sales/revenue"}}]
        assert method == "POST" and path == "/recipes:validate?live=true"
        return {"error": {"code": "UNKNOWN_SEMANTIC_OBJECT"}}
    monkeypatch.setattr(s, "_call", fake_call)
    result = asyncio.run(s.list_recipes())
    assert result["recipes"][0]["available"] is False
    assert result["recipes"][0]["unavailable_reason"]["code"] == "UNKNOWN_SEMANTIC_OBJECT"


def test_method_execution_only_appends_to_the_requested_run(monkeypatch):
    s = load(monkeypatch)
    seen = {}

    async def fake_call(_method, _path, **kwargs):
        assert _method == "POST" and _path == "/runs/run_test/steps"
        seen.update(kwargs["json"])
        return {"status": "success", "run_id": "run_test"}

    monkeypatch.setattr(s, "_call", fake_call)
    result = asyncio.run(s.run_step("run_test", "query.trend", {"metric": "cube://local/sales/revenue"},
                                   purpose="Check the change"))
    assert result["run_id"] == "run_test"
    assert seen["purpose"] == "Check the change" and "question" not in seen


def test_selection_sources_are_executable_templates_not_copied_winners(monkeypatch):
    s = load(monkeypatch)
    result = s._compact_result({"status": "success", "step_id": "groups", "selections": {"ranked_groups": {
        "complete": True, "rank_by": "metric", "direction": "desc",
        "candidates": [{"path": [{"member": "cube://x/orders/group", "value": str(i)}], "score": 100 - i} for i in range(20)]}}})
    assert len(result["selections"]["ranked_groups"]["candidates"]) == 3
    assert result["selections"]["ranked_groups"]["candidate_count"] == 20
    assert result["selection_sources"]["ranked_groups"]["condition"] == {
        "source": "step", "step_id": "groups", "output": "ranked_groups", "select": "first", "project": "condition"}


def test_semantic_search_forwards_provider_date_hints_without_domain_assumptions(monkeypatch):
    s = load(monkeypatch)

    async def fake_call(_method, _path, **kwargs):
        return {"objects": [{"ref": "cube://production/manufacturing/inspection_date", "kind": "time_dimension",
            "title": "Inspection date", "metadata": {"suggestedDateRange": ["2025-01-01", "2025-06-30"],
                                                     "calendarType": "mapped", "unrelated": "not forwarded"}}]}

    monkeypatch.setattr(s, "_call", fake_call)
    result = asyncio.run(s.search_semantic(kind="time_dimension"))
    assert result["objects"][0]["metadata"] == {"suggestedDateRange": ["2025-01-01", "2025-06-30"], "calendarType": "mapped"}


def test_recipe_free_analysis_starts_one_open_run(monkeypatch):
    s = load(monkeypatch)
    seen = {}

    async def fake_call(_method, _path, **kwargs):
        seen.update(kwargs["json"])
        return {"id": "run_test", "status": "open", "steps": [], "caller": {"subject": "alice"},
                "error": None,
                "plan": {"question": kwargs["json"]["question"], "recipe": None,
                         "scope": kwargs["json"]["scope"]}}

    monkeypatch.setattr(s, "_call", fake_call)
    result = asyncio.run(s.start_analysis("Which payment type is largest?", ["2026-06-01", "2026-06-30"]))
    assert result["run_id"] == "run_test" and result["status"] == "open"
    assert seen["recipe"] is None and seen["question"] == "Which payment type is largest?"
    assert seen["scope"]["date_range"] == ["2026-06-01", "2026-06-30"]


def test_step_purpose_is_forwarded_as_intent(monkeypatch):
    s = load(monkeypatch)
    seen = {}

    async def fake_call(_method, _path, **kwargs):
        seen.update(kwargs["json"])
        return {"status": "success", "run_id": "run_test"}

    monkeypatch.setattr(s, "_call", fake_call)
    asyncio.run(s.run_step("run_test", "query.trend", {"metric": "cube://local/sales/revenue"},
                           purpose="Check how revenue changed over time"))
    assert seen["purpose"] == "Check how revenue changed over time"


def test_conclusion_and_known_model_are_forwarded_without_guessing(monkeypatch):
    from decision_layer.core.models import ExecutionAuthor, RunConclusion, RunFinding
    from mcp.types import InitializeRequestParams
    from types import SimpleNamespace
    s = load(monkeypatch)
    seen = {}
    async def fake_call(_method, _path, **kwargs):
        seen.update(kwargs["json"])
        return {}
    monkeypatch.setattr(s, "_call", fake_call)
    params = InitializeRequestParams.model_validate({"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0"}})
    ctx = SimpleNamespace(session=SimpleNamespace(client_params=params))
    asyncio.run(s.complete_run("run_test", conclusion=RunConclusion(answer="Short answer", findings=[RunFinding(text="Finding", step_indices=[0])]), author=ExecutionAuthor(model_id="known-model"), ctx=ctx))
    assert seen["conclusion"]["findings"][0]["step_indices"] == [0]
    assert seen["author"]["client_source"] == "protocol"
    assert seen["author"]["model_id"] == "known-model" and "model_revision" not in seen["author"]
    tools = asyncio.run(s.mcp.list_tools())
    schema = next(tool.input_schema for tool in tools if tool.name == "complete_run")
    assert "ctx" not in schema["properties"] and "conclusion" in schema["properties"]
    assert "conclusion" in schema["required"]
    assert "complete_run(summary)" not in s.INSTRUCTIONS
    assert s._author(None, None) is None


def test_restricted_profile(monkeypatch):
    s = load(monkeypatch, DL_MCP_METHODS="query.drilldown,query.trend", DL_MCP_RECIPES="off",
             DL_MCP_RULES="relaxed")
    names = {t.name for t in asyncio.run(s.mcp.list_tools())}
    assert "start_run" not in names and "list_recipes" not in names and "run_method" not in names
    assert {"start_analysis", "run_step"} <= names
    assert "complete_run" in names
    assert "simple arithmetic" in s.INSTRUCTIONS and "causal.cem" not in s.INSTRUCTIONS
    assert "list_recipes" not in s.INSTRUCTIONS
    r = asyncio.run(s.run_step("run_test", "query.compare", {"metric": "x"}, purpose="Compare"))
    assert r["error"]["code"] == "METHOD_NOT_EXPOSED"
    monkeypatch.delenv("DL_MCP_METHODS")
    monkeypatch.delenv("DL_MCP_RECIPES")
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)

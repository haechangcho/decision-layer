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
    assert {"start_run", "start_analysis", "run_step", "run_method"} <= names
    assert "query.trend" in s.INSTRUCTIONS and "simple arithmetic" in s.INSTRUCTIONS    # relaxed by default (ADR-032)


def test_strict_rule(monkeypatch):
    s = load(monkeypatch, DL_MCP_RULES="strict")
    assert "simple arithmetic" not in s.INSTRUCTIONS and "Never compute" in s.INSTRUCTIONS
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)


def test_ad_hoc_method_forwards_the_original_question(monkeypatch):
    s = load(monkeypatch)
    seen = {}

    async def fake_call(_method, _path, **kwargs):
        seen.update(kwargs["json"])
        return {"status": "success", "run_id": "run_test"}

    monkeypatch.setattr(s, "_call", fake_call)
    result = asyncio.run(s.run_method("query.trend", {"metric": "cube://local/sales/revenue"},
                                      question="Why did revenue change?"))
    assert result["run_id"] == "run_test"
    assert seen["question"] == "Why did revenue change?"


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


def test_restricted_profile(monkeypatch):
    s = load(monkeypatch, DL_MCP_METHODS="query.drilldown,query.trend", DL_MCP_RECIPES="off",
             DL_MCP_RULES="relaxed")
    names = {t.name for t in asyncio.run(s.mcp.list_tools())}
    assert "start_run" not in names and "start_analysis" not in names and "run_method" in names
    assert "simple arithmetic" in s.INSTRUCTIONS and "causal.cem" not in s.INSTRUCTIONS
    assert "list_recipes" not in s.INSTRUCTIONS.split("Rules")[0]
    r = asyncio.run(s.run_method("query.compare", {"metric": "x"}))
    assert r["error"]["code"] == "METHOD_NOT_EXPOSED"
    monkeypatch.delenv("DL_MCP_METHODS")
    monkeypatch.delenv("DL_MCP_RECIPES")
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)

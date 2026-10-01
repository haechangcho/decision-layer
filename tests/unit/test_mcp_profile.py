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
    names = {t.name for t in asyncio.run(s.mcp.list_tools())}
    assert {"start_run", "run_step", "run_method"} <= names
    assert "query.trend" in s.INSTRUCTIONS and "simple arithmetic" in s.INSTRUCTIONS    # relaxed by default (ADR-032)


def test_strict_rule(monkeypatch):
    s = load(monkeypatch, DL_MCP_RULES="strict")
    assert "simple arithmetic" not in s.INSTRUCTIONS and "Never compute" in s.INSTRUCTIONS
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)


def test_restricted_profile(monkeypatch):
    s = load(monkeypatch, DL_MCP_METHODS="query.drilldown,query.trend", DL_MCP_RECIPES="off",
             DL_MCP_RULES="relaxed")
    names = {t.name for t in asyncio.run(s.mcp.list_tools())}
    assert "start_run" not in names and "run_method" in names
    assert "simple arithmetic" in s.INSTRUCTIONS and "causal.cem" not in s.INSTRUCTIONS
    assert "list_recipes" not in s.INSTRUCTIONS.split("Rules")[0]
    r = asyncio.run(s.run_method("query.compare", {"metric": "x"}))
    assert r["error"]["code"] == "METHOD_NOT_EXPOSED"
    monkeypatch.delenv("DL_MCP_METHODS")
    monkeypatch.delenv("DL_MCP_RECIPES")
    monkeypatch.delenv("DL_MCP_RULES")
    importlib.reload(s)

"""Messages are English in code and complete in every catalog (ADR-031)."""
import ast
import re
import string
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.i18n import _, available, catalog, negotiate, set_locale
from decision_layer.methods import registry
from decision_layer.mcp import server as mcp_server
from decision_layer.settings import Settings
from tests.support.semantic import Q3, RR, FakeProvider

SRC = Path(__file__).parents[2] / "src" / "decision_layer"
HANGUL = re.compile("[가-힣]")


def source_files():
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def msgids() -> set[str]:
    """Every string that must be translatable: _("…") literals, manifest texts, MCP texts."""
    ids = set()
    for p in source_files():
        for node in ast.walk(ast.parse(p.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                ids.add(node.args[0].value)
    for m in registry.manifests():
        ids |= {m.description, m.label} | {text for r in m.roles.values() for text in (r.description, r.label)} | {text for p in m.parameters.values() for text in (p.description, p.label)}
    ids |= set(mcp_server.DOCS.values()) | set(mcp_server.SECTIONS.values())
    return {i for i in ids if i}


def fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_no_hangul_in_code():
    hits = [f"{p.relative_to(SRC)}:{i}" for p in source_files()
            for i, line in enumerate(p.read_text().splitlines(), 1) if HANGUL.search(line)]
    assert not hits, "user-facing text belongs in i18n catalogs: " + ", ".join(hits)


@pytest.mark.parametrize("locale", [loc for loc in available() if loc != "en"])
def test_catalog_is_complete_and_consistent(locale):
    cat, ids = catalog(locale), msgids()
    missing = sorted(ids - set(cat))
    unused = sorted(set(cat) - ids)
    assert not missing, f"{locale}: untranslated: {missing[:5]}"
    assert not unused, f"{locale}: unused entries: {unused[:5]}"
    mismatched = [k for k, v in cat.items() if fields(k) != fields(v)]
    assert not mismatched, f"{locale}: placeholders differ: {mismatched[:5]}"


def test_underscore_is_never_rebound():
    """`_` is the translation function; a local named `_` would shadow it inside that function."""
    bad = []
    for p in source_files():
        for node in ast.walk(ast.parse(p.read_text())):
            names = []
            if isinstance(node, (ast.Assign, ast.For, ast.AsyncFor, ast.With)):
                targets = node.targets if isinstance(node, ast.Assign) else [getattr(node, "target", None)]
                names = [n.id for t in targets if t is not None for n in ast.walk(t) if isinstance(n, ast.Name)]
            elif isinstance(node, ast.arguments):
                names = [a.arg for a in node.args + node.kwonlyargs]
            if "_" in names:
                bad.append(f"{p.relative_to(SRC)}:{node.lineno if hasattr(node, 'lineno') else '?'}")
    assert not bad, bad


def test_translate_and_negotiate():
    assert negotiate("ko-KR,ko;q=0.9,en;q=0.8") == "ko" and negotiate("fr, en") == "en" and negotiate(None, "ko") == "ko"
    token = set_locale("ko")
    try:
        assert _("Run not found: {run_id}", run_id="x") == "실행 기록이 없습니다: x"
    finally:
        set_locale("en")
    assert _("Run not found: {run_id}", run_id="x") == "Run not found: x"
    assert token


def test_api_speaks_the_requested_language(cube_meta):
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s", cube_service_groups=("ecommerce",),
                 database_url="memory", allow_service_credentials=True)
    c = TestClient(create_app(s, FakeProvider(cube_meta)))
    en = c.get("/runs/run_x").json()["error"]["message"]
    ko = c.get("/runs/run_x", headers={"Accept-Language": "ko"}).json()["error"]["message"]
    assert (en, ko) == ("Run not found: run_x", "실행 기록이 없습니다: run_x")
    assert HANGUL.search(c.get("/methods/query.trend", headers={"Accept-Language": "ko"}).json()["description"])
    assert not HANGUL.search(c.get("/methods/query.trend").json()["description"])
    # background jobs keep the request's language
    r = c.post("/methods/query.trend:run", headers={"Accept-Language": "ko"},
               json={"bindings": {"metric": RR}, "scope": {"date_range": list(Q3)}}).json()
    assert HANGUL.search(r["validation"][0]["message"])

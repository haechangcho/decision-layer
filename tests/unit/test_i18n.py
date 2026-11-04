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
    for registered in registry._versions.values():
        m = registered.manifest
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
    name = "stats.regression_adjustment"
    assert HANGUL.search(c.get(f"/methods/{name}", headers={"Accept-Language": "ko"}).json()["description"])
    assert not HANGUL.search(c.get(f"/methods/{name}").json()["description"])
    # A refused execution still uses the request locale before a source query.
    r = c.post(f"/methods/{name}:run", headers={"Accept-Language": "ko"},
               json={"bindings": {}, "scope": {"date_range": list(Q3)}}).json()
    assert HANGUL.search(r["error"]["message"])


def test_run_runtime_messages_cannot_bypass_translation():
    """Guard the message sinks, not just the strings already wrapped in _()."""
    def raw_text(value):
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.strip():
            yield value
        elif isinstance(value, (ast.List, ast.Tuple)):
            for item in value.elts:
                yield from raw_text(item)
        elif isinstance(value, ast.IfExp):
            yield from raw_text(value.body)
            yield from raw_text(value.orelse)
        elif isinstance(value, ast.JoinedStr):
            yield value

    hits = []
    for path in (SRC / 'runs').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            values = []
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                values += node.exc.args[:1]
            if isinstance(node, ast.Call):
                values += [k.value for k in node.keywords if k.arg in {'message', 'warnings', 'title'}]
                if (isinstance(node.func, ast.Attribute) and node.func.attr == 'append'
                        and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == 'warnings'):
                    values += node.args
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Attribute) and t.attr == 'warnings' for t in node.targets):
                values.append(node.value)
            if isinstance(node, ast.Dict):
                values += [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value == 'message']
            for value in values:
                hits += [f'{path.relative_to(SRC)}:{literal.lineno}' for literal in raw_text(value)]
    assert not hits, 'Run messages must use _() and a catalog entry: ' + ', '.join(hits)


def test_mcp_instructions_request_the_configured_narrative_language(monkeypatch):
    from decision_layer.i18n import reset_locale
    for locale in ('en', 'ko'):
        monkeypatch.setattr(mcp_server, 'LOCALE', locale)
        context = set_locale(locale)
        try:
            text = mcp_server.instructions()
            if locale == 'ko':
                assert '분석 목적, 발견 사항, 결론은 한국어로 작성' in text
            else:
                assert 'conclusions in English' in text
        finally:
            reset_locale(context)

import ast
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from decision_layer.methods.assets import AssetError
from decision_layer.methods.formatting import format_python
from tests.unit.test_method_asset_editor import app


def test_formatter_preserves_program_and_comments_without_executing(tmp_path):
    sentinel = tmp_path / "must-not-exist"
    source = f'''from pathlib import Path
Path({str(sentinel)!r}).write_text("executed")
# Keep this review explanation.
def analyze(data, scale=2):
 return data.assign(value=data[ 'value' ]*scale)
'''
    formatted = format_python(source)
    assert not sentinel.exists()
    assert ast.dump(ast.parse(formatted)) == ast.dump(ast.parse(source))
    assert "# Keep this review explanation." in formatted
    assert '    return data.assign(value=data["value"] * scale)' in formatted
    assert format_python(formatted) == formatted


def test_format_api_needs_edit_permission_but_never_saves_checks_or_publishes(tmp_path, provider):
    with TestClient(app(tmp_path, provider)) as client:
        old = client.get("/methods/stats.regression_adjustment/source").json()
        response = client.post("/methods/stats.regression_adjustment/source:format", json={
            "content": 'def analyze(data):\n return data[ "value" ]*2\n'
        })
        assert response.status_code == 200, response.text
        assert response.json()["changed"]
        assert '    return data["value"] * 2' in response.json()["content"]
        assert client.get("/methods/stats.regression_adjustment/source").json() == old
        assert not list((tmp_path / "assets").rglob("*.json"))
        invalid = client.post("/methods/stats.regression_adjustment/source:format", json={"content": "def broken("})
        assert invalid.status_code == 400
        assert client.post("/methods/analysis.drilldown/source:format", json={"content": "pass"}).status_code == 400
    with TestClient(app(tmp_path, provider, enabled=False)) as client:
        assert client.post("/methods/stats.regression_adjustment/source:format", json={"content": "pass"}).status_code == 400


def test_formatter_checks_byte_limit_and_stops_on_invalid_syntax():
    with pytest.raises(AssetError, match="150 KB"):
        format_python("#" + "가" * 60_000)
    with pytest.raises(AssetError, match="syntax error"):
        format_python("def invalid(")


def test_focused_builtin_sources_use_the_shared_style_without_rewriting_evidence():
    from decision_layer.methods import registry

    for name in ("stats.regression_adjustment", "stats.binary_matching"):
        source = registry.get(name).source_snapshot
        assert source.editor_content == format_python(source.editor_content)
        assert source.authoring_content == source.editor_content
        assert '    python_method(\n' in source.editor_content
        path = Path("src/decision_layer/methods") / ("native_regression.py" if "regression" in name else "native_matching.py")
        assert source.files[0].content == path.read_text()

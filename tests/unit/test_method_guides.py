"""Contributor documentation shares executable examples and scenario scope."""
import importlib.util
import re
from pathlib import Path
import pytest
from tests.support.notebooks import execute_notebook

ROOT = Path(__file__).resolve().parents[2]
PAGES = ("methods", "method-patterns", "method-scenarios", "statistical-methods", "method-discovery")


@pytest.mark.parametrize("page", PAGES)
def test_translations_share_code_and_cases(page):
    en = (ROOT / f"docs/guides/{page}.md").read_text()
    ko = (ROOT / f"docs/ko/guides/{page}.md").read_text()
    pattern = r"```[^\n]*\n(.*?)```|^<<< ([^\n]+)$"
    assert re.findall(pattern, en, flags=re.M | re.S) == re.findall(pattern, ko, flags=re.M | re.S)
    if page == "method-scenarios":
        from examples.methods.scenarios.scenarios import scenarios
        for case in scenarios():
            assert f"| {case.name} |" in en and f"| {case.name} |" in ko


@pytest.mark.skipif(not importlib.util.find_spec("dowhy") or not importlib.util.find_spec("econml"),
                    reason="Install analytical extras for optional notebook")
async def test_optional_notebook_imports_the_tested_implementations(monkeypatch):
    namespace = await execute_notebook(ROOT / "docs/tutorials/methods/query_scenarios.ipynb", monkeypatch)
    assert namespace["trial"].result.status == "success"
    assert abs(namespace["dowhy_trial"].result.primary.data["value"] - 2) < .15
    assert abs(namespace["econml_trial"].result.primary.data["value"] - 2) < .15

"""Public example contracts must remain reproducible without downloading the workbook."""

import importlib.util
import json
from pathlib import Path


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "online-retail"


def test_public_reference_cases_and_pinned_source():
    spec = importlib.util.spec_from_file_location("online_retail_loader", EXAMPLE / "load.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads((EXAMPLE / "evals" / "cases.json").read_text())
    assert data["archive_sha256"] == module.SOURCE_SHA256
    assert len({case["id"] for case in data["cases"]}) == len(data["cases"])
    assert len(data["cases"]) == 9
    assert sum(bool(case.get("reference_sql")) for case in data["cases"]) == 7
    assert sum(case["expected"].get("answerable") is False for case in data["cases"]) == 2
    assert module.identifier(12345.0) == "12345"
    assert module.identifier(None) is None

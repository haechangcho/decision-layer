"""Execute the contributor journey and repeated individual notebook cells."""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

from tests.support.notebooks import execute_notebook

ROOT = Path(__file__).resolve().parents[2] / "examples/methods/patterns"


@pytest.mark.skipif(
    not all(importlib.util.find_spec(package) for package in ("IPython", "pandas", "dowhy")),
    reason="This tutorial requires pandas, IPython and DoWhy",
)
async def test_workshop_authoring_and_translated_examples(monkeypatch):
    ko = ROOT / "write_your_method.ko.ipynb"
    en = ROOT / "write_your_method.en.ipynb"

    def code_cells(path):
        return {
            cell["id"]: "".join(cell["source"])
            for cell in json.loads(path.read_text())["cells"]
            if cell["cell_type"] == "code"
        }

    ko_cells, en_cells = code_cells(ko), code_cells(en)
    assert ko_cells.keys() == en_cells.keys()
    assert [ast.dump(ast.parse(source)) for source in ko_cells.values()] == [
        ast.dump(ast.parse(source)) for source in en_cells.values()
    ]

    namespace = await execute_notebook(ko, monkeypatch)
    assert namespace["trial"].result.primary.data == [
        {"value_1": 30, "group_1": "A"},
        {"value_1": 20, "group_1": "B"},
        {"value_1": 10, "group_1": "C"},
    ]
    assert namespace["multi_trial"].result.primary.data == [
        {"value_1": 30, "value_2": 25, "group_1": "A", "group_2": "X"},
        {"value_1": 20, "value_2": 15, "group_1": "B", "group_2": "Y"},
        {"value_1": 10, "value_2": 5, "group_1": "C", "group_2": "Z"},
    ]
    assert len(namespace["multi_trial"].attempts) == 1
    assert [row["rank"] for row in namespace["edited_trial"].result.primary.data] == [1, 2, 3]
    assert [row["difference"] for row in namespace["peer_trial"].result.primary.data] == [4, 6]
    assert namespace["my_by_group"].manifest.version == "1.0.0"
    assert namespace["my_ranked_by_group"].manifest.version == "1.1.0"
    assert not namespace["RUN_LIVE"]
    assert namespace["live"] is None

    # Re-run out of order: every use cell creates its own connection and registry.
    for _ in range(2):
        for cell_id in ("run-peer", "run-ranked-group", "run-group", "run-multi-group"):
            pending = eval(
                compile(ko_cells[cell_id], cell_id, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT),
                namespace,
            )
            await pending
    assert len(namespace["trial"].attempts) == 1
    assert len(namespace["multi_trial"].attempts) == 1
    assert len(namespace["peer_trial"].attempts) == 3
    assert "rank" not in namespace["trial"].result.primary.data[0]

    if importlib.util.find_spec("dowhy"):
        semantic_result = namespace["dowhy_trial"].result.primary.data
        assert abs(semantic_result["value"] - 2) < 0.15
        assert semantic_result["estimator"] == "backdoor.linear_regression"
        assert semantic_result["assumptions_status"] == "not_verified"
        assert namespace["standalone_result"]["value"] == semantic_result["value"]
        assert namespace["refused_trial"].result.status == "refused"
        assert len(namespace["refused_trial"].attempts) == 1

        # Notebook definitions remain directly reviewable alongside their Python file.
        module = ast.parse((ROOT / "binary_regression.py").read_text())
        functions = {
            node.name: ast.dump(node)
            for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for cell_id in ("define-regression-calculation", "define-regression-method"):
            for node in ast.parse(ko_cells[cell_id]).body:
                assert ast.dump(node) == functions[node.name]
            assert "decision_layer.methods.statistics" not in ko_cells[cell_id]

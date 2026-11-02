"""Guard the treatment boundary: business questions never contain procedure hints."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location(
    "business_pilot", Path(__file__).parents[2] / "examples/complete-journey/evals/codex_pilot.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


@pytest.mark.parametrize("condition", ["cube", "cube_playbook", "decision_layer"])
def test_same_business_question_with_only_document_treatment(monkeypatch, tmp_path, condition):
    question = "10번 캠페인, 다음에도 진행할 만했는지 알려줘."
    doc = tmp_path / "guide.md"
    doc.write_text("Analyst-only OLS procedure, no answer values.")
    output = tmp_path / "output"
    args = ["pilot", "--question", question, "--condition", condition, "--output", str(output),
            "--model", "test-model", "--playbook", str(doc)]
    monkeypatch.setattr("sys.argv", args)

    def run(cmd, **kwargs):
        prompt = cmd[-1]
        assert prompt.endswith("Question: " + question)
        assert "OLS" not in prompt
        assert "benchmark-campaign" not in prompt
        assert "--model" in cmd and "test-model" in cmd
        guide = Path(kwargs["cwd"]) / "campaign-playbook.md"
        assert guide.exists() is (condition == "cube_playbook")
        if guide.exists():
            assert guide.read_text() == doc.read_text()
        config = next(c for c in cmd if c.startswith("mcp_servers."))
        assert config.startswith("mcp_servers.decision_layer=" if condition == "decision_layer"
                                 else "mcp_servers.cube=")
        stdout = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7}})
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(pilot.subprocess, "run", run)
    pilot.main()
    summary = json.loads((output / f"{condition}-summary.json").read_text())
    assert summary["question"] == question and summary["condition"] == condition


def test_document_condition_requires_a_document(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pilot", "--question", "Business question", "--condition", "cube_playbook"])
    with pytest.raises(SystemExit) as error:
        pilot.main()
    assert error.value.code == 2

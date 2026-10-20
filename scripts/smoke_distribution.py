"""Check the installed distribution without importing from the source checkout."""

import asyncio
import importlib.metadata
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

import decision_layer
from decision_layer.demo.runtime import ASSETS, prepare


assert (
    Path(decision_layer.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
)
print(
    "Installed:", importlib.metadata.version("decision-layer"), decision_layer.__file__
)
cli = Path(sys.executable).parent / "decision-layer"


def run(*args, cwd):
    return subprocess.check_output([str(cli), *args], cwd=cwd, text=True)


with tempfile.TemporaryDirectory(prefix="decision-layer-install-") as folder:
    root = Path(folder)
    assert "demo" in run("--help", cwd=root)
    assert "--cube-port" in run("demo", "--help", cwd=root)
    sample = prepare(root / "sample")
    assert all((sample.root / name).is_file() for name in ASSETS)
    assert "cubejs/cube:" in (sample.root / "compose.yaml").read_text()
    # Reproduce upgrading a demo created before editable starters existed.
    for kind in ("metric_lookup", "drilldown", "ols", "matching"):
        shutil.rmtree(sample.methods_dir / kind)
    (sample.root / "decision-layer.yaml").write_text(
        "config_version: 1\nname: sample_shop\n"
    )
    saved_run = sample.root / ".decision-layer" / "preserved-run.txt"
    saved_run.write_text("keep execution evidence")
    sample = prepare(sample.root)
    assert not sample.config.include_builtin_methods
    assert all(
        (sample.methods_dir / kind / "method.py").is_file()
        for kind in ("ols", "matching")
    )
    assert saved_run.read_text() == "keep execution evidence"
    run("init", "qa_team", cwd=root)
    project = root / "qa_team"
    for definition in (
        "metric_lookup/SKILL.md",
        "drilldown/SKILL.md",
        "ols/method.py",
        "matching/method.py",
    ):
        assert (project / "qa_team" / "methods" / definition).is_file()
    print(run("test", cwd=project))
    initial = json.loads(run("list", "--json", cwd=project))
    assert len(initial) == 4
    assert all(item["version"] == "2.0.0" for item in initial)
    assert all(
        Path(item["source"]).resolve().is_relative_to(project.resolve())
        for item in initial
    )
    run("new", "python", "rank", cwd=project)
    run("new", "skill", "review", cwd=project)
    print(run("check", cwd=project))
    methods = json.loads(run("list", "--json", cwd=project))
    assert {"qa_team.rank", "qa_team.review"} <= {item["name"] for item in methods}
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import pandas as pd
from qa_team.methods.rank.method import analyze
from decision_layer.console import create_console
from decision_layer.settings import Settings
from fastapi.testclient import TestClient
from pathlib import Path
result = analyze(pd.DataFrame({'group': ['A', 'B', 'C'], 'value': [30, 20, 20]}))
assert result['rank'].tolist() == [1.0, 2.0, 2.0]
with TestClient(create_console(Settings(project_dir=str(Path.cwd()), database_url='memory')), base_url='http://localhost') as client:
    assert client.get('/ui/methods/qa_team.rank').status_code == 200
    assert 'text/html' in client.get('/ui/').headers['content-type']
    response = client.get('/api/methods/qa_team.rank')
    assert response.status_code == 200, response.text
print('Installed CLI, calculation and API discovery passed')
""",
        ],
        cwd=project,
        check=True,
    )

from smoke_mcp import verify_mcp

asyncio.run(verify_mcp())

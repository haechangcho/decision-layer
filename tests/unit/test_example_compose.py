"""Check example isolation without starting containers or downloading data."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "complete-journey"


def compose_config(*args: str) -> dict:
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is required to render example configuration")
    result = subprocess.run(
        ["docker", "compose", *args, "config", "--format", "json"],
        cwd=EXAMPLE,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_examples_have_separate_state_and_expected_providers():
    cube = compose_config()
    dbt = compose_config("-f", "compose.yaml", "-f", "compose.dbt.yaml")

    assert cube["name"] == "decision-layer-cube"
    assert dbt["name"] == "decision-layer-dbt"
    assert "cube" in cube["services"] and "metricflow" not in cube["services"]
    assert "metricflow" in dbt["services"] and "cube" not in dbt["services"]
    assert cube["services"]["api"]["environment"]["DL_DEFAULT_SOURCE_PROVIDER"] == "cube"
    assert dbt["services"]["api"]["environment"]["DL_DEFAULT_SOURCE_PROVIDER"] == "metricflow"

    for volume in ("postgres_data", "runs", "source_cache"):
        assert cube["volumes"][volume]["name"] != dbt["volumes"][volume]["name"]

    mounts = []
    for config in (cube, dbt):
        mounts.append({m["target"]: m for m in config["services"]["api"]["volumes"]})
        assert set(mounts[-1]) == {"/recipes", "/data"}
        assert mounts[-1]["/data"]["type"] == "volume"
    assert Path(mounts[0]["/recipes"]["source"]).name == "recipes"
    assert Path(mounts[1]["/recipes"]["source"]).name == "recipes-dbt"


@pytest.mark.parametrize("name", ["decision-layer-cube", "decision-layer-dbt"])
def test_documented_project_names_match_defaults(name):
    files = [] if name.endswith("cube") else ["-f", "compose.yaml", "-f", "compose.dbt.yaml"]
    assert compose_config("-p", name, *files)["name"] == name

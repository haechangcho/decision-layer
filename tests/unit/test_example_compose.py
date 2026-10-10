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


def test_local_example_uses_cube_and_preserves_state():
    cube = compose_config()
    assert cube["name"] == "decision-layer-cube"
    assert set(cube["services"]) == {"postgres", "import", "cube", "api", "web"}
    assert cube["services"]["api"]["environment"]["DL_DEFAULT_SOURCE_PROVIDER"] == "cube"
    mounts = {m["target"]: m for m in cube["services"]["api"]["volumes"]}
    assert set(mounts) == {"/recipes", "/data"}
    assert mounts["/data"]["type"] == "volume"
    assert Path(mounts["/recipes"]["source"]).name == "recipes"


def test_documented_project_name_matches_default():
    assert compose_config("-p", "decision-layer-cube")["name"] == "decision-layer-cube"

import importlib.util
from pathlib import Path
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "examples/complete-journey"
spec = importlib.util.spec_from_file_location("journey_loader", FOLDER / "load.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


def test_corrupt_archive_refused(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("transaction_data.csv", "fake")
    with pytest.raises(ValueError, match="checksum"):
        loader.validate_archive(archive)


def test_source_and_semantic_boundaries():
    assert len(loader.HEADERS) == 8
    assert "classification_1" in loader.HEADERS["hh_demographic"]
    cubes = [cube for path in (FOLDER / "cube/model/cubes").glob("*.yml") for cube in yaml.safe_load(path.read_text())["cubes"]]
    assert len(cubes) == len({cube["name"] for cube in cubes}) == 6
    transactions = next(cube for cube in cubes if cube["name"] == "transaction")
    assert {join["name"] for join in transactions["joins"]} == {"product", "household"}
    time = next(item for item in transactions["dimensions"] if item["name"] == "analysis_date")
    assert time["sql"] == "transaction_date" and time["type"] == "time"
    assert time["meta"]["suggestedDateRange"] == ["2000-01-01", "2001-12-11"]
    assert time["meta"]["calendarType"] == "mapped"
    campaign = next(cube for cube in cubes if cube["name"] == "campaign")
    assert {item["sql"] for item in campaign["dimensions"] if item["type"] == "time"} == {"start_date", "end_date"}

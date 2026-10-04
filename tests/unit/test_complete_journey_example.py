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
    model = yaml.safe_load((FOLDER / "cube/model/cubes/retail.yml").read_text())
    transactions = model["cubes"][0]
    assert {join["name"] for join in transactions["joins"]} == {"product", "household"}
    assert "2000-01-01" in transactions["sql"]

"""The public example refuses changed source bytes before touching a database."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "chinook"


@pytest.fixture
def loader():
    spec = importlib.util.spec_from_file_location("chinook_loader", EXAMPLE / "load.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_changed_upstream_bytes_are_rejected_before_parsing(loader, tmp_path):
    source = tmp_path / "changed.json"
    source.write_text('{"Genre": []}')
    with pytest.raises(ValueError, match="checksum changed"):
        loader.read_source(source)


def test_matching_digest_does_not_bypass_dataset_structure_checks(loader, monkeypatch, tmp_path):
    source = tmp_path / "source.json"
    source.write_text('{"Genre": []}')
    monkeypatch.setattr(loader, "SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="table list"):
        loader.read_source(source)
    monkeypatch.setattr(loader, "TABLES", {"Genre": ("genre", 25)})
    with pytest.raises(ValueError, match="row count"):
        loader.read_source(source)


def test_reference_cases_pin_the_same_release_as_the_importer(loader):
    cases = json.loads((EXAMPLE / "evals/cases.json").read_text())
    assert cases["source_url"] == loader.SOURCE_URL
    assert cases["source_sha256"] == loader.SOURCE_SHA256
    assert len({case["id"] for case in cases["cases"]}) == len(cases["cases"])

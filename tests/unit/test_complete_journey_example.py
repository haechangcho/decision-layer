import importlib.util
from pathlib import Path
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "src/decision_layer/demo/assets/journey"
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
    cubes = [
        cube
        for path in (FOLDER / "cube/model/cubes").glob("*.yml")
        for cube in yaml.safe_load(path.read_text())["cubes"]
    ]
    assert len(cubes) == len({cube["name"] for cube in cubes}) == 11
    transactions = next(cube for cube in cubes if cube["name"] == "transaction")
    assert {join["name"] for join in transactions["joins"]} == {"product", "household"}
    time = next(
        item for item in transactions["dimensions"] if item["name"] == "analysis_date"
    )
    assert time["sql"] == "transaction_date" and time["type"] == "time"
    assert "meta" not in time
    assert all(
        "meta" not in member
        for cube in cubes
        for member in [*cube.get("dimensions", []), *cube.get("measures", [])]
    )
    campaign = next(cube for cube in cubes if cube["name"] == "campaign")
    assert {
        item["sql"] for item in campaign["dimensions"] if item["type"] == "time"
    } == {"start_date", "end_date"}
    outcomes = next(
        cube for cube in cubes if cube["name"] == "campaign_household_outcomes"
    )
    assert "WHERE eligible" in outcomes["sql"]
    assert (
        next(m for m in outcomes["measures"] if m["name"] == "post_sales_mean")["type"]
        == "avg"
    )
    assert (
        next(d for d in outcomes["dimensions"] if d.get("primary_key"))["name"]
        == "observation_id"
    )


def test_every_original_table_column_has_a_semantic_member():
    import re

    models = {
        cube["name"]: cube
        for path in (FOLDER / "cube/model/cubes").glob("*.yml")
        for cube in yaml.safe_load(path.read_text())["cubes"]
    }
    names = {"transaction_data": "transaction", "campaign_desc": "campaign",
             "campaign_table": "campaign_contact", "coupon_redempt": "redemption"}
    for table, headers in loader.HEADERS.items():
        cube = models[names.get(table, table)]
        assert "journey." + table in cube.get("sql_table", cube.get("sql", ""))
        members = [*cube.get("dimensions", []), *cube.get("measures", [])]
        exposed = {m["sql"].split("::")[0] for m in members
                   if m.get("public", not m.get("primary_key", False))
                   and re.fullmatch(r"\w+(?:::\w+)?", m.get("sql", ""))}
        assert set(headers.lower().split()) <= exposed, (table, exposed)

    # Product mappings are not a unique coupon dimension for redemption facts.
    assert "coupon" not in {j["name"] for j in models["redemption"]["joins"]}
    for name in ("coupon", "causal_data"):
        key = next(d for d in models[name]["dimensions"] if d.get("primary_key"))
        assert key["public"] is False
        assert "row_number" not in models[name]["sql"].lower()


def test_dbt_example_needs_no_decision_layer_annotations():
    models = ROOT / "examples/complete-journey/dbt/models"
    for path in models.glob("*.yml"):
        definitions = yaml.safe_load(path.read_text())
        for metric in definitions.get("metrics", []):
            assert "decision_layer" not in metric.get("config", {}).get("meta", {})
    transaction = yaml.safe_load((models / "transactions.yml").read_text())
    rate = next(m for m in transaction["metrics"] if m["name"] == "coupon_line_rate")
    assert (
        rate["type_params"]["expr"]
        == "100.0 * coupon_lines / nullif(transaction_count, 0)"
    )

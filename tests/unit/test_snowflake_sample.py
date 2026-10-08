import importlib.util
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "examples/complete-journey"
spec = importlib.util.spec_from_file_location("snowflake_sample", FOLDER / "snowflake/copy_sample.py")
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)


@pytest.mark.parametrize("value", ["foo;DROP TABLE bar", "a.b", "a'", "", "1abc"])
def test_sample_identifiers_refuse_sql(value):
    with pytest.raises(ValueError, match="identifier"):
        sample.identifier(value)


def test_sample_table_scope_and_precision():
    assert len(sample.TABLES) == 10
    assert sample.identifier("dl_journey_test") == "DL_JOURNEY_TEST"
    assert sample.TYPES["numeric"] == "NUMBER(38,10)"
    assert sample.TYPES["date"] == "DATE"


def test_sample_manifest_refuses_unknown_source(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"source_sha256": "other"}))
    with pytest.raises(ValueError, match="source checksum"):
        sample.read_manifest(tmp_path)


def test_sample_manifest_refuses_modified_exports(tmp_path):
    tables = []
    for name in sample.TABLES:
        path = tmp_path / f"{name}.csv.gz"
        path.write_bytes(b"sample")
        tables.append({"name": name, "columns": [{"name": "ID", "type": "VARCHAR"}],
                       "rows": 1, "sha256": sample.digest(path)})
    (tmp_path / "manifest.json").write_text(json.dumps({
        "source_sha256": sample.SOURCE_SHA256, "tables": tables,
    }))
    assert sample.read_manifest(tmp_path)["tables"] == tables
    (tmp_path / "product.csv.gz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="file changed"):
        sample.read_manifest(tmp_path)


def test_dbt_time_spine_dialects_and_decimal_precision():
    source = (FOLDER / "dbt/models/time_spine.sql").read_text()
    assert "target.type == 'snowflake'" in source
    assert "generator(rowcount => 1826)" in source
    assert "generate_series" in source
    assert (date(2003, 12, 31) - date(1999, 1, 1)).days + 1 == 1826
    assert "decimal(18, 4)" in (FOLDER / "dbt/models/transactions.sql").read_text()


@pytest.mark.parametrize("existing", [False, True])
def test_upload_verifies_sample_and_never_replaces_compute(tmp_path, monkeypatch, existing):
    manifest = {"tables": [{"name": name, "columns": [{"name": "ID", "type": "VARCHAR"}],
                            "rows": 2} for name in sample.TABLES],
                "baseline": {"receipts": "12.34", "first_date": "2000-01-01", "last_date": "2001-12-11"}}
    monkeypatch.setattr(sample, "read_manifest", lambda folder: manifest)
    monkeypatch.setattr(sample.getpass, "getpass", lambda prompt: "test-secret")

    class Cursor:
        statements = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            self.statements.append(statement)

        def fetchall(self):
            if self.statements[-1] == "SHOW WAREHOUSES" and existing:
                return [("DL_TEST_WH",)]
            return []

        def fetchone(self):
            if "SUM(CAST" in self.statements[-1]:
                return ("12.34", date(2000, 1, 1), date(2001, 12, 11))
            return (2,)

    cursor = Cursor()

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def cursor(self):
            return cursor

    connector = SimpleNamespace(connect=lambda **kwargs: Connection())
    monkeypatch.setitem(sys.modules, "snowflake", SimpleNamespace(connector=connector))
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    if existing:
        with pytest.raises(ValueError, match="Warehouse already exists"):
            sample.upload_sample(tmp_path, "org-account", "user", "DL_JOURNEY_TEST", "DL_TEST_WH")
        assert cursor.statements == ["SHOW WAREHOUSES"]
    else:
        sample.upload_sample(tmp_path, "org-account", "user", "DL_JOURNEY_TEST", "DL_TEST_WH")
        assert sum(s.startswith("COPY INTO") for s in cursor.statements) == 10
        assert cursor.statements[-1] == "ALTER WAREHOUSE DL_TEST_WH SUSPEND"
        assert any("NULL_IF=('\\\\N')" in s and "EMPTY_FIELD_AS_NULL=FALSE" in s
                   for s in cursor.statements)
        assert not any("REPLACE" in s or "TRUNCATE" in s or "DROP" in s for s in cursor.statements)


def test_dbt_identity_permissions_are_limited_to_sample_and_model_schema(monkeypatch):
    monkeypatch.setitem(sys.modules, "copy_sample", sample)
    spec = importlib.util.spec_from_file_location("dbt_test_setup", FOLDER / "snowflake/setup_dbt.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    sql = setup.statements("DL_JOURNEY_TEST", "DL_TEST_WH", "a2V5")
    assert sum("GRANT SELECT ON TABLE" in s for s in sql) == 10
    assert "GRANT CREATE TABLE, CREATE VIEW ON SCHEMA DL_JOURNEY_TEST.ANALYTICS TO ROLE DL_DBT_TEST_ROLE" in sql
    assert sql[-1] == "GRANT ROLE DL_DBT_TEST_ROLE TO USER DL_DBT_TEST"
    assert not any(word in "\n".join(sql) for word in ["ACCOUNTADMIN", "ALL PRIVILEGES", "FUTURE", "TO ROLE PUBLIC", "CREATE SCHEMA ON DATABASE"])
    assert "TYPE=SERVICE" in sql[-2]
    with pytest.raises(ValueError):
        setup.statements("db;drop", "DL_TEST_WH", "a2V5")
    with pytest.raises(ValueError):
        setup.statements("DL_JOURNEY_TEST", "DL_TEST_WH", "bad'key")

"""Check independent SQL references and source integrity in a read-only transaction."""

from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def comparable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def verify():
    cases = json.loads(Path(__file__).with_name("cases.json").read_text())
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT source_sha256 FROM demo_meta.imports WHERE dataset = 'chinook-1.4.5'")
            assert cursor.fetchone()["source_sha256"] == cases["source_sha256"]
            cursor.execute("SELECT count(*) AS tables FROM information_schema.tables WHERE table_schema = 'chinook'")
            assert cursor.fetchone()["tables"] == 11
            cursor.execute("SELECT bool_and(NOT has_table_privilege('chinook_reader', table_schema || '.' || table_name, 'INSERT,UPDATE,DELETE')) AS read_only FROM information_schema.tables WHERE table_schema = 'chinook'")
            assert cursor.fetchone()["read_only"] is True
            checked = 0
            for case in cases["cases"]:
                if not case.get("reference_sql"):
                    continue
                cursor.execute(case["reference_sql"])
                actual = {key: comparable(value) for key, value in cursor.fetchone().items()}
                if actual != case["expected"]:
                    raise AssertionError(f"{case['id']}: expected {case['expected']}, got {actual}")
                checked += 1
                print(f"{case['id']}: {actual}", flush=True)
    print(f"Verified 11 tables and {checked} numeric cases; refusal cases require interpretation review.")


if __name__ == "__main__":
    verify()

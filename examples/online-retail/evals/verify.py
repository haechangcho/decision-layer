"""Check the public reference answers against the pinned imported source."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def comparable(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def verify() -> None:
    cases = json.loads(Path(__file__).with_name("cases.json").read_text())["cases"]
    checked = 0
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            for case in cases:
                if not case.get("reference_sql"):
                    continue
                cursor.execute(case["reference_sql"])
                row = cursor.fetchone()
                actual = {key: comparable(value) for key, value in row.items()}
                if actual != case["expected"]:
                    raise AssertionError(f"{case['id']}: expected {case['expected']}, got {actual}")
                checked += 1
                print(f"{case['id']}: {actual}", flush=True)
    print(f"Verified {checked} numeric reference cases; {len(cases) - checked} refusal cases need human review.")


if __name__ == "__main__":
    verify()

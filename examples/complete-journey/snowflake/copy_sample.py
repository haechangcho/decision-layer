"""Copy only the pinned local retail sample to an isolated Snowflake database."""
from __future__ import annotations

import argparse
from decimal import Decimal
import getpass
import gzip
import hashlib
import json
import os
from pathlib import Path
import re

TABLES = (
    "campaign_desc", "campaign_table", "causal_data", "coupon", "coupon_redempt",
    "hh_demographic", "product", "transaction_data", "household",
    "campaign_household_outcomes",
)
SOURCE_SHA256 = "5e0a3d72fe8562fe0ab995f70fb58b74359e8ec4bbccd1521e2b137da0558f9a"
TYPES = {
    "text": "VARCHAR", "character varying": "VARCHAR", "date": "DATE",
    "boolean": "BOOLEAN", "integer": "NUMBER(38,0)", "bigint": "NUMBER(38,0)",
    "smallint": "NUMBER(38,0)", "numeric": "NUMBER(38,10)",
}


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid SQL identifier: {value!r}")
    return value.upper()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export_sample(folder: Path, dsn: str) -> None:
    import psycopg
    from psycopg import sql

    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError("Use an empty export directory; existing files are not overwritten.")
    manifest = {"source_sha256": SOURCE_SHA256, "tables": []}
    # A single read-only snapshot keeps raw and derived rows consistent during export.
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SELECT table_name, source_sha256, rows FROM journey_meta.imports")
        pins = cursor.fetchall()
        if (len(pins) != 8 or {row[0] for row in pins} != set(TABLES[:8])
                or any(row[1] != SOURCE_SHA256 for row in pins)):
            raise ValueError("This is not the pinned Complete Journey sample database.")
        expected_rows = {row[0]: row[2] for row in pins}
        for table in TABLES:
            cursor.execute(
                "SELECT a.attname, format_type(a.atttypid, NULL) "
                "FROM pg_attribute a WHERE a.attrelid = %s::regclass "
                "AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum",
                (f"journey.{table}",),
            )
            columns = [{"name": identifier(name), "type": TYPES[kind]}
                       for name, kind in cursor.fetchall()]
            if not columns:
                raise ValueError(f"Missing table: {table}")
            cursor.execute(sql.SQL("SELECT count(*) FROM journey.{}").format(sql.Identifier(table)))
            rows = cursor.fetchone()[0]
            if table in expected_rows and rows != expected_rows[table]:
                raise ValueError(f"Source row count differs from the pinned import: {table}")
            path = folder / f"{table}.csv.gz"
            with gzip.open(path, "wb", compresslevel=1) as output, cursor.copy(
                sql.SQL("COPY (SELECT * FROM journey.{}) TO STDOUT WITH (FORMAT CSV, NULL '\\N')")
                .format(sql.Identifier(table))
            ) as copy:
                for block in copy:
                    output.write(block)
            manifest["tables"].append({
                "name": table, "columns": columns, "rows": rows, "sha256": digest(path),
            })
            print(f"Exported {table}: {rows:,} rows", flush=True)
        cursor.execute("SELECT sum(cast(sales_value as decimal(18,4))), min(transaction_date), "
                       "max(transaction_date) FROM journey.transaction_data")
        receipts, first_date, last_date = cursor.fetchone()
        manifest["baseline"] = {
            "receipts": str(receipts), "first_date": str(first_date), "last_date": str(last_date),
        }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def read_manifest(folder: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest["source_sha256"] != SOURCE_SHA256:
        raise ValueError("Unexpected sample source checksum.")
    tables = manifest["tables"]
    if len(tables) != len(TABLES) or {t["name"] for t in tables} != set(TABLES):
        raise ValueError("Unexpected sample tables.")
    for table in tables:
        for column in table["columns"]:
            identifier(column["name"])
            if column["type"] not in TYPES.values():
                raise ValueError("Unexpected column type.")
        if digest(folder / f"{table['name']}.csv.gz") != table["sha256"]:
            raise ValueError(f"Export file changed: {table['name']}")
    return manifest


def upload_sample(folder: Path, account: str, user: str, database: str, warehouse: str) -> None:
    import snowflake.connector

    database, warehouse = identifier(database), identifier(warehouse)
    manifest = read_manifest(folder)
    password = getpass.getpass("Snowflake password (not saved): ")
    passcode = getpass.getpass("MFA code (Enter for push approval or if not enrolled): ")
    with snowflake.connector.connect(
        account=account, user=user, password=password,
        authenticator="username_password_mfa", client_request_mfa_token=False,
        **({"passcode": passcode} if passcode else {}),
        role="ACCOUNTADMIN",
        login_timeout=120, session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 600},
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW WAREHOUSES")
        if any(row[0] == warehouse for row in cursor.fetchall()):
            raise ValueError("Warehouse already exists. Choose a new --warehouse; existing compute is not changed.")
        cursor.execute(f"CREATE WAREHOUSE IF NOT EXISTS {warehouse} "
                       "WAREHOUSE_SIZE='XSMALL' AUTO_SUSPEND=60 AUTO_RESUME=TRUE "
                       "INITIALLY_SUSPENDED=TRUE")
        cursor.execute(f"USE WAREHOUSE {warehouse}")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database}")
        cursor.execute(f"USE DATABASE {database}")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS JOURNEY")
        cursor.execute("USE SCHEMA JOURNEY")
        cursor.execute("SHOW TABLES IN SCHEMA JOURNEY")
        if cursor.fetchall():
            raise ValueError("Destination schema already has tables. Use a new database; nothing is overwritten.")
        cursor.execute("CREATE TEMPORARY STAGE SAMPLE_UPLOAD")
        for table in manifest["tables"]:
            name = identifier(table["name"])
            columns = ", ".join(f"{identifier(c['name'])} {c['type']}" for c in table["columns"])
            cursor.execute(f"CREATE TABLE {name} ({columns})")
            path = (folder / f"{table['name']}.csv.gz").resolve()
            if "'" in str(path):
                raise ValueError("Export path cannot contain a single quote.")
            cursor.execute(f"PUT 'file://{path}' @SAMPLE_UPLOAD AUTO_COMPRESS=FALSE")
            cursor.execute(
                f"COPY INTO {name} FROM @SAMPLE_UPLOAD/{path.name} "
                "FILE_FORMAT=(TYPE=CSV COMPRESSION=GZIP FIELD_OPTIONALLY_ENCLOSED_BY='\"' "
                "NULL_IF=('\\\\N') EMPTY_FIELD_AS_NULL=FALSE ESCAPE_UNENCLOSED_FIELD=NONE) "
                "ON_ERROR=ABORT_STATEMENT"
            )
            cursor.execute(f"SELECT COUNT(*) FROM {name}")
            if cursor.fetchone()[0] != table["rows"]:
                raise ValueError(f"Row count mismatch: {name}")
            print(f"Verified {name}: {table['rows']:,} rows", flush=True)
        cursor.execute("SELECT SUM(CAST(SALES_VALUE AS NUMBER(18,4))), "
                       "MIN(TRANSACTION_DATE), MAX(TRANSACTION_DATE) FROM TRANSACTION_DATA")
        receipts, first_date, last_date = cursor.fetchone()
        baseline = manifest["baseline"]
        if (Decimal(str(receipts)) != Decimal(baseline["receipts"])
                or str(first_date) != baseline["first_date"] or str(last_date) != baseline["last_date"]):
            raise ValueError("Receipt total or date coverage differs from the PostgreSQL snapshot.")
        cursor.execute(f"ALTER WAREHOUSE {warehouse} SUSPEND")
        print(f"Verified receipts={receipts}, dates={first_date}..{last_date}; warehouse suspended.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "upload"])
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--account")
    parser.add_argument("--user")
    parser.add_argument("--database", default="DL_JOURNEY_TEST")
    parser.add_argument("--warehouse", default="DL_TEST_WH")
    args = parser.parse_args()
    if args.action == "export":
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            parser.error("Export needs DATABASE_URL for the local sample database.")
        export_sample(args.directory, dsn)
    else:
        if not args.account or not args.user:
            parser.error("Upload needs --account and --user.")
        upload_sample(args.directory, args.account, args.user, args.database, args.warehouse)


if __name__ == "__main__":
    main()

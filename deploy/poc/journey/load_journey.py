"""Load and verify Complete Journey in the explicitly provisioned PoC database."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from decision_layer.demo.assets.journey.load import (
    HEADERS,
    SOURCE_SHA256,
    load,
    validate_archive,
)
from decision_layer.demo.assets.journey.verify import verify

DATABASE = "dl_demo_journey"
LOADER = "dl_demo_loader"
READER = "dl_demo_reader"


def check_existing_schemas(cur, owner):
    """Refuse foreign or incomplete schemas before an import touches them."""
    cur.execute("""SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace
        WHERE nspname IN ('journey', 'journey_meta')""")
    schemas = dict(cur.fetchall())
    if schemas and (
        set(schemas) != {"journey", "journey_meta"}
        or any(value != owner for value in schemas.values())
    ):
        raise ValueError(
            "Unexpected existing schemas; inspect the database before importing."
        )
    if schemas:
        cur.execute("SELECT to_regclass('journey_meta.imports') IS NOT NULL")
        if not cur.fetchone()[0]:
            raise ValueError(
                "Existing data has no import marker; refusing to modify it."
            )
        cur.execute("SELECT table_name, source_sha256 FROM journey_meta.imports")
        imports = cur.fetchall()
        if {table for table, _ in imports} != set(HEADERS) or any(
            digest != SOURCE_SHA256 for _, digest in imports
        ):
            raise ValueError(
                "Existing import marker does not match the pinned archive."
            )
    return not schemas


def preflight(database_url):
    """Reject other databases, foreign schemas, or unexpectedly powerful roles."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("""SELECT current_database(), current_user, session_user,
            pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()""")
        if cur.fetchone() != (DATABASE, LOADER, LOADER, LOADER):
            raise ValueError(
                "Connect as dl_demo_loader to its owned dl_demo_journey database."
            )
        cur.execute(
            """SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
            rolreplication, rolbypassrls FROM pg_roles WHERE rolname IN (%s, %s)""",
            (LOADER, READER),
        )
        roles = {row[0]: row[1:] for row in cur.fetchall()}
        if roles != {
            LOADER: (True, False, False, False, False, False),
            READER: (True, False, False, False, False, False),
        }:
            raise ValueError(
                "The two dedicated roles are missing or have unexpected privileges."
            )
        cur.execute(
            """SELECT EXISTS (
              SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
              WHERE r.rolname IN (%s, %s)
            )""",
            (LOADER, READER),
        )
        if cur.fetchone()[0]:
            raise ValueError("The dedicated roles must not be members of other roles.")
        check_existing_schemas(cur, LOADER)
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def preflight_sampledb(database_url):
    """Allow this STG exception only for the explicitly approved DB and account."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("""SELECT current_database(), current_user, session_user,
            has_database_privilege(current_user, current_database(), 'CREATE')""")
        if cur.fetchone() != ("sampledb", "sampleuser", "sampleuser", True):
            raise ValueError(
                "Connect as sampleuser to sampledb with schema CREATE privilege."
            )
        return check_existing_schemas(cur, "sampleuser")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        required=True,
        type=Path,
        help="Path to the official Complete Journey zip",
    )
    parser.add_argument(
        "--existing-sampledb",
        action="store_true",
        help="Use sampleuser and isolated journey schemas in the existing STG sampledb",
    )
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error(
            "Set DATABASE_URL for the dedicated loader; use PGPASSFILE for the password."
        )
    validate_archive(args.archive)
    require_new_schemas = False
    if args.existing_sampledb:
        require_new_schemas = preflight_sampledb(database_url)
    else:
        preflight(database_url)
    load(
        database_url,
        supplied=args.archive,
        manage_reader=False,
        require_new_schemas=require_new_schemas,
    )
    if args.existing_sampledb:
        print(json.dumps(verify(database_url), ensure_ascii=False))
        return
    # Only the new schema is granted; admin credentials never enter the importer.
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("GRANT USAGE ON SCHEMA journey TO dl_demo_reader")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA journey TO dl_demo_reader")
        cur.execute(
            """SELECT has_schema_privilege(%s, 'journey', 'USAGE'),
            has_table_privilege(%s, 'journey.transaction_data', 'SELECT'),
            has_table_privilege(%s, 'journey.transaction_data', 'INSERT'),
            has_schema_privilege(%s, 'journey', 'CREATE')""",
            (READER, READER, READER, READER),
        )
        if cur.fetchone() != (True, True, False, False):
            raise ValueError("Reader privileges do not match the read-only contract.")
    print(json.dumps(verify(database_url), ensure_ascii=False))


if __name__ == "__main__":
    main()

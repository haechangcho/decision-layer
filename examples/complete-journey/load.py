"""Stream the pinned official Complete Journey archive into an isolated database."""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
from urllib.request import urlopen
import zipfile

SOURCE_URL = "https://downloads.ctfassets.net/psj0p18eh7z1/3e9OAF7F9ONT4pwJc1luEw/d56af8aabad51bdb9888aad0240bd105/dunnhumby_The-Complete-Journey.zip"
SOURCE_SHA256 = "5e0a3d72fe8562fe0ab995f70fb58b74359e8ec4bbccd1521e2b137da0558f9a"
HEADERS = {
    "campaign_desc": "DESCRIPTION CAMPAIGN START_DAY END_DAY",
    "campaign_table": "DESCRIPTION household_key CAMPAIGN",
    "causal_data": "PRODUCT_ID STORE_ID WEEK_NO display mailer",
    "coupon": "COUPON_UPC PRODUCT_ID CAMPAIGN",
    "coupon_redempt": "household_key DAY COUPON_UPC CAMPAIGN",
    "hh_demographic": "classification_1 classification_2 classification_3 HOMEOWNER_DESC classification_5 classification_4 KID_CATEGORY_DESC household_key",
    "product": "PRODUCT_ID MANUFACTURER DEPARTMENT BRAND COMMODITY_DESC SUB_COMMODITY_DESC CURR_SIZE_OF_PRODUCT",
    "transaction_data": "household_key BASKET_ID DAY PRODUCT_ID QUANTITY SALES_VALUE STORE_ID RETAIL_DISC TRANS_TIME WEEK_NO COUPON_DISC COUPON_MATCH_DISC",
}


def validate_archive(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("Official archive checksum changed; review the source before updating the pin.")
    with zipfile.ZipFile(path) as archive:
        for table, header in HEADERS.items():
            names = [n for n in archive.namelist() if n.endswith("/" + table + ".csv")]
            if len(names) != 1:
                raise ValueError(f"Missing or ambiguous table: {table}")
            with io.TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig") as stream:
                if next(csv.reader(stream)) != header.split():
                    raise ValueError(f"Unexpected source columns: {table}")


def source_path():
    supplied = Path("/input/complete-journey.zip")
    if supplied.is_file():
        validate_archive(supplied)
        return supplied
    cached = Path("/cache/complete-journey.zip")
    if not cached.is_file():
        cached.parent.mkdir(parents=True, exist_ok=True)
        temporary = cached.with_suffix(".download")
        with urlopen(SOURCE_URL, timeout=180) as response, temporary.open("wb") as target:
            while block := response.read(1024 * 1024):
                target.write(block)
        validate_archive(temporary)
        temporary.replace(cached)
    validate_archive(cached)
    return cached


def load():
    import psycopg
    from psycopg import sql
    source = source_path()
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(671821204)")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS journey_meta")
        cursor.execute("CREATE TABLE IF NOT EXISTS journey_meta.imports (table_name text PRIMARY KEY, source_sha256 text NOT NULL, rows bigint NOT NULL)")
        cursor.execute("SELECT table_name, source_sha256, rows FROM journey_meta.imports")
        previous = cursor.fetchall()
        if previous:
            if {r[0] for r in previous} != set(HEADERS) or any(r[1] != SOURCE_SHA256 for r in previous):
                raise ValueError("Existing import differs from the pinned source; use a new volume.")
            for table, _, count in previous:
                cursor.execute(sql.SQL("SELECT count(*) FROM journey.{}").format(sql.Identifier(table)))
                if cursor.fetchone()[0] != count:
                    raise ValueError(f"Existing table changed: {table}")
            cursor.execute(Path(__file__).with_name("calendar.sql").read_text())
            cursor.execute(Path(__file__).with_name("campaign_outcomes.sql").read_text())
            cursor.execute("GRANT SELECT ON journey.campaign_household_outcomes TO journey_reader")
            print("Pinned Complete Journey import already present.", flush=True)
            return
        cursor.execute("CREATE SCHEMA journey")
        with zipfile.ZipFile(source) as archive:
            for table, headers in HEADERS.items():
                columns = [h.lower() for h in headers.split()]
                cursor.execute(sql.SQL("CREATE TABLE journey.{} ({})").format(
                    sql.Identifier(table), sql.SQL(", ").join(sql.SQL("{} text NOT NULL").format(sql.Identifier(c)) for c in columns)))
                name = next(n for n in archive.namelist() if n.endswith("/" + table + ".csv"))
                count = 0
                with io.TextIOWrapper(archive.open(name), encoding="utf-8-sig") as stream:
                    reader = csv.reader(stream)
                    next(reader)
                    with cursor.copy(sql.SQL("COPY journey.{} FROM STDIN").format(sql.Identifier(table))) as copy:
                        for row in reader:
                            if len(row) != len(columns):
                                raise ValueError(f"Inconsistent row in {table}")
                            copy.write_row(row)
                            count += 1
                cursor.execute("INSERT INTO journey_meta.imports VALUES (%s, %s, %s)", (table, SOURCE_SHA256, count))
                print(f"{table}: {count:,} rows", flush=True)
        # Keep original coded demographics and source identifiers; never guess their meanings.
        cursor.execute("CREATE UNIQUE INDEX product_key ON journey.product(product_id)")
        cursor.execute("CREATE UNIQUE INDEX demographic_key ON journey.hh_demographic(household_key)")
        cursor.execute("CREATE UNIQUE INDEX campaign_key ON journey.campaign_desc(campaign)")
        cursor.execute("CREATE INDEX transaction_household ON journey.transaction_data(household_key)")
        cursor.execute("CREATE INDEX transaction_product ON journey.transaction_data(product_id)")
        cursor.execute("CREATE INDEX recipient_household ON journey.campaign_table(household_key)")
        cursor.execute("CREATE TABLE journey.household AS SELECT DISTINCT household_key FROM journey.transaction_data")
        cursor.execute("CREATE UNIQUE INDEX household_key ON journey.household(household_key)")
        cursor.execute(Path(__file__).with_name("calendar.sql").read_text())
        cursor.execute(Path(__file__).with_name("campaign_outcomes.sql").read_text())
        cursor.execute("CREATE ROLE journey_reader LOGIN PASSWORD 'local-read-only'")
        cursor.execute("GRANT USAGE ON SCHEMA journey TO journey_reader")
        cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA journey TO journey_reader")
    print("Import complete; Cube uses SELECT-only credentials.", flush=True)


if __name__ == "__main__":
    load()

"""Import pinned upstream data into the isolated Chinook example database."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import urlopen


SOURCE_URL = "https://github.com/lerocha/chinook-database/releases/download/v1.4.5/ChinookData.json"
SOURCE_SHA256 = "2998161de437518e3447e779c7ce7418f081895e388081bff315f3c258752d8c"
TABLES = {
    "Genre": ("genre", 25),
    "MediaType": ("media_type", 5),
    "Artist": ("artist", 275),
    "Album": ("album", 347),
    "Track": ("track", 3503),
    "Employee": ("employee", 8),
    "Customer": ("customer", 59),
    "Invoice": ("invoice", 412),
    "InvoiceLine": ("invoice_line", 2240),
    "Playlist": ("playlist", 18),
    "PlaylistTrack": ("playlist_track", 8715),
}


def column_name(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def read_source(path: Path) -> dict:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        raise ValueError("Chinook source checksum changed. Review the official release before updating the pin.")
    data = json.loads(content, parse_float=Decimal)
    if set(data) != set(TABLES):
        raise ValueError("Unexpected Chinook table list")
    for name, (_, expected) in TABLES.items():
        if len(data[name]) != expected:
            raise ValueError(f"Unexpected row count for {name}")
    return data


def source_path() -> Path:
    supplied = Path("/input/ChinookData.json")
    if supplied.is_file():
        return supplied
    cached = Path("/cache/ChinookData.json")
    if not cached.is_file():
        cached.parent.mkdir(parents=True, exist_ok=True)
        temporary = cached.with_suffix(".download")
        with urlopen(SOURCE_URL, timeout=90) as response:
            temporary.write_bytes(response.read())
        read_source(temporary)
        temporary.replace(cached)
    return cached


def load() -> None:
    import psycopg
    from psycopg import sql

    data = read_source(source_path())
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(671821202)")
            cursor.execute("SELECT to_regclass('demo_meta.imports')")
            if cursor.fetchone()[0]:
                cursor.execute("SELECT source_sha256 FROM demo_meta.imports WHERE dataset = 'chinook-1.4.5'")
                imported = cursor.fetchone()
                if imported:
                    if imported[0] != SOURCE_SHA256:
                        raise ValueError("Existing import differs from the pinned source; use a fresh example volume.")
                    for _, (table, expected) in TABLES.items():
                        cursor.execute(sql.SQL("SELECT count(*) FROM chinook.{}").format(sql.Identifier(table)))
                        if cursor.fetchone()[0] != expected:
                            raise ValueError(f"Existing {table} changed; use a fresh example volume.")
                    print("Pinned Chinook import is already present.", flush=True)
                    return

            cursor.execute(Path(__file__).with_name("schema.sql").read_text())
            for name, (table, _) in TABLES.items():
                rows = data[name]
                fields = tuple(rows[0])
                statement = sql.SQL("COPY chinook.{} ({}) FROM STDIN").format(
                    sql.Identifier(table), sql.SQL(", ").join(sql.Identifier(column_name(field)) for field in fields)
                )
                with cursor.copy(statement) as copy:
                    for row in rows:
                        if set(row) != set(fields):
                            raise ValueError(f"Inconsistent source columns in {name}")
                        copy.write_row(tuple(row[field] for field in fields))
                print(f"{table}: {len(rows)} rows", flush=True)

            cursor.execute("INSERT INTO demo_meta.imports (dataset, source_sha256) VALUES (%s, %s)",
                           ("chinook-1.4.5", SOURCE_SHA256))
            cursor.execute("CREATE ROLE chinook_reader LOGIN PASSWORD 'local-read-only'")
            cursor.execute("GRANT CONNECT ON DATABASE chinook TO chinook_reader")
            cursor.execute("GRANT USAGE ON SCHEMA chinook TO chinook_reader")
            cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA chinook TO chinook_reader")
    print("Chinook import complete; Cube uses the read-only role.", flush=True)


if __name__ == "__main__":
    load()

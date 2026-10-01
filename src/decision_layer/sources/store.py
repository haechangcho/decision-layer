"""Small source-settings store sharing the Run database, but a separate table."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Protocol


class SourceStore(Protocol):
    async def get(self) -> dict | None: ...
    async def save(self, doc: dict) -> None: ...


class MemorySourceStore:
    def __init__(self) -> None:
        self.doc: dict | None = None

    async def get(self) -> dict | None:
        return self.doc.copy() if self.doc is not None else None

    async def save(self, doc: dict) -> None:
        self.doc = doc.copy()


class SqliteSourceStore:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS source_config (id TEXT PRIMARY KEY, doc TEXT NOT NULL)")
        self.db.commit()

    async def get(self) -> dict | None:
        import json
        with self.lock:
            row = self.db.execute("SELECT doc FROM source_config WHERE id = 'current'").fetchone()
        return json.loads(row[0]) if row else None

    async def save(self, doc: dict) -> None:
        import json
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO source_config(id, doc) VALUES ('current', ?)",
                            (json.dumps(doc, separators=(",", ":")),))
            self.db.commit()


class PostgresSourceStore:
    def __init__(self, url: str) -> None:
        self.url = url

    async def _connect(self):
        import psycopg
        from psycopg.rows import dict_row
        conn = await psycopg.AsyncConnection.connect(self.url, autocommit=True, row_factory=dict_row)
        await conn.execute("CREATE SCHEMA IF NOT EXISTS decision_layer")
        await conn.execute("CREATE TABLE IF NOT EXISTS decision_layer.source_config (id TEXT PRIMARY KEY, doc JSONB NOT NULL)")
        return conn

    async def get(self) -> dict | None:
        async with await self._connect() as conn:
            row = await (await conn.execute("SELECT doc FROM decision_layer.source_config WHERE id = 'current'")).fetchone()
        return row["doc"] if row else None

    async def save(self, doc: dict) -> None:
        import json
        async with await self._connect() as conn:
            await conn.execute("""INSERT INTO decision_layer.source_config(id, doc) VALUES ('current', %s)
                                  ON CONFLICT (id) DO UPDATE SET doc = EXCLUDED.doc""", (json.dumps(doc, separators=(",", ":")),))


def open_source_store(url: str | None) -> SourceStore:
    if not url or url == "memory":
        return MemorySourceStore()
    if url.startswith("sqlite:///"):
        return SqliteSourceStore(url.removeprefix("sqlite:///"))
    if url.startswith(("postgresql://", "postgres://")):
        return PostgresSourceStore(url)
    raise ValueError(f"Unsupported DL_DATABASE_URL scheme: {url.split('://')[0]}://…")

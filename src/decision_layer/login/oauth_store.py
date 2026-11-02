"""Persistent OAuth clients and short-lived, single-use transactions (ADR-131).

Client secrets and transaction payloads are encrypted by OAuthProvider. Keys for
bearer-like transaction IDs are hashed there. Consume is atomic in every backend.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


class OAuthStore:
    def __init__(self, url: str):
        self.url = url
        self.rows: dict[str, tuple[str, float | None]] = {}
        self.lock = threading.Lock()
        self.db = None
        if url.startswith("sqlite:///"):
            path = url.removeprefix("sqlite:///")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
            self.db.execute("CREATE TABLE IF NOT EXISTS oauth_state (id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL)")
            self.db.commit()
        elif url != "memory" and not url.startswith(("postgresql://", "postgres://")):
            raise ValueError("Unsupported OAuth store")

    async def _connect(self):
        import psycopg
        conn = await psycopg.AsyncConnection.connect(self.url, autocommit=True)
        await conn.execute("CREATE SCHEMA IF NOT EXISTS decision_layer")
        await conn.execute("CREATE TABLE IF NOT EXISTS decision_layer.oauth_state (id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires DOUBLE PRECISION)")
        return conn

    async def put(self, key: str, payload: str, expires: float | None):
        if self.url == "memory":
            self.rows = {k: v for k, v in self.rows.items() if v[1] is None or v[1] > time.time()}
            self.rows[key] = (payload, expires)
        elif self.db:
            with self.lock:
                self.db.execute("DELETE FROM oauth_state WHERE expires <= ?", (time.time(),))
                self.db.execute("INSERT INTO oauth_state VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, expires=excluded.expires", (key, payload, expires))
                self.db.commit()
        else:
            async with await self._connect() as conn:
                await conn.execute("DELETE FROM decision_layer.oauth_state WHERE expires <= %s", (time.time(),))
                await conn.execute("INSERT INTO decision_layer.oauth_state VALUES (%s,%s,%s) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, expires=excluded.expires", (key, payload, expires))

    async def read(self, key: str, *, consume: bool = False) -> str | None:
        if self.url == "memory":
            row = self.rows.pop(key, None) if consume else self.rows.get(key)
        elif self.db:
            with self.lock:
                sql = "DELETE FROM oauth_state WHERE id=? RETURNING payload, expires" if consume else "SELECT payload, expires FROM oauth_state WHERE id=?"
                row = self.db.execute(sql, (key,)).fetchone()
                self.db.commit()
        else:
            async with await self._connect() as conn:
                sql = "DELETE FROM decision_layer.oauth_state WHERE id=%s RETURNING payload, expires" if consume else "SELECT payload, expires FROM decision_layer.oauth_state WHERE id=%s"
                row = await (await conn.execute(sql, (key,))).fetchone()
        return row[0] if row and (row[1] is None or row[1] > time.time()) else None

    async def count_clients(self) -> int:
        if self.url == "memory":
            return sum(k.startswith("client:") for k in self.rows)
        if self.db:
            with self.lock:
                return self.db.execute("SELECT count(*) FROM oauth_state WHERE id LIKE 'client:%'").fetchone()[0]
        async with await self._connect() as conn:
            return (await (await conn.execute("SELECT count(*) FROM decision_layer.oauth_state WHERE id LIKE 'client:%'")).fetchone())[0]

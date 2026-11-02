"""Opaque access tokens for MCP and REST clients (ADR-130/131).

OAuth issues short-lived, client/resource-bound tokens; a signed-in person may
also create a personal token in the browser. Only the SHA-256 digest is stored,
beside the Run database in a separate table. A token keeps the role its owner had
when it was created until it expires or is revoked.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .sessions import Person

PREFIX = "dlp_"


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _document(record) -> str:
    # Keep the original JSON shape readable by the previous image on rollback.
    # OAuth binding lives in additive columns that older versions ignore.
    return json.dumps({k: v for k, v in asdict(record).items() if k not in ("client_id", "resource")})


def _record(row) -> "AccessToken":
    doc, client_id, resource = row
    values = json.loads(doc) if isinstance(doc, str) else doc
    return AccessToken(**{**values, "client_id": client_id, "resource": resource})


@dataclass(frozen=True)
class AccessToken:
    id: str
    subject: str
    role: str
    label: str
    created_at: int
    expires_at: int
    name: str | None = None
    revoked_at: int | None = None
    # OAuth tokens are bound to this DL resource and client, never a Cube token.
    client_id: str | None = None
    resource: str | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None and time.time() < self.expires_at

    def person(self) -> Person:
        return Person(subject=self.subject, role=self.role, name=self.name)


class AccessTokenStore:
    """Memory implementation; the SQLite/PostgreSQL stores share its logic."""

    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, AccessToken]] = {}

    async def _put(self, digest: str, record: AccessToken) -> None:
        self._rows[record.id] = (digest, record)

    async def _by_digest(self, digest: str) -> AccessToken | None:
        return next((r for d, r in self._rows.values() if d == digest), None)

    async def _all(self, subject: str) -> list[AccessToken]:
        return [r for _d, r in self._rows.values() if r.subject == subject]

    async def _replace(self, record: AccessToken) -> None:
        digest, _old = self._rows[record.id]
        self._rows[record.id] = (digest, record)

    async def create(self, person: Person, label: str, days: int, *, seconds: int | None = None,
                     client_id: str | None = None, resource: str | None = None) -> tuple[str, AccessToken]:
        token = PREFIX + secrets.token_urlsafe(32)
        now = int(time.time())
        record = AccessToken(id=uuid.uuid4().hex[:12], subject=person.subject, role=person.role,
                             name=person.name, label=label.strip()[:80] or "MCP",
                             created_at=now, expires_at=now + (seconds if seconds is not None else days * 86400),
                             client_id=client_id, resource=resource)
        await self._put(_digest(token), record)
        return token, record

    async def verify(self, token: str, *, resource: str | None = None) -> AccessToken | None:
        if not token.startswith(PREFIX):
            return None
        record = await self._by_digest(_digest(token))
        return record if record and record.active and (record.resource is None or record.resource == resource) else None

    async def list(self, subject: str) -> list[AccessToken]:
        return sorted(await self._all(subject), key=lambda r: r.created_at, reverse=True)

    async def revoke(self, subject: str, token_id: str) -> bool:
        record = next((r for r in await self._all(subject) if r.id == token_id), None)
        if record is None or record.revoked_at is not None:
            return False
        await self._replace(AccessToken(**{**asdict(record), "revoked_at": int(time.time())}))
        return True


class SqliteAccessTokenStore(AccessTokenStore):
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("""CREATE TABLE IF NOT EXISTS access_tokens (
            id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, subject TEXT NOT NULL, doc TEXT NOT NULL,
            client_id TEXT, resource TEXT)""")
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(access_tokens)")}
        for column in ("client_id", "resource"):
            if column not in columns:
                self.db.execute(f"ALTER TABLE access_tokens ADD COLUMN {column} TEXT")
        self.db.commit()

    async def _put(self, digest, record):
        with self.lock:
            self.db.execute("INSERT INTO access_tokens(id, digest, subject, doc, client_id, resource) VALUES (?, ?, ?, ?, ?, ?)",
                            (record.id, digest, record.subject, _document(record), record.client_id, record.resource))
            self.db.commit()

    async def _by_digest(self, digest):
        with self.lock:
            row = self.db.execute("SELECT doc, client_id, resource FROM access_tokens WHERE digest = ?", (digest,)).fetchone()
        return _record(row) if row else None

    async def _all(self, subject):
        with self.lock:
            rows = self.db.execute("SELECT doc, client_id, resource FROM access_tokens WHERE subject = ?", (subject,)).fetchall()
        return [_record(row) for row in rows]

    async def _replace(self, record):
        with self.lock:
            self.db.execute("UPDATE access_tokens SET doc = ? WHERE id = ?", (_document(record), record.id))
            self.db.commit()


class PostgresAccessTokenStore(AccessTokenStore):
    def __init__(self, url: str) -> None:
        self.url = url

    async def _connect(self):
        import psycopg
        conn = await psycopg.AsyncConnection.connect(self.url, autocommit=True)
        await conn.execute("CREATE SCHEMA IF NOT EXISTS decision_layer")
        await conn.execute("""CREATE TABLE IF NOT EXISTS decision_layer.access_tokens (
            id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE, subject TEXT NOT NULL, doc JSONB NOT NULL,
            client_id TEXT, resource TEXT)""")
        await conn.execute("ALTER TABLE decision_layer.access_tokens ADD COLUMN IF NOT EXISTS client_id TEXT")
        await conn.execute("ALTER TABLE decision_layer.access_tokens ADD COLUMN IF NOT EXISTS resource TEXT")
        return conn

    async def _put(self, digest, record):
        async with await self._connect() as conn:
            await conn.execute("INSERT INTO decision_layer.access_tokens(id, digest, subject, doc, client_id, resource) VALUES (%s, %s, %s, %s, %s, %s)",
                               (record.id, digest, record.subject, _document(record), record.client_id, record.resource))

    async def _by_digest(self, digest):
        async with await self._connect() as conn:
            row = await (await conn.execute("SELECT doc, client_id, resource FROM decision_layer.access_tokens WHERE digest = %s",
                                            (digest,))).fetchone()
        return _record(row) if row else None

    async def _all(self, subject):
        async with await self._connect() as conn:
            rows = await (await conn.execute("SELECT doc, client_id, resource FROM decision_layer.access_tokens WHERE subject = %s",
                                             (subject,))).fetchall()
        return [_record(row) for row in rows]

    async def _replace(self, record):
        async with await self._connect() as conn:
            await conn.execute("UPDATE decision_layer.access_tokens SET doc = %s WHERE id = %s",
                               (_document(record), record.id))


def open_token_store(url: str | None) -> AccessTokenStore:
    if not url or url == "memory":
        return AccessTokenStore()
    if url.startswith("sqlite:///"):
        return SqliteAccessTokenStore(url.removeprefix("sqlite:///"))
    if url.startswith(("postgresql://", "postgres://")):
        return PostgresAccessTokenStore(url)
    raise ValueError(f"Unsupported DL_DATABASE_URL scheme: {url.split('://')[0]}://…")

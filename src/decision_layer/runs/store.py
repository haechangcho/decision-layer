"""Run storage (ADR-025: recipes are files, runs live in a database).

A Run is stored whole as JSON next to a few indexed columns. Two backends:
- sqlite:///path  — local development and tests (stdlib, no server)
- postgresql://…  — the infra stack (table in schema `decision_layer`)
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from ..core.errors import DecisionLayerError
from ..core.models import Run
from ..i18n import _


class UnknownRun(DecisionLayerError):
    code = "UNKNOWN_RUN"
    http_status = 404


class RunStore(Protocol):
    async def save(self, run: Run) -> None: ...
    async def get(self, run_id: str) -> Run: ...
    async def list(self, limit: int = 50, recipe: str | None = None, subject: str | None = None) -> list[Run]: ...
    async def running(self) -> list[Run]: ...


def _row(run: Run) -> tuple:
    return (run.id, run.plan.recipe, run.status, run.caller.subject, run.created_at.isoformat(),
            run.finished_at.isoformat() if run.finished_at else None, run.model_dump_json())


class MemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, str] = {}

    async def save(self, run: Run) -> None:
        self._runs[run.id] = run.model_dump_json()

    async def get(self, run_id: str) -> Run:
        if run_id not in self._runs:
            raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))
        return Run.model_validate_json(self._runs[run_id])

    async def list(self, limit: int = 50, recipe: str | None = None, subject: str | None = None) -> list[Run]:
        runs = [Run.model_validate_json(d) for d in self._runs.values()]
        runs = [r for r in runs if (recipe is None or (r.plan.recipe or "").startswith(recipe))
                and (subject is None or r.caller.subject == subject)]
        return sorted(runs, key=lambda r: r.id, reverse=True)[:limit]

    async def running(self) -> list[Run]:
        return [r for r in (Run.model_validate_json(d) for d in self._runs.values()) if r.running]


class SqliteRunStore:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()  # jobs save from worker threads with their own event loops
        self._db.execute("""CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, recipe TEXT, status TEXT, subject TEXT,
            created_at TEXT, finished_at TEXT, doc TEXT NOT NULL)""")
        self._db.commit()

    async def save(self, run: Run) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?)", _row(run))
            self._db.commit()

    async def get(self, run_id: str) -> Run:
        row = self._db.execute("SELECT doc FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))
        return Run.model_validate_json(row[0])

    async def list(self, limit: int = 50, recipe: str | None = None, subject: str | None = None) -> list[Run]:
        where, args = _where(recipe, subject, "?")
        rows = self._db.execute(f"SELECT doc FROM runs{where} ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
        return [Run.model_validate_json(r[0]) for r in rows]

    async def running(self) -> list[Run]:
        rows = self._db.execute("SELECT doc FROM runs WHERE json_extract(doc, '$.running') IS NOT NULL").fetchall()
        return [Run.model_validate_json(r[0]) for r in rows]


class PostgresRunStore:
    def __init__(self, url: str) -> None:
        self.url = url
        self._ready = False

    async def _conn(self):
        import psycopg  # only needed for this backend

        conn = await psycopg.AsyncConnection.connect(self.url, autocommit=True)
        if not self._ready:
            # databases created before the rename kept runs in schema "analytica"
            await conn.execute("""DO $$ BEGIN
                IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'analytica')
                   AND NOT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'decision_layer') THEN
                    ALTER SCHEMA analytica RENAME TO decision_layer;
                END IF; END $$""")
            await conn.execute("CREATE SCHEMA IF NOT EXISTS decision_layer")
            await conn.execute("""CREATE TABLE IF NOT EXISTS decision_layer.runs (
                id TEXT PRIMARY KEY, recipe TEXT, status TEXT, subject TEXT,
                created_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, doc JSONB NOT NULL)""")
            self._ready = True
        return conn

    async def save(self, run: Run) -> None:
        async with await self._conn() as conn:
            await conn.execute(
                """INSERT INTO decision_layer.runs VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, finished_at = EXCLUDED.finished_at,
                                                  doc = EXCLUDED.doc""", _row(run))

    async def get(self, run_id: str) -> Run:
        async with await self._conn() as conn:
            row = await (await conn.execute("SELECT doc FROM decision_layer.runs WHERE id = %s", (run_id,))).fetchone()
        if not row:
            raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))
        return Run.model_validate(row[0])

    async def list(self, limit: int = 50, recipe: str | None = None, subject: str | None = None) -> list[Run]:
        where, args = _where(recipe, subject, "%s")
        async with await self._conn() as conn:
            rows = await (await conn.execute(f"SELECT doc FROM decision_layer.runs{where} ORDER BY id DESC LIMIT %s",
                                             [*args, limit])).fetchall()
        return [Run.model_validate(r[0]) for r in rows]

    async def running(self) -> list[Run]:
        async with await self._conn() as conn:
            rows = await (await conn.execute(
                "SELECT doc FROM decision_layer.runs WHERE jsonb_typeof(doc->'running') = 'object'")).fetchall()
        return [Run.model_validate(r[0]) for r in rows]


def _where(recipe: str | None, subject: str | None, mark: str) -> tuple[str, list]:
    clauses, args = [], []
    if recipe:
        clauses.append(f"recipe LIKE {mark}")
        args.append(recipe + "%")
    if subject is not None:
        clauses.append(f"subject = {mark}")
        args.append(subject)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), args


def open_store(url: str | None) -> RunStore:
    if not url or url == "memory":
        return MemoryRunStore()
    if url.startswith("sqlite:///"):
        return SqliteRunStore(url.removeprefix("sqlite:///"))
    if url.startswith(("postgresql://", "postgres://")):
        return PostgresRunStore(url)
    raise ValueError(f"Unsupported DL_DATABASE_URL scheme: {url.split('://')[0]}://…")


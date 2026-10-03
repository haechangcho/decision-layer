"""Runtime settings from the environment (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .env import env

_REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    cube_api_url: str = field(default_factory=lambda: os.environ.get("CUBE_API_URL", "http://localhost:4000/cubejs-api/v1"))
    cube_instance: str = field(default_factory=lambda: os.environ.get("CUBE_INSTANCE", "local"))
    cube_api_secret: str | None = field(default_factory=lambda: os.environ.get("CUBE_API_SECRET") or None)
    cube_service_groups: tuple[str, ...] = field(default_factory=lambda: tuple(
        g.strip() for g in os.environ.get("CUBE_SERVICE_GROUPS", "").split(",") if g.strip()))
    # local/dev only: requests without Authorization use the service credentials above (ADR-029)
    allow_service_credentials: bool = field(default_factory=lambda: env(
        "DL_ALLOW_SERVICE_CREDENTIALS", "").lower() in ("1", "true", "yes"))
    # default message language when a request sends no supported Accept-Language (en, ko)
    locale: str = field(default_factory=lambda: env("DL_LOCALE", "en"))
    # how long a request waits for its analysis job before answering 202 (the client then polls the run)
    request_wait_seconds: float = field(default_factory=lambda: float(env("DL_REQUEST_WAIT_SECONDS", "25")))
    job_workers: int = field(default_factory=lambda: int(env("DL_JOB_WORKERS", "4")))
    # runs: sqlite:///path | postgresql://… | memory
    database_url: str = field(default_factory=lambda: env(
        "DL_DATABASE_URL", f"sqlite:///{_REPO / 'data' / 'decision_layer.db'}"))
    # organisation-specific Recipes live outside the code; none are loaded unless configured
    recipes_dir: str | None = field(default_factory=lambda: env("DL_RECIPES_DIR") or None)
    # Source administration is separate from Cube query access (ADR-033).
    source_admin_token: str | None = field(default_factory=lambda: os.environ.get("DL_SOURCE_ADMIN_TOKEN") or None)
    # Fernet key, provisioned outside the database; empty disables secret writes.
    source_config_key: str | None = field(default_factory=lambda: os.environ.get("DL_SOURCE_CONFIG_KEY") or None)

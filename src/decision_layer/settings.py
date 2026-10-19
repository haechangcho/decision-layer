"""Runtime settings from the environment (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .env import env
from .core.periods import ExecutionPolicy

_REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    deployment_mode: str = field(default_factory=lambda: env("DL_DEPLOYMENT_MODE", "local"))
    http_allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip().lower() for value in env("DL_HTTP_ALLOWED_HOSTS", "localhost,127.0.0.1,::1,api").split(",") if value.strip()))
    # Exact endpoints approved outside the HTTP API. An admin key cannot enlarge this list.
    source_allowed_urls: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip().rstrip("/") for value in env("DL_SOURCE_ALLOWED_URLS", "").split(",") if value.strip()))
    recipe_editors: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip() for value in env("DL_RECIPE_EDITORS", "").split(",") if value.strip()))
    recipe_publishers: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip() for value in env("DL_RECIPE_PUBLISHERS", "").split(",") if value.strip()))

    def validate_deployment(self) -> None:
        if self.deployment_mode not in ("local", "demo"):
            raise ValueError("Only local and demo deployments are supported. Shared deployment requires independent app identity, network isolation and code sandboxing; these release gates are not implemented yet.")

    execution_policy: ExecutionPolicy = field(default_factory=lambda: ExecutionPolicy.model_validate_json(
        env("DL_EXECUTION_POLICY", "{}")))
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
    method_modules: tuple[str, ...] = field(default_factory=lambda: tuple(
        value.strip() for value in env("DL_METHOD_MODULES", "").split(",") if value.strip()))
    method_editors: tuple[str, ...] = field(default_factory=lambda: tuple(v.strip() for v in env("DL_METHOD_EDITORS", "").split(",") if v.strip()))
    method_publishers: tuple[str, ...] = field(default_factory=lambda: tuple(v.strip() for v in env("DL_METHOD_PUBLISHERS", "").split(",") if v.strip()))
    method_assets_dir: str | None = field(default_factory=lambda: env("DL_METHOD_ASSETS_DIR") or None)
    allow_method_editing: bool = field(default_factory=lambda: env("DL_ALLOW_METHOD_EDITING", "false").lower() == "true")
    skills_dir: str | None = field(default_factory=lambda: env("DL_SKILLS_DIR") or None)
    recipes_dir: str | None = field(default_factory=lambda: env("DL_RECIPES_DIR") or None)
    # Source administration is separate from Cube query access (ADR-033).
    source_admin_token: str | None = field(default_factory=lambda: os.environ.get("DL_SOURCE_ADMIN_TOKEN") or None)
    # Fernet key, provisioned outside the database; empty disables secret writes.
    source_config_key: str | None = field(default_factory=lambda: os.environ.get("DL_SOURCE_CONFIG_KEY") or None)
    issue_repository: str = field(default_factory=lambda: env("DL_ISSUE_REPOSITORY", "haechangcho/decision-layer"))
    # Explicit project directory shared by CLI, local Python and API startup.
    project_dir: str | None = field(default_factory=lambda: env("DL_PROJECT_DIR") or None)

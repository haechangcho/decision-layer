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
        if self.deployment_mode == "shared":
            self.login.validate(self)
            return
        if self.deployment_mode not in ("local", "demo"):
            raise ValueError("Only local, demo and shared deployments are supported.")

    @property
    def shared(self) -> bool:
        return self.deployment_mode == "shared"

    login: "LoginSettings" = field(default_factory=lambda: LoginSettings())

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


def _names(value: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (value or "").split(",") if v.strip())


@dataclass(frozen=True)
class LoginSettings:
    """Application login for shared deployments (ADR-130).

    The OIDC provider verifies people; Decision Layer signs short-lived Cube tokens
    for them with its own key, so the Cube WebApp secret is never shared.
    """
    issuer: str | None = field(default_factory=lambda: env("DL_OIDC_ISSUER") or None)
    client_id: str | None = field(default_factory=lambda: env("DL_OIDC_CLIENT_ID") or None)
    client_secret: str | None = field(default_factory=lambda: env("DL_OIDC_CLIENT_SECRET") or None)
    scopes: str = field(default_factory=lambda: env("DL_OIDC_SCOPES", "openid profile email cube_groups"))
    groups_claim: str = field(default_factory=lambda: env("DL_OIDC_GROUPS_CLAIM", "cube_groups"))
    # Browser-visible origin; the callback is {public_url}/auth/callback.
    public_url: str | None = field(default_factory=lambda: (env("DL_PUBLIC_URL") or "").rstrip("/") or None)
    session_secret: str | None = field(default_factory=lambda: env("DL_SESSION_SECRET") or None)
    session_hours: float = field(default_factory=lambda: float(env("DL_SESSION_HOURS", "8")))
    access_token_days: int = field(default_factory=lambda: int(env("DL_ACCESS_TOKEN_DAYS", "30")))
    mcp_access_token_seconds: int = field(default_factory=lambda: int(env("DL_MCP_ACCESS_TOKEN_SECONDS", "3600")))
    mcp_redirect_hosts: tuple[str, ...] = field(default_factory=lambda: _names(env(
        "DL_MCP_REDIRECT_HOSTS", "localhost,127.0.0.1,::1,claude.ai,claude.com,chatgpt.com,chat.openai.com")))
    # IdP groups allowed to sign in, by application role.
    admin_groups: tuple[str, ...] = field(default_factory=lambda: _names(env("DL_ADMIN_GROUPS")))
    user_groups: tuple[str, ...] = field(default_factory=lambda: _names(env("DL_USER_GROUPS")))
    # Cube access-policy groups carried by the tokens Decision Layer signs.
    cube_token_secret: str | None = field(default_factory=lambda: env("DL_CUBE_TOKEN_SECRET") or None)
    cube_admin_groups: tuple[str, ...] = field(default_factory=lambda: _names(env("DL_CUBE_ADMIN_GROUPS", "admin")))
    cube_user_groups: tuple[str, ...] = field(default_factory=lambda: _names(env("DL_CUBE_USER_GROUPS", "guest")))

    @property
    def redirect_uri(self) -> str:
        return f"{self.public_url}/auth/callback"

    @property
    def secure_cookies(self) -> bool:
        return bool(self.public_url and self.public_url.startswith("https://"))

    def validate(self, settings: "Settings") -> None:
        from urllib.parse import urlsplit

        missing = [name for name, value in (
            ("DL_OIDC_ISSUER", self.issuer), ("DL_OIDC_CLIENT_ID", self.client_id),
            ("DL_OIDC_CLIENT_SECRET", self.client_secret), ("DL_PUBLIC_URL", self.public_url),
            ("DL_SESSION_SECRET", self.session_secret), ("DL_CUBE_TOKEN_SECRET", self.cube_token_secret),
            ("DL_ADMIN_GROUPS", self.admin_groups), ("DL_CUBE_ADMIN_GROUPS", self.cube_admin_groups),
            ("DL_CUBE_USER_GROUPS", self.cube_user_groups)) if not value]
        if missing:
            raise ValueError("Shared deployment requires " + ", ".join(missing))
        for name, value in (("DL_SESSION_SECRET", self.session_secret), ("DL_CUBE_TOKEN_SECRET", self.cube_token_secret)):
            if len(value) < 32:
                raise ValueError(f"{name} must be at least 32 characters")
        if self.session_secret == self.cube_token_secret:
            raise ValueError("DL_SESSION_SECRET and DL_CUBE_TOKEN_SECRET must differ")
        if not 60 <= self.mcp_access_token_seconds <= 86400:
            raise ValueError("DL_MCP_ACCESS_TOKEN_SECONDS must be between 60 and 86400")
        if not self.mcp_redirect_hosts:
            raise ValueError("DL_MCP_REDIRECT_HOSTS must not be empty")
        public = urlsplit(self.public_url)
        if public.scheme != "https" and public.hostname not in ("localhost", "127.0.0.1"):
            raise ValueError("DL_PUBLIC_URL must use https outside a localhost tunnel")
        if public.hostname not in settings.http_allowed_hosts:
            raise ValueError("DL_HTTP_ALLOWED_HOSTS must include the DL_PUBLIC_URL host")
        if urlsplit(self.issuer).scheme != "https":
            raise ValueError("DL_OIDC_ISSUER must use https")
        # Shared mode keeps code and endpoints operator-owned (ADR-130): no service
        # identity, no HTTP source administration and no Web code editing.
        if settings.allow_service_credentials:
            raise ValueError("Shared deployment cannot allow service credentials")
        if settings.allow_method_editing:
            raise ValueError("Shared deployment cannot allow Method editing")
        if settings.source_admin_token:
            raise ValueError("Shared deployment cannot enable HTTP source administration")

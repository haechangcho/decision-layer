"""Environment-overridable source settings; persisted secrets are always encrypted."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, field_validator

from ..core.errors import DecisionLayerError
from .store import SourceStore


class SourceConfigError(DecisionLayerError):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.http_status = code, status


class SourceConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["cube", "dbt"] = "cube"
    environment_id: int | None = Field(default=None, gt=0)
    instance: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]+$")
    api_url: str
    auth_method: Literal["token", "api_secret", "none"] = "token"
    api_secret: SecretStr | None = None
    clear_secret: bool = False
    service_groups: list[str] = Field(default_factory=list)

    @field_validator("api_url")
    @classmethod
    def valid_api_url(cls, value: str) -> str:
        raw = value.strip()
        try:
            parsed = AnyHttpUrl(raw)
        except ValueError as exc:
            raise ValueError("Enter a valid http or https semantic API URL") from exc
        if parsed.scheme not in ("http", "https"):
            raise ValueError("API URL must use http or https")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("API URL must not contain credentials, query parameters or a fragment")
        return raw.rstrip("/")

    @field_validator("service_groups")
    @classmethod
    def clean_groups(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(v.strip() for v in values if v.strip()))


@dataclass(frozen=True)
class EffectiveSource:
    api_url: str
    instance: str
    auth_method: Literal["token", "api_secret", "none"]
    api_secret: str | None
    service_groups: tuple[str, ...]
    environment_overrides: dict[str, bool]
    saved_secret: bool
    provider: str = "cube"
    environment_id: int | None = None


class SourceConfigManager:
    def __init__(self, store: SourceStore, settings) -> None:
        self.store, self.settings = store, settings
        self.current_provider = os.environ.get("DL_SOURCE_PROVIDER") or os.environ.get("DL_DEFAULT_SOURCE_PROVIDER", "cube")
        self.current_instance = settings.cube_instance

    def _fernet(self) -> Fernet:
        key = self.settings.source_config_key
        if not key:
            raise SourceConfigError("SOURCE_ENCRYPTION_NOT_CONFIGURED",
                                    "Set DL_SOURCE_CONFIG_KEY before saving a Cube API secret.", 503)
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise SourceConfigError("SOURCE_ENCRYPTION_KEY_INVALID",
                                    "DL_SOURCE_CONFIG_KEY must be a valid Fernet key.", 503) from exc

    async def effective(self, *, resolve_secret: bool = True, provider: str | None = None) -> EffectiveSource:
        document = await self.store.get() or {}
        name = provider or os.environ.get("DL_SOURCE_PROVIDER") or document.get("provider") or os.environ.get("DL_DEFAULT_SOURCE_PROVIDER", "cube")
        if name not in ("cube", "dbt"):
            raise SourceConfigError("SOURCE_PROVIDER_INVALID", "Choose Cube or the official dbt Semantic Layer API. The local MetricFlow gateway is no longer supported; configure a supported connection without changing historical Runs.")
        saved = document.get("connections", {}).get(name, document if document.get("provider", "cube") == name else {})
        prefix = {"cube": "CUBE", "dbt": "DBT"}[name]
        env_environment = os.environ.get("DBT_ENVIRONMENT_ID") if name == "dbt" else None
        environment_id = env_environment or saved.get("environment_id") if name == "dbt" else None
        if environment_id is not None:
            try:
                environment_id = int(environment_id)
                if environment_id <= 0:
                    raise ValueError()
            except (TypeError, ValueError) as exc:
                raise SourceConfigError("SOURCE_ENVIRONMENT_INVALID", "DBT_ENVIRONMENT_ID must be a positive integer.") from exc
        env_url = os.environ.get(prefix + "_API_URL")
        env_instance = os.environ.get(prefix + "_INSTANCE")
        env_secret = os.environ.get("CUBE_API_SECRET") if name == "cube" else None
        env_method = os.environ.get(prefix + "_AUTH_METHOD")
        env_groups = os.environ.get("CUBE_SERVICE_GROUPS") if name == "cube" else None
        encrypted = saved.get("api_secret_ciphertext")
        saved_secret = bool(encrypted)
        secret = env_secret or (self.settings.cube_api_secret if name == "cube" else None)
        if resolve_secret and secret is None and encrypted:
            try:
                secret = self._fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
                raise SourceConfigError("SOURCE_SECRET_UNREADABLE",
                                        "The saved Cube secret cannot be decrypted. Check DL_SOURCE_CONFIG_KEY.", 503) from exc
        if env_method and env_method not in ("token", "api_secret", "none"):
            raise SourceConfigError("SOURCE_AUTH_METHOD_INVALID", "CUBE_AUTH_METHOD must be token, api_secret or none.", 503)
        method = env_method or ("api_secret" if env_secret else saved.get("auth_method") or
                                ("api_secret" if secret else "token"))
        if name == "dbt" and method != "token":
            raise SourceConfigError("SOURCE_AUTH_METHOD_INVALID", "dbt Semantic Layer requires an access token.")
        groups = env_groups.split(",") if env_groups is not None else saved.get(
            "service_groups", list(self.settings.cube_service_groups) if name == "cube" else [])
        instance = env_instance or saved.get("instance") or self.settings.cube_instance
        if name == "dbt":
            instance = env_instance or saved.get("instance") or (f"env-{environment_id}" if environment_id else "production")
        if provider is None:
            self.current_provider, self.current_instance = name, instance
        default_url = os.environ.get("DL_DEFAULT_CUBE_URL") or self.settings.cube_api_url
        if name == "dbt":
            default_url = "https://semantic-layer.cloud.getdbt.com/api/graphql"
        return EffectiveSource(
            provider=name,
            environment_id=environment_id,
            api_url=env_url or saved.get("api_url") or default_url,
            instance=instance,
            auth_method=method,
            api_secret=secret,
            service_groups=tuple(g.strip() for g in groups if g.strip()),
            environment_overrides={"provider": bool(os.environ.get("DL_SOURCE_PROVIDER")), "api_url": bool(env_url), "instance": bool(env_instance), "environment_id": bool(env_environment),
                                   "auth_method": bool(env_method or env_secret),
                                   "api_secret": bool(env_secret), "service_groups": env_groups is not None},
            saved_secret=saved_secret or bool(env_secret),
        )

    async def view(self) -> dict:
        current = await self.effective(resolve_secret=False)
        return {"provider": current.provider, "instance": current.instance, "api_url": current.api_url, "environment_id": current.environment_id,
                "auth_method": current.auth_method, "api_secret_configured": current.saved_secret,
                "service_groups": list(current.service_groups),
                "environment_overrides": current.environment_overrides,
                "service_credentials_allowed": self.settings.allow_service_credentials,
                "admin_configured": bool(self.settings.source_admin_token),
                # editing the shared connection needs the admin key only on a shared deployment
                "admin_required": bool(self.settings.source_admin_token),
                # a field is editable in the UI only when no environment variable fixes it
                "editable": not all(current.environment_overrides.get(k) for k in
                                    ("provider", "api_url", "auth_method", "service_groups")),
                "encryption_configured": bool(self.settings.source_config_key)}

    async def save(self, value: SourceConfigInput) -> None:
        fixed = os.environ.get("DL_SOURCE_PROVIDER")
        if fixed and fixed != value.provider:
            raise SourceConfigError("SOURCE_ENV_OVERRIDDEN", "The provider is fixed by DL_SOURCE_PROVIDER.", 409)
        if value.provider == "dbt" and value.auth_method != "token":
            raise SourceConfigError("SOURCE_AUTH_METHOD_INVALID", "dbt Semantic Layer requires an access token.")
        if value.provider != "cube" and (value.auth_method == "api_secret" or value.api_secret):
            raise SourceConfigError("SOURCE_AUTH_METHOD_INVALID", "API secrets apply only to Cube development connections.")
        if value.auth_method != "token" and not self.settings.allow_service_credentials:
            raise SourceConfigError("SOURCE_DEV_AUTH_DISABLED", "Development authentication is disabled on this deployment.", 403)
        effective = await self.effective(resolve_secret=False, provider=value.provider)
        environment_id = effective.environment_id if effective.environment_overrides["environment_id"] else value.environment_id
        if value.provider == "dbt" and not environment_id:
            raise SourceConfigError("SOURCE_ENVIRONMENT_REQUIRED", "Enter the dbt deployment environment ID.")
        if effective.environment_overrides["environment_id"] and value.environment_id not in (None, effective.environment_id):
            raise SourceConfigError("SOURCE_ENV_OVERRIDDEN", "The environment ID is fixed by DBT_ENVIRONMENT_ID.", 409)
        field_map = {"api_url": "api_url", "auth_method": "auth_method",
                     "api_secret": "api_secret", "service_groups": "service_groups"}
        blocked = [key for key, env_key in field_map.items() if effective.environment_overrides[env_key]
                   and (key == "api_secret" and (value.api_secret or value.clear_secret)
                        or key == "service_groups" and value.service_groups != list(effective.service_groups)
                        or key == "api_url" and value.api_url.rstrip("/") != effective.api_url.rstrip("/")
                        or key == "auth_method" and value.auth_method != effective.auth_method)]
        if blocked:
            raise SourceConfigError("SOURCE_ENV_OVERRIDDEN",
                                    "These settings are fixed by environment variables: " + ", ".join(blocked), 409)
        prior = await self.store.get() or {}
        connections = dict(prior.get("connections", {}))
        if "api_url" in prior:
            connections.setdefault(prior.get("provider", "cube"), {k: v for k, v in prior.items() if k != "connections"})
        ciphertext = connections.get(value.provider, {}).get("api_secret_ciphertext")
        if value.clear_secret:
            ciphertext = None
        elif value.api_secret and value.api_secret.get_secret_value():
            ciphertext = self._fernet().encrypt(value.api_secret.get_secret_value().encode()).decode("ascii")
        if value.instance and effective.environment_overrides["instance"] and value.instance != effective.instance:
            raise SourceConfigError("SOURCE_ENV_OVERRIDDEN", "The instance is fixed by environment variables.", 409)
        connections[value.provider] = {"api_url": value.api_url, "auth_method": value.auth_method,
                               "instance": value.instance or effective.instance,
                               "environment_id": environment_id,
                               "api_secret_ciphertext": ciphertext,
                               "service_groups": value.service_groups}
        await self.store.save({**connections[value.provider], "provider": value.provider, "connections": connections})

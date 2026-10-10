import asyncio
import sqlite3

import pytest

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.semantic.providers.cube.provider import CubeProvider
from decision_layer.settings import Settings
from decision_layer.sources.config import SourceConfigInput, SourceConfigManager, SourceConfigError
from decision_layer.sources.store import MemorySourceStore, SqliteSourceStore
from test_cube_provider import FakeClient
from decision_layer.core.errors import ProviderAccessDenied, ProviderError
from decision_layer.core.models import SemanticCatalog, SemanticObject
from decision_layer.semantic.providers.cube.client import CubeConnectionError


def test_removed_gateway_is_rejected_and_saved_state_can_be_reconfigured(monkeypatch):
    from pydantic import ValidationError
    from decision_layer.sources.provider import make_provider

    monkeypatch.delenv("DL_SOURCE_PROVIDER", raising=False)
    monkeypatch.delenv("DL_DEFAULT_SOURCE_PROVIDER", raising=False)
    with pytest.raises(ValidationError):
        SourceConfigInput(provider="metricflow", api_url="http://legacy:4100")
    with pytest.raises(ValueError, match="Unsupported semantic provider"):
        make_provider("metricflow", "http://legacy:4100", "legacy")

    async def check():
        store = MemorySourceStore()
        await store.save({"provider": "metricflow", "api_url": "http://legacy:4100", "instance": "legacy"})
        manager = SourceConfigManager(store, Settings(database_url="memory"))
        with pytest.raises(SourceConfigError) as error:
            await manager.view()
        assert error.value.code == "SOURCE_PROVIDER_INVALID"
        await manager.save(SourceConfigInput(provider="dbt", api_url="https://dbt.example/api/graphql", environment_id=123))
        assert (await manager.view())["provider"] == "dbt"
        assert (await store.get())["connections"]["metricflow"]["instance"] == "legacy"

    asyncio.run(check())


def test_saved_secret_is_encrypted_and_never_returned(tmp_path, monkeypatch):
    for key in ("CUBE_API_URL", "CUBE_API_SECRET", "CUBE_AUTH_METHOD", "CUBE_SERVICE_GROUPS", "CUBE_INSTANCE"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "settings.db"
    settings = Settings(database_url="memory", source_config_key=Fernet.generate_key().decode(), allow_service_credentials=True)
    manager = SourceConfigManager(SqliteSourceStore(str(path)), settings)

    async def save_and_read():
        await manager.save(SourceConfigInput(api_url="http://cube.test/cubejs-api/v1", auth_method="api_secret",
                                             api_secret="top-secret"))
        return await manager.view()

    view = asyncio.run(save_and_read())
    raw = sqlite3.connect(path).execute("SELECT doc FROM source_config").fetchone()[0]
    assert "top-secret" not in raw
    assert view["api_secret_configured"] is True
    assert "api_secret" not in view


def test_environment_values_override_saved_values_and_reject_edits(monkeypatch):
    monkeypatch.setenv("CUBE_API_URL", "https://locked.example/cubejs-api/v1")
    settings = Settings(database_url="memory")
    manager = SourceConfigManager(MemorySourceStore(), settings)

    async def check():
        view = await manager.view()
        assert view["api_url"] == "https://locked.example/cubejs-api/v1"
        assert view["environment_overrides"]["api_url"] is True
        try:
            await manager.save(SourceConfigInput(api_url="http://other/cubejs-api/v1"))
        except SourceConfigError as exc:
            assert exc.code == "SOURCE_ENV_OVERRIDDEN"
        else:
            raise AssertionError("environment-fixed URL was editable")

    asyncio.run(check())


def test_source_admin_and_connection_test(cube_meta):
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="test-secret",
                        cube_service_groups=("ecommerce",), database_url="memory", allow_service_credentials=True,
                        source_admin_token="admin-key")
    provider = CubeProvider(FakeClient(cube_meta, rows_total=1), "local")
    client = TestClient(create_app(settings, provider))
    # viewing the current connection is always open (no admin key)
    view = client.get("/sources/current")
    assert view.status_code == 200 and view.json()["admin_required"] is True and view.json()["editable"] is True
    # with an admin token set (shared deployment), editing/testing needs the key
    denied = client.post("/sources/current:test", json={"api_url": "http://x", "auth_method": "api_secret"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "SOURCE_ADMIN_REQUIRED", denied.text
    headers = {"X-Decision-Layer-Admin-Key": "admin-key"}
    result = client.post("/sources/current:test", headers=headers,
                         json={"api_url": "http://x", "auth_method": "api_secret"})
    assert result.status_code == 200
    assert result.json()["measures"] > 0
    readiness = client.get("/sources/current/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["metrics"]


def test_local_install_edits_without_admin_key(cube_meta):
    # no admin token = single-user/local install: editing is open, no key required (ADR-033)
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="test-secret",
                        cube_service_groups=("ecommerce",), database_url="memory", allow_service_credentials=True)
    provider = CubeProvider(FakeClient(cube_meta, rows_total=1), "local")
    client = TestClient(create_app(settings, provider))
    view = client.get("/sources/current")
    assert view.status_code == 200 and view.json()["admin_required"] is False
    result = client.post("/sources/current:test", json={"api_url": "http://x", "auth_method": "api_secret"})
    assert result.status_code == 200 and result.json()["measures"] > 0


@pytest.mark.parametrize("error,code,status", [
    (ProviderAccessDenied("Authorization header is required"), "SOURCE_AUTH_FAILED", 401),
    (CubeConnectionError("Connection refused"), "SOURCE_UNREACHABLE", 502),
    (ProviderError("Model compilation failed"), "SOURCE_PROVIDER_ERROR", 502),
])
def test_connection_failure_diagnostics(cube_meta, error, code, status):
    class FailingClient(FakeClient):
        async def meta(self, token):
            raise error

    settings = Settings(database_url="memory", source_admin_token="admin-key")
    provider = CubeProvider(FailingClient(cube_meta), "local")
    with TestClient(create_app(settings, provider)) as client:
        result = client.post("/sources/current:test",
                             headers={"X-Decision-Layer-Admin-Key": "admin-key",
                                      "Authorization": "Bearer caller-token"},
                             json={"api_url": "http://cube.test/cubejs-api/v1", "auth_method": "token"})
    assert result.status_code == status
    assert result.json()["error"]["code"] == code


def test_readiness_uses_canonical_entity_relations_not_cube_ref_format():
    class OtherProvider:
        name = "dbt"
        instance = "warehouse"

        def capabilities(self):
            return CubeProvider(FakeClient({"cubes": []}), "warehouse").capabilities()

        async def discover(self, credentials):
            key = "dbt://warehouse/orders/order_id"
            return SemanticCatalog(provider=self.name, instance=self.instance, objects=[
                SemanticObject(ref="dbt://warehouse/orders/return_rate", kind="measure",
                               data_type="number", title="Return rate", metric_kind="ratio",
                               ratio_parts=("dbt://warehouse/orders/returned", "dbt://warehouse/orders/count"),
                               entity=key),
                SemanticObject(ref="dbt://warehouse/orders/returned", kind="measure",
                               data_type="number", title="Returned", entity=key),
                SemanticObject(ref="dbt://warehouse/orders/count", kind="measure",
                               data_type="number", title="Count", entity=key),
                SemanticObject(ref=key, kind="dimension", data_type="string", title="Order ID", entity=key),
                SemanticObject(ref="dbt://warehouse/orders/created_at", kind="time_dimension",
                               data_type="time", title="Created at", entity=key),
                SemanticObject(ref="dbt://warehouse/customers/segment", kind="dimension",
                               data_type="string", title="Customer segment",
                               entity="dbt://warehouse/customers/customer_id"),
                SemanticObject(ref="dbt://warehouse/customers/lifetime_value", kind="measure",
                               data_type="number", title="Lifetime value",
                               entity="dbt://warehouse/customers/customer_id"),
            ])

    settings = Settings(database_url="memory", allow_service_credentials=True, cube_api_secret="test-secret")
    with TestClient(create_app(settings, OtherProvider())) as client:
        response = client.get("/sources/current/readiness", headers={"Authorization": "Bearer test-user"})
    assert response.status_code == 200
    readiness = response.json()
    assert readiness["provider"] == "dbt"
    metric = next(row for row in readiness["metrics"]
                  if row["metric"]["ref"] == "dbt://warehouse/orders/return_rate")
    assert metric["checks"]["time"]["status"] == "ready"
    assert metric["checks"]["entity_key"]["status"] == "ready"
    assert metric["checks"]["decomposition"]["status"] == "ready"
    assert metric["checks"]["time"]["dimensions"] == ["dbt://warehouse/orders/created_at"]
    other = next(row for row in readiness["metrics"]
                 if row["metric"]["ref"] == "dbt://warehouse/customers/lifetime_value")
    assert other["checks"]["time"]["status"] == "unknown"
    assert other["checks"]["time"]["dimensions"] == []
    assert other["checks"]["entity_key"]["status"] == "missing"
    assert other["checks"]["entity_key"]["impact"] is None


@pytest.mark.parametrize("mode,allowed,token,status", [
    ("token", True, None, 401),
    ("token", True, "accepted", 200),
    ("token", True, "rejected", 401),
    ("none", False, None, 403),
    ("none", True, None, 200),
    ("api_secret", False, None, 403),
])
def test_explicit_auth_matches_test_and_execution(cube_meta, monkeypatch, mode, allowed, token, status):
    for key in ("CUBE_API_URL", "CUBE_API_SECRET", "CUBE_AUTH_METHOD", "CUBE_SERVICE_GROUPS", "CUBE_INSTANCE"):
        monkeypatch.delenv(key, raising=False)
    seen = []

    class RecordingClient(FakeClient):
        async def meta(self, bearer):
            seen.append(bearer)
            if bearer == "rejected":
                raise ProviderAccessDenied("Invalid token")
            return await super().meta(bearer)

    settings = Settings(database_url="memory", source_admin_token="admin",
                        allow_service_credentials=allowed, cube_api_secret="s" * 32)
    app = create_app(settings, CubeProvider(RecordingClient(cube_meta), "local"))
    body = {"api_url": "http://chosen.example/cubejs-api/v1", "auth_method": mode}
    headers = {"X-Decision-Layer-Admin-Key": "admin"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with TestClient(app) as client:
        response = client.post("/sources/current:test", headers=headers, json=body)
        assert response.status_code == status, response.text
        assert client.post("/sources/current:connect-local").status_code == 404
        if status == 403:
            assert client.put("/sources/current", headers=headers, json=body).status_code == 403
            assert seen == []
            return
        assert client.put("/sources/current", headers=headers, json=body).status_code == 200
        result = client.get("/semantic/catalog", headers=headers)
        assert result.status_code == (403 if token == "rejected" else status), result.text
        if token:
            assert seen and all(value == token for value in seen)
        else:
            assert all(value is None for value in seen)
        if mode == "token" and token is None:
            assert seen == []

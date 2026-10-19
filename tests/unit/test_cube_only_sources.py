"""The initial product cannot activate or test a non-Cube connection."""
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from decision_layer.api.app import create_app
from decision_layer.settings import Settings
from decision_layer.sources.config import SourceConfigError, SourceConfigInput, SourceConfigManager
from decision_layer.sources.provider import ConfiguredSemanticProvider, make_provider
from decision_layer.sources.store import MemorySourceStore


@pytest.mark.parametrize("name", ["dbt", "bigquery", "dw", "dm", "postgres", "csv"])
@respx.mock
def test_unsupported_connections_are_rejected_before_network(name):
    with pytest.raises(ValidationError):
        SourceConfigInput(provider=name, api_url="https://unapproved.example/api")
    with pytest.raises(ValueError, match="Cube only"):
        make_provider(name, "https://unapproved.example/api", "old")
    with TestClient(create_app(Settings(database_url="memory", source_admin_token="admin"))) as client:
        assert [item["provider"] for item in client.get("/sources/providers").json()] == ["cube"]
        for verb, path in [("PUT", "/sources/current"), ("POST", "/sources/current:test")]:
            response = client.request(verb, path,
                headers={"X-Decision-Layer-Admin-Key": "admin", "Authorization": "Bearer never-forward"},
                json={"provider": name, "api_url": "https://unapproved.example/api"})
            assert response.status_code == 422
        assert client.get("/sources/current").json()["provider"] == "cube"
    assert not respx.calls


async def test_old_dbt_setting_is_preserved_and_requires_explicit_cube_selection(monkeypatch):
    monkeypatch.delenv("DL_SOURCE_PROVIDER", raising=False)
    monkeypatch.delenv("DL_DEFAULT_SOURCE_PROVIDER", raising=False)
    store = MemorySourceStore()
    prior = {"provider": "dbt", "api_url": "https://old.example/graphql", "instance": "old", "environment_id": 123}
    await store.save(prior)
    settings = Settings(database_url="memory")
    manager = SourceConfigManager(store, settings)
    with pytest.raises(SourceConfigError, match="Cube only"):
        await manager.effective()
    assert await store.get() == prior
    await manager.save(SourceConfigInput(api_url=settings.cube_api_url))
    assert (await manager.view())["provider"] == "cube"
    assert (await store.get())["connections"]["dbt"] == prior


async def test_cube_request_keeps_bound_connection_when_configuration_changes(monkeypatch):
    for key in ("DL_SOURCE_PROVIDER", "CUBE_API_URL", "CUBE_INSTANCE"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(database_url="memory", source_allowed_urls=("https://second.example/cubejs-api/v1",))
    manager = SourceConfigManager(MemorySourceStore(), settings)
    await manager.save(SourceConfigInput(api_url=settings.cube_api_url, instance="first"))
    bound = ConfiguredSemanticProvider(manager)
    bound.bind(await manager.effective())
    await manager.save(SourceConfigInput(api_url="https://second.example/cubejs-api/v1", instance="second"))
    assert (await bound._provider()).instance == "first"
    assert (await ConfiguredSemanticProvider(manager)._provider()).instance == "second"

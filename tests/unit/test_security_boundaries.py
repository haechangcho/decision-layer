import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.settings import Settings
from decision_layer.sources.config import SourceConfigError, SourceConfigInput, SourceConfigManager
from decision_layer.sources.store import MemorySourceStore
from tests.support.semantic import FakeProvider, RR, Q3
from tests.unit.test_access import bearer
from tests.unit.test_recipe_authoring import recipe


@pytest.mark.parametrize("mode", ["shared", "production", ""])
def test_unsupported_deployment_fails_closed(mode):
    with pytest.raises(ValueError, match="Shared deployment requires"):
        create_app(Settings(database_url="memory", deployment_mode=mode))


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data", "http://attacker.invalid", "http://localhost:1"])
def test_unapproved_destination_never_receives_credentials(cube_meta, url):
    settings = Settings(database_url="memory", cube_api_url="http://approved.invalid/api",
                        source_admin_token="admin", cube_api_secret="saved-secret", allow_service_credentials=True)
    provider = FakeProvider(cube_meta)
    async def must_not_discover(credentials):
        raise AssertionError("Unapproved URL reached provider")
    provider.discover = must_not_discover
    with TestClient(create_app(settings, provider)) as client:
        for path, verb in [("/sources/current:test", "POST"), ("/sources/current", "PUT")]:
            response = client.request(verb, path, json={"api_url": url, "auth_method": "api_secret"},
                                      headers={"X-Decision-Layer-Admin-Key": "admin", "Authorization": "Bearer private-token"})
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "SOURCE_ENDPOINT_NOT_APPROVED"


async def test_secret_is_not_reused_after_endpoint_changes(monkeypatch):
    for key in ("CUBE_API_URL", "CUBE_API_SECRET", "CUBE_AUTH_METHOD"):
        monkeypatch.delenv(key, raising=False)
    first, second = "https://one.example/api", "https://two.example/api"
    settings = Settings(database_url="memory", cube_api_url=first, source_allowed_urls=(second,),
                        source_config_key=Fernet.generate_key().decode(), allow_service_credentials=True)
    manager = SourceConfigManager(MemorySourceStore(), settings)
    await manager.save(SourceConfigInput(api_url=first, auth_method="api_secret", api_secret="first-secret"))
    with pytest.raises(SourceConfigError, match="own explicitly supplied secret"):
        await manager.save(SourceConfigInput(api_url=second, auth_method="api_secret"))
    assert (await manager.effective()).api_url == first
    monkeypatch.setenv("CUBE_API_URL", second)
    assert (await manager.effective()).api_secret is None
    # Saving the newly environment-selected address must not rebind the old
    # ciphertext to it, even though it now equals the effective URL.
    with pytest.raises(SourceConfigError, match="own explicitly supplied secret"):
        await manager.save(SourceConfigInput(api_url=second, auth_method="api_secret"))
    await manager.save(SourceConfigInput(api_url=second, auth_method="api_secret", api_secret="second-secret"))
    assert (await manager.effective()).api_secret == "second-secret"


def test_test_endpoint_does_not_reuse_current_secret_for_another_approved_endpoint(cube_meta):
    settings = Settings(database_url="memory", cube_api_url="http://one.example/api", source_admin_token="admin",
                        source_allowed_urls=("http://two.example/api",), cube_api_secret="first-secret",
                        allow_service_credentials=True)
    provider = FakeProvider(cube_meta)
    async def must_not_discover(credentials):
        raise AssertionError("Existing secret escaped to another endpoint")
    provider.discover = must_not_discover
    with TestClient(create_app(settings, provider)) as client:
        response = client.post("/sources/current:test", json={"api_url": "http://two.example/api", "auth_method": "api_secret"},
                               headers={"X-Decision-Layer-Admin-Key": "admin"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SOURCE_SECRET_REQUIRED"


def test_recipe_roles_archive_restore_and_shared_run_promotion(cube_meta, tmp_path):
    settings = Settings(database_url="memory", recipes_dir=str(tmp_path), recipe_editors=("editor",),
                        recipe_publishers=("publisher",))
    with TestClient(create_app(settings, FakeProvider(cube_meta))) as client:
        draft = recipe().model_copy(update={"status": "draft"}).model_dump(mode="json")
        body = {"recipe": draft}
        for subject in ("reader", "service:decision-layer"):
            assert client.put("/recipes/orders-test", headers=bearer(subject), json=body).status_code == 403
        assert client.put("/recipes/orders-test", headers=bearer("editor"), json=body).status_code == 200
        assert client.get("/recipes:drafts", headers=bearer("reader")).status_code == 403
        publish = {"base_version": "1.0.0"}
        assert client.post("/recipes/orders-test/publish", headers=bearer("editor"), json=publish).status_code == 403
        published = client.post("/recipes/orders-test/publish", headers=bearer("publisher"), json=publish)
        assert published.status_code == 200 and published.json()["version"] == "1.0.1"
        assert client.delete("/recipes/orders-test?base_version=1.0.1", headers=bearer("editor")).status_code == 403
        assert client.delete("/recipes/orders-test?base_version=1.0.1", headers=bearer("publisher")).status_code == 204
        assert client.get("/recipes/orders-test", headers=bearer("reader")).status_code == 404
        assert client.post("/recipes/orders-test/restore", headers=bearer("publisher"),
                           json={"base_version": "1.0.1"}).status_code == 200
        run = client.post("/methods/test.series:run", headers=bearer("editor"),
                          json={"bindings": {"metric": RR}, "scope": {"date_range": list(Q3)}}).json()
        run_id = run["run_id"]
        assert client.post(f"/runs/{run_id}:share", headers=bearer("editor"), json={"subjects": ["publisher"]}).status_code == 200
        assert client.get(f"/runs/{run_id}", headers=bearer("publisher")).status_code == 200
        # Even a publisher cannot turn read access into ownership.
        assert client.post(f"/runs/{run_id}/recipe", headers=bearer("publisher"), json={}).status_code == 404
        assert client.get(f"/runs/{run_id}/recipe-candidate?indices=0", headers=bearer("publisher")).status_code == 404


@pytest.mark.parametrize("headers", [{"Host": "rebinding.example"}, {"Origin": "https://attacker.example"}, {"Origin": "null"}])
def test_local_http_rejects_untrusted_host_or_origin(cube_meta, headers):
    settings = Settings(database_url="memory", allow_service_credentials=True, cube_api_secret="local-secret")
    with TestClient(create_app(settings, FakeProvider(cube_meta))) as client:
        assert client.post("/runs", headers=headers, json={}).status_code == 403


def test_provider_subject_cannot_impersonate_local_service_permissions(cube_meta, tmp_path):
    settings = Settings(database_url="memory", recipes_dir=str(tmp_path), allow_service_credentials=True,
                        cube_api_secret="local-secret")
    with TestClient(create_app(settings, FakeProvider(cube_meta))) as client:
        response = client.put("/recipes/orders-test", headers=bearer("service:decision-layer"),
                              json={"recipe": recipe().model_dump(mode="json")})
        assert response.status_code == 403


pytestmark = pytest.mark.usefixtures("query_methods")

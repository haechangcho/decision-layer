from fastapi.testclient import TestClient
import jwt

from decision_layer.api.app import create_app
from decision_layer.semantic.providers.cube.provider import CubeProvider
from decision_layer.settings import Settings
from conftest import ref
from test_cube_provider import FakeClient


def client(cube_meta, **settings):
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret=settings.get("secret"),
                 cube_service_groups=("ecommerce",), database_url="memory", allow_service_credentials=True,
                 recipes_dir=settings.get("recipes_dir"))
    return TestClient(create_app(s, CubeProvider(FakeClient(cube_meta, rows_total=3), "local")))


def test_catalog_and_preview(cube_meta):
    c = client(cube_meta, secret="s")
    assert c.get("/health").json()["status"] == "ok"
    cat = c.get("/semantic/catalog").json()
    assert any(o["ref"] == ref("ecom_order.return_rate") for o in cat["objects"])
    r = c.post("/datasets/preview", json={"grain": "aggregate", "measures": [ref("ecom_order.count")],
                                           "dimensions": [ref("ecom_order.channel")]})
    assert r.status_code == 200 and len(r.json()["rows"]) == 3


def test_errors_are_structured(cube_meta):
    c = client(cube_meta)  # no service secret, no header
    r = c.get("/semantic/catalog")
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    r = c.get("/semantic/objects", params={"ref": ref("ecom_order.nope")}, headers={"Authorization": "Bearer t"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "UNKNOWN_SEMANTIC_OBJECT"
    r = c.post("/datasets/preview", json={"grain": "entity", "measures": [ref("ecom_order.count")]},
               headers={"Authorization": "Bearer t"})
    assert r.status_code == 422  # contract validation (entity grain without entity)


def test_recipe_writes_use_caller_identity_and_create_new_versions(cube_meta, tmp_path):
    c = client(cube_meta, recipes_dir=str(tmp_path))
    document = {"recipe": {"name": "orders-test", "version": "1.0.0", "description": "test",
        "semantic_scope": {"primary_metric": ref("ecom_order.return_rate")}, "mode": "pipeline",
        "steps": [{"id": "trend", "method": "query.trend", "bindings": {"metric": "$scope.primary_metric"},
                   "params": {"granularity": "month"}}]}, "base_version": None}
    assert client(cube_meta, recipes_dir=str(tmp_path)).put("/recipes/orders-test", json=document).status_code == 401
    caller = {"Authorization": f"Bearer {jwt.encode({'sub': 'alice'}, 'test-secret')}"}
    first = c.put("/recipes/orders-test", json=document, headers=caller)
    assert first.status_code == 200, first.json()
    assert first.json()["version"] == "1.0.0"
    stale = c.put("/recipes/orders-test", json=document, headers=caller)
    assert stale.status_code == 409
    document["recipe"]["version"] = "1.0.1"
    document["recipe"]["description"] = "updated"
    document["base_version"] = "1.0.0"
    second = c.put("/recipes/orders-test", json=document, headers=caller)
    assert second.status_code == 200 and second.json()["version"] == "1.0.1"
    assert c.get("/recipes/orders-test", headers=caller).json()["description"] == "updated"


def test_live_recipe_validation_identifies_the_field_for_an_unknown_semantic_ref(cube_meta):
    c = client(cube_meta, secret="s")
    candidate = {"name": "orders-test", "version": "1.0.0", "description": "test",
        "semantic_scope": {"primary_metric": ref("ecom_order.nope")}, "mode": "pipeline",
        "steps": [{"id": "trend", "method": "query.trend", "bindings": {"metric": "$scope.primary_metric"},
                   "params": {"granularity": "month"}}]}
    response = c.post("/recipes:validate?live=true", json=candidate)
    assert response.status_code == 404
    assert response.json()["error"]["details"]["field"] == "semantic_scope.primary_metric"


def test_draft_publish_uses_the_same_recipe_files_and_hides_unpublished_versions(cube_meta, tmp_path):
    c = client(cube_meta, recipes_dir=str(tmp_path), secret="s")
    candidate = {"name": "orders-test", "version": "1.0.0", "description": "test", "status": "draft",
        "semantic_scope": {"primary_metric": ref("ecom_order.return_rate")}, "mode": "pipeline",
        "steps": [{"id": "trend", "method": "query.trend", "bindings": {"metric": "$scope.primary_metric"},
                   "params": {"granularity": "month"}}]}
    saved = c.put("/recipes/orders-test", json={"recipe": candidate, "base_version": None})
    assert saved.status_code == 200, saved.json()
    assert c.get("/recipes").json() == []
    assert [item["name"] for item in c.get("/recipes:drafts").json()] == ["orders-test"]
    assert c.get("/recipes/orders-test").status_code == 404
    assert c.get("/recipes/orders-test/edit").json()["status"] == "draft"
    assert c.post("/runs", json={"recipe": "orders-test@1.0.0"}).status_code == 404

    published = c.post("/recipes/orders-test/publish", json={"base_version": "1.0.0"})
    assert published.status_code == 200, published.json()
    assert published.json()["version"] == "1.0.1"
    assert published.json()["status"] == "published"
    assert c.get("/recipes/orders-test").json()["version"] == "1.0.1"
    assert len(c.get("/recipes").json()) == 1
    assert c.get("/recipes:drafts").json() == []
    assert c.post("/recipes/orders-test/publish", json={"base_version": "1.0.0"}).status_code == 409


def test_recipe_yaml_round_trip_uses_the_canonical_parser(cube_meta):
    c = client(cube_meta, secret="s")
    candidate = {"name": "orders-test", "version": "1.0.0", "description": "test", "status": "draft",
        "semantic_scope": {"primary_metric": ref("ecom_order.return_rate")}, "mode": "pipeline",
        "steps": [{"id": "trend", "method": "query.trend", "bindings": {"metric": "$scope.primary_metric"},
                   "params": {"granularity": "month"}}]}
    formatted = c.post("/recipes:format", json=candidate)
    assert formatted.status_code == 200, formatted.json()
    parsed = c.post("/recipes:parse", json=formatted.json())
    assert parsed.status_code == 200, parsed.json()
    assert parsed.json()["status"] == "draft"
    assert parsed.json()["semantic_scope"]["primary_metric"] == candidate["semantic_scope"]["primary_metric"]
    invalid = c.post("/recipes:parse", json={"yaml": "steps: ["})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_RECIPE_EDIT"


def test_pre_rename_environment_names_still_work(monkeypatch):
    from decision_layer.env import env

    monkeypatch.delenv("DL_LOCALE", raising=False)
    monkeypatch.setenv("ANALYTICA_LOCALE", "ko")
    monkeypatch.setenv("ANALYTICA_URL", "http://old")
    assert env("DL_LOCALE") == "ko" and env("DL_API_URL") == "http://old"
    monkeypatch.setenv("DL_LOCALE", "en")
    assert env("DL_LOCALE") == "en"                     # the new name wins

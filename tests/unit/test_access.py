"""Run ownership, sharing and authentication (ADR-029)."""
import jwt
import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.settings import Settings
from tests.support.semantic import Q3, RR, FakeProvider
from tests.support.runs import REPO_RECIPES

SCOPE = {"date_range": list(Q3)}
COMPARE = {"bindings": {"metric": RR}, "scope": SCOPE}


def bearer(sub=None, groups=("ecommerce",)):
    claims = {"groups": list(groups), **({"sub": sub} if sub else {})}
    return {"Authorization": "Bearer " + jwt.encode(claims, "any-secret-the-fake-accepts", algorithm="HS256")}


@pytest.fixture
def client(cube_meta):
    def make(allow_service=False):
        s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s", cube_service_groups=("ecommerce",),
                     database_url="memory", recipes_dir=str(REPO_RECIPES), allow_service_credentials=allow_service)
        return TestClient(create_app(s, FakeProvider(cube_meta)))
    return make


def test_service_credentials_are_opt_in(client):
    assert client().get("/runs").json()["error"]["code"] == "UNAUTHENTICATED"
    assert client(allow_service=True).get("/runs").status_code == 200


def test_rejected_or_anonymous_tokens(client):
    c = client()
    r = c.get("/runs", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "PROVIDER_ACCESS_DENIED"
    r = c.get("/runs", headers=bearer(sub=None))                   # accepted by the provider but no subject
    assert r.status_code == 403 and "sub" in r.json()["error"]["message"]


def test_runs_are_private_until_shared(client):
    c = client()
    alice, bob = bearer("alice"), bearer("bob")
    run_id = c.post("/methods/query.trend:run", json=COMPARE, headers=alice).json()["run_id"]

    assert [r["id"] for r in c.get("/runs", headers=alice).json()] == [run_id]
    assert c.get("/runs", headers=bob).json() == []
    r = c.get(f"/runs/{run_id}", headers=bob)
    assert r.status_code == 404 and r.json()["error"]["code"] == "UNKNOWN_RUN"   # existence not revealed

    assert c.post(f"/runs/{run_id}:share", json={"subjects": ["alice"]}, headers=bob).status_code == 404
    assert c.post(f"/runs/{run_id}:share", json={"subjects": ["bob"]}, headers=alice).json()["shared_with"] == ["bob"]
    assert c.get(f"/runs/{run_id}", headers=bob).json()["id"] == run_id
    assert c.get("/runs", headers=bob).json() == []                                # list shows own runs only
    c.post(f"/runs/{run_id}:share", json={"subjects": []}, headers=alice)
    assert c.get(f"/runs/{run_id}", headers=bob).status_code == 404


def test_shared_runs_are_read_only(client):
    c = client()
    alice, bob = bearer("alice"), bearer("bob")
    run = c.post("/runs", json={"recipe": "return-rate-investigation", "scope": SCOPE}, headers=alice).json()
    c.post(f"/runs/{run['id']}:share", json={"subjects": ["*"]}, headers=alice)
    assert c.get(f"/runs/{run['id']}", headers=bob).status_code == 200
    step = {"method": "query.trend", "bindings": {"metric": RR}}
    assert c.post(f"/runs/{run['id']}/steps", json=step, headers=bob).status_code == 404
    assert c.post(f"/runs/{run['id']}:complete", json={}, headers=bob).status_code == 404
    assert c.post(f"/runs/{run['id']}/steps", json=step, headers=alice).json()["status"] == "success"


def test_shared_run_hidden_from_viewer_without_access(client):
    c = client()
    alice = bearer("alice")
    carol = bearer("carol", groups=("limited",))                  # carol's catalog lacks the metric
    run_id = c.post("/methods/query.trend:run", json=COMPARE, headers=alice).json()["run_id"]
    c.post(f"/runs/{run_id}:share", json={"subjects": ["*"]}, headers=alice)
    r = c.get(f"/runs/{run_id}", headers=carol)
    assert r.status_code == 403 and r.json()["error"]["code"] == "PROVIDER_ACCESS_DENIED"

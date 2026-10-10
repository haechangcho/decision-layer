import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.settings import Settings
from test_methods import FakeProvider, AMOUNT, Q3


@pytest.fixture
def client(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    app = create_app(Settings(cube_api_url="http://x", cube_instance="local",
        cube_api_secret="test-secret-at-least-32-characters", database_url="memory",
        recipes_dir=str(tmp_path), allow_service_credentials=True), provider)
    return TestClient(app), provider


def request():
    return {"question": "Which manufacturer received most in the first half of 2001?",
        "goals": [{"id": "manufacturer", "description": "Find the top manufacturer"}],
        "scope": {"date_range": ["2001-01-01", "2001-06-30"]},
        "conclusion": {"answer": "The connected catalog does not expose a manufacturer dimension.",
            "goal_outcomes": [{"goal_id": "manufacturer", "status": "unsupported", "reason_code": "semantic_missing",
                               "reason": "Inspected the connected product dimensions"}]},
        "semantic_gaps": [{"goal_id": "manufacturer", "reason": "Manufacturer grouping is required",
            "evidence": "Product dimensions returned by the catalog: brand, commodity, department",
            "proposal": "Review and expose the manufacturer identifier",
            "requirements": [{"description": "Manufacturer", "kind": "dimension"}]}]}


def test_single_call_records_unanswered_question_without_queries_or_approval(client):
    c, provider = client
    response = c.post("/analyses:blocked", json=request(), headers={"X-Decision-Layer-Client": "mcp"})
    assert response.status_code == 200, response.json()
    run = response.json()
    assert run["plan"]["question"] == request()["question"]
    assert run["status"] == "completed" and run["steps"] == [] and provider.calls == 0
    assert run["remediations"][0]["status"] == "proposed"
    assert run["remediations"][0]["requirements"][0]["ref"] is None
    assert c.get(f"/runs/{run['id']}").json()["conclusion"] == run["conclusion"]
    assert len(c.get("/runs").json()) == 1


def test_shared_model_draft_covers_multiple_goals_without_execution(client):
    c, provider = client
    req = request()
    req["goals"].append({"id": "department", "description": "Find departments within the manufacturer"})
    req["conclusion"]["goal_outcomes"].append({"goal_id": "department", "status": "unsupported", "reason_code": "semantic_missing", "reason": "Manufacturer filtering also requires this dimension"})
    gap = req["semantic_gaps"][0]
    gap["related_goal_ids"] = ["department"]
    gap["model_drafts"] = [{"provider": "dbt", "title": "Dimension fragment",
        "yaml": 'dimensions:\n  - name: "<dimension_name>"\n    type: categorical\n    expr: "<source_column>"',
        "basis": [gap["evidence"]], "unresolved": ["Physical column and owning model unknown"]}]
    response = c.post("/analyses:blocked", json=req)
    assert response.status_code == 200, response.json()
    saved = response.json()["remediations"]
    assert len(saved) == 1 and saved[0]["related_goal_ids"] == ["department"]
    assert saved[0]["model_drafts"] == gap["model_drafts"]
    assert provider.calls == 0
    req["semantic_gaps"].append({**gap, "goal_id": "department", "related_goal_ids": []})
    assert c.post("/analyses:blocked", json=req).status_code == 400
    assert len(c.get("/runs").json()) == 1


@pytest.mark.parametrize("change", ["supported", "missing_proposal", "access_proposal", "bad_evidence"])
def test_invalid_diagnosis_creates_no_half_finished_run(client, change):
    c, _provider = client
    req = request()
    if change == "supported":
        req["conclusion"]["goal_outcomes"][0]["status"] = "supported"
    elif change == "missing_proposal":
        req["semantic_gaps"] = []
    elif change == "access_proposal":
        req["conclusion"]["goal_outcomes"][0]["reason_code"] = "access_denied"
    else:
        req["conclusion"]["findings"] = [{"text": "Invented answer", "step_indices": [0]}]
    assert c.post("/analyses:blocked", json=req).status_code == 400
    assert c.get("/runs").json() == []


def test_reuses_existing_run_and_preserves_its_question(client):
    c, _provider = client
    req = request()
    started = c.post("/runs", json={"question": req["question"], "goals": req["goals"], "scope": req["scope"]}).json()
    req["run_id"] = started["id"]
    assert c.post("/analyses:blocked", json=req).json()["id"] == started["id"]
    assert len(c.get("/runs").json()) == 1
    assert c.post("/analyses:blocked", json=req).status_code == 400


def test_nonsemantic_failure_records_no_model_proposal(client):
    c, provider = client
    req = request()
    req["semantic_gaps"] = []
    req["conclusion"]["goal_outcomes"][0]["reason_code"] = "method_missing"
    run = c.post("/analyses:blocked", json=req).json()
    assert run["remediations"] == [] and provider.calls == 0


def test_partial_analysis_keeps_executed_steps_in_same_run(client):
    c, _provider = client
    req = request()
    req["scope"] = {"date_range": list(Q3)}
    req["goals"].append({"id": "total", "description": "Inspect total", "semantic_refs": [AMOUNT]})
    started = c.post("/runs", json={"question": req["question"], "goals": req["goals"], "scope": req["scope"]}).json()
    run_id = started["id"]
    result = c.post(f"/runs/{run_id}/steps", json={"method": "query.aggregate", "bindings": {"metric": AMOUNT}, "goal_ids": ["total"]})
    assert result.status_code == 200 and result.json()["status"] == "success"
    before = c.get(f"/runs/{run_id}").json()
    req["run_id"] = run_id
    # get_run supplies the complete original typed goals, not a newly invented subset.
    req["goals"] = before["goals"]
    req["conclusion"]["goal_outcomes"].append({"goal_id": "total", "status": "supported", "step_indices": [0]})
    req["conclusion"]["findings"] = [{"text": "The total was queried; manufacturer grouping remains unavailable.", "step_indices": [0]}]
    response = c.post("/analyses:blocked", json=req)
    assert response.status_code == 200, response.json()
    assert response.json()["steps"] == before["steps"]
    assert response.json()["id"] == run_id
    assert len(c.get("/runs").json()) == 1

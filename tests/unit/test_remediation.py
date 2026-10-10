import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import AnalysisGoal, CallerInfo, SemanticObject
from decision_layer.methods.base import InvalidBinding
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs import remediation
from decision_layer.runs.engine import RunBusy, RunEngine
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore, UnknownRun
from decision_layer.service import RemediationCreateRequest, RemediationReviewRequest, RemediationCheckRequest, RemediationRetryRequest
from decision_layer.settings import Settings
from test_methods import FakeProvider, CREDS, AMOUNT, Q3

MISSING = "cube://local/customer/pre_spending_band"
ME = CallerInfo(subject="alice")


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_review_refresh_retry_and_preserve_history(cube_meta, tmp_path, backend):
    provider = FakeProvider(cube_meta)
    store = MemoryRunStore() if backend == "memory" else SqliteRunStore(str(tmp_path / "runs.db"))
    engine = RunEngine(provider, RecipeStore(tmp_path, "cube", "local"), store)
    run = await engine.start(CREDS, ME, recipe=None, question="Compare spending controlling prior spending",
        scope={"date_range": list(Q3)}, goals=[AnalysisGoal(id="compare", description="Compare comparable households")])
    original = run.model_dump()
    req = RemediationCreateRequest(goal_id="compare", reason="No prior spending dimension found",
        evidence="Inspected the connected catalog", proposal="Add a pre-period spending band",
        requirements=[{"description": "Pre-period spending", "kind": "dimension"}])
    run = await remediation.create(engine, ME, run.id, req)
    item = run.remediations[0]
    with pytest.raises(InvalidBinding):
        await remediation.recheck(engine, CREDS, ME, run.id, item.id, RemediationCheckRequest(base_revision=0))
    with pytest.raises(UnknownRun):
        await remediation.review(engine, CallerInfo(subject="bob"), run.id, item.id,
            RemediationReviewRequest(base_revision=0, decision="confirmed", note="Reviewed", requirements=item.requirements))
    reviewed = RemediationReviewRequest(base_revision=0, decision="confirmed", note="Pre-treatment band is needed",
        requirements=[{"description": "Pre-period spending", "kind": "dimension", "ref": MISSING, "data_type": "string"}])
    run = await remediation.review(engine, ME, run.id, item.id, reviewed)
    with pytest.raises(RunBusy):
        await remediation.review(engine, ME, run.id, item.id, reviewed)
    run = await remediation.recheck(engine, CREDS, ME, run.id, item.id, RemediationCheckRequest(base_revision=1))
    assert not run.remediations[0].checks[-1]["ready"]
    assert run.remediations[0].checks[-1]["results"][0]["issues"] == ["not_visible"]
    with pytest.raises(InvalidBinding):
        await remediation.retry(engine, CREDS, ME, run.id, item.id, RemediationRetryRequest(base_revision=2), "web", 5)
    run = await store.get(run.id)
    provider.catalog.objects.append(SemanticObject(ref=MISSING, title="Prior spending band", kind="dimension", data_type="string"))
    calls = []
    async def refresh(creds):
        calls.append(creds)
        return provider.catalog
    provider.refresh_catalog = refresh
    retry = await remediation.retry(engine, CREDS, ME, run.id, item.id,
        RemediationRetryRequest(base_revision=run.remediations[0].revision), "web", 5)
    assert calls == [CREDS]
    assert retry.id != run.id and retry.retry_of.run_id == run.id
    assert retry.plan.question == run.plan.question and retry.goals == run.goals
    assert retry.plan.scope["date_range"] == list(Q3)
    assert retry.steps == [] and retry.plan.recipe is None and retry.status == "open"
    assert provider.calls == 0
    old = await store.get(run.id)
    for field in ("steps", "conclusion", "plan", "created_at", "status"):
        assert old.model_dump()[field] == original[field]
    assert old.remediations[0].events[-1]["run_id"] == retry.id
    from decision_layer.core.models import PlanStep
    _, result = await engine.step(CREDS, ME, retry.id, PlanStep(method="query.aggregate", bindings={"metric": AMOUNT}))
    assert result.status == "success"
    assert (await store.get(run.id)).steps == []


def test_api_model_checks_and_invalid_goals(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="test-secret-at-least-32-characters",
        database_url="memory", recipes_dir=str(tmp_path), allow_service_credentials=True)
    client = TestClient(create_app(settings, provider))
    run = client.post("/runs", json={"question": "Compare spending", "goals": [{"id": "compare", "description": "Compare"}], "scope": {"date_range": list(Q3)}}).json()
    path = f"/runs/{run['id']}"
    body = {"goal_id": "unknown", "reason": "Missing", "evidence": "Catalog inspected", "proposal": "Add definition", "requirements": [{"description": "Spend", "kind": "measure", "ref": AMOUNT, "metric_kind": "average"}]}
    assert client.post(path + "/remediations", json=body).status_code == 400
    body["goal_id"] = "compare"
    response = client.post(path + "/remediations", json=body)
    assert response.status_code == 200, response.json()
    item = response.json()["remediations"][0]
    fix = path + f"/remediations/{item['id']}"
    reviewed = client.put(fix, json={"base_revision": 0, "decision": "confirmed", "note": "Reviewed", "requirements": item["requirements"]})
    assert reviewed.status_code == 200
    checked = client.post(fix + ":check", json={"base_revision": 1})
    assert checked.status_code == 200
    assert "metric_kind_mismatch" in checked.json()["remediations"][0]["checks"][-1]["results"][0]["issues"]
    assert client.post(fix + ":retry", json={"base_revision": 2}).status_code == 400
    assert len(client.get("/runs").json()) == 1


async def test_private_requirement_and_dismissal_block_retry(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    e = RunEngine(provider, RecipeStore(tmp_path, "cube", "local"), MemoryRunStore())
    run = await e.start(CREDS, ME, recipe=None, question="Find answer", scope={"date_range": list(Q3)}, goals=[AnalysisGoal(id="a", description="Answer")])
    run = await remediation.create(e, ME, run.id, RemediationCreateRequest(goal_id="a", reason="Unavailable",
        evidence="Catalog", proposal="Review", requirements=[{"description": "Metric", "kind": "measure", "ref": AMOUNT}]))
    item = run.remediations[0]
    provider.catalog.get(AMOUNT).public = False
    run = await remediation.review(e, ME, run.id, item.id, RemediationReviewRequest(base_revision=0,
        decision="confirmed", note="Check access", requirements=item.requirements))
    run = await remediation.recheck(e, CREDS, ME, run.id, item.id, RemediationCheckRequest(base_revision=1))
    assert run.remediations[0].checks[-1]["results"][0]["title"] is None
    run = await remediation.review(e, ME, run.id, item.id, RemediationReviewRequest(base_revision=2,
        decision="dismissed", note="Not a model defect", requirements=item.requirements))
    with pytest.raises(InvalidBinding):
        await remediation.retry(e, CREDS, ME, run.id, item.id, RemediationRetryRequest(base_revision=3), "web", 5)


async def test_retry_rechecks_access_and_keeps_goals(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    e = RunEngine(provider, RecipeStore(tmp_path, "cube", "local"), MemoryRunStore())
    run = await e.start(CREDS, ME, recipe=None, question="Inspect total", scope={"date_range": list(Q3)},
        goals=[AnalysisGoal(id="a", description="Inspect total", semantic_refs=[AMOUNT], required_capabilities=["aggregate"])])
    req = RemediationCreateRequest(goal_id="a", reason="Verify definition", evidence="Catalog inspected", proposal="Review metric",
        requirements=[{"description": "Metric", "kind": "measure", "ref": AMOUNT}])
    run = await remediation.create(e, ME, run.id, req)
    fix = run.remediations[0]
    run = await remediation.review(e, ME, run.id, fix.id, RemediationReviewRequest(base_revision=0, decision="confirmed", note="Verified", requirements=fix.requirements))
    run = await remediation.recheck(e, CREDS, ME, run.id, fix.id, RemediationCheckRequest(base_revision=1))
    assert run.remediations[0].checks[-1]["ready"]
    # Approval and an earlier metadata pass do not authorize a later private definition.
    provider.catalog.get(AMOUNT).public = False
    with pytest.raises(InvalidBinding):
        await remediation.retry(e, CREDS, ME, run.id, fix.id, RemediationRetryRequest(base_revision=2), "web", 5)
    assert len(await e.list(ME)) == 1
    provider.catalog.get(AMOUNT).public = True
    current = await e.store.get(run.id)
    with pytest.raises(InvalidBinding):
        await remediation.retry(e, CREDS, ME, run.id, fix.id, RemediationRetryRequest(base_revision=current.remediations[0].revision,
            goals=[AnalysisGoal(id="a", description="Different question")]), "web", 5)
    assert len(await e.list(ME)) == 1

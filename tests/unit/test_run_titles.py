"""Display metadata must never replace the analytical question or evidence."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from decision_layer.api.app import create_app
from decision_layer.core.models import AnalysisPlan, CallerInfo, Run, RunningJob
from decision_layer.runs.errors import RunBusy, RunTitleConflict
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore, UnknownRun
from decision_layer.service import RunTitleRequest
from decision_layer.settings import Settings
from tests.support.runs import ME, SCOPE, engine
from tests.support.semantic import CREDS


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_rename_is_owner_only_revision_checked_and_preserves_evidence(
    provider, tmp_path, backend
):
    store = (
        MemoryRunStore()
        if backend == "memory"
        else SqliteRunStore(str(tmp_path / "runs.db"))
    )
    e = engine(provider, store, recipes_dir=tmp_path)
    question = "긴 질문 원문입니다. 조건과 요청을 모두 그대로 보존해야 합니다.\n추가 요청도 포함합니다."
    run = await e.start(
        CREDS, ME, recipe=None, question=question, scope=SCOPE, title="수취액 점검"
    )
    run.shared_with = ["bob"]
    await store.save(run)
    before = run.model_dump(mode="json")
    with pytest.raises(UnknownRun):
        await e.rename(CallerInfo(subject="bob"), run.id, "Changed by reader", 0)
    renamed = await e.rename(ME, run.id, "  1월 수취액\n 상품군 분석  ", 0)
    assert renamed.title == "1월 수취액 상품군 분석"
    assert renamed.title_revision == 1
    after = (await store.get(run.id)).model_dump(mode="json")
    assert {
        k: v for k, v in before.items() if k not in ("title", "title_revision")
    } == {k: v for k, v in after.items() if k not in ("title", "title_revision")}
    with pytest.raises(RunTitleConflict):
        await e.rename(ME, run.id, "Stale title", 0)
    renamed.running = RunningJob(kind="step")
    await store.save(renamed)
    with pytest.raises(RunBusy):
        await e.rename(ME, run.id, "Busy title", 1)
    renamed.running = None
    renamed.status = "completed"
    await store.save(renamed)
    assert (await e.rename(ME, run.id, "완료한 분석", 1)).title == "완료한 분석"


@pytest.mark.parametrize("title", ["", "  \n ", "x" * 81])
def test_invalid_titles_are_rejected(title):
    with pytest.raises(ValidationError):
        RunTitleRequest(title=title, base_revision=0)


def test_historical_run_gets_bounded_label_without_mutating_question():
    original = "긴 질문 전체 " * 50
    legacy = Run.model_validate({"id": "old", "plan": {"question": original}})
    assert len(legacy.title) <= 80 and legacy.title.endswith("…")
    assert legacy.plan.question == original
    assert legacy.title_revision == 0
    assert Run(id="blank", plan=AnalysisPlan(question="   ")).title.strip()


def test_canonical_api_accepts_title_then_renames_only_metadata(provider, tmp_path):
    settings = Settings(
        cube_api_url="http://x",
        cube_instance="local",
        cube_api_secret="test-secret-at-least-32-characters",
        database_url="memory",
        recipes_dir=str(tmp_path),
        allow_service_credentials=True,
    )
    c = TestClient(create_app(settings, provider))
    original = "A complete user question with every condition preserved."
    run = c.post(
        "/runs", json={"question": original, "title": "Short topic", "scope": SCOPE}
    ).json()
    path = f"/runs/{run['id']}/title"
    r = c.patch(path, json={"title": "Renamed topic", "base_revision": 0})
    assert r.status_code == 200, r.json()
    assert r.json()["title"] == "Renamed topic"
    assert r.json()["plan"]["question"] == original
    assert c.patch(path, json={"title": "Stale", "base_revision": 0}).status_code == 409
    assert c.patch(path, json={"title": "", "base_revision": 1}).status_code == 422
    assert c.get("/runs").json()[0]["title"] == "Renamed topic"


async def test_mcp_transports_short_title_and_original_question(monkeypatch):
    from decision_layer.mcp import server

    calls = []

    async def call(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "id": "run",
            "title": "상품군 점검",
            "title_revision": 1,
            "status": "open",
            "caller": {},
            "plan": {"question": "원래 질문 전체", "scope": {}},
            "steps": [],
        }

    monkeypatch.setattr(server, "_call", call)
    compact = await server.start_analysis(
        "원래 질문 전체", goals=[], title="상품군 점검"
    )
    assert calls[-1][2]["json"]["question"] == "원래 질문 전체"
    assert calls[-1][2]["json"]["title"] == compact["title"] == "상품군 점검"
    await server.start_run("recipe", "원래 질문 전체", goals=[], title="상품군 점검")
    assert calls[-1][2]["json"]["title"] == "상품군 점검"
    renamed = await server.rename_run("run", "새 제목", 0)
    assert renamed["title_revision"] == 1
    assert calls[-1] == (
        "PATCH",
        "/runs/run/title",
        {"json": {"title": "새 제목", "base_revision": 0}},
    )

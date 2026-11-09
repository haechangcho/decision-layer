import pytest
from decision_layer.core.models import RunConclusion, RunFinding, CallerInfo
from decision_layer.methods import InvalidBinding
from decision_layer.runs.errors import RunBusy, RunConclusionConflict
from decision_layer.runs.store import UnknownRun
from tests.support.runs import engine, ME, SCOPE
from tests.support.semantic import CREDS


async def completed(provider, tmp_path):
    e = engine(provider, recipes_dir=tmp_path)
    run = await e.start(
        CREDS, ME, recipe=None, question="Original question", scope=SCOPE
    )
    run = await e.complete(
        ME, run.id, None, RunConclusion(answer="Original answer", findings=[])
    )
    return e, run


async def test_revision_preserves_old_answer_and_all_execution_evidence(
    provider, tmp_path
):
    e, run = await completed(provider, tmp_path)
    before = run.model_dump(mode="json")
    corrected = await e.revise_conclusion(
        ME,
        run.id,
        RunConclusion(answer="Corrected answer", findings=[]),
        0,
        "Clarify the observation",
    )
    assert corrected.conclusion.answer == "Corrected answer"
    assert corrected.conclusion_history[0]["conclusion"]["answer"] == "Original answer"
    assert corrected.conclusion_history[0]["reason"] == "Clarify the observation"
    after = corrected.model_dump(mode="json")
    changed = {"conclusion", "summary", "conclusion_history", "conclusion_author"}
    assert {k: v for k, v in before.items() if k not in changed} == {
        k: v for k, v in after.items() if k not in changed
    }
    with pytest.raises(RunConclusionConflict):
        await e.revise_conclusion(
            ME, run.id, RunConclusion(answer="Stale", findings=[]), 0, "Old revision"
        )
    with pytest.raises(UnknownRun):
        await e.revise_conclusion(
            CallerInfo(subject="another"),
            run.id,
            RunConclusion(answer="Other", findings=[]),
            1,
            "Not mine",
        )
    with pytest.raises(InvalidBinding):
        await e.revise_conclusion(
            ME,
            run.id,
            RunConclusion(
                answer="Bad link",
                findings=[RunFinding(text="Made up", step_indices=[8])],
            ),
            1,
            "Invalid step",
        )


async def test_open_run_cannot_be_revised(provider, tmp_path):
    e = engine(provider, recipes_dir=tmp_path)
    run = await e.start(CREDS, ME, recipe=None, question="Question", scope=SCOPE)
    with pytest.raises(RunBusy):
        await e.revise_conclusion(
            ME, run.id, RunConclusion(answer="Too early", findings=[]), 0, "Not done"
        )


async def test_conclusion_review_mcp_uses_canonical_api(monkeypatch):
    from decision_layer.mcp import server
    from decision_layer.service import RunConclusionReview

    calls = []

    async def call(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "id": "run",
            "caller": {},
            "plan": {},
            "steps": [],
            "status": "completed",
            "conclusion_history": [{}],
        }

    monkeypatch.setattr(server, "_call", call)
    result = await server.review_run_conclusion(
        "run",
        RunConclusionReview(
            conclusion=RunConclusion(answer="New", findings=[]),
            base_revision=0,
            reason="Correction",
        ),
    )
    assert calls[0][:2] == ("POST", "/runs/run/conclusion-reviews")
    assert calls[0][2]["json"]["base_revision"] == 0
    assert result["conclusion_revision"] == 1

"""Retire classification metadata without losing stored evidence or input checks."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from decision_layer.api.app import create_app
from decision_layer.core.models import AnalysisGoal, PlanStep
from decision_layer.settings import Settings
from tests.support.runs import ME, SCOPE, engine
from tests.support.semantic import AMOUNT, CAT, CREDS, FakeProvider


def test_public_contracts_do_not_require_or_expose_classification(cube_meta, tmp_path):
    settings = Settings(
        cube_api_url="http://fixture",
        cube_instance="local",
        cube_api_secret="fixture-secret",
        cube_service_groups=("ecommerce",),
        allow_service_credentials=True,
        database_url="memory",
        recipes_dir=str(tmp_path),
    )
    with TestClient(create_app(settings, FakeProvider(cube_meta))) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]
        assert "Interpretation" not in schemas
        for name in ("MethodManifest", "Result", "AnalysisGoal"):
            assert "interpretation" not in schemas[name]["properties"]
        methods = client.get("/methods").json()
        assert methods and all("interpretation" not in item for item in methods)
    # Requests still reject unknown goal fields rather than silently accepting typos.
    with pytest.raises(ValidationError):
        AnalysisGoal(id="answer", description="Answer", interpretation="association")
    with pytest.raises(ValidationError):
        AnalysisGoal(id="answer", description="Answer", unknown_field=True)


async def test_old_run_loads_goals_and_query_evidence_without_retired_fields(
    provider, tmp_path, query_methods
):
    service = engine(provider, recipes_dir=tmp_path)
    run = await service.start(
        CREDS,
        ME,
        recipe=None,
        question="Compare the requested groups",
        scope=SCOPE,
        goals=[
            AnalysisGoal(
                id="answer", description="Compare groups", semantic_refs=[AMOUNT]
            )
        ],
    )
    run, result = await service.step(
        CREDS,
        ME,
        run.id,
        PlanStep(
            method="test.lookup",
            bindings={"metric": AMOUNT, "dimensions": [CAT]},
            goal_ids=["answer"],
        ),
    )
    assert result.status == "success"
    original = run.model_dump(mode="json")
    stored = json.loads(json.dumps(original))
    stored["goals"][0]["interpretation"] = "descriptive"
    stored["steps"][0]["result"]["interpretation"] = "descriptive"
    old_json = json.dumps(stored)
    service.store._runs[run.id] = old_json

    restored = await service.get(CREDS, ME, run.id)
    assert restored.model_dump(mode="json") == original
    assert restored.steps[0].result.provenance.queries
    assert service.store._runs[run.id] == old_json

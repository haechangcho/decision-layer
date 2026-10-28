"""Removal means no installed code or execution fallback; stored evidence survives."""

import json
from datetime import datetime, timezone
import pytest
import yaml
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import (
    AnalysisPlan,
    Artifact,
    PlanStep,
    Recipe,
    Result,
    Run,
    StepRecord,
)
from decision_layer.methods import InvalidBinding, registry
from decision_layer.methods.loading import configured_registry
from decision_layer.recipes.authoring import RecipeEditError, validate_recipe
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore
from decision_layer.settings import Settings
from tests.support.runs import ME, SCOPE
from tests.support.semantic import AMOUNT, CREDS

REMOVED = {
    "query.aggregate": "1.0.0",
    "query.trend": "1.0.0",
    "query.drilldown": "2.0.0",
    "query.peer_comparison": "1.0.0",
    "query.unit_change": "1.0.0",
    "query.unit_distribution": "1.0.0",
    "causal.cem": "1.1.1",
    "stats.ols": "1.0.0",
    "stats.binary_regression": "1.0.0",
    "stats.linear_dml": "1.0.0",
    "stats.two_period_contrast": "1.0.0",
    "stats.adjusted_difference": "1.0.0",
    "stats.dml": "1.0.0",
    "stats.did": "1.0.0",
    "stats.period_change": "1.0.0",
    "stats.series_diagnostics": "1.1.0",
    "analysis.trend": "1.1.0",
    "analysis.peer_comparison": "1.0.1",
    "guide.metric_lookup": "1.0.1",
    "guide.breakdown": "1.0.1",
    "guide.peer_comparison": "1.0.1",
}
OLDER = [
    ("analysis.metric_lookup", "1.0.0"),
    ("analysis.metric_lookup", "2.1.0"),
    ("analysis.drilldown", "1.0.1"),
    ("analysis.drilldown", "1.1.0"),
    ("analysis.drilldown", "2.1.0"),
    ("analysis.trend", "1.0.0"),
    ("stats.binary_matching", "1.0.0"),
    ("stats.regression_adjustment", "1.0.0"),
    ("stats.series_diagnostics", "1.0.0"),
    ("stats.binary_matching", "1.1.0"),
    ("stats.regression_adjustment", "1.1.0"),
]
CURRENT = {
    "analysis.metric_lookup",
    "analysis.drilldown",
    "stats.regression_adjustment",
    "stats.binary_matching",
}


def test_only_four_current_definitions_ship_without_hidden_registration():
    own = configured_registry(Settings())
    assert set(own._methods) == {m.name for m in own.manifests()} == CURRENT
    assert len(own._versions) == 4
    assert not hasattr(own, "_compatibility")
    for name, version in [*REMOVED.items(), *OLDER]:
        with pytest.raises(InvalidBinding):
            own.get(name, version)
    for name in REMOVED:
        with pytest.raises(InvalidBinding):
            own.get(name)


def test_removed_methods_cannot_be_described_edited_or_run(provider, tmp_path):
    settings = Settings(
        database_url="memory",
        recipes_dir=str(tmp_path),
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
    )
    with TestClient(create_app(settings, provider)) as client:
        assert {m["name"] for m in client.get("/methods").json()} == CURRENT
        for name, version in REMOVED.items():
            assert client.get(f"/methods/{name}").status_code == 400
            assert client.get(f"/methods/{name}/source").status_code == 400
            response = client.post(
                f"/methods/{name}:run",
                json={
                    "method_version": version,
                    "bindings": {"metric": AMOUNT},
                    "scope": SCOPE,
                },
            )
            assert response.status_code == 400
        assert client.post("/datasets/preview", json={}).status_code == 404
        assert client.get("/runs").json() == []
    assert provider.calls == 0


@pytest.mark.parametrize("pin", [None, "1.0.0"])
async def test_old_recipe_remains_readable_but_cannot_execute_or_publish(
    provider, tmp_path, pin
):
    recipe = Recipe(
        name="archived",
        version="1.0.0",
        description="Stored old procedure",
        mode="pipeline",
        semantic_scope={"primary_metric": AMOUNT},
        steps=[
            PlanStep(
                id="old",
                method="query.aggregate",
                method_version=pin,
                bindings={"metric": AMOUNT},
            )
        ],
    )
    (tmp_path / "archived.yaml").write_text(
        yaml.safe_dump(recipe.model_dump(mode="json"))
    )
    original = (tmp_path / "archived.yaml").read_bytes()
    recipes = RecipeStore(tmp_path, "cube", "local")
    assert recipes.get("archived") == recipe
    from decision_layer.recipes.routing import search_recipes

    found = await search_recipes(
        recipes, provider, CREDS, "Stored old procedure", [], {}, 5
    )
    assert found["candidates"] == []
    with pytest.raises(RecipeEditError):
        validate_recipe(recipe)
    engine = RunEngine(provider, recipes, MemoryRunStore())
    with pytest.raises(InvalidBinding):
        await engine.start(CREDS, ME, recipe="archived", question="Replay", scope=SCOPE)
    assert provider.calls == 0
    assert (tmp_path / "archived.yaml").read_bytes() == original


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_historical_results_and_source_are_readable_without_installing_method(
    tmp_path, backend
):
    from decision_layer.core.models import MethodSource, SourceFile
    from hashlib import sha256

    source = "class Aggregate: pass\n"
    now = datetime.now(timezone.utc)
    run = Run(
        id="historical-removed-method",
        caller=ME,
        plan=AnalysisPlan(),
        status="completed",
        steps=[
            StepRecord(
                step=PlanStep(id="old", method="query.aggregate"),
                method="method://query/aggregate@1.0.0",
                result=Result(
                    status="success",
                    primary=Artifact(type="table", data=[{"value": 3}]),
                ),
                code=MethodSource(
                    name="query.aggregate",
                    version="1.0.0",
                    available=True,
                    files=[
                        SourceFile(
                            name="old.aggregate",
                            content=source,
                            sha256=sha256(source.encode()).hexdigest(),
                        )
                    ],
                ),
                started_at=now,
                finished_at=now,
            )
        ],
    )
    store = (
        MemoryRunStore()
        if backend == "memory"
        else SqliteRunStore(str(tmp_path / "history.db"))
    )
    await store.save(run)
    restored = await store.get(run.id)
    assert restored.steps[0].result.primary.data == [{"value": 3}]
    assert restored.steps[0].code.files[0].content == source
    with pytest.raises(InvalidBinding):
        registry.get("query.aggregate", "1.0.0")


async def test_current_campaign_example_uses_only_current_skills():
    from examples.recipes.skill_chain import campaign_recipe
    from examples.recipes.skill_chain_demo import demonstrate

    assert {s.method for s in campaign_recipe().steps} <= CURRENT
    run = await demonstrate()
    assert run.status == "completed"
    assert [s.step.method for s in run.steps] == [
        "analysis.drilldown",
        "analysis.metric_lookup",
    ]
    assert len(run.query_attempts) == 3

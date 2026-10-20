"""Installed starters are editable project definitions, executed by canonical APIs."""

from pathlib import Path
import shutil
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient

from decision_layer.cli import main
from decision_layer.core.models import DatasetSpec, TimeScope
from decision_layer.methods import InvalidBinding, registry
from decision_layer.methods.loading import configured_registry
from decision_layer.project import PROJECT_FILE, Project, ProjectError
from decision_layer.project_scaffold import init_project
from decision_layer.settings import Settings
from decision_layer.testing import FixtureProvider, QueryFixture
from tests.support.methods.cases import BASELINE, DATE, FEB, M, TREAT, UNIT, catalog

EXPECTED = {
    "analysis.metric_lookup",
    "analysis.drilldown",
    "stats.regression_adjustment",
    "stats.binary_matching",
}


@pytest.fixture
def project(tmp_path):
    return init_project(tmp_path / "team", "team_" + uuid4().hex)


def test_default_project_owns_all_discovered_definitions(project):
    target = configured_registry(Settings(project_dir=str(project.root)))
    assert {m.name for m in target.manifests()} == EXPECTED
    for name in EXPECTED:
        method = target.get(name)
        assert method.manifest.version == "2.0.0"
        assert Path(method.definition_path).is_relative_to(project.methods_dir)
        assert Path(method.definition_path).is_file()
        # Legacy pinned Recipes retain their exact implementation and contract.
        old = registry.get(name)
        assert target.get(name, old.manifest.version) is old
    assert registry.get("stats.regression_adjustment").manifest.version == "1.1.0"


def test_removing_a_starter_does_not_resurrect_a_package_default(project):
    shutil.rmtree(project.methods_dir / "matching")
    target = configured_registry(Settings(project_dir=str(project.root)))
    assert {m.name for m in target.manifests()} == EXPECTED - {"stats.binary_matching"}
    with pytest.raises(InvalidBinding, match="Unknown method"):
        target.get("stats.binary_matching")
    assert target.get("stats.binary_matching", "1.1.0")


def test_failed_project_load_preserves_registry(project):
    (project.methods_dir / "ols" / "method.py").write_text("not valid Python syntax !")
    target = registry.copy()
    before = [(m.name, m.version) for m in target.manifests()]
    with pytest.raises(ProjectError):
        project.load(target)
    assert [(m.name, m.version) for m in target.manifests()] == before


def test_legacy_config_keeps_package_defaults(tmp_path):
    project = init_project(tmp_path / "legacy", "legacy_" + uuid4().hex, empty=True)
    (project.root / PROJECT_FILE).write_text(f"name: {project.config.name}\n")
    target = registry.copy()
    Project.find(project.root).load(target)
    assert {m.name for m in target.manifests()} == EXPECTED
    assert target.get("stats.regression_adjustment").manifest.version == "1.1.0"


def test_project_files_survive_reinitialization(project):
    path = project.methods_dir / "ols" / "method.py"
    source = path.read_text() + "\n# Team customization\n"
    path.write_text(source)
    with pytest.raises(ProjectError, match="not empty"):
        init_project(project.root)
    assert path.read_text() == source


def test_generated_calculation_tests_run_without_cube(project, capfd):
    assert main(["test", "--project", str(project.root)]) == 0
    assert "13 passed" in capfd.readouterr().out


@pytest.mark.parametrize(
    "method", ["stats.regression_adjustment", "stats.binary_matching"]
)
async def test_starter_executes_through_mcp_rest_and_spawned_worker(
    project, tmp_path, monkeypatch, method
):
    from decision_layer.api.app import create_app
    from decision_layer.mcp import server

    x = np.tile(np.linspace(-1, 1, 100), 2)
    treatment = np.repeat([0, 1], 100)
    rows = [
        [float(3 * x[i] + 2 * treatment[i]), int(treatment[i]), float(x[i]), str(i)]
        for i in range(200)
    ]
    query = DatasetSpec(
        grain="entity",
        measures=[M],
        dimensions=[TREAT, BASELINE],
        entity=UNIT,
        time=TimeScope(dimension=DATE, date_range=FEB),
        limit_rows=50001,
    )
    provider = FixtureProvider(catalog(), [QueryFixture(query, rows)])
    settings = Settings(
        project_dir=str(project.root),
        database_url="memory",
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
        cube_service_groups=("ecommerce",),
        recipes_dir=str(tmp_path / "recipes"),
    )
    with TestClient(create_app(settings, provider)) as client:

        async def call(verb, path, **kwargs):
            response = client.request(verb, path, **kwargs)
            assert response.status_code == 200, response.text
            return response.json()

        monkeypatch.setattr(server, "_call", call)
        monkeypatch.setattr(server, "METHODS", set())
        methods = (await server.list_methods())["methods"]
        assert {item["name"] for item in methods} == EXPECTED
        manifest = await server.describe_method(method)
        assert manifest["version"] == "2.0.0"
        assert "entity_id" in manifest["roles"]
        run = client.post(
            "/runs",
            json={
                "question": "Compare the observed groups",
                "scope": {"date_range": list(FEB), "time_dimension": DATE},
            },
        ).json()
        result = await server.run_step(
            run["id"],
            method,
            bindings={
                "entity_id": UNIT,
                "outcome": M,
                "treatment": TREAT,
                "confounders": [BASELINE],
            },
            params={},
            purpose="Apply the registered calculation",
            goal_ids=[],
        )
        assert result["status"] == "success", result
        saved = client.get(f"/runs/{run['id']}").json()["steps"][0]
        assert saved["result"]["primary"]["data"]["value"] == pytest.approx(2)
        assert saved["result"]["primary"]["data"]["causal_claim"] == "not_established"
        assert saved["code"]["available"]
        assert saved["result"]["provenance"]["method"].endswith("@2.0.0")
        assert len(provider.calls) == 1

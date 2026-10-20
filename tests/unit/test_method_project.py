"""A scaffolded project uses one loader from local Python through the server worker."""

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from decision_layer.cli import init_project, main, new_method
from decision_layer.methods import (
    InvalidBinding,
    MethodRegistry,
    Scope,
    registry as builtins,
)
from decision_layer.methods.loading import configured_registry
from decision_layer.project import PROJECT_FILE, Project, ProjectError
from decision_layer.settings import Settings
from examples.methods.authoring.sample_data import DATE, DATES, DIMENSION, METRIC
from examples.methods.authoring.plain_python import practice_session


@pytest.fixture
def project(tmp_path):
    project = init_project(tmp_path / "analysis", "project_" + uuid4().hex, empty=True)
    new_method(project, "python", "rank")
    new_method(project, "skill", "review")
    return project


async def test_scaffold_lists_and_runs_through_local_registry(project):
    session = await practice_session()
    loaded = session.load_project(str(project.root))
    name = project.config.name + ".rank"
    assert {m.name for m in loaded} == {name, project.config.name + ".review"}
    assert name in {m.name for m in session.list_methods()}
    assert (
        session.find_methods(names=[name])["candidates"][0]["manifest"]["name"] == name
    )
    trial = await session.run(
        name, value=METRIC, group=DIMENSION, scope=Scope(DATES, DATE)
    )
    assert [row["rank"] for row in trial.result.primary.data] == [1, 2, 2]
    assert session.registry.get(name).source_snapshot.available
    with pytest.raises(InvalidBinding):
        builtins.get(name)


async def test_rest_mcp_and_spawned_worker_use_project_definitions(
    project, tmp_path, monkeypatch
):
    from decision_layer.api.app import create_app
    from decision_layer.mcp import server
    from tests.unit.test_method_assets import data_provider

    rank = project.methods_dir / "rank" / "method.py"
    (rank.parent / "calculation.py").write_text(
        "def rank_data(data, descending):\n"
        '    return data.assign(rank=data["value"].rank(method="min", ascending=not descending))\n'
    )
    rank.write_text(
        rank.read_text()
        .replace(
            "def analyze(data, descending=True):",
            "from .calculation import rank_data\n\ndef analyze(data, descending=True):",
        )
        .replace(
            '    return data.assign(rank=data["value"].rank(method="min", ascending=not descending))',
            "    return rank_data(data, descending)",
        )
    )

    settings = Settings(
        project_dir=str(project.root),
        database_url="memory",
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
        cube_service_groups=("ecommerce",),
        recipes_dir=str(tmp_path / "recipes"),
    )
    name = project.config.name + ".rank"
    with TestClient(create_app(settings, data_provider())) as client:

        async def call(verb, path, **kwargs):
            response = client.request(verb, path, **kwargs)
            assert response.status_code == 200, response.text
            return response.json()

        monkeypatch.setattr(server, "_call", call)
        monkeypatch.setattr(server, "METHODS", set())
        assert name in {m["name"] for m in (await server.list_methods())["methods"]}
        manifest = await server.describe_method(name)
        assert manifest["data_inputs"]["data"]["columns"]["value"]["kind"] == "measure"
        skill = await server.describe_method(project.config.name + ".review")
        assert skill["agent_executable"] and skill["guide"]["markdown"]
        run = client.post(
            "/runs",
            json={
                "question": "Rank values",
                "scope": {"date_range": list(DATES), "time_dimension": DATE},
            },
        ).json()
        result = await server.run_step(
            run["id"],
            name,
            bindings={"value": METRIC, "group": DIMENSION},
            params={},
            purpose="Rank the observed groups",
            goal_ids=[],
        )
        assert result["status"] == "success"
        saved = client.get(f"/runs/{run['id']}").json()
        assert [
            row["rank"] for row in saved["steps"][0]["result"]["primary"]["data"]
        ] == [1, 2, 2]
        assert saved["steps"][0]["code"]["available"]


def test_cli_and_startup_share_sources_and_project_discovery(
    project, monkeypatch, capsys
):
    monkeypatch.chdir(project.methods_dir)
    assert Project.find().root == project.root
    assert main(["check"]) == 0
    assert "no semantic query" in capsys.readouterr().out
    assert main(["list", "--json"]) == 0
    import json

    rows = json.loads(capsys.readouterr().out)
    row = next(m for m in rows if m["name"] == project.config.name + ".rank")
    assert Path(row["source"]) == project.methods_dir / "rank" / "method.py"
    assert row["name"] in {m.name for m in configured_registry(Settings()).manifests()}


@pytest.mark.parametrize(
    "problem",
    ["duplicate", "missing_export", "syntax", "unknown_tool", "mixed", "skill_export"],
)
def test_invalid_entries_fail_with_source_and_no_partial_registration(project, problem):
    rank = project.methods_dir / "rank" / "method.py"
    review = project.methods_dir / "review" / "SKILL.md"
    if problem == "duplicate":
        review.write_text(
            review.read_text().replace(
                project.config.name + ".review", project.config.name + ".rank"
            )
        )
    elif problem == "missing_export":
        rank.write_text(rank.read_text().replace("METHOD =", "OTHER ="))
    elif problem == "syntax":
        rank.write_text("def broken(:\n")
    elif problem == "unknown_tool":
        review.write_text(
            review.read_text().replace(
                "query_execution: true",
                "suggested_methods: [missing.tool]\nquery_execution: true",
            )
        )
    elif problem == "skill_export":
        rank.write_text(
            f"from decision_layer.methods import SkillMethod\nMETHOD = SkillMethod.from_file({str(review)!r})\n"
        )
    else:
        (rank.parent / "SKILL.md").write_text(review.read_text())
    registry = MethodRegistry()
    with pytest.raises(ProjectError, match=r"method.py|SKILL.md|Choose either"):
        project.load(registry)
    assert registry.manifests() == []


def test_helpers_are_not_entries_and_skill_references_can_point_forward(project):
    (project.methods_dir / "not_an_entry.py").write_text(
        "raise RuntimeError('must not import')"
    )
    review = project.methods_dir / "review" / "SKILL.md"
    review.write_text(
        review.read_text().replace(
            "query_execution: true",
            f"suggested_methods: [{project.config.name}.rank]\nquery_execution: true",
        )
    )
    registry = MethodRegistry()
    project.load(registry)
    assert len(registry.manifests()) == 2


def test_project_paths_do_not_escape_and_existing_files_are_not_overwritten(
    project, tmp_path
):
    outside = tmp_path / "external"
    outside.mkdir()
    (project.methods_dir / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProjectError, match="stay inside"):
        project.load(MethodRegistry())
    with pytest.raises(ProjectError, match="not empty"):
        init_project(project.root)
    with pytest.raises(ProjectError, match="already exists"):
        new_method(project, "python", "rank")
    with pytest.raises(ProjectError, match="Expected"):
        Project.find(project.root / "README.md")
    (project.root / PROJECT_FILE).write_text("name: invalid-name\n")
    with pytest.raises(ProjectError, match=PROJECT_FILE):
        Project.find(project.root)


def test_explicit_missing_project_does_not_fall_back_to_defaults(tmp_path):
    with pytest.raises(ProjectError, match="No decision-layer.yaml"):
        configured_registry(Settings(project_dir=str(tmp_path)))


@pytest.mark.parametrize("database_url", [None, "memory"])
def test_cli_serve_selects_the_project_for_the_same_api_factory(
    project, monkeypatch, database_url
):
    import uvicorn

    captured = {}
    monkeypatch.setenv("DL_PROJECT_DIR", "unused")
    if database_url is None:
        monkeypatch.delenv("DL_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DL_DATABASE_URL", database_url)
    monkeypatch.setattr(
        uvicorn, "run", lambda app, **kwargs: captured.update(app=app, **kwargs)
    )
    assert main(["serve", "--api-only", "--project", str(project.root), "--reload"]) == 0
    assert Settings().project_dir == str(project.root)
    assert Settings().database_url == (
        database_url
        or f"sqlite:///{project.root / '.decision-layer' / 'decision_layer.db'}"
    )
    assert captured["app"] == "decision_layer.api.app:app"
    assert "*.md" in captured["reload_includes"]

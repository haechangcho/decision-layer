"""The installed sample owns only its data services and local project state."""

from importlib.resources import files
import json
from unittest.mock import MagicMock
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from decision_layer.cli import main
from decision_layer.demo import runtime


def test_cli_demo_does_not_require_a_repository_or_project(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        runtime,
        "run_demo",
        lambda action, **options: calls.append((action, options)) or 0,
    )
    assert main(["demo", "--port", "8050"]) == 0
    assert calls == [("start", {"directory": None, "port": 8050, "cube_port": None})]


def test_sample_resources_and_rerun_preserve_runs_and_methods(tmp_path):
    root = tmp_path / "sample"
    project = runtime.prepare(root)
    assert project.config.name == "sample_shop"
    state = root / ".decision-layer" / "runs.db"
    state.write_bytes(b"keep execution history")
    custom = project.methods_dir / "my_method.py"
    custom.write_text("keep my function")
    runtime.prepare(root)
    assert state.read_bytes() == b"keep execution history"
    assert custom.read_text() == "keep my function"
    compose = yaml.safe_load((root / "compose.yaml").read_text())
    assert set(compose["services"]) == {"postgres", "cube"}
    assert "build" not in compose["services"]["cube"]
    assert not compose["services"]["postgres"].get("ports")
    assert compose["services"]["cube"]["ports"] == [
        "127.0.0.1:${DL_DEMO_CUBE_PORT:-4100}:4000"
    ]
    for relative in runtime.ASSETS:
        assert (root / relative).is_file()


def test_unmanaged_directory_and_symlink_are_never_overwritten(tmp_path):
    root = tmp_path / "sample"
    root.mkdir()
    keep = root / "keep.txt"
    keep.write_text("private project")
    with pytest.raises(ValueError, match="existing files were preserved"):
        runtime.prepare(root)
    assert keep.read_text() == "private project"
    assert list(root.iterdir()) == [keep]
    root = tmp_path / "managed"
    runtime.prepare(root)
    seed = root / "seed.sql"
    seed.unlink()
    seed.symlink_to(keep)
    with pytest.raises(ValueError, match="inside its directory"):
        runtime.prepare(root)
    assert keep.read_text() == "private project"


def test_normal_directory_aliases_use_one_sample_root(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    project = runtime.prepare(alias / "sample")
    assert project.root == actual / "sample"
    assert (project.root / "compose.yaml").is_file()


def test_demo_environment_excludes_real_source_credentials_and_project(
    monkeypatch, tmp_path
):
    for key in (
        "CUBE_API_SECRET",
        "CUBE_API_URL",
        "DL_PROJECT_DIR",
        "DL_METHOD_MODULES",
        "DL_TOKEN",
        "ANALYTICA_CUBE_URL",
    ):
        monkeypatch.setenv(key, "real-company-configuration")
    environment = runtime.server_environment(tmp_path, 4410)
    assert environment["CUBE_API_URL"] == "http://127.0.0.1:4410/cubejs-api/v1"
    assert environment["CUBE_API_SECRET"] == runtime.SECRET
    assert environment["DL_PROJECT_DIR"] == str(tmp_path)
    assert not any(
        value == "real-company-configuration" for value in environment.values()
    )
    assert (
        environment["DL_DATABASE_URL"]
        == f"sqlite:///{tmp_path / '.decision-layer' / 'runs.db'}"
    )
    assert environment["DL_ALLOW_SERVICE_CREDENTIALS"] == "true"


def test_compose_is_scoped_to_one_demo_and_keeps_volumes(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *args, **kwargs: calls.append((args, kwargs))
        or SimpleNamespace(returncode=0),
    )
    for root in (tmp_path / "first", tmp_path / "second"):
        runtime.compose(root, 4410, "stop")
    commands = [call[0][0] for call in calls]
    assert commands[0][3] != commands[1][3]
    assert all(
        command[-1] == "stop" and "--volumes" not in command for command in commands
    )
    assert calls[0][1]["env"]["DL_DEMO_CUBE_PORT"] == "4410"


def test_stop_uses_saved_configuration_without_starting_an_api(monkeypatch, tmp_path):
    runtime.prepare(tmp_path)
    (tmp_path / ".decision-layer" / "demo.json").write_text(
        json.dumps({"port": 8450, "cube_port": 4450})
    )
    calls = []
    monkeypatch.setattr(runtime, "require_docker", lambda: None)
    monkeypatch.setattr(
        runtime, "compose", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    assert runtime.run_demo("stop", directory=tmp_path) == 0
    assert calls == [((tmp_path, 4450, "stop"), {})]


@pytest.mark.parametrize("failure", ["interrupt", "query_error", "startup_error"])
def test_startup_failure_or_interrupt_stops_only_its_child_and_sample_services(
    monkeypatch, tmp_path, failure
):
    console = tmp_path / "installed" / "static"
    console.mkdir(parents=True)
    (console / "index.html").write_text("<html>packaged console</html>")
    monkeypatch.setattr(
        runtime,
        "files",
        lambda package: console.parent
        if package == "decision_layer"
        else files(package),
    )
    directory = tmp_path / "sample"
    calls = []

    class Process:
        alive = True

        def poll(self):
            return None if self.alive else 0

        def terminate(self):
            calls.append("terminate")
            self.alive = False

        def wait(self, **kwargs):
            return 0

    process = Process()
    monkeypatch.setattr(runtime, "require_docker", lambda: None)

    def compose(*args, **kwargs):
        calls.append(("compose", args[2:]))
        if failure == "startup_error" and args[2] == "up":
            raise ValueError("container startup failed")

    monkeypatch.setattr(runtime, "compose", compose)
    monkeypatch.setattr(runtime, "socket", SimpleNamespace(socket=MagicMock()))
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runtime, "wait_for_api", lambda *args: None)

    def walkthrough(client):
        raise (
            KeyboardInterrupt
            if failure == "interrupt"
            else RuntimeError("query failed")
        )

    monkeypatch.setattr(runtime, "walkthrough", walkthrough)
    if failure == "interrupt":
        assert runtime.run_demo(directory=directory, port=54321) == 0
    else:
        with pytest.raises(ValueError, match="startup failed|walkthrough failed"):
            runtime.run_demo(directory=directory, port=54321)
    assert calls[-1] == ("compose", ("stop",))
    assert ("terminate" in calls) == (failure != "startup_error")


def test_api_startup_failure_does_not_query_another_server(tmp_path):
    with pytest.raises(ValueError, match="stopped before it was ready"):
        runtime.wait_for_api(SimpleNamespace(poll=lambda: 1), None, tmp_path)


def test_missing_docker_fails_before_creating_a_sample(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runtime.shutil, "which", lambda name: None)
    directory = tmp_path / "sample"
    assert main(["demo", "--directory", str(directory)]) == 1
    assert "Install Docker" in capsys.readouterr().err
    assert not directory.exists()


@pytest.mark.parametrize("port,cube_port", [(0, 4100), (8000, 70000), (8000, 8000)])
def test_invalid_ports_do_not_start_services(monkeypatch, tmp_path, port, cube_port):
    def unexpected():
        pytest.fail("Docker must not be invoked for invalid ports")

    monkeypatch.setattr(runtime, "require_docker", unexpected)
    with pytest.raises(ValueError, match="Ports|different"):
        runtime.run_demo(directory=tmp_path / "sample", port=port, cube_port=cube_port)


def legacy_demo(root):
    from decision_layer.project_scaffold import init_project

    project = init_project(root, "sample_shop", empty=True)
    (root / runtime.MARKER).write_text(json.dumps(runtime.OWNER))
    (root / "decision-layer.yaml").write_text("config_version: 1\nname: sample_shop\n")
    metadata = root / "pyproject.toml"
    contents = metadata.read_text()
    contents = (
        contents[: contents.index("[project.optional-dependencies]")]
        + contents[contents.index("[tool.hatch") :]
    )
    import re

    metadata.write_text(
        re.sub(
            r"decision-layer\[stats,mcp\]==[A-Za-z0-9.]+",
            "decision-layer[stats]==0.1.0a5",
            contents,
        )
    )
    return project


def test_old_empty_demo_gains_editable_methods_once_and_preserves_history(tmp_path):
    from decision_layer.methods.loading import configured_registry
    from decision_layer.settings import Settings
    import shutil
    import tomllib

    root = tmp_path / "sample"
    old = legacy_demo(root)
    (root / ".decision-layer").mkdir()
    history = root / ".decision-layer" / "runs.db"
    history.write_bytes(b"keep recorded runs")
    recipes = root / "recipes"
    recipes.mkdir()
    (recipes / "mine.yaml").write_text("keep recipe")
    project = runtime.prepare(root)
    assert project.config.include_builtin_methods is False
    assert history.read_bytes() == b"keep recorded runs"
    assert (recipes / "mine.yaml").read_text() == "keep recipe"
    for entry in [
        "metric_lookup/SKILL.md",
        "drilldown/SKILL.md",
        "ols/method.py",
        "matching/method.py",
    ]:
        assert (old.methods_dir / entry).is_file()
    metadata = tomllib.loads((root / "pyproject.toml").read_text())
    assert metadata["project"]["optional-dependencies"]["test"]
    target = configured_registry(Settings(project_dir=str(root)))
    assert len(target.manifests()) == 4
    assert all(item.version == "2.0.0" for item in target.manifests())
    assert target.get("stats.regression_adjustment", "1.1.0")
    source = project.methods_dir / "ols" / "method.py"
    source.write_text(source.read_text() + "\n# my change\n")
    shutil.rmtree(project.methods_dir / "matching")
    runtime.prepare(root)
    assert source.read_text().endswith("# my change\n")
    assert not (project.methods_dir / "matching").exists()


def test_old_custom_demo_remains_untouched(tmp_path):
    project = legacy_demo(tmp_path / "sample")
    custom = project.methods_dir / "custom.py"
    custom.write_text("keep my helper")
    config = (project.root / "decision-layer.yaml").read_bytes()
    metadata = (project.root / "pyproject.toml").read_bytes()
    runtime.prepare(project.root)
    assert (project.root / "decision-layer.yaml").read_bytes() == config
    assert (project.root / "pyproject.toml").read_bytes() == metadata
    assert custom.read_text() == "keep my helper"
    assert not (project.methods_dir / "ols").exists()


def test_old_demo_upgrade_rolls_back_on_partial_copy(tmp_path, monkeypatch):
    from decision_layer.demo import upgrade

    project = legacy_demo(tmp_path / "sample")
    original = (project.root / "decision-layer.yaml").read_bytes()

    def broken_copy(source, destination, **kwargs):
        (destination / "partial.py").write_text("partial")
        raise OSError("disk failure")

    monkeypatch.setattr(upgrade.shutil, "copytree", broken_copy)
    with pytest.raises(OSError, match="disk failure"):
        runtime.prepare(project.root)
    assert (project.root / "decision-layer.yaml").read_bytes() == original
    assert sorted(p.name for p in project.methods_dir.iterdir()) == ["__init__.py"]


def test_upgrade_preserves_custom_project_dependencies(tmp_path):
    project = legacy_demo(tmp_path / "sample")
    metadata = project.root / "pyproject.toml"
    content = metadata.read_text().replace(
        "dependencies = [", 'dependencies = ["my-company-package", '
    )
    metadata.write_text(content)
    runtime.prepare(project.root)
    assert metadata.read_text() == content
    assert (project.methods_dir / "ols" / "method.py").is_file()


def test_upgrade_does_not_fill_an_explicitly_empty_project(tmp_path):
    from decision_layer.project_scaffold import init_project

    project = init_project(tmp_path / "sample", "sample_shop", empty=True)
    (project.root / runtime.MARKER).write_text(json.dumps(runtime.OWNER))
    runtime.prepare(project.root)
    assert not (project.methods_dir / "ols").exists()


def test_upgrade_rejects_configuration_symlink(tmp_path):
    project = legacy_demo(tmp_path / "sample")
    configuration = project.root / "decision-layer.yaml"
    outside = tmp_path / "outside.yaml"
    content = configuration.read_text()
    outside.write_text(content)
    configuration.unlink()
    configuration.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        runtime.prepare(project.root)
    assert outside.read_text() == content


def test_default_demo_is_created_in_current_workspace_and_keeps_venv(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "dl"
    environment = workspace / ".venv"
    environment.mkdir(parents=True)
    keep = environment / "pyvenv.cfg"
    keep.write_text("keep interpreter configuration")
    monkeypatch.chdir(workspace)
    assert runtime.demo_directory() == workspace
    project = runtime.prepare(runtime.demo_directory())
    assert (workspace / "decision-layer.yaml").is_file()
    assert project.methods_dir == workspace / "sample_shop" / "methods"
    for entry in [
        "metric_lookup/SKILL.md",
        "drilldown/SKILL.md",
        "ols/method.py",
        "matching/method.py",
    ]:
        assert (project.methods_dir / entry).is_file()
    assert keep.read_text() == "keep interpreter configuration"
    # Repeat and stop from a package subdirectory still select this workspace.
    monkeypatch.chdir(project.methods_dir / "ols")
    assert runtime.demo_directory() == workspace


def test_default_demo_does_not_overwrite_a_populated_workspace(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("keep my project")
    monkeypatch.chdir(tmp_path)
    selected = runtime.demo_directory()
    assert selected == tmp_path / "decision-layer-demo"
    runtime.prepare(selected)
    assert readme.read_text() == "keep my project"
    assert runtime.demo_directory() == selected


def test_default_demo_does_not_reuse_the_old_global_project(tmp_path, monkeypatch):
    home = tmp_path / "home"
    old = home / ".decision-layer" / "demo"
    runtime.prepare(old)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(workspace)
    assert runtime.demo_directory() == workspace
    assert runtime.demo_directory(old) == old

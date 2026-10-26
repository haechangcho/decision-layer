"""Build the pre-v2 on-disk layout for compatibility checks."""

from pathlib import Path

from decision_layer import __version__
from decision_layer.project import Project
from decision_layer.project_scaffold import init_project


def legacy_project(root, name="sample_shop", *, empty=False):
    project = init_project(root, name, empty=empty)
    if not empty:
        for source in (Path(__file__).parent / "legacy_starters").rglob("*.txt"):
            relative = source.relative_to(Path(__file__).parent / "legacy_starters")
            (project.methods_dir / relative.with_suffix("")).write_bytes(
                source.read_bytes()
            )
        for checks in project.methods_dir.rglob("checks.py"):
            checks.unlink()
    package = project.root / name
    package.mkdir()
    (package / "__init__.py").touch()
    project.methods_dir.rename(package / "methods")
    config = project.root / "decision-layer.yaml"
    config.write_text(
        config.read_text().replace("config_version: 2", "config_version: 1")
    )
    metadata = project.root / "pyproject.toml"
    metadata.write_text(
        metadata.read_text().replace('packages = ["methods"]', f'packages = ["{name}"]').replace(
            f"decision-layer=={__version__}", f"decision-layer[stats,mcp]=={__version__}"
        )
    )
    return Project.find(project.root)

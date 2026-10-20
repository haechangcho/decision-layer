"""Upgrade the original empty managed demo without replacing user definitions."""

from pathlib import Path
import re
import shutil
import tempfile
import tomllib

import yaml

from ..project import PROJECT_FILE, Project
from ..project_scaffold import init_project


def _stock_metadata(path: Path, name: str) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        metadata = tomllib.loads(path.read_text())
        dependencies = metadata["project"]["dependencies"]
        if len(dependencies) != 1 or not re.fullmatch(
            r"decision-layer\[stats\]==[A-Za-z0-9.]+", dependencies[0]
        ):
            return False
        return metadata == {
            "build-system": {
                "requires": ["hatchling"],
                "build-backend": "hatchling.build",
            },
            "project": {
                "name": f"{name}-methods",
                "version": "0.1.0",
                "requires-python": ">=3.11",
                "dependencies": dependencies,
            },
            "tool": {"hatch": {"build": {"targets": {"wheel": {"packages": [name]}}}}},
        }
    except (ValueError, KeyError, TypeError):
        return False


def upgrade_empty_demo(project: Project) -> Project:
    """Called only after the demo ownership marker has been verified."""
    config_path = project.root / PROJECT_FILE
    if config_path.is_symlink():
        raise ValueError("Sample project configuration must not be a symlink.")
    config = yaml.safe_load(config_path.read_text())
    # Explicit settings, including a deliberate empty project, are authoritative.
    if "include_builtin_methods" in config:
        return project
    entries = project.methods_dir.rglob("*")
    if any(
        p.is_symlink()
        or (p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts)
        for p in entries
    ):
        return project
    kinds = ("metric_lookup", "drilldown", "ols", "matching")
    if any((project.methods_dir / kind).exists() for kind in kinds):
        return project
    metadata_path = project.root / "pyproject.toml"
    originals = {config_path: config_path.read_bytes()}
    if _stock_metadata(metadata_path, project.config.name):
        originals[metadata_path] = metadata_path.read_bytes()
    created = []
    with tempfile.TemporaryDirectory(
        prefix=".starter-upgrade-", dir=project.root
    ) as folder:
        staged = init_project(Path(folder) / "project", project.config.name)
        try:
            for kind in kinds:
                destination = project.methods_dir / kind
                destination.mkdir()
                created.append(destination)
                shutil.copytree(
                    staged.methods_dir / kind, destination, dirs_exist_ok=True
                )
            if metadata_path in originals:
                metadata_path.write_bytes((staged.root / "pyproject.toml").read_bytes())
            new_config = Path(folder) / PROJECT_FILE
            new_config.write_text(
                yaml.safe_dump(
                    {**config, "include_builtin_methods": False}, sort_keys=False
                )
            )
            new_config.replace(config_path)
        except Exception:
            for path, content in originals.items():
                path.write_bytes(content)
            for path in created:
                shutil.rmtree(path)
            raise
    return Project.find(project.root)

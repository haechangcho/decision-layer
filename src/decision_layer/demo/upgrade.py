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
                content = (staged.root / "pyproject.toml").read_text()
                if project.config.config_version == 1:
                    content = content.replace(
                        'packages = ["methods"]',
                        f'packages = ["{project.config.name}"]',
                    )
                metadata_path.write_text(content)
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


def upgrade_stock_layout(project, assets, asset_pairs):
    """Flatten an untouched a9 demo; custom projects keep their original layout."""
    import copy
    import json
    from ..project_scaffold import default_project_name

    root = project.root
    backup = root / ".decision-layer/layout-v1"
    package = root / project.config.name
    config_path = root / PROJECT_FILE
    if (
        project.config.config_version != 1
        or project.config.name != "sample_shop"
        or project.config.include_builtin_methods is not False
        or backup.exists()
        or (root / "methods").exists()
    ):
        return project
    marker = root / ".decision-layer/demo-dataset.json"
    if (
        not marker.is_file()
        or json.loads(marker.read_text()).get("dataset") != "complete-journey"
    ):
        return project
    if (
        not package.is_dir()
        or package.is_symlink()
        or not (package / "__init__.py").is_file()
        or any(
            p.name not in {"methods", "__init__.py", "__pycache__"}
            for p in package.iterdir()
        )
        or (package / "__init__.py").read_bytes() != b""
    ):
        return project
    from hashlib import sha256

    expected = json.loads(assets.joinpath("layout-v1-starters.json").read_text())
    found = {}
    for path in project.methods_dir.rglob("*"):
        if path.is_symlink():
            return project
        if path.is_file() and "__pycache__" not in path.parts:
            found[path.relative_to(project.methods_dir).as_posix()] = sha256(
                path.read_bytes()
            ).hexdigest()
    if found != expected:
        return project
    for relative, source in asset_pairs:
        path = root / relative
        if (
            path.is_symlink()
            or not path.is_file()
            or path.read_bytes() != assets.joinpath(source).read_bytes()
        ):
            return project
    asset_paths = {relative for relative, source in asset_pairs}
    for path in (root / "journey").rglob("*"):
        if path.is_symlink() or (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.relative_to(root).as_posix() not in asset_paths
        ):
            return project
    metadata_path = root / "pyproject.toml"
    if metadata_path.is_symlink() or not metadata_path.is_file():
        return project
    previous_metadata = tomllib.loads(metadata_path.read_text())
    dependencies = previous_metadata.get("project", {}).get("dependencies", [])
    if len(dependencies) != 1 or not re.fullmatch(
        r"decision-layer\[stats,mcp\]==[A-Za-z0-9.]+", dependencies[0]
    ):
        return project
    moved = []
    with tempfile.TemporaryDirectory(
        prefix=".layout-upgrade-", dir=root / ".decision-layer"
    ) as folder:
        staged = init_project(Path(folder) / "project", default_project_name(root))
        expected_metadata = copy.deepcopy(
            tomllib.loads((staged.root / "pyproject.toml").read_text())
        )
        expected_metadata["project"].update(
            name=project.config.name + "-methods", dependencies=dependencies
        )
        expected_metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] = [
            project.config.name
        ]
        if previous_metadata != expected_metadata:
            return project
        new_readme = (staged.root / "README.md").read_text()
        old_readme = new_readme.replace(
            "# " + staged.config.name + "\n", "# " + project.config.name + "\n", 1
        ).replace(
            "Edit Skills and Python calculations in `methods/`. Reusable procedures live in `recipes/`.\n",
            f"Skill and Python definitions live in `{project.config.name}/methods/` files.\n",
        )
        readme = root / "README.md"
        replace_readme = (
            readme.is_file()
            and not readme.is_symlink()
            and readme.read_text() == old_readme
        )
        backup.mkdir()

        def move(source, destination):
            source.replace(destination)
            moved.append((source, destination))

        try:
            move(project.methods_dir, root / "methods")
            move(package, backup / "package")
            for path in (
                root / "compose.yaml",
                root / "journey",
                config_path,
                metadata_path,
            ):
                move(path, backup / path.name)
            for path in (config_path, metadata_path):
                path.write_bytes((staged.root / path.name).read_bytes())
            if replace_readme:
                move(readme, backup / "README.md")
                readme.write_text(new_readme)
        except Exception:
            for source, destination in reversed(moved):
                if source.is_file():
                    source.unlink()
                destination.replace(source)
            backup.rmdir()
            raise
    print(
        "Project layout updated: methods/. Previous generated files are kept in .decision-layer/layout-v1/.",
        flush=True,
    )
    return Project.find(root)

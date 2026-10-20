"""Create a marked team project and its Python or Skill entry files."""

from __future__ import annotations
import keyword
from pathlib import Path
import re
from .project import PROJECT_FILE, Project, ProjectConfig, ProjectError


def init_project(path: str | Path, name: str | None = None, *, empty=False):
    root = Path(path).resolve()
    name = name or re.sub(r"\W", "_", root.name).lower()
    config = ProjectConfig(name=name, include_builtin_methods=False)
    if root.exists() and any(root.iterdir()):
        raise ProjectError(f"Directory is not empty: {root}")
    methods = root / name / "methods"
    methods.mkdir(parents=True)
    (root / PROJECT_FILE).write_text(
        f"config_version: 1\nname: {config.name}\ninclude_builtin_methods: false\n"
    )
    from . import __version__

    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n\n'
        f'[project]\nname = "{name}-methods"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        f'dependencies = ["decision-layer[stats,mcp]=={__version__}"]\n\n'
        '[project.optional-dependencies]\ntest = ["pytest>=8,<10"]\n\n'
        f'[tool.hatch.build.targets.wheel]\npackages = ["{name}"]\n'
    )
    (root / name / "__init__.py").touch()
    (methods / "__init__.py").touch()
    (root / "README.md").write_text(
        f"# {name}\n\n"
        f"Skill and Python definitions live in `{name}/methods/` files.\n"
        "Default Method names: analysis.metric_lookup, analysis.drilldown, "
        "stats.regression_adjustment, stats.binary_matching.\n"
        "Edit calculations and tests together; increment the Method version when changing behavior.\n\n"
        "```sh\npython -m pip install -e '.[test]'\n"
        "decision-layer check\ndecision-layer test\ndecision-layer list\n"
        "decision-layer serve --reload\n```\n\n"
        "Tests use synthetic data and need no server or Cube connection.\n"
        "Actual data execution in the admin UI requires a Cube connection.\n"
        "CLI source paths and web code refer to the same project files.\n\n"
        "`decision-layer new python rank` or `decision-layer new skill investigation` to add a definition.\n"
        "Keep the project in Git. Package upgrades never overwrite project files.\n"
        "Runs are stored in .decision-layer/decision_layer.db; Recipes in recipes/.\n"
    )
    if not empty:
        from importlib.resources import files

        template = files("decision_layer") / "starters" / "methods"
        for kind in ("metric_lookup", "drilldown", "ols", "matching"):
            folder = methods / kind
            folder.mkdir()
            (folder / "__init__.py").touch()
            for source in template.joinpath(kind).iterdir():
                if source.name in {"SKILL.md", "method.py", "test_method.py"}:
                    (folder / source.name).write_bytes(source.read_bytes())
    (root / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/\nbuild/\ndist/\n.venv/\n.decision-layer/\n"
    )
    return Project(root, config)


def new_method(project: Project, kind: str, name: str):
    if kind not in {"python", "skill"}:
        raise ProjectError("Definition kind must be python or skill")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
        raise ProjectError("Use a Python identifier such as adjusted_difference")
    folder = project.methods_dir / name
    if folder.exists():
        raise ProjectError(f"Definition already exists: {folder}")
    folder.mkdir()
    (folder / "__init__.py").touch()
    identity = f"{project.config.name}.{name}"
    if kind == "python":
        path = folder / "method.py"
        path.write_text(
            "from decision_layer.methods import Column, DataInput, python_method\n\n\n"
            "def analyze(data, descending=True):\n"
            '    """Rank observed groups by a selected metric, retaining ties."""\n'
            '    return data.assign(rank=data["value"].rank(method="min", ascending=not descending))\n\n\n'
            "METHOD = python_method(\n"
            "    analyze,\n"
            f'    name="{identity}",\n'
            '    version="1.0.0",\n'
            '    inputs={"data": DataInput(columns={\n'
            '        "value": Column(source="measure"),\n'
            '        "group": Column(source="dimension"),\n'
            "    })},\n"
            ")\n"
        )
    else:
        path = folder / "SKILL.md"
        path.write_text(
            f"---\nname: {identity}\nversion: 1.0.0\n"
            "description: Inspect a governed metric for a selected period.\n"
            "query_execution: true\nroles:\n  metric:\n    kind: measure\n---\n\n"
            "# Inspect the selected metric\n\n"
            "1. Confirm the metric meaning and period with the user.\n"
            "2. Query the bound metric through the recorded Cube tools.\n"
            "3. Report only observed values with query evidence and limitations.\n"
            "4. Stop and ask when a required input is ambiguous or unavailable.\n"
        )
    return path

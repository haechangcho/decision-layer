"""Scaffold, inspect and serve the same Method project."""

from __future__ import annotations

import argparse
import inspect
import json
import keyword
import os
from pathlib import Path
import re
import sys

from .project import PROJECT_FILE, Project, ProjectConfig, ProjectError
from .core.errors import DecisionLayerError


def init_project(path: str | Path, name: str | None = None):
    root = Path(path).resolve()
    name = name or re.sub(r"\W", "_", root.name).lower()
    config = ProjectConfig(name=name)
    if root.exists() and any(root.iterdir()):
        raise ProjectError(f"Directory is not empty: {root}")
    methods = root / name / "methods"
    methods.mkdir(parents=True)
    (root / PROJECT_FILE).write_text(f"config_version: 1\nname: {config.name}\n")
    from . import __version__

    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n\n'
        f'[project]\nname = "{name}-methods"\nversion = "0.1.0"\n'
        'requires-python = ">=3.11"\n'
        f'dependencies = ["decision-layer[stats]=={__version__}"]\n\n'
        f'[tool.hatch.build.targets.wheel]\npackages = ["{name}"]\n'
    )
    (root / name / "__init__.py").touch()
    (methods / "__init__.py").touch()
    (root / "README.md").write_text(
        f"# {name}\n\nDefinitions live in `{name}/methods/`.\n\n"
        "```sh\ndecision-layer new python rank\ndecision-layer new skill investigation\n"
        "decision-layer check\ndecision-layer list\ndecision-layer serve --reload\n```\n\n"
        "Use the same Python environment as Decision Layer. Project code is imported at check/startup.\n"
        "Open the Admin URL printed by serve to inspect Methods and test semantic inputs.\n"
        "Run history is stored in .decision-layer/decision_layer.db; recipes live in recipes/.\n"
        "Edit project Methods in their source files. Web publication creates separate versions.\n"
        "Commit the project to Git; deploy the same files and dependencies and restart the API.\n"
    )
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\n.decision-layer/\n")
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
            "from decision_layer.methods import DataInput, python_method\n\n\n"
            "def analyze(data, descending=True):\n"
            '    """Rank observed groups by a selected metric, retaining ties."""\n'
            '    return data.assign(rank=data["value"].rank(method="min", ascending=not descending))\n\n\n'
            "METHOD = python_method(\n"
            "    analyze,\n"
            f'    name="{identity}",\n'
            '    version="1.0.0",\n'
            '    output="table",\n'
            '    inputs={"data": DataInput(measures=["value"], dimensions=["group"])},\n'
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


def project_registry(project):
    from .methods.loading import configured_registry
    from .settings import Settings

    settings = Settings(project_dir=str(project.root))
    registry = configured_registry(settings)
    from .methods.assets import MethodAssets

    MethodAssets(settings.method_assets_dir, registry)
    return registry


def main(argv=None):
    parser = argparse.ArgumentParser(prog="decision-layer")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a Method project")
    init.add_argument("directory")
    init.add_argument("--name")
    new = commands.add_parser("new", help="Add a Python Method or Skill")
    new.add_argument("kind", choices=["python", "skill"])
    new.add_argument("name")
    check = commands.add_parser("check", help="Validate project registration")
    listing = commands.add_parser(
        "list", help="List Methods and their definition paths"
    )
    serve = commands.add_parser("serve", help="Start the admin UI and API with this project")
    for cmd in (new, check, listing, serve):
        cmd.add_argument(
            "--project",
            help="Project directory (default: search current directory and parents)",
        )
    listing.add_argument("--json", action="store_true")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument("--api-only", action="store_true", help="Start only the API")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            project = init_project(args.directory, args.name)
            print(f"Created {project.root / PROJECT_FILE}")
            print(
                f"Next: cd {project.root}\n  decision-layer new python rank\n  decision-layer check"
            )
            return 0
        project = Project.find(args.project or os.environ.get("DL_PROJECT_DIR"))
        if args.command == "new":
            print(new_method(project, args.kind, args.name))
            return 0
        if args.command == "serve":
            os.environ["DL_PROJECT_DIR"] = str(project.root)
            os.environ.setdefault(
                "DL_DATABASE_URL",
                f"sqlite:///{project.root / '.decision-layer' / 'decision_layer.db'}",
            )
            os.environ.setdefault("DL_RECIPES_DIR", str(project.root / "recipes"))
            os.environ.setdefault("DL_METHOD_ASSETS_DIR", str(project.root / ".decision-layer" / "method-assets"))
            if not args.api_only:
                from .console import STATIC_DIR
                if not (STATIC_DIR / "index.html").is_file():
                    raise ValueError("Admin UI is missing. Install the released package or run npm run build:console in web/. Use --api-only for API development.")
            print(f"Project: {project.root / PROJECT_FILE}", flush=True)
            if not args.api_only:
                print(f"Admin: http://{args.host}:{args.port}/ui/", flush=True)
            print(f"API docs: http://{args.host}:{args.port}/docs", flush=True)
            import uvicorn

            uvicorn.run(
                "decision_layer.api.app:app" if args.api_only else "decision_layer.console:create_console",
                factory=not args.api_only,
                host=args.host,
                port=args.port,
                reload=args.reload,
                reload_dirs=[str(project.root)] if args.reload else None,
                reload_includes=["*.py", "*.md", PROJECT_FILE] if args.reload else None,
            )
            return 0
        registry = project_registry(project)
        entries = []
        for manifest in registry.manifests():
            method = registry.get(manifest.name)
            source = getattr(method, "definition_path", None)
            if source is None and manifest.implementation == "python":
                source = inspect.getsourcefile(getattr(method, "fn", type(method)))
            entries.append(
                {
                    "name": manifest.name,
                    "version": manifest.version,
                    "implementation": manifest.implementation,
                    "source": str(source) if source else "bundled Skill",
                }
            )
        if args.command == "check":
            print(
                f"Valid: {project.root / PROJECT_FILE} ({len(entries)} registered Methods)"
            )
            print(
                "Registration checked; no semantic query or analytical calculation executed."
            )
        elif args.json:
            print(json.dumps(entries, indent=2))
        else:
            print("NAME\tVERSION\tKIND\tSOURCE")
            for item in entries:
                print("\t".join(item.values()))
        return 0
    except (DecisionLayerError, ValueError, ImportError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

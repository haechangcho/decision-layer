"""Prepare sample resources, start data services, then serve the installed console."""

from __future__ import annotations

from hashlib import sha256
from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import httpx

from ..project import Project
from ..project_scaffold import init_project
from .replay import walkthrough

MARKER = ".decision-layer-demo.json"
OWNER = {"format": 1, "owner": "decision-layer-demo"}
SECRET = "local-quickstart-secret-change-me-0123456789"
ASSETS = ("compose.yaml", "seed.sql", "cube/model/sales.yml", "cube/healthcheck.cjs")


def demo_directory(directory=None) -> Path:
    if directory is not None:
        return Path(directory).expanduser().resolve()
    current = Path.cwd().resolve()
    # A command from inside a demo keeps using that same project.
    for candidate in (current, *current.parents):
        marker = candidate / MARKER
        if marker.exists() or marker.is_symlink():
            return candidate
    if all(entry.name == ".venv" for entry in current.iterdir()):
        return current
    # Never initialize over unrelated files in a populated working directory.
    return current / "decision-layer-demo"


def require_managed(root: Path) -> None:
    marker = root / MARKER
    try:
        owned = json.loads(marker.read_text()) == OWNER
    except (OSError, ValueError):
        owned = False
    if not owned:
        raise ValueError(
            f"Not a Decision Layer demo directory: {root}. Choose an empty --directory; existing files were preserved."
        )


def prepare(root: Path) -> Project:
    root = root.resolve()
    if root.exists() and any(entry.name != ".venv" for entry in root.iterdir()):
        require_managed(root)
        project = Project.find(root)
        from .upgrade import upgrade_empty_demo

        project = upgrade_empty_demo(project)
    else:
        project = init_project(root, "sample_shop")
        (root / MARKER).write_text(json.dumps(OWNER) + "\n")
    assets = files("decision_layer.demo").joinpath("assets")
    for relative in ASSETS:
        destination = root / relative
        # These paths are managed sample files, never arbitrary user symlink targets.
        if destination.is_symlink() or not destination.resolve().is_relative_to(root):
            raise ValueError(
                f"Sample path must stay inside its directory: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(assets.joinpath(relative).read_bytes())
    (root / ".decision-layer").mkdir(exist_ok=True)
    return project


def require_docker() -> None:
    if not shutil.which("docker"):
        raise ValueError(
            "Install Docker with Compose v2 and start it, then run decision-layer demo again."
        )
    for args in (["compose", "version"], ["info"]):
        try:
            result = subprocess.run(
                ["docker", *args], capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                "Docker did not respond. Start Docker and try again."
            ) from exc
        if result.returncode:
            raise ValueError(
                "Docker with Compose v2 must be running and accessible. Start Docker, then run decision-layer demo again."
            )


def compose(root: Path, cube_port: int, *args, check=True) -> None:
    root = root.resolve()
    project = "decision-layer-demo-" + sha256(str(root).encode()).hexdigest()[:12]
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            project,
            "--file",
            str(root / "compose.yaml"),
            *args,
        ],
        cwd=root,
        env={**os.environ, "DL_DEMO_CUBE_PORT": str(cube_port)},
    )
    if check and result.returncode:
        raise ValueError(
            f"Sample services could not {' '.join(args)}. Check Docker and port {cube_port}; use --cube-port to choose another port. Data remains in {root}."
        )


def server_environment(root: Path, cube_port: int) -> dict[str, str]:
    # A demo must never inherit the user's real source, credentials or project.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DL_", "CUBE_", "ANALYTICA_"))
    }
    environment.update(
        {
            "DL_DEPLOYMENT_MODE": "demo",
            "DL_PROJECT_DIR": str(root),
            "DL_DATABASE_URL": f"sqlite:///{root / '.decision-layer' / 'runs.db'}",
            "DL_RECIPES_DIR": str(root / "recipes"),
            "DL_METHOD_ASSETS_DIR": str(root / ".decision-layer" / "method-assets"),
            "DL_ALLOW_SERVICE_CREDENTIALS": "true",
            "DL_HTTP_ALLOWED_HOSTS": "localhost,127.0.0.1,::1",
            "CUBE_API_URL": f"http://127.0.0.1:{cube_port}/cubejs-api/v1",
            "CUBE_INSTANCE": "quickstart",
            "CUBE_AUTH_METHOD": "api_secret",
            "CUBE_API_SECRET": SECRET,
            "DL_LOCALE": os.environ.get("DL_LOCALE", "en"),
        }
    )
    return environment


def wait_for_api(process, client, root: Path) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError(
                "The demo API stopped before it was ready. See the server output above."
            )
        try:
            response = client.get("/project", timeout=2)
            if response.is_success and response.json().get("path") == str(root):
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.2)
    raise ValueError("The demo API did not become ready within 60 seconds.")


def _port(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
        raise ValueError("Ports must be integers between 1 and 65535.")
    return value


def run_demo(action="start", *, directory=None, port=None, cube_port=None) -> int:
    root = demo_directory(directory)
    if action == "stop":
        require_managed(root)
    config_path = root / ".decision-layer" / "demo.json"
    saved = json.loads(config_path.read_text()) if config_path.exists() else {}
    port = _port(port if port is not None else saved.get("port", 8000))
    cube_port = _port(
        cube_port if cube_port is not None else saved.get("cube_port", 4100)
    )
    if port == cube_port:
        raise ValueError("The Web/API port and Cube port must be different.")
    require_docker()
    if action == "stop":
        compose(root, cube_port, "stop")
        print(f"Sample containers stopped. Data and Runs remain in {root}.")
        return 0

    if not files("decision_layer").joinpath("static/index.html").is_file():
        raise ValueError(
            "Admin UI is missing. Install the released package or build the console before running the demo."
        )
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    except OSError as exc:
        raise ValueError(
            f"Port {port} is unavailable. Run decision-layer demo --port <available-port>."
        ) from exc
    project = prepare(root)
    config_path.write_text(
        json.dumps({"port": port, "cube_port": cube_port}, indent=2) + "\n"
    )
    print(
        f"Sample project: {root}\nMethods: {project.methods_dir}\nPreparing PostgreSQL and Cube. First startup downloads Docker images.",
        flush=True,
    )
    process = None
    try:
        compose(root, cube_port, "up", "--detach", "--wait", "--wait-timeout", "300")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "decision_layer.console:create_console",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=root,
            env=server_environment(root, cube_port),
        )
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}/api", timeout=150, trust_env=False
        ) as client:
            wait_for_api(process, client, root)
            evidence = walkthrough(client)
        (root / ".decision-layer" / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
        print(
            f"\nAdmin: http://127.0.0.1:{port}/ui/recipes\nRuns:  http://127.0.0.1:{port}/ui/runs",
            flush=True,
        )
        for month in ("january", "february", "march"):
            print(
                f"{month.title()}: http://127.0.0.1:{port}/ui/runs/{evidence[month]['id']}",
                flush=True,
            )
        print(
            "\nSynthetic data. Press Ctrl+C to stop the server and sample containers; data and Runs are kept.",
            flush=True,
        )
        return process.wait()
    except KeyboardInterrupt:
        return 0
    except (httpx.HTTPError, RuntimeError) as exc:
        raise ValueError(
            f"Sample walkthrough failed: {exc}. Data and Runs remain in {root}."
        ) from exc
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        compose(root, cube_port, "stop", check=False)

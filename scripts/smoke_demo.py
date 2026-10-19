"""Exercise the installed demo outside the checkout, including Ctrl+C cleanup."""

import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import httpx


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix="decision-layer-demo-qa-") as folder:
        root = Path(folder).resolve() / "sample"
        port, cube_port = available_port(), available_port()
        while port == cube_port:
            cube_port = available_port()
        log_path = Path(folder) / "demo.log"
        command = [
            sys.executable,
            "-m",
            "decision_layer",
            "demo",
            "--directory",
            str(root),
            "--port",
            str(port),
            "--cube-port",
            str(cube_port),
        ]
        with log_path.open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=folder,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            evidence_path = root / ".decision-layer" / "evidence.json"
            deadline = time.monotonic() + 360
            while not evidence_path.exists():
                if process.poll() is not None:
                    raise RuntimeError(
                        "Installed demo exited before completing its walkthrough"
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Installed demo did not finish within 360 seconds"
                    )
                time.sleep(0.5)
            evidence = json.loads(evidence_path.read_text())
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", trust_env=False
            ) as client:
                response = client.get("/ui/recipes")
                assert (
                    response.status_code == 200
                    and "text/html" in response.headers["content-type"]
                )
                for month in ("january", "february", "march"):
                    run = evidence[month]
                    response = client.get(f"/api/runs/{run['id']}")
                    assert response.status_code == 200
                    assert response.json()["steps"] == run["steps"]
                assert (
                    evidence["january"]["status"]
                    == evidence["february"]["status"]
                    == "completed"
                )
                assert (
                    evidence["march"]["steps"][-1]["result"]["status"] == "needs_input"
                )
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=45) == 0
            assert (root / ".decision-layer" / "runs.db").stat().st_size > 0
            assert evidence_path.is_file()
            print(
                "PASS: installed demo, live Cube, packaged UI, recorded Runs and Ctrl+C shutdown."
            )
        except BaseException:
            print(log_path.read_text(), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            # Remove only the QA sample's already-stopped containers and volumes.
            if (root / ".decision-layer-demo.json").is_file():
                from decision_layer.demo.runtime import compose

                compose(root, cube_port, "down", "--volumes", check=False)


if __name__ == "__main__":
    main()

"""Exercise the installed demo outside the checkout, including Ctrl+C cleanup."""

import asyncio
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

import httpx

from smoke_mcp import verify_mcp


def verify_statistics(api_url):
    """Pin entity extraction and honest refusal on the official campaign sample."""
    from decision_layer.demo.client import request, settled

    base = "cube://journey/campaign_household_outcomes/"
    with httpx.Client(base_url=api_url, timeout=150, trust_env=False) as client:
        for method in ("stats.regression_adjustment", "stats.binary_matching"):
            run = request(
                client,
                "POST",
                "/runs?wait=60",
                json={
                    "question": "Compare campaign 8 target-list membership and later receipts, adjusting for prior activity. Association only.",
                    "scope": {
                        "date_range": ["2001-01-01", "2001-06-30"],
                        "time_dimension": base + "campaign_start_date",
                        "filters": [
                            {
                                "member": base + "campaign_id",
                                "operator": "equals",
                                "values": ["8"],
                            }
                        ],
                    },
                },
            )
            request(
                client,
                "POST",
                f"/runs/{run['id']}/steps?wait=60",
                json={
                    "method": method,
                    "bindings": {
                        "entity_id": base + "observation_id",
                        "outcome": base + "post_sales_mean",
                        "treatment": base + "targeted",
                        "confounders": [
                            base + "pre_sales_mean",
                            base + "pre_frequency_mean",
                        ],
                    },
                },
            )
            run = settled(client, run["id"])
            result = run["steps"][-1]["result"]
            assert result["provenance"]["queries"]
            if method == "stats.regression_adjustment":
                assert result["status"] == "success", result
                estimate = result["primary"]["data"]
                # Independently checked using raw SQL and NumPy least squares.
                assert estimate["n_observations"] == 2008
                assert abs(estimate["value"] - 32.46579465777122) < 1e-7
                assert estimate["causal_claim"] == "not_established"
            else:
                assert result["status"] == "refused" and result["primary"] is None
                assert any("overlap" in warning for warning in result["warnings"])
    print(
        "PASS: real campaign OLS agrees with independent reference; matching refuses insufficient overlap."
    )


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix="decision-layer-demo-qa-") as folder:
        root = Path(folder).resolve() / "sample"
        root.mkdir()
        (root / ".venv").mkdir()
        environment_marker = root / ".venv" / "preserved.txt"
        environment_marker.write_text("keep virtual environment")
        port, cube_port = available_port(), available_port()
        while port == cube_port:
            cube_port = available_port()
        log_path = Path(folder) / "demo.log"
        command = [
            sys.executable,
            "-m",
            "decision_layer",
            "demo",
            "--port",
            str(port),
            "--cube-port",
            str(cube_port),
        ]
        with log_path.open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            evidence_path = root / ".decision-layer" / "evidence.json"
            deadline = time.monotonic() + 1200
            while not evidence_path.exists():
                if process.poll() is not None:
                    raise RuntimeError(
                        "Installed demo exited before completing its walkthrough"
                    )
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "Installed demo did not finish within 1200 seconds"
                    )
                time.sleep(0.5)
            evidence = json.loads(evidence_path.read_text())
            assert (root / "decision-layer.yaml").is_file()
            assert environment_marker.read_text() == "keep virtual environment"
            for entry in (
                "metric_lookup/SKILL.md",
                "drilldown/SKILL.md",
                "ols/method.py",
                "matching/method.py",
            ):
                assert (root / "methods" / entry).is_file()
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", trust_env=False
            ) as client:
                response = client.get("/ui/recipes")
                assert (
                    response.status_code == 200
                    and "text/html" in response.headers["content-type"]
                )
                for month in ("january", "february"):
                    run = evidence[month]
                    response = client.get(f"/api/runs/{run['id']}")
                    assert response.status_code == 200
                    assert response.json()["steps"] == run["steps"]
                assert (
                    evidence["january"]["status"]
                    == evidence["february"]["status"]
                    == "completed"
                )
                reference = json.loads(
                    (root / ".decision-layer/source-reference.json").read_text()
                )
                assert len(reference["tables"]) == 8
                assert reference["households"] == 2500
                assert float(reference["retailer_receipts"]) == 8057463.08
            asyncio.run(
                verify_mcp(f"http://127.0.0.1:{port}", f"http://127.0.0.1:{port}/ui")
            )
            verify_statistics(f"http://127.0.0.1:{port}/api")
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

"""REST helpers shared by installed demo walkthroughs."""

import json
import time


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    return response.json()


def settled(client, run_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        run = request(client, "GET", f"/runs/{run_id}")
        if not run.get("running"):
            if run.get("error") or run["status"] == "failed":
                raise RuntimeError(json.dumps(run.get("error") or run))
            return run
        time.sleep(0.3)
    raise TimeoutError(f"Run {run_id} did not finish in 120 seconds")

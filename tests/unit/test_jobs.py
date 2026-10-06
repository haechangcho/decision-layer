"""Background execution: 202 + polling, busy runs, recorded errors, restart recovery (ADR-030)."""
import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.errors import ProviderError
from decision_layer.core.models import CallerInfo, Run, RunningJob
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.store import MemoryRunStore
from decision_layer.settings import Settings
from test_methods import Q3, RR, FakeProvider
from test_runs import REPO_RECIPES

SCOPE = {"date_range": list(Q3)}
COMPARE = {"bindings": {"metric": RR}, "scope": SCOPE}


class GatedProvider(FakeProvider):
    """execute() blocks until the test opens the gate; optionally fails afterwards."""

    def __init__(self, cube_meta):
        super().__init__(cube_meta)
        self.gate, self.fail = threading.Event(), False

    async def execute(self, spec, credentials, *, with_sql=False):
        await asyncio.to_thread(self.gate.wait, 10)
        if self.fail:
            raise ProviderError("Cube 오류: boom")
        return await super().execute(spec, credentials, with_sql=with_sql)


@pytest.fixture
def setup(cube_meta):
    provider = GatedProvider(cube_meta)
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s", cube_service_groups=("ecommerce",),
                 database_url="memory", recipes_dir=str(REPO_RECIPES), allow_service_credentials=True,
                 request_wait_seconds=0.2)
    with TestClient(create_app(s, provider)) as c:
        yield c, provider


def poll(c, run_id, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        r = c.get(f"/runs/{run_id}/result")
        if r.status_code != 202:
            return r
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_slow_method_answers_202_then_result(setup):
    c, provider = setup
    r = c.post("/methods/query.trend:run?wait=0", json=COMPARE)
    assert r.status_code == 202 and r.json()["status"] == "running"
    run_id = r.json()["run_id"]
    assert c.get(f"/runs/{run_id}").json()["running"]["method"] == "query.trend"
    assert c.get("/health").status_code == 200                 # the API is not blocked by the job
    provider.gate.set()
    done = poll(c, run_id)
    assert done.status_code == 200 and done.json()["status"] == "success" and done.json()["run_id"] == run_id
    run = c.get(f"/runs/{run_id}").json()
    assert run["running"] is None and run["status"] == "completed"


def test_fast_method_answers_directly(setup):
    c, provider = setup
    provider.gate.set()
    r = c.post("/methods/query.trend:run?wait=10", json=COMPARE)
    assert r.status_code == 200 and r.json()["status"] == "success"


def test_busy_run_rejects_next_step(setup):
    c, provider = setup
    provider.gate.set()                                          # recipe validators query on start
    run = c.post("/runs", json={"recipe": "return-rate-investigation", "scope": SCOPE}).json()
    provider.gate.clear()
    step = {"method": "query.trend", "bindings": {"metric": RR}}
    assert c.post(f"/runs/{run['id']}/steps?wait=0", json=step).status_code == 202
    r = c.post(f"/runs/{run['id']}/steps", json=step)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RUN_BUSY"
    provider.gate.set()
    assert poll(c, run["id"]).json()["status"] == "success"
    assert c.post(f"/runs/{run['id']}/steps", json=step).status_code == 200


def test_job_error_is_recorded(setup):
    c, provider = setup
    run_id = c.post("/methods/query.trend:run?wait=0", json=COMPARE).json()["run_id"]
    provider.fail = True
    provider.gate.set()
    r = poll(c, run_id)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PROVIDER_ERROR"
    run = c.get(f"/runs/{run_id}").json()
    assert run["status"] == "failed" and run["error"]["message"].startswith("Cube 오류")


def test_error_within_wait_is_returned_directly(setup):
    c, provider = setup
    provider.fail = True
    provider.gate.set()
    r = c.post("/methods/query.trend:run?wait=5", json=COMPARE)
    assert r.status_code == 502 and r.json()["error"]["code"] == "PROVIDER_ERROR"


async def test_recover_marks_interrupted_runs(cube_meta):
    store = MemoryRunStore()
    me = CallerInfo(subject="alice")
    adhoc = Run(id="run_a", caller=me, plan={}, running=RunningJob(kind="adhoc", method="query.trend"))
    step = Run(id="run_b", caller=me, plan={}, running=RunningJob(kind="step", method="query.trend"))
    for r in (adhoc, step):
        await store.save(r)
    e = RunEngine(FakeProvider(cube_meta), None, store)
    assert await e.recover() == 2
    a, b = await store.get("run_a"), await store.get("run_b")
    assert (a.status, a.running, a.error["code"]) == ("failed", None, "INTERRUPTED")
    assert (b.status, b.running) == ("open", None)                # an investigation can continue


async def test_mcp_wait_for_run(monkeypatch):
    from decision_layer.mcp import server

    states = iter([
        {"id": "r", "running": {"kind": "adhoc"}, "error": None, "steps": []},
        {"id": "r", "status": "open", "plan": {"question": "Compare groups"}, "caller": {}, "running": None, "error": None,
         "steps": [{"step": {"id": "step_1", "method": "query.drilldown", "purpose": "Compare groups", "bindings": {}, "params": {}},
                    "result": {"status": "success", "provenance": {"queries": []}}}]},
    ])

    async def fake_call(method, path, **kw):
        return next(states)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(server, "_call", fake_call)
    monkeypatch.setattr(server.asyncio, "sleep", no_sleep)
    result = await server.wait_for_run("r")
    assert result["status"] == "open" and result["steps"][0]["result"]["status"] == "success"
    assert result["next"] == {"tools": ["run_step", "complete_run"], "run_id": "r"}

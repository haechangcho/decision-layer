from pathlib import Path
from tests.support.notebooks import execute_notebook
from examples.methods.first_method.fixtures import DATES

async def test_cube_notebook_with_mock_http(cube_meta, monkeypatch):
    import json
    import httpx
    import jwt
    import respx
    from tests.support.semantic import AMOUNT, CAT, DT
    token = jwt.encode({"sub": "developer"}, "fixture-secret-longer-than-32-bytes", algorithm="HS256")
    env = {"CUBE_API_URL": "https://cube.fixture/cubejs-api/v1", "CUBE_TOKEN": token,
           "CUBE_METRIC": AMOUNT, "CUBE_DIMENSION": CAT, "CUBE_TIME_DIMENSION": DT,
           "ANALYSIS_START": DATES[0], "ANALYSIS_END": DATES[1]}
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("CUBE_INSTANCE", "local")
    loads = []
    def load(request):
        assert request.headers["authorization"] == f"Bearer {token}"
        query = json.loads(request.content)["query"]
        assert query["timeDimensions"][0]["dateRange"] == list(DATES)
        loads.append(query)
        metric = query["measures"][0]
        dimensions = query.get("dimensions") or []
        if dimensions:
            data = [{metric: value, dimensions[0]: label} for value, label in [(30, "A"), (20, "B"), (10, "C")]]
        else:
            data = [{metric: 60}]
        return httpx.Response(200, json={"data": data})
    path = Path(__file__).resolve().parents[2] / "examples/methods/first_method/explore.ipynb"
    with respx.mock:
        respx.get(env["CUBE_API_URL"] + "/meta").respond(200, json=cube_meta)
        respx.post(env["CUBE_API_URL"] + "/load").mock(side_effect=load)
        respx.post(env["CUBE_API_URL"] + "/sql").respond(200, json={"sql": {"sql": ["SELECT fixture", []]}})
        namespace = await execute_notebook(path, monkeypatch)
    assert len(loads) == 3
    assert len(namespace["run"].steps) == 2
    assert [row[AMOUNT] for row in namespace["result"].primary.data] == [30, 20, 10]

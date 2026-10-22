"""Both introductory notebooks run from their new directory without a server."""

from pathlib import Path

import pytest

pytest.importorskip("statsmodels")

from tests.support.notebooks import execute_notebook


@pytest.mark.parametrize("language", ["ko", "en"])
async def test_introductory_notebook_from_tutorial_directory(language, monkeypatch):
    directory = Path(__file__).resolve().parents[2] / "docs/tutorials/methods"
    monkeypatch.chdir(directory)
    namespace = await execute_notebook(
        directory / f"write_your_method.{language}.ipynb", monkeypatch
    )
    assert [method.name for method in namespace["session"].list_methods()] == [
        "my_team.rank",
        "my_team.ols",
    ]
    assert namespace["trial"].result.status == "success"
    assert namespace["trial"].result.primary.data == namespace["standalone"].to_dict(
        orient="records"
    )
    result = namespace["ols_trial"].result
    assert result.status == "success"
    assert namespace["my_ols"].output == "auto"
    assert result.primary.type == "estimate"
    assert namespace["my_ols"].checks == (namespace["check_ols"],)
    assert any(
        check.code == "PYTHON_CHECK" and check.status == "pass"
        for check in result.validation
    )
    assert result.primary.data["value"] == pytest.approx(50)
    assert result.primary.data["n_observations"] == 200
    assert result.primary.data["r_squared"] == pytest.approx(
        namespace["direct_ols"]["r_squared"]
    )
    assert result.primary.data["causal_claim"] == "not_established"


async def test_notebook_mcp_example_executes_with_the_mcp_run_contract(
    tmp_path, monkeypatch
):
    """The executable example must pass actual MCP-origin goals and step validation."""
    import json
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from decision_layer.api.app import create_app
    from decision_layer.core.models import AnalysisGoal
    from decision_layer.mcp import server
    from decision_layer.settings import Settings

    directory = Path(__file__).resolve().parents[2] / "docs/tutorials/methods"
    notebook = json.loads((directory / "write_your_method.ko.ipynb").read_text())
    namespace = await execute_notebook(
        directory / "write_your_method.ko.ipynb", monkeypatch
    )
    sources = {cell["id"]: "".join(cell["source"]) for cell in notebook["cells"]}
    check = next(
        source for source in sources.values() if source.startswith("def check_ols")
    )
    module = "\n\n".join(
        [
            "import pandas as pd\nfrom decision_layer.methods import Column, DataInput, python_method",
            sources["ols-function"],
            check,
            sources["ols-register"].split("\nsession.register")[0],
            "METHODS = [my_ols]",
        ]
    )
    (tmp_path / "notebook_mcp_contract.py").write_text(module)
    monkeypatch.syspath_prepend(str(tmp_path))
    settings = Settings(
        database_url="memory",
        recipes_dir=str(tmp_path),
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
        cube_service_groups=("ecommerce",),
        method_modules=("notebook_mcp_contract",),
    )
    with TestClient(create_app(settings, namespace["session"].provider)) as http:

        async def call(method, path, **kwargs):
            response = http.request(
                method, path, headers={"X-Decision-Layer-Client": "mcp"}, **kwargs
            )
            assert response.status_code == 200, response.text
            return response.json()

        class NotebookClient:
            async def call_tool(self, name, arguments):
                arguments = dict(arguments)
                if name == "start_analysis":
                    arguments["goals"] = [
                        AnalysisGoal.model_validate(item) for item in arguments["goals"]
                    ]
                value = await getattr(server, name)(**arguments)
                return SimpleNamespace(structured_content=value)

        monkeypatch.setattr(server, "_call", call)
        monkeypatch.setattr(server, "METHODS", set())
        result = await namespace["run_ols_with_mcp"](NotebookClient())
        assert result.structured_content["status"] == "success"
        assert result.structured_content["primary"]["data"]["value"] == pytest.approx(
            50
        )
        run = http.get(f"/runs/{result.structured_content['run_id']}").json()
        assert run["origin"] == "mcp"
        assert run["steps"][0]["step"]["goal_ids"] == [run["goals"][0]["id"]]

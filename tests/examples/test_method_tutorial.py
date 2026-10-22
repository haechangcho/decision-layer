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
    assert namespace["my_ols"].checks == (namespace["check_ols"],)
    assert any(check.code == "PYTHON_CHECK" and check.status == "pass" for check in result.validation)
    assert result.primary.data["value"] == pytest.approx(50)
    assert result.primary.data["n_observations"] == 200
    assert result.primary.data["r_squared"] == pytest.approx(
        namespace["direct_ols"]["r_squared"]
    )
    assert result.primary.data["causal_claim"] == "not_established"

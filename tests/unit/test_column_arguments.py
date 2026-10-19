"""Ordinary functions receive resolved column names through every execution surface."""

import json

import pytest

pd = pytest.importorskip("pandas")

from decision_layer.core.models import DataInput, RoleSpec
from decision_layer.methods import InvalidBinding, Scope, python_method
from examples.methods.authoring.sample_data import METRIC, DIMENSION, DATE, DATES
from tests.support.methods.column_arguments import METHODS, rank_values, ols
from examples.methods.authoring.plain_python import practice_session


async def test_direct_and_governed_function_calls_agree_and_record_column_arguments():
    method = METHODS[0]
    session = await practice_session()
    session.register(method)
    frame = pd.DataFrame({"revenue": [30, 20, 20], "region": ["A", "B", "C"]})
    expected = rank_values(frame, "revenue", "region", False).rename(
        columns={"revenue": "value", "region": "group"}
    )
    trial = await session.run(
        method,
        value=METRIC,
        group=DIMENSION,
        descending=False,
        scope=Scope(DATES, DATE),
    )
    assert trial.result.primary.data == expected.to_dict(orient="records")
    mapping = json.loads(trial.result.provenance.runtime["python.resolved_inputs"])[
        "data"
    ]
    assert mapping["column_args"] == {"value": "value", "group": "group"}
    assert set(method.manifest.parameters) == {"descending"}
    assert trial.attempts[0].spec.measures == [METRIC]


async def test_ols_list_columns_match_native_statsmodels_and_known_slope():
    pytest.importorskip("statsmodels")
    from tests.support.methods.continuous import sample, example_session
    from tests.support.methods.cases import (
        M,
        RATE,
        BASELINE,
        UNIT,
        FEB,
        DATE as TIME,
    )

    direct = ols(sample(), "outcome", "treatment", ["baseline"])
    session = await example_session()
    session.register(METHODS[1])
    trial = await session.run(
        METHODS[1],
        outcome=M,
        treatment=RATE,
        confounders=[BASELINE],
        unit=UNIT,
        scope=Scope(FEB, TIME),
    )
    assert trial.result.status == "success"
    assert direct["value"] == pytest.approx(50)
    assert trial.result.primary.data["value"] == pytest.approx(direct["value"])
    assert trial.result.primary.data["coefficients"]["confounders_0"] == pytest.approx(
        3
    )
    assert trial.result.interpretation == "association"
    mapping = json.loads(trial.result.provenance.runtime["python.resolved_inputs"])[
        "data"
    ]
    assert mapping["column_args"]["confounders"] == ["confounders_0"]
    assert mapping["semantic_refs"]["confounders_0"] == BASELINE
    session.provider.assert_consumed()


@pytest.mark.parametrize("attack", ["missing", "raw_column", "params_override"])
async def test_unresolved_bindings_and_client_column_overrides_never_query(attack):
    session = await practice_session()
    session.register(METHODS[0])
    bindings = {"value": METRIC, "group": DIMENSION}
    params = {}
    if attack == "missing":
        del bindings["value"]
    if attack == "raw_column":
        bindings["value"] = "value"
    if attack == "params_override":
        params["value"] = "private_column"
    from decision_layer.core.errors import DecisionLayerError

    with pytest.raises(DecisionLayerError):
        await session.run(
            METHODS[0], bindings=bindings, params=params, scope=Scope(DATES, DATE)
        )
    assert session.provider.calls == []


def test_column_argument_registration_rejects_ambiguous_ownership_and_typos():
    def function(data, value):
        return data

    with pytest.raises(ValueError, match="declared data columns"):
        DataInput(measures=["value"], column_args=["typo"])
    with pytest.raises(ValueError, match="declared data columns"):
        DataInput(measures=["value"], column_args=["value", "value"])
    with pytest.raises(ValueError, match="actual function arguments"):
        python_method(
            function,
            name="test.typo",
            version="1.0.0",
            inputs={"data": DataInput(measures=["missing"], column_args=["missing"])},
        )

    def two(left, right, value):
        return left

    with pytest.raises(ValueError, match="exactly one"):
        python_method(
            two,
            name="test.two",
            version="1.0.0",
            inputs={
                name: DataInput(measures=["value"], column_args=["value"])
                for name in ("left", "right")
            },
        )
    with pytest.raises(ValueError, match="Parameter types"):
        python_method(
            function,
            name="test.override",
            version="1.0.0",
            inputs={"data": DataInput(measures=["value"], column_args=["value"])},
            parameters={"value": str},
        )


@pytest.mark.parametrize("multiple,expected", [(False, None), (True, [])])
async def test_optional_column_arguments_have_explicit_absent_values(
    multiple, expected
):
    from decision_layer.dev import MethodSession
    from decision_layer.core.models import DatasetSpec, TimeScope
    from decision_layer.testing import FixtureProvider, QueryFixture
    from tests.support.methods.cases import catalog, M, UNIT, FEB, DATE as TIME

    def ordinary(data, extra):
        assert extra == expected
        return float(data.outcome.sum())

    method = python_method(
        ordinary,
        name="test.optional",
        version="1.0.0",
        inputs={
            "data": DataInput(
                entity="unit",
                measures=["outcome"],
                columns={
                    "extra": RoleSpec(
                        kind="dimension", required=False, multiple=multiple
                    )
                },
                column_args=["extra"],
            )
        },
    )
    spec = DatasetSpec(
        grain="entity",
        entity=UNIT,
        measures=[M],
        time=TimeScope(dimension=TIME, date_range=FEB),
        limit_rows=50001,
    )
    session = await MethodSession.fixture(
        FixtureProvider(catalog(), [QueryFixture(spec, [[4, "a"]])])
    )
    session.register(method)
    result = (
        await session.run(method, outcome=M, unit=UNIT, scope=Scope(FEB, TIME))
    ).result
    assert result.status == "success" and result.primary.data["value"] == 4


async def test_rest_worker_and_mcp_share_the_column_contract(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from decision_layer.mcp import server
    from tests.unit.test_method_assets import data_provider

    settings = Settings(
        database_url="memory",
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
        cube_service_groups=("ecommerce",),
        method_modules=("tests.support.methods.column_arguments",),
        recipes_dir=str(tmp_path),
    )
    with TestClient(create_app(settings, data_provider())) as client:

        async def call(verb, path, **kwargs):
            response = client.request(verb, path, **kwargs)
            assert response.status_code == 200, response.text
            return response.json()

        monkeypatch.setattr(server, "_call", call)
        monkeypatch.setattr(server, "METHODS", set())
        manifest = await server.describe_method("workshop.rank_columns")
        assert manifest["data_inputs"]["data"]["column_args"] == ["value", "group"]
        run = client.post(
            "/runs",
            json={
                "question": "Rank values",
                "scope": {"date_range": list(DATES), "time_dimension": DATE},
            },
        ).json()
        result = await server.run_step(
            run["id"],
            "workshop.rank_columns",
            bindings={"value": METRIC, "group": DIMENSION},
            params={"descending": False},
            purpose="Compare observed groups",
            goal_ids=[],
        )
        assert result["status"] == "success"
        saved = client.get(f"/runs/{run['id']}").json()
        step = saved["steps"][0]
        assert [row["rank"] for row in step["result"]["primary"]["data"]] == [3, 1, 1]
        mapping = json.loads(
            step["result"]["provenance"]["runtime"]["python.resolved_inputs"]
        )
        assert mapping["data"]["column_args"] == {"value": "value", "group": "group"}
        assert saved["query_attempts"] and step["code"]


@pytest.mark.parametrize(
    "invalid", ["constant_outcome", "singular", "missing", "categorical"]
)
def test_ordinary_ols_rejects_invalid_data_without_framework(invalid):
    pytest.importorskip("statsmodels")
    from tests.support.methods.continuous import sample

    frame = sample()
    if invalid == "constant_outcome":
        frame["outcome"] = 1.0
    elif invalid == "singular":
        frame["baseline"] = frame["treatment"]
    elif invalid == "missing":
        frame.loc[0, "outcome"] = float("nan")
    else:
        frame["baseline"] = "category"
    with pytest.raises(ValueError):
        ols(frame, "outcome", "treatment", ["baseline"])


@pytest.mark.parametrize("index", [0, 1])
def test_editable_source_preserves_ordinary_column_registration(index, tmp_path):
    from decision_layer.methods.source import capture_source
    from tests.unit.test_authoring_source import import_source

    method = METHODS[index]
    restored = import_source(
        tmp_path / f"column_example_{index}.py", capture_source(method).editor_content
    )
    assert restored.manifest == method.manifest

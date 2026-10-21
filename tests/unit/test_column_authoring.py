"""The concise authoring API compiles to the canonical query/worker contract."""

import json

import pytest

from decision_layer.core.models import DatasetSpec, TimeScope, MethodManifest
from decision_layer.dev import MethodSession
from decision_layer.methods import (
    Column,
    DataInput,
    InvalidBinding,
    Scope,
    python_method,
)
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.authoring.sample_data import (
    METRIC,
    DIMENSION,
    DATE,
    DATES,
    fixture_provider,
)
from examples.methods.authoring.plain_python import practice_session
from tests.support.methods.continuous import example_session
from tests.support.methods.cases import (
    M,
    RATE,
    BASELINE,
    UNIT,
    FEB,
    DATE as TIME,
)
from examples.methods.project.methods.rank.method import METHOD as RANK
from examples.methods.project.methods.ols.method import METHOD as OLS

# Also loaded by the real server worker in the integration test below.
METHODS = [RANK, OLS]


async def test_rank_uses_group_grain_and_infers_table():
    session = await practice_session()
    session.register(RANK)
    trial = await session.run(
        RANK.manifest.name,
        bindings={"value": METRIC, "group": DIMENSION},
        params={"descending": False},
        scope=Scope(DATES, DATE),
    )
    assert trial.result.status == "success"
    assert [row["rank"] for row in trial.result.primary.data] == [3, 1, 1]
    assert trial.attempts[0].spec.grain == "aggregate"
    assert trial.attempts[0].spec.dimensions == [DIMENSION]
    assert RANK.manifest.data_inputs["data"].column_args == []
    assert set(RANK.manifest.parameters) == {"descending"}
    assert (
        MethodManifest.model_validate_json(RANK.manifest.model_dump_json())
        == RANK.manifest
    )


async def test_ols_uses_entity_and_injects_column_list():
    session = await example_session()
    session.register(OLS)
    trial = await session.run(
        OLS.manifest.name,
        bindings={
            "entity_id": UNIT,
            "outcome": M,
            "treatment": RATE,
            "confounders": [BASELINE],
        },
        scope=Scope(FEB, TIME),
    )
    assert trial.result.status == "success"
    assert trial.result.primary.data["value"] == pytest.approx(50)
    assert trial.result.primary.data["coefficients"]["confounders_0"] == pytest.approx(
        3
    )
    assert trial.attempts[0].spec.entity == UNIT
    assert trial.attempts[0].spec.measures == [M, RATE]
    assert trial.attempts[0].spec.dimensions == [BASELINE]
    mapping = json.loads(trial.result.provenance.runtime["python.resolved_inputs"])[
        "data"
    ]
    assert mapping["column_args"] == {
        "outcome": "outcome",
        "treatment": "treatment",
        "confounders": ["confounders_0"],
    }
    assert not OLS.manifest.parameters
    assert OLS.manifest.roles["entity_id"].kind == "entity"
    assert trial.result.interpretation == "association"


@pytest.mark.parametrize(
    "invalid",
    ["missing_entity", "wrong_entity", "wrong_dtype", "override", "duplicate_entity"],
)
async def test_invalid_inputs_stop_before_query(invalid):
    session = await example_session()
    session.register(OLS)
    bindings = {
        "entity_id": UNIT,
        "outcome": M,
        "treatment": RATE,
        "confounders": [BASELINE],
    }
    entity = None
    params = {}
    if invalid == "missing_entity":
        del bindings["entity_id"]
    if invalid == "wrong_entity":
        bindings["entity_id"] = RATE
    if invalid == "wrong_dtype":
        bindings["treatment"] = UNIT
    if invalid == "override":
        params["outcome"] = "private_column"
    if invalid == "duplicate_entity":
        entity = UNIT
    with pytest.raises(InvalidBinding):
        await session.run(
            OLS, entity=entity, bindings=bindings, params=params, scope=Scope(FEB, TIME)
        )
    assert session.provider.calls == []


def test_source_is_required_and_typos_fail():
    for values in (
        {},
        {"source": []},
        {"source": ["measure", "measure"]},
        {"source": "metric"},
        {"source": "measure", "data_type": "number"},
    ):
        with pytest.raises(ValueError):
            Column(**values)
    with pytest.raises(ValueError, match="grain or"):
        DataInput(
            grain="entity", entity="unit", columns={"x": Column(source="measure")}
        )


def test_ambiguous_column_arguments_need_explicit_owner():
    def compare(left, right, value):
        return left[value]

    inputs = {
        key: DataInput(columns={"value": Column(source="measure")})
        for key in ("left", "right")
    }
    with pytest.raises(ValueError, match="exactly one"):
        python_method(compare, name="test.ambiguous", version="1.0.0", inputs=inputs)
    inputs["left"] = DataInput(
        columns={"value": Column(source="measure")}, column_args=["value"]
    )
    method = python_method(
        compare, name="test.explicit", version="1.0.0", inputs=inputs
    )
    assert method.inputs["left"].column_args == ["value"]
    assert method.inputs["right"].column_args == []


async def test_aggregate_mixed_source_list_preserves_aliases_and_grain():
    def calculate(data, fields):
        assert fields == ["fields_0", "fields_1"]
        return data

    method = python_method(
        calculate,
        name="test.mixed_columns",
        version="1.0.0",
        inputs={
            "data": DataInput(
                columns={
                    "fields": Column(source=["measure", "dimension"], multiple=True)
                }
            )
        },
    )
    spec = DatasetSpec(
        grain="aggregate",
        measures=[METRIC],
        dimensions=[DIMENSION],
        time=TimeScope(dimension=DATE, date_range=DATES),
        limit_rows=50001,
    )
    provider = FixtureProvider(
        fixture_provider().catalog, [QueryFixture(spec, [[3, "A"], [4, "B"]])]
    )
    session = await MethodSession.fixture(provider)
    session.register(method)
    trial = await session.run(
        method, bindings={"fields": [METRIC, DIMENSION]}, scope=Scope(DATES, DATE)
    )
    assert trial.result.status == "success"
    assert trial.result.primary.data == [
        {"fields_0": 3, "fields_1": "A"},
        {"fields_0": 4, "fields_1": "B"},
    ]


async def test_duplicate_group_is_refused():
    spec = DatasetSpec(
        grain="aggregate",
        measures=[METRIC],
        dimensions=[DIMENSION],
        time=TimeScope(dimension=DATE, date_range=DATES),
        limit_rows=50001,
    )
    session = await MethodSession.fixture(
        FixtureProvider(
            fixture_provider().catalog, [QueryFixture(spec, [[3, "A"], [4, "A"]])]
        )
    )
    session.register(RANK)
    trial = await session.run(
        RANK, bindings={"value": METRIC, "group": DIMENSION}, scope=Scope(DATES, DATE)
    )
    assert trial.result.status == "refused"
    assert any(
        v.code == "UNIQUE_GRAIN" and v.status == "fail" for v in trial.result.validation
    )


async def test_entity_ols_through_mcp_rest_and_worker(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from decision_layer.mcp import server
    from tests.support.methods.continuous import sample
    from tests.support.methods.cases import catalog

    spec = DatasetSpec(
        grain="entity",
        entity=UNIT,
        measures=[M, RATE],
        dimensions=[BASELINE],
        time=TimeScope(dimension=TIME, date_range=FEB),
        limit_rows=50001,
    )
    provider = FixtureProvider(
        catalog(),
        [
            QueryFixture(
                spec,
                sample()[["outcome", "treatment", "baseline", "unit"]].values.tolist(),
            )
        ],
    )
    settings = Settings(
        database_url="memory",
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
        cube_service_groups=("ecommerce",),
        method_modules=("tests.unit.test_column_authoring",),
        recipes_dir=str(tmp_path),
    )
    with TestClient(create_app(settings, provider)) as client:

        async def call(verb, path, **kwargs):
            response = client.request(verb, path, **kwargs)
            assert response.status_code == 200, response.text
            return response.json()

        monkeypatch.setattr(server, "_call", call)
        monkeypatch.setattr(server, "METHODS", set())
        manifest = await server.describe_method(OLS.manifest.name)
        assert manifest["roles"]["entity_id"]["kind"] == "entity"
        run = client.post(
            "/runs",
            json={
                "question": "Analyze the observed relationship",
                "scope": {"date_range": list(FEB), "time_dimension": TIME},
            },
        ).json()
        result = await server.run_step(
            run["id"],
            OLS.manifest.name,
            bindings={
                "entity_id": UNIT,
                "outcome": M,
                "treatment": RATE,
                "confounders": [BASELINE],
            },
            purpose="Estimate association",
            goal_ids=[],
        )
        assert result["status"] == "success"
        saved = client.get(f"/runs/{run['id']}").json()
        assert saved["steps"][0]["result"]["primary"]["data"]["value"] == pytest.approx(
            50
        )
        assert saved["query_attempts"] and saved["steps"][0]["code"]


async def test_numeric_dimension_is_checked_before_function():
    from tests.support.methods.cases import catalog

    def never(data):
        raise AssertionError("Invalid data reached calculation")

    method = python_method(
        never,
        name="test.numeric_dimension",
        version="1.0.0",
        inputs={
            "data": DataInput(
                grain="entity",
                columns={
                    "outcome": Column(source="measure", dtype="number"),
                    "baseline": Column(source="dimension", dtype="number"),
                },
            )
        },
    )
    spec = DatasetSpec(
        grain="entity",
        entity=UNIT,
        measures=[M],
        dimensions=[BASELINE],
        time=TimeScope(dimension=TIME, date_range=FEB),
        limit_rows=50001,
    )
    session = await MethodSession.fixture(
        FixtureProvider(catalog(), [QueryFixture(spec, [[3, float("nan"), "A"]])])
    )
    session.register(method)
    trial = await session.run(
        method,
        entity=UNIT,
        bindings={"outcome": M, "baseline": BASELINE},
        scope=Scope(FEB, TIME),
    )
    assert trial.result.status == "refused"
    assert any(
        v.code == "FINITE_NUMERIC_COLUMNS" and v.status == "fail"
        for v in trial.result.validation
    )


@pytest.mark.parametrize("method", METHODS)
def test_source_roundtrip_preserves_new_declarations(method, tmp_path):
    from decision_layer.methods.source import capture_source
    from tests.unit.test_authoring_source import import_source

    source = capture_source(method).editor_content
    assert "Column(" in source
    restored = import_source(tmp_path / "restored_columns.py", source)
    assert restored.manifest == method.manifest


@pytest.mark.parametrize(
    "options",
    [
        {"source": "measure"},
        {"source": ["dimension", "measure"]},
        {"source": "dimension", "multiple": True},
        {"source": "dimension", "required": False},
    ],
)
def test_entity_key_requires_one_required_dimension(options):
    with pytest.raises(ValueError, match="one required dimension"):
        Column(role="entity_key", **options)


@pytest.mark.parametrize(
    "extra",
    [
        {"grain": "entity"},
        {"grain": "aggregate"},
        {"entity": "unit"},
    ],
)
def test_entity_key_rejects_competing_grain_declarations(extra):
    with pytest.raises(ValueError, match="without grain or legacy entity"):
        DataInput(
            columns={
                "entity_id": Column(source="dimension", role="entity_key"),
                "outcome": Column(source="measure"),
            },
            **extra,
        )


def test_entity_key_rejects_multiple_keys():
    with pytest.raises(ValueError, match="only one entity_key"):
        DataInput(
            columns={
                "customer_id": Column(source="dimension", role="entity_key"),
                "order_id": Column(source="dimension", role="entity_key"),
            }
        )


@pytest.mark.parametrize("key_name", ["entity_id", "customer_id", "order_id"])
async def test_entity_key_preserves_name_and_injects_column_argument(key_name):
    from tests.support.methods.cases import catalog

    # Give the ordinary function the author-selected argument name.
    namespace = {}
    exec(
        f"def calculate(data, {key_name}):\n"
        f'    assert {key_name} == "{key_name}"\n'
        f'    return data[[{key_name}, "outcome"]]\n',
        namespace,
    )
    method = python_method(
        namespace["calculate"],
        name="test.entity_alias",
        version="1.0.0",
        inputs={
            "data": DataInput(
                columns={
                    key_name: Column(
                        source="dimension",
                        role="entity_key",
                        description="Observation identifier",
                    ),
                    "outcome": Column(source="measure"),
                }
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
        FixtureProvider(catalog(), [QueryFixture(spec, [[3, "A"], [4, "B"]])])
    )
    session.register(method)
    trial = await session.run(
        method, bindings={key_name: UNIT, "outcome": M}, scope=Scope(FEB, TIME)
    )
    assert trial.result.status == "success"
    assert trial.result.primary.data == [
        {key_name: "A", "outcome": 3},
        {key_name: "B", "outcome": 4},
    ]
    assert method.manifest.roles[key_name].description == "Observation identifier"
    assert (
        MethodManifest.model_validate_json(method.manifest.model_dump_json())
        == method.manifest
    )
    mapping = json.loads(trial.result.provenance.runtime["python.resolved_inputs"])[
        "data"
    ]
    assert mapping["grain_keys"] == [key_name]
    assert mapping["column_args"] == {key_name: key_name}
    assert mapping["semantic_refs"][key_name] == UNIT


@pytest.mark.parametrize("ids", [[None, "B"], ["A", "A"]])
async def test_entity_key_rejects_null_and_duplicate_values(ids):
    from tests.support.methods.cases import catalog

    def never(data):
        raise AssertionError("Invalid entity observations reached function")

    method = python_method(
        never,
        name="test.bad_entity_key",
        version="1.0.0",
        inputs={
            "data": DataInput(
                columns={
                    "entity_id": Column(source="dimension", role="entity_key"),
                    "outcome": Column(source="measure"),
                }
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
        FixtureProvider(catalog(), [QueryFixture(spec, [[3, ids[0]], [4, ids[1]]])])
    )
    session.register(method)
    trial = await session.run(
        method, bindings={"entity_id": UNIT, "outcome": M}, scope=Scope(FEB, TIME)
    )
    assert trial.result.status == "refused"
    assert trial.result.primary is None

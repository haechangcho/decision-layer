"""An existing synthetic demo executes only the current query Skills."""

from fastapi.testclient import TestClient
from decision_layer.api.app import create_app
from decision_layer.core.models import (
    DatasetSpec,
    Filter,
    SemanticCatalog,
    SemanticObject,
    TimeScope,
)
from decision_layer.demo.legacy_replay import (
    DATE,
    DEPARTMENT,
    METRIC,
    REGION,
    walkthrough,
)
from decision_layer.settings import Settings
from decision_layer.testing import FixtureProvider, QueryFixture


def test_synthetic_walkthrough_uses_recorded_skills_and_waits_on_tie(tmp_path):
    catalog = SemanticCatalog(
        provider="cube",
        instance="quickstart",
        objects=[
            SemanticObject(
                ref=METRIC,
                kind="measure",
                data_type="number",
                title="Value",
                metric_kind="additive",
                dimension_refs=[DEPARTMENT, REGION, DATE],
                time_dimension=DATE,
            ),
            SemanticObject(
                ref=DEPARTMENT, kind="dimension", data_type="string", title="Department"
            ),
            SemanticObject(
                ref=REGION, kind="dimension", data_type="string", title="Region"
            ),
            SemanticObject(
                ref=DATE, kind="time_dimension", data_type="time", title="Date"
            ),
        ],
    )
    queries = []
    for dates, department, value, regional in [
        (("2026-01-01", "2026-01-31"), "Home", 6200, 3720),
        (("2026-02-01", "2026-02-28"), "Grocery", 6720, 4032),
    ]:
        for dimension, rows, filters in [
            (DEPARTMENT, [[value, department], [1000, "Other"]], []),
            (
                REGION,
                [[regional, "North"], [1000, "South"]],
                [Filter(member=DEPARTMENT, operator="equals", values=[department])],
            ),
        ]:
            queries.append(
                QueryFixture(
                    DatasetSpec(
                        grain="aggregate",
                        measures=[METRIC],
                        dimensions=[dimension],
                        time=TimeScope(dimension=DATE, date_range=dates),
                        filters=filters,
                        order=[(METRIC, "desc"), (dimension, "asc")],
                        limit_rows=1000,
                    ),
                    rows,
                )
            )
    queries.append(
        QueryFixture(
            DatasetSpec(
                grain="aggregate",
                measures=[METRIC],
                dimensions=[DEPARTMENT],
                time=TimeScope(dimension=DATE, date_range=("2026-03-01", "2026-03-31")),
                order=[(METRIC, "desc"), (DEPARTMENT, "asc")],
                limit_rows=1000,
            ),
            [[1000, "Grocery"], [1000, "Home"]],
        )
    )
    provider = FixtureProvider(catalog, queries)
    settings = Settings(
        database_url="memory",
        recipes_dir=str(tmp_path),
        allow_service_credentials=True,
        cube_api_secret="test-secret-at-least-32-characters",
    )
    with TestClient(create_app(settings, provider)) as client:
        evidence = walkthrough(client, emit=lambda text: None)
    for key in ("january", "february"):
        assert all(
            record["step"]["method"] == "analysis.drilldown"
            for record in evidence[key]["steps"]
        )
    assert evidence["march"]["active_skill_step"] == "departments"
    provider.assert_consumed()

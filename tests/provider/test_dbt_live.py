"""Opt-in, read-only smoke test against an actual hosted dbt Semantic Layer."""
import os

import pytest

from decision_layer.core.models import DatasetSpec
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.dbt.provider import DbtSemanticLayerProvider

REQUIRED = ("DL_DBT_TEST_URL", "DL_DBT_TEST_ENVIRONMENT_ID", "DL_DBT_TEST_TOKEN", "DL_DBT_TEST_METRIC")
pytestmark = pytest.mark.skipif(not all(os.environ.get(k) for k in REQUIRED), reason="Real dbt API credentials and a test metric are required")


async def test_hosted_catalog_query_and_sql():
    provider = DbtSemanticLayerProvider(os.environ["DL_DBT_TEST_URL"], "smoke", int(os.environ["DL_DBT_TEST_ENVIRONMENT_ID"]))
    creds = RequestCredentials(os.environ["DL_DBT_TEST_TOKEN"])
    catalog = await provider.discover(creds)
    metric = f"dbt://smoke/metrics/{os.environ['DL_DBT_TEST_METRIC']}"
    assert catalog.get(metric) is not None
    dataset = await provider.execute(DatasetSpec(grain="aggregate", measures=[metric], limit_rows=5), creds, with_sql=True)
    assert dataset.columns[0].ref == metric
    assert dataset.provenance[0].native_query["queryId"]
    assert dataset.provenance[0].provider == "dbt"

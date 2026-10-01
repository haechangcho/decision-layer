"""Against a running Cube with the ecommerce example model and data (examples/ecommerce).

    cd examples/ecommerce && docker compose up -d
    CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_SECRET=example-secret-change-me-0123456789 pytest -m cube

Expected values: examples/ecommerce/EXPECTED.md.
"""
import os

import pytest

from decision_layer.core.models import DatasetSpec, Filter, TimeScope
from decision_layer.semantic.credentials import ServiceCredentials
from decision_layer.semantic.providers.cube.client import CubeClient
from decision_layer.semantic.providers.cube.provider import CubeProvider
from conftest import ref

pytestmark = [pytest.mark.cube, pytest.mark.skipif(not os.environ.get("CUBE_API_SECRET"), reason="CUBE_API_SECRET not set")]
PERIOD = TimeScope(dimension=ref("ecom_order.order_dt"), date_range=("2026-01-01", "2026-09-30"))


def provider():
    return CubeProvider(CubeClient(os.environ.get("CUBE_API_URL", "http://localhost:5005/cubejs-api/v1")), "local")


def creds(*groups):
    return ServiceCredentials(os.environ["CUBE_API_SECRET"], groups or ("ecommerce",))


async def test_discover():
    cat = await provider().discover(creds())
    assert cat.get(ref("ecom_order.return_rate")).title == "반품률(%)"


async def test_category_return_rates():
    ds = await provider().execute(DatasetSpec(grain="aggregate", measures=[ref("ecom_order.return_rate")],
                                              dimensions=[ref("ecom_product.category_nm")], time=PERIOD,
                                              order=[(ref("ecom_order.return_rate"), "desc")]), creds(), with_sql=True)
    assert ds.rows[0][0] == "여성의류" and round(ds.rows[0][1], 2) == 16.73
    assert ds.provenance[0].native_query["_view"] == "ecommerce_kpi" and "SELECT" in ds.provenance[0].compiled_sql


async def test_entity_grain_for_one_seller():
    ds = await provider().execute(DatasetSpec(grain="entity", entity=ref("ecom_order.order_id"),
                                              measures=[ref("ecom_order.return_rate")],
                                              dimensions=[ref("ecom_product.category_nm")], time=PERIOD,
                                              filters=[Filter(member=ref("ecom_order.seller_id"), operator="equals", values=["S017"])]),
                                  creds())
    assert len(ds.rows) == 2050
    women = [r for r in ds.rows if r[1] == "여성의류"]
    assert len(women) == 526 and round(100 * sum(r[2] for r in women) / 100 / len(women), 2) == 22.81


async def test_full_entity_grain_pages():
    ds = await provider().execute(DatasetSpec(grain="entity", entity=ref("ecom_order.order_id"),
                                              measures=[ref("ecom_order.count")], time=PERIOD), creds())
    # 4 full pages + one empty page that confirms the end (exact multiple of the page size)
    assert len(ds.rows) == 200_000 and ds.provenance[0].pages == 5

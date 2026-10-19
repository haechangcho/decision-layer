"""Offline customer data through the real Cube metadata mapper and query compiler.

Only Cube responses are fixtures. No running Cube or warehouse is contacted.
"""

from copy import deepcopy

from decision_layer.dev import MethodSession
from decision_layer.semantic.providers.cube.client import CubeClient
from decision_layer.semantic.providers.cube.provider import CubeProvider


def customer_sample():
    """Known association: purchase amount rises by 50 per extra ad exposure."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(7)
    exposures = rng.integers(0, 11, 200)
    age = rng.integers(18, 71, 200)
    prior = rng.integers(0, 501, 200) * 100
    return pd.DataFrame(
        {
            "id": [f"C{i + 1:03}" for i in range(200)],
            "purchase_amount": 1000 + 50 * exposures + 10 * age + 0.2 * prior,
            "ad_exposures": exposures,
            "age": age,
            "prior_purchase_amount": prior,
        }
    )


def customer_meta():
    """A provider-owned monthly customer summary, including prior-period spend."""
    return {
        "cubes": [
            {
                "name": "customers",
                "measures": [
                    {
                        "name": "customers.purchase_amount",
                        "type": "number",
                        "aggType": "sum",
                        "title": "구매 금액",
                    },
                    {
                        "name": "customers.ad_exposures",
                        "type": "number",
                        "aggType": "sum",
                        "title": "광고 노출 횟수",
                    },
                    {
                        "name": "customers.prior_purchase_amount",
                        "type": "number",
                        "aggType": "sum",
                        "title": "이전 기간 구매 금액",
                    },
                ],
                "dimensions": [
                    {
                        "name": "customers.id",
                        "type": "string",
                        "primaryKey": True,
                        "title": "고객 ID",
                    },
                    {"name": "customers.age", "type": "number", "title": "나이"},
                    {"name": "customers.date", "type": "time", "title": "집계 기준일"},
                ],
            },
            {
                "name": "sales",
                "measures": [
                    {
                        "name": "sales.revenue",
                        "type": "number",
                        "aggType": "sum",
                        "title": "매출",
                    },
                ],
                "dimensions": [
                    {"name": "sales.product", "type": "string", "title": "상품"},
                    {"name": "sales.date", "type": "time", "title": "매출 기준일"},
                ],
            },
        ]
    }


class CustomerFixtureClient(CubeClient):
    """Replay exact Cube requests; never silently answer an unfamiliar query."""

    def __init__(self):
        super().__init__("https://offline.invalid/cubejs-api/v1")
        self.requests = []

    async def _get(self, path, token):
        if path != "/meta":
            raise AssertionError(f"Unexpected fixture endpoint: {path}")
        return customer_meta()

    async def _post(self, path, payload, token):
        query = payload["query"]
        expected = {
            "dimensions": ["customers.id", "customers.age"],
            "measures": [
                "customers.purchase_amount",
                "customers.ad_exposures",
                "customers.prior_purchase_amount",
            ],
            "timeDimensions": [
                {
                    "dimension": "customers.date",
                    "dateRange": ["2026-02-01", "2026-02-28"],
                }
            ],
            "order": [["customers.id", "asc"]],
        }
        sales_query = {
            "dimensions": ["sales.product"],
            "measures": ["sales.revenue"],
            "timeDimensions": [
                {
                    "dimension": "sales.date",
                    "dateRange": ["2026-09-01", "2026-09-30"],
                }
            ],
        }
        base_query = {
            key: value for key, value in query.items() if key not in ("limit", "offset")
        }
        if path not in ("/load", "/sql") or base_query not in (expected, sales_query):
            raise AssertionError(f"Unexpected customer fixture query: {query}")
        self.requests.append({"path": path, "body": deepcopy(payload)})
        if path == "/sql":
            return {"sql": {"sql": []}}
        rows = (
            [
                {"sales.product": "A", "sales.revenue": 30},
                {"sales.product": "B", "sales.revenue": 20},
                {"sales.product": "C", "sales.revenue": 20},
            ]
            if base_query == sales_query
            else (
                customer_sample()
                .rename(columns=lambda name: f"customers.{name}")
                .to_dict(orient="records")
            )
        )
        offset = query.get("offset", 0)
        return {"data": rows[offset : offset + query.get("limit", len(rows))]}


async def practice_session():
    """One empty session for the sales and customer examples, with no network."""
    return await MethodSession.fixture(
        CubeProvider(CustomerFixtureClient(), instance="shop")
    )


customer_session = practice_session

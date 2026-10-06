"""Opt-in live Recipe-free exploration; not an LLM planning benchmark."""
import json
import os
import sys

import httpx
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

API = os.environ.get("DL_JOURNEY_API_URL")
pytestmark = pytest.mark.skipif(not API, reason="Set DL_JOURNEY_API_URL to the Complete Journey API")
PROVIDER = os.environ.get("DL_JOURNEY_PROVIDER", "cube")
PREFIX = f"{PROVIDER}://journey/"


def data(response):
    assert not response.is_error
    payload = response.structured_content or json.loads(response.content[0].text)
    assert not payload.get("error"), payload
    return payload


async def test_mcp_exploration_and_peer_comparison():
    server = StdioServerParameters(command=sys.executable, args=["-m", "decision_layer.mcp.server"],
                                   env={"DL_API_URL": API, "DL_LOCALE": "ko"})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        data(await client.call_tool("list_recipes"))
        if PROVIDER == "metricflow":
            receipts, department, rate, store = "metrics/receipts", "dimensions/product__department", "metrics/coupon_line_rate", "dimensions/transaction__store"
        else:
            receipts, department, rate, store = "transaction/receipts", "product/department", "transaction/coupon_line_rate", "transaction/store"
        question = "어떤 부문의 수취액이 가장 높고, 가장 높은 매장의 쿠폰 사용 비율은 동료·전체 집단과 얼마나 달라?"
        started = data(await client.call_tool("start_analysis", {"question": question}))
        run_id = started["run_id"]
        result = data(await client.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown", "purpose": "수취액이 가장 큰 상품 부문 확인",
            "bindings": {"metric": PREFIX + receipts, "dimensions": [PREFIX + department, PREFIX + store]},
        }))
        assert result["status"] == "success", result
        row = result["primary"]["data"]["rows"][0]
        assert row["value"] == "GROCERY" and row["metric"] == pytest.approx(4093814.14, abs=0.01)
        stores = data(await client.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown", "purpose": "최상위 부문에서 수취액이 가장 큰 매장 확인",
            "bindings": {"metric": PREFIX + receipts, "dimensions": [PREFIX + department, PREFIX + store]},
            "params": {"drill_path": {"source": "step", "step_id": "step_1", "project": "path"}},
        }))
        assert stores["status"] == "success"
        top_store = stores["primary"]["data"]["rows"][0]["value"]
        assert top_store == "367"
        peer = data(await client.call_tool("run_step", {
            "run_id": run_id, "method": "query.peer_comparison", "purpose": "최상위 매장의 쿠폰 사용 비율을 동료·전체 집단과 비교",
            "bindings": {"metric": PREFIX + rate},
            "params": {"subject": {"source": "step", "step_id": "step_2", "project": "condition"},
                       "peers": {"source": "step", "step_id": "step_2", "project": "parents"}},
        }))
        assert peer["status"] == "success", peer
        rows = peer["primary"]["data"]["rows"]
        assert len(rows) == 3 and all(row["count"] is None for row in rows)
        assert rows[0]["metric"] == pytest.approx(1.613, abs=0.0001)
        assert rows[1]["difference_from_subject"] == pytest.approx(rows[0]["metric"] - rows[1]["metric"], abs=0.0002)
        assert PREFIX + store in peer["provenance"]["semantic_refs"]
        assert peer["primary"]["data"]["statistical_judgement"] == "not_tested"
        pending = data(await client.call_tool("get_run", {"run_id": run_id}))
        assert pending["status"] == "open" and pending["conclusion"] is None
        assert pending["question"] == question and len(pending["steps"]) == 3
        assert all(step["purpose"] for step in pending["steps"])
        assert pending["steps"][2]["requested_step"]["params"]["subject"]["source"] == "step"
        assert len(pending["steps"][2]["input_resolutions"]) == 2
        data(await client.call_tool("complete_run", {"run_id": run_id, "conclusion": {
            "answer": "GROCERY 수취액이 가장 높습니다. 최상위 매장 367의 쿠폰 사용 비율은 동료 및 전체 비교 집단보다 높습니다.",
            "findings": [{"text": "상품 부문별 수취액을 비교했습니다.", "step_indices": [0]},
                         {"text": "최상위 부문에서 수취액 1위 매장을 찾았습니다.", "step_indices": [1]},
                         {"text": "선택한 매장을 제외한 동료·전체 집단과 비교했습니다.", "step_indices": [2]}],
            "limitations": ["인과 효과나 부정 행위는 판단하지 않았습니다."]}}))
    async with httpx.AsyncClient(base_url=API, timeout=60) as api:
        response = await api.get(f"/runs/{run_id}/recipe-candidate", params=[("indices", 0), ("indices", 1), ("indices", 2)])
        response.raise_for_status()
        assert len(response.json()["recipe"]["steps"]) == 3
        assert response.json()["recipe"]["steps"][2]["params"]["subject"]["source"] == "step"
    print(f"JOURNEY_MCP_RUN_ID={run_id}")

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
PREFIX = "cube://journey/"


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
        assert data(await client.call_tool("list_recipes"))["recipes"] == []
        started = data(await client.call_tool("start_analysis", {"question": "어떤 부문의 수취액이 가장 높고, 364 매장의 쿠폰 사용 비율은 동료·전체 집단과 얼마나 달라?"}))
        run_id = started["run_id"]
        result = data(await client.call_tool("run_step", {
            "run_id": run_id, "method": "query.drilldown", "purpose": "수취액이 가장 큰 상품 부문 확인",
            "bindings": {"metric": PREFIX + "transaction/receipts", "dimensions": [PREFIX + "product/department"]},
        }))
        assert result["status"] == "success", result
        row = result["primary"]["data"]["rows"][0]
        assert row["value"] == "GROCERY" and row["metric"] == pytest.approx(4093814.14, abs=0.01)
        peer = data(await client.call_tool("run_step", {
            "run_id": run_id, "method": "query.peer_comparison", "purpose": "364 매장의 식료품 쿠폰 사용 비율을 다른 매장과 비교",
            "bindings": {"metric": PREFIX + "transaction/coupon_line_rate"},
            "params": {"subject": [{"member": PREFIX + "transaction/store", "value": "364"}],
                       "peers": [{"member": PREFIX + "product/department", "value": "GROCERY"}]},
        }))
        assert peer["status"] == "success", peer
        rows = peer["primary"]["data"]["rows"]
        assert len(rows) == 3 and all(row["count"] >= 30 for row in rows)
        assert rows[0]["metric"] == pytest.approx(0.8131917777275808, abs=0.0001)
        assert rows[1]["difference_from_subject"] == pytest.approx(rows[0]["metric"] - rows[1]["metric"], abs=0.0002)
        assert PREFIX + "transaction/store" in peer["provenance"]["semantic_refs"]
        assert peer["primary"]["data"]["statistical_judgement"] == "not_tested"
        data(await client.call_tool("complete_run", {"run_id": run_id, "summary": "GROCERY 수취액이 가장 높음. 364 매장의 쿠폰 사용 비율을 대상 제외 집단과 비교했으며, 인과 효과나 부정 행위는 판단하지 않음."}))
    async with httpx.AsyncClient(base_url=API, timeout=60) as api:
        response = await api.get(f"/runs/{run_id}/recipe-candidate", params=[("indices", 0), ("indices", 1)])
        response.raise_for_status()
        assert len(response.json()["recipe"]["steps"]) == 2
    print(f"JOURNEY_MCP_RUN_ID={run_id}")

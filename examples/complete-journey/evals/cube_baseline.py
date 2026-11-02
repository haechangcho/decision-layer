"""Read-only Cube API tools for the Complete Journey comparison.

Set BENCH_CUBE_URL and BENCH_CUBE_TOKEN in the local process environment. This
is a benchmark adapter, not an official Cube MCP server or product connector.
"""
import csv
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer("cube-baseline", instructions="Discover and query the governed Cube catalog.")


async def request(path, params=None):
    url = os.environ["BENCH_CUBE_URL"].rstrip("/")
    token = os.environ["BENCH_CUBE_TOKEN"]
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url + path, params=params, headers={"Authorization": token})
        response.raise_for_status()
        return response.json()


@server.tool()
async def get_catalog() -> dict:
    """Return Cube measures, dimensions, types and descriptions."""
    return await request("/meta")


@server.tool()
async def query_metrics(query: dict) -> dict:
    """Execute a Cube JSON query using discovered measures and dimensions."""
    return await request("/load", {"query": json.dumps(query)})


@server.tool()
async def export_query_csv(query: dict) -> dict:
    """Run a Cube query and save its single-page results to a local CSV for Python.

    The query is caller-specified; no analytical procedure or calculation is
    supplied. The tool rejects a result that reaches the row limit.
    """
    if "offset" in query or "total" in query:
        raise ValueError("Export does not accept offset or total")
    limit = query.get("limit", 50000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50000:
        raise ValueError("Export limit must be between 1 and 50000")
    query = {**query, "limit": limit}
    result = await request("/load", {"query": json.dumps(query)})
    rows = result.get("data")
    if not isinstance(rows, list) or not rows or len(rows) >= limit:
        raise ValueError("A nonempty complete single-page Cube result is required")
    if any(not isinstance(row, dict) or row.keys() != rows[0].keys() for row in rows):
        raise ValueError("Cube returned inconsistent row columns")
    folder = Path(os.environ["BENCH_EXPORT_DIR"]).resolve(strict=True)
    path = folder / f"cube-{uuid4().hex}.csv"
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"query": query, "path": str(path), "rows": len(rows),
            "columns": list(rows[0]), "retrieval_complete": True,
            "limitations": ["Query exhaustion does not verify source ingestion completeness."]}


if __name__ == "__main__":
    server.run(transport="stdio")

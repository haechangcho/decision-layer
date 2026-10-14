"""Read-only semantic MCP baseline for the synthetic sample, not a product adapter."""
import json
import os
import time
import httpx
import jwt
from mcp.server.mcpserver import MCPServer

server = MCPServer('semantic-baseline', instructions='Query the governed Cube model. Discover its members first. Use the supplied investigation procedure and verify every numeric claim with tool results.')
URL = os.environ.get('BENCH_CUBE_URL', 'http://127.0.0.1:4100/cubejs-api/v1')

async def call(path, params=None):
    token = jwt.encode({'sub':'benchmark','exp':int(time.time())+300}, 'local-quickstart-secret-change-me-0123456789', algorithm='HS256')
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(URL+path, params=params, headers={'Authorization':token})
        response.raise_for_status()
        return response.json()

@server.tool()
async def get_catalog() -> dict:
    """Discover provider-owned measures, dimensions, types and descriptions."""
    return await call('/meta')

@server.tool()
async def query_metrics(query: dict) -> dict:
    """Execute a read-only Cube JSON query using discovered measures, dimensions,
    timeDimensions [{dimension,dateRange:[start,end]}], filters, order and limit.
    Retrieve all candidate groups before selecting a leader; tied leaders need input.
    """
    return await call('/load', {'query':json.dumps(query)})

if __name__ == '__main__':
    server.run(transport='stdio')

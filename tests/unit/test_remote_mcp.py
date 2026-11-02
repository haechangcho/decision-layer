"""Remote MCP over streamable HTTP in shared deployments (ADR-130)."""
import asyncio
import socket
import threading
import time

import httpx
import pytest

from decision_layer.console import create_console
from decision_layer.login.sessions import Person
from tests.unit.test_shared_login import shared_settings


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path, monkeypatch):
    import uvicorn

    port = _free_port()
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html>")
    monkeypatch.setenv("DL_API_URL", f"http://127.0.0.1:{port}")
    app = create_console(shared_settings(tmp_path / "recipes"), static_dir=static)
    api = next(route.app for route in app.routes if getattr(route, "path", None) == "/api")
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    instance = uvicorn.Server(config)
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    for _ in range(100):
        if instance.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", api.state.login
    instance.should_exit = True
    thread.join(timeout=10)


def test_mcp_requires_an_access_token(server):
    url, _login = server
    for headers in ({}, {"Authorization": "Bearer some-cube-jwt"}):
        response = httpx.post(url + "/mcp", headers=headers, json={})
        assert response.status_code == 401 and response.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.parametrize("oauth", [False, True])
def test_mcp_tools_run_as_the_token_owner(server, oauth):
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    url, login = server
    options = {"seconds": 3600, "client_id": "test-client", "resource": login.config.public_url + "/mcp"} if oauth else {}
    token, _record = asyncio.run(login.tokens.create(Person("oidc:alice", "user", "Alice"), "test", 1, **options))

    async def call(headers):
        async with httpx2.AsyncClient(headers=headers, timeout=30) as http, \
                streamable_http_client(url + "/mcp", http_client=http) as (read, write), \
                ClientSession(read, write) as session:
            await session.initialize()
            tools = {tool.name for tool in (await session.list_tools()).tools}
            result = await session.call_tool("list_methods", {})
            return tools, result

    tools, result = asyncio.run(call({"Authorization": f"Bearer {token}"}))
    assert {"list_methods", "start_analysis", "get_run"} <= tools
    assert not result.is_error and "methods" in str(result.structured_content or result.content)
    asyncio.run(login.tokens.revoke("oidc:alice", _record.id))
    # Invalid tokens are now rejected before MCP initialization/listing, not only
    # when a tool forwards the token to the API.
    revoked = httpx.post(url + "/mcp", headers={"Authorization": f"Bearer {token}"}, json={})
    assert revoked.status_code == 401


def test_mcp_rejects_wrong_resource_and_expired_tokens(server):
    url, login = server
    for resource, seconds in (("https://cube.example/mcp", 3600), (login.config.public_url + "/mcp", -1)):
        token, record = asyncio.run(login.tokens.create(Person("oidc:alice", "admin"), "test", 0,
            seconds=seconds, client_id="test-client", resource=resource))
        response = httpx.post(url + "/mcp", headers={"Authorization": "Bearer " + token}, json={})
        assert response.status_code == 401

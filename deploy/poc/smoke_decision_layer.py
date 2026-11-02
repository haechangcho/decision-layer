"""Check a built image without host mounts, published ports or warehouse access."""

import argparse
import json
import subprocess
from uuid import uuid4


CHECK = r"""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import time
import urllib.error
import urllib.request

import decision_layer
import numpy
import pandas
import sklearn
import statsmodels.api
from decision_layer.methods import registry
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

assert os.getuid() == 10001
assert 'site-packages' in str(Path(decision_layer.__file__).resolve())
assert not Path('/build').exists() and not Path('/app/src').exists()
values = numpy.arange(80, dtype=float)
frame = pandas.DataFrame({'entity_id': values, 'x': values, 'z': values % 7, 'y': 3 + 2 * values + 0.5 * (values % 7)})
assert abs(registry.get('stats.regression_adjustment').fn(frame, 'y', 'x', ['z'])['value'] - 2) < 1e-8

def get(path):
    return urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=3)

for attempt in range(100):
    try:
        health = json.load(get('/health'))
        break
    except (OSError, urllib.error.URLError):
        time.sleep(0.2)
else:
    raise AssertionError('Image server did not become ready')
assert health['status'] == 'ok'
assert json.load(get('/api/health'))['version'] == importlib.metadata.version('decision-layer')
html = get('/ui/methods').read().decode()
asset = re.search(r'<script[^>]+src="([^"]+)"', html)[1]
assert get(asset).status == 200
try:
    get('/ui/assets/missing.js')
except urllib.error.HTTPError as exc:
    assert exc.code == 404
else:
    raise AssertionError('Missing JS must not return index.html')
try:
    get('/semantic/catalog')
except urllib.error.HTTPError as exc:
    assert exc.code == 401
else:
    raise AssertionError('Catalog accepted an unauthenticated request')
expected = {'analysis.metric_lookup', 'analysis.drilldown', 'stats.regression_adjustment', 'stats.binary_matching'}
assert {m['name'] for m in json.load(get('/methods'))} == expected

async def check_mcp():
    server = StdioServerParameters(command=shutil.which('decision-layer-mcp'),
        env={'DL_API_URL': 'http://127.0.0.1:8000', 'DL_LOCALE': 'en'})
    async with stdio_client(server) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert {'list_methods', 'get_semantic_catalog', 'run_skill_query'} <= names
        result = await client.call_tool('list_methods', {})
        assert not result.is_error
        payload = result.structured_content or json.loads(result.content[0].text)
        assert {m['name'] for m in payload['methods']} == expected

asyncio.run(check_mcp())
Path('/data/image-smoke-marker').write_text('persistent')
print('PASS: installed wheel, non-root user, UI/assets, REST, authentication refusal, statistics imports and stdio MCP.')
"""

RESTART_CHECK = r"""
from pathlib import Path
import json
import time
import urllib.request
for attempt in range(100):
    try:
        assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3))['status'] == 'ok'
        break
    except OSError:
        time.sleep(0.2)
else:
    raise AssertionError('Image did not recover after restart')
assert Path('/data/image-smoke-marker').read_text() == 'persistent'
assert Path('/data/decision_layer.db').is_file()
print('PASS: restart preserves writable state.')
"""

# Shared mode with placeholder login settings: no IdP is contacted on these paths.
SHARED_ENV = {
    "DL_DEPLOYMENT_MODE": "shared",
    "DL_PUBLIC_URL": "http://localhost:5104",
    "DL_OIDC_ISSUER": "https://idp.invalid/application/o/decision-layer/",
    "DL_OIDC_CLIENT_ID": "smoke",
    "DL_OIDC_CLIENT_SECRET": "smoke",
    "DL_ADMIN_GROUPS": "dl-poc-admin",
    "DL_SESSION_SECRET": "session-" + "s" * 32,
    "DL_CUBE_TOKEN_SECRET": "cube-" + "c" * 32,
    "DL_API_URL": "http://127.0.0.1:8000",
}

SHARED_CHECK = r"""
import asyncio
import json
import time
import urllib.error
import urllib.request

from decision_layer.login.sessions import Person
from decision_layer.login.tokens import open_token_store

def call(path, token=None, method='GET', body=None):
    request = urllib.request.Request('http://127.0.0.1:8000' + path, method=method, data=body,
        headers={'Authorization': f'Bearer {token}'} if token else {})
    try:
        response = urllib.request.urlopen(request, timeout=10)
        return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b'{}')

for attempt in range(100):
    try:
        if call('/health')[0] == 200:
            break
    except OSError:
        time.sleep(0.2)
else:
    raise AssertionError('Shared server did not become ready')
status, body = call('/methods')
assert status == 401 and body['error']['code'] == 'LOGIN_REQUIRED', body
assert call('/openapi.json')[0] in (401, 404)
assert call('/mcp', method='POST', body=b'{}')[0] == 401
token, _ = asyncio.run(open_token_store('sqlite:////data/decision_layer.db').create(
    Person('oidc:smoke', 'user', 'Smoke'), 'smoke', 1))
status, me = call('/me', token)
assert status == 200 and me['subject'] == 'oidc:smoke' and me['groups'] == ['guest'], me
assert call('/methods', token)[0] == 200
print('PASS: shared mode requires login, rejects anonymous MCP and accepts access tokens.')
"""


def docker(*args, script=None, check=True):
    return subprocess.run(
        ["docker", *args],
        input=script,
        text=True,
        capture_output=True,
        check=check,
        timeout=120,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    args = parser.parse_args()
    name = "dl-image-smoke-" + uuid4().hex[:12]
    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--name",
            name,
            "--env",
            "OPENBLAS_NUM_THREADS=1",
            "--env",
            "OMP_NUM_THREADS=1",
            args.image,
        )
        print(docker("exec", "-i", name, "python", "-", script=CHECK).stdout.strip())
        docker("restart", name)
        print(
            docker(
                "exec", "-i", name, "python", "-", script=RESTART_CHECK
            ).stdout.strip()
        )
        rejected = docker(
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--env",
            "DL_DEPLOYMENT_MODE=shared",
            args.image,
            check=False,
        )
        assert rejected.returncode != 0
        assert "Shared deployment requires" in rejected.stderr
        print("PASS: shared deployment without login settings fails closed.")
        docker("rm", "--force", "--volumes", name, check=False)
        env = [arg for key, value in SHARED_ENV.items() for arg in ("--env", f"{key}={value}")]
        docker("run", "--detach", "--rm", "--platform", "linux/amd64", "--network", "none",
               "--name", name, *env, args.image)
        print(docker("exec", "-i", name, "python", "-", script=SHARED_CHECK).stdout.strip())
        info = json.loads(docker("image", "inspect", args.image).stdout)[0]
        print(
            json.dumps(
                {
                    "image": args.image,
                    "id": info["Id"],
                    "architecture": info["Architecture"],
                }
            )
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        print(exc.stderr)
        print(docker("logs", "--tail", "60", name, check=False).stdout)
        raise
    finally:
        docker("rm", "--force", "--volumes", name, check=False)


if __name__ == "__main__":
    main()

"""Query an image against a disposable PostgreSQL, without exposing host ports."""

import argparse
import json
import subprocess
import time
from uuid import uuid4

from smoke_decision_layer import docker


BOOTSTRAP = r"""
const fs = require('fs');
require('@cubejs-backend/native').loadNative();
fs.mkdirSync('model', { recursive: true });
fs.writeFileSync('cube.config.js', `module.exports = {
  AUTHENTIK_CUBE_ROLE_GROUPS: { admin: [], guest: [] },
  CUBE_WEB_MENUS: { admin: [], guest: [] },
  HC_ANALYTICS_URL: ''
};`);
fs.writeFileSync('cube.py', `from cube import config
@config('check_auth')
def check_auth(ctx, token):
    if token.removeprefix('Bearer ').strip() != 'image-smoke-token':
        raise Exception('Invalid JWT fixture token')
    return {'security_context': {'sub': 'image-smoke', 'cubeGroups': ['demo']}}
`);
fs.writeFileSync('model/sales.yml', `cubes:
  - name: smoke_sales
    sql_table: public.sales
    dimensions:
      - name: id
        sql: id
        type: number
        primary_key: true
      - name: region
        sql: region
        type: string
    measures:
      - name: count
        type: count
      - name: receipts
        sql: amount
        type: sum
`);
const child = require('child_process').spawn('cubejs', ['server'], { stdio: 'inherit' });
process.on('SIGTERM', () => child.kill('SIGTERM'));
child.on('exit', code => process.exit(code ?? 1));
"""

CHECK = r"""
const assert = require('assert/strict');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function main() {
  let ready = false;
  for (let n = 0; n < 180; n++) {
    try {
      if ((await fetch('http://127.0.0.1:4000/readyz')).ok) { ready = true; break; }
    } catch (_) {}
    await delay(500);
  }
  assert(ready, 'Cube did not become ready');
  const base = 'http://127.0.0.1:4000/cubejs-api/v1';
  assert(!(await fetch(base + '/meta')).ok, 'Python auth accepted a missing token');
  const headers = { Authorization: 'Bearer image-smoke-token', 'Content-Type': 'application/json' };
  const response = await fetch(base + '/meta', { headers });
  const meta = await response.json();
  assert(response.ok, JSON.stringify(meta));
  assert(meta.cubes.some(c => c.name === 'smoke_sales'));
  let result;
  for (let n = 0; n < 20; n++) {
    const response = await fetch(base + '/load', {
      method: 'POST', headers,
      body: JSON.stringify({ query: { measures: ['smoke_sales.receipts', 'smoke_sales.count'],
        dimensions: ['smoke_sales.region'], order: { 'smoke_sales.region': 'asc' } } })
    });
    result = await response.json();
    if (result.error === 'Continue wait') { await delay(500); continue; }
    assert(response.ok && !result.error, JSON.stringify(result));
    break;
  }
  assert.deepEqual(result.data.map(row => [row['smoke_sales.region'],
    Number(row['smoke_sales.receipts']), Number(row['smoke_sales.count'])]),
    [['North', 30, 2], ['South', 30, 1]]);
  console.log('PASS: native module, Python configuration/auth, production mode, PostgreSQL query and memory queue without CubeStore.');
}
main().catch(err => { console.error(err); process.exit(1); });
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--postgres-image", default="postgres:16.4")
    args = parser.parse_args()
    prefix = "cube-image-smoke-" + uuid4().hex[:12]
    pg, cube = prefix + "-pg", prefix + "-cube"
    try:
        docker("network", "create", "--internal", prefix)
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            pg,
            "--network",
            prefix,
            "--network-alias",
            "postgres",
            "--env",
            "POSTGRES_DB=smoke",
            "--env",
            "POSTGRES_PASSWORD=image-smoke-only",
            args.postgres_image,
        )
        for _ in range(60):
            if (
                docker(
                    "exec",
                    pg,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    "-d",
                    "smoke",
                    check=False,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Fixture PostgreSQL did not become ready")
        docker(
            "exec",
            "-i",
            pg,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "smoke",
            script="CREATE TABLE sales (id integer PRIMARY KEY, region text, amount numeric);\n"
            "INSERT INTO sales VALUES (1, 'North', 10), (2, 'North', 20), (3, 'South', 30);\n",
        )
        options = []
        for key, value in {
            "CUBEJS_DEV_MODE": "false",
            "CUBEJS_DB_TYPE": "postgres",
            "CUBEJS_DB_HOST": "postgres",
            "CUBEJS_DB_NAME": "smoke",
            "CUBEJS_DB_USER": "postgres",
            "CUBEJS_DB_PASS": "image-smoke-only",
            "CUBEJS_API_SECRET": "image-smoke-only-signing-secret-32-characters",
            "CUBEJS_SCHEMA_PATH": "model",
            "CUBEJS_CACHE_AND_QUEUE_DRIVER": "memory",
            "CUBEJS_EXTERNAL_DEFAULT": "false",
            "CUBEJS_SCHEDULED_REFRESH_DEFAULT": "false",
            "CUBEJS_SCHEDULED_REFRESH": "false",
            "CUBEJS_TELEMETRY": "false",
        }.items():
            options.extend(["--env", f"{key}={value}"])
        docker(
            "run",
            "--detach",
            "--platform",
            "linux/amd64",
            "--name",
            cube,
            "--network",
            prefix,
            *options,
            "--entrypoint",
            "node",
            args.image,
            "-e",
            BOOTSTRAP,
        )
        print(docker("exec", "-i", cube, "node", "-", script=CHECK).stdout.strip())
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
    except (AssertionError, subprocess.SubprocessError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stdout)
            print(exc.stderr)
        for name in (cube, pg):
            state = docker("inspect", "--format", "{{json .State}}", name, check=False)
            print(state.stdout)
            logs = docker("logs", "--tail", "60", name, check=False)
            print(logs.stdout, logs.stderr)
        raise
    finally:
        for name in (cube, pg):
            docker("rm", "--force", "--volumes", name, check=False)
        docker("network", "rm", prefix, check=False)


if __name__ == "__main__":
    main()

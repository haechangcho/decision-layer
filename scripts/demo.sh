#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
command -v docker >/dev/null || { echo 'Install Docker with Compose, start it, then rerun: bash scripts/demo.sh' >&2; exit 1; }
docker compose version >/dev/null
docker info >/dev/null 2>&1 || { echo 'Docker is not running or is inaccessible. Start Docker, then rerun this command.' >&2; exit 1; }
compose=(docker compose -f examples/quickstart/compose.yaml)
case "${1:-start}" in
  start)
    echo 'Starting an isolated synthetic sample. First build downloads dependencies and may take several minutes.'
    if ! "${compose[@]}" up -d --build --wait --wait-timeout 300; then
      echo 'Startup failed. Inspect: docker compose -f examples/quickstart/compose.yaml logs --tail=60' >&2
      echo 'If ports are occupied, set DL_DEMO_WEB_PORT and DL_DEMO_API_PORT and rerun.' >&2
      exit 1
    fi
    "${compose[@]}" exec -T api python /demo/replay.py --web "http://localhost:${DL_DEMO_WEB_PORT:-3100}" --output /data/quickstart-evidence.json
    echo "Open http://localhost:${DL_DEMO_WEB_PORT:-3100}/runs to inspect the real execution records."
    ;;
  replay) "${compose[@]}" exec -T api python /demo/replay.py --web "http://localhost:${DL_DEMO_WEB_PORT:-3100}" --output /data/quickstart-evidence.json ;;
  stop) "${compose[@]}" stop ;;
  *) echo 'Usage: bash scripts/demo.sh [start|replay|stop]' >&2; exit 2 ;;
esac

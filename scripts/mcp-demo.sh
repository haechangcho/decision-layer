#!/usr/bin/env bash
# MCP stdout must contain only protocol messages. Startup logs go to stderr.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
compose=(docker compose -f examples/quickstart/compose.yaml)
"${compose[@]}" up -d --wait --wait-timeout 180 api >&2
exec "${compose[@]}" exec -T -e DL_API_URL=http://127.0.0.1:8000 -e "DL_WEB_URL=http://localhost:${DL_DEMO_WEB_PORT:-3100}" api decision-layer-mcp

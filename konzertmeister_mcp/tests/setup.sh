#!/usr/bin/env bash
# Installs what the unit tests need – the same pinned packages as the image.
# Called by the "Test" workflow from the repository root before `pytest <app>/tests`.
set -euo pipefail
app="$(cd "$(dirname "$0")/.." && pwd)"
pip install -c "$app/constraints.txt" mcp httpx uvicorn starlette python-multipart tzdata
pip install aiohttp pytest pyyaml
# nginx, to check the generated configuration (test_nginx_accepts_the_generated_configuration)
if ! command -v nginx >/dev/null && command -v sudo >/dev/null; then
  sudo apt-get install -y -qq nginx-core >/dev/null || echo "nginx not installed – that test is skipped"
fi

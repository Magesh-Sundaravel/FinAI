#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DEV_USER_EMAIL="${DEV_USER_EMAIL:-dev-user@gmail.com}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/finai-uv-cache}"
PORT="${PORT:-8000}"

uv run python scripts/seed_local_data.py --email "$DEV_USER_EMAIL" --reset
uv run uvicorn app.main:app --port "$PORT" --reload

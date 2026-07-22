#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-/opt/conda/bin/python}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

export CHECKPOINT_PATH="${CHECKPOINT_PATH:-$ROOT/model/saved/best_model.pt}"
export PROCESSED_PATH="${PROCESSED_PATH:-$ROOT/processed}"
export MODEL_VERSION="${MODEL_VERSION:-monitor-v2.0}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

cd "$ROOT"
exec "$PYTHON" -m uvicorn api:app --host "$HOST" --port "$PORT" --workers 1

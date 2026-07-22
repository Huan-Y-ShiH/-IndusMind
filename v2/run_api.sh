#!/usr/bin/env bash
set -euo pipefail

export CHECKPOINT_PATH="${CHECKPOINT_PATH:-./v2/model/saved/best_model.pt}"
export PROCESSED_PATH="${PROCESSED_PATH:-./processed}"
export MODEL_VERSION="${MODEL_VERSION:-monitor-v2.0}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
PYTHON_BIN="${PYTHON_BIN:-python}"

exec "${PYTHON_BIN}" -m uvicorn v2.api:app \
  --host 0.0.0.0 \
  --port "${PORT:-8001}" \
  --workers 1

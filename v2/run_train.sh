#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
PYTHON_BIN="${PYTHON_BIN:-python}"

"${PYTHON_BIN}" -m v2.train \
  --data-path "${DATA_PATH:-./processed}" \
  --output "${OUTPUT_PATH:-./v2/model/saved}" \
  --device cuda \
  --epochs "${EPOCHS:-60}" \
  --warmup-epochs "${WARMUP_EPOCHS:-3}" \
  --batch-size "${BATCH_SIZE:-512}" \
  --num-workers "${NUM_WORKERS:-4}" \
  --lr "${LEARNING_RATE:-0.0003}" \
  --svdd-weight "${SVDD_WEIGHT:-0.05}" \
  --degradation-weight "${DEGRADATION_WEIGHT:-0.02}" \
  --rul-cap "${RUL_CAP:-0}"

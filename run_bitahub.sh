#!/usr/bin/env bash
# Bitahub / RTX 4090 training entrypoint
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-/opt/conda/bin/python}"
DATA_PATH="${DATA_PATH:-$ROOT/processed}"
OUTPUT="${OUTPUT:-$ROOT/model/saved}"

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export PYTHONUNBUFFERED=1

echo "=================================================="
echo " IndusMind RUL Training (Bitahub)"
echo "=================================================="
"$PYTHON" - <<'PY'
import torch, sys
print(f"Python: {sys.version.split()[0]}")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print("==================================================")
PY

mkdir -p "$OUTPUT"
cd "$ROOT"

exec "$PYTHON" train.py \
  --data-path "$DATA_PATH" \
  --output "$OUTPUT" \
  --device cuda \
  --epochs "${EPOCHS:-150}" \
  --batch-size "${BATCH_SIZE:-256}" \
  --lr "${LR:-0.001}" \
  --patience "${PATIENCE:-25}" \
  --dropout "${DROPOUT:-0.3}" \
  --max-rul 0 \
  --weight-decay "${WEIGHT_DECAY:-0.0001}" \
  --num-workers "${NUM_WORKERS:-4}" \
  --lstm-hidden 128 \
  --lstm-layers 2

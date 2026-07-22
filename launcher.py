"""
ModelArts Launcher - IndusMind Monitor v2 on Tesla V100

Boot:
  python launcher.py

Data channel (data_url_0) must contain the NEW processed artifacts:
  X_train.npy, y_train.npy, unit_train.npy,
  X_val.npy, y_val.npy, max_rul.npy
"""
import sys
import os

# Prefer CUDA on ModelArts; fall back only if unavailable.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

sys.argv = [
    "train.py",
    "--data-path", "/home/ma-user/modelarts/inputs/data_url_0",
    "--output", "/home/ma-user/modelarts/outputs/train_url_0",
    "--device", "cuda",
    "--epochs", "60",
    "--warmup-epochs", "3",
    "--batch-size", "256",
    "--lr", "0.0003",
    "--patience", "12",
    "--dropout", "0.25",
    "--weight-decay", "0.0001",
    "--num-workers", "4",
    "--svdd-weight", "0.05",
    "--degradation-weight", "0.02",
]

print("=" * 50)
print(" IndusMind Monitor v2 Training (ModelArts / V100)")
print("=" * 50)
import torch

print(f"Python: {sys.version.split()[0]}")
print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA capability: {torch.cuda.get_device_capability(0)}")
else:
    raise RuntimeError(
        "CUDA is unavailable. Select a ModelArts GPU flavor with Tesla V100 "
        "and a CUDA-enabled PyTorch image."
    )
print("=" * 50)

import train

train.main()

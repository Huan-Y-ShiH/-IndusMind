"""
ModelArts Launcher - IndusMind RUL Training (Integrated FD001-004)
"""
import sys
import os

sys.argv = [
    "train.py",
    "--data-path", "/home/ma-user/modelarts/inputs/data_url_0",
    "--output", "/home/ma-user/modelarts/outputs/train_url_0",
    "--epochs", "150",
    "--batch-size", "128",
    "--lr", "0.001",
    "--patience", "25",
    "--dropout", "0.4",
    "--max-rul", "0",
    "--weight-decay", "0.0001",
]

print("=" * 50)
print(" IndusMind RUL Training (FD001-004)")
print("=" * 50)
import torch
print(f"Python: {sys.version.split()[0]}")
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
print("=" * 50)

import train
train.main()

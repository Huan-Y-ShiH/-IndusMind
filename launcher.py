"""
ModelArts Launcher for IndusMind RUL Training.
Runs 'python launcher.py' (no permission issue).
"""
import sys
import os

# Override sys.argv with ModelArts paths
sys.path.insert(0, "/home/ma-user/modelarts/user-job-dir/code")
sys.argv = [
    "train.py",
    "--data-path", "/home/ma-user/modelarts/inputs/data_url_0",
    "--output", "/home/ma-user/modelarts/outputs/train_url_0",
    "--epochs", "100",
    "--batch-size", "64",
    "--lr", "0.001",
    "--patience", "15",
]

print("=" * 50)
print(" IndusMind RUL Training via launcher")
print("=" * 50)
print(f"Args: {sys.argv}")
print(f"Python: {sys.version}")
print(f"CUDA available: {__import__('torch').cuda.is_available()}")
print("=" * 50)

# Run train.py main()
import train
train.main()

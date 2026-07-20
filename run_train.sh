#!/bin/bash
# IndusMind - ModelArts Training Launcher
# Wraps python train.py to avoid "Permission denied"

echo "================================"
echo " IndusMind RUL Training v1"
echo "================================"
echo "Time: $(date)"
echo "Host: $(hostname)"
echo "GPU: $(nvidia-smi -L 2>/dev/null || echo 'CPU mode')"
echo "================================"

cd /home/ma-user/modelarts/user-job-dir/code/

echo "Files in code dir:"
ls -la

echo ""
echo "Starting training..."
python train.py     --data-path /home/ma-user/modelarts/inputs/data_url_0     --output /home/ma-user/modelarts/outputs/train_url_0     --epochs 100     --batch-size 64     --lr 0.001     --patience 15

EXIT_CODE=$?
echo ""
echo "================================"
echo " Training exited with code: $EXIT_CODE"
echo "================================"
exit $EXIT_CODE

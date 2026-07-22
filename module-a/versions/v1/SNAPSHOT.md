# v1 回滚快照

- Git commit：`24f749a820f488705ea719e0f6dfaaf8dc169cd8`
- 线上模型：`monitor-v1.0`
- 模型：2 层 BiLSTM，约 596k 参数
- 最佳端点 RMSE：`26.27 cycles`
- 最佳 epoch：`1`
- 原线上端口：`8000`

回滚代码：

```bash
git checkout 24f749a820f488705ea719e0f6dfaaf8dc169cd8 -- \
  api.py infer.py launcher.py lstm_transformer.py \
  preprocess_integrated.py run_api.sh run_bitahub.sh train.py
```

v1 文档位于根目录，升级过程中保持原样不动。

v1 权重由线上 `/root/indus_data/model/saved/best_model.pt` 保留；
部署 v2 前应复制到线上 `versions/v1/model/saved/`。

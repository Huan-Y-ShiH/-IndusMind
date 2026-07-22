# IndusMind Monitor v2

v2 使用一个共享的 TCN-BiGRU 编码器，同时提供：

- RUL 回归：端点 RMSE 作为主晋级指标；
- 工况感知 Deep SVDD：输出独立异常分数和异常类型；
- 双 Integrated Gradients：分别解释 RUL 和异常距离；
- v1 兼容接口：继续使用 `POST /api/v1/monitor/analyze`。

## 训练

```bash
bash v2/run_train.sh
```

训练按发动机划分独立校准集。健康窗口用于构建每种工况的 SVDD
中心、异常距离分位数和 Integrated Gradients 基线，校准样本不参与梯度更新。

晋级条件是 v2 的标准 CMAPSS 发动机端点 RMSE 严格低于 v1 的
`26.27 cycles`。结果写入 `v2/model/saved/metadata.json`。

## 灰度 API

```bash
PORT=8001 bash v2/run_api.sh
```

请求字段与 v1 相同。v2 会填充原来为 `null` 的：

- `anomaly_score`
- `anomaly_type`
- `feature_attribution`

并新增两个向后兼容的可选字段：

- `anomaly_attribution`
- `attribution_metadata`

`pseudo_attribution` 在 v2 中保留字段但返回 `null`。

## 晋级与回滚

先在 `8001` 验证模型与接口。只有 `ready_for_promotion=true` 且代理指标
通过后，才把 v2 切换到 `8000`。v1 的代码快照和权重保存在
`versions/v1/`，可直接回滚。

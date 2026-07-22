# IndusMind 异常检测与正式归因能力补全方案

> **✅ 状态：已实现** — 本提案在 v2 (`monitor-v2.0`) 中已完成。
> v2 实现了比提案更强的方案：共享 TCN-BiGRU 编码器 + Deep SVDD 异常头 + 双 Integrated Gradients 归因，而非提案中的 Z-score。
> 详见 `README.md` 第 7 节（v2 架构）和第 9 节（API 变更）。
>
> **以下为提案原文，保留作为历史记录。**

## 1. 提交目的

当前 IndusMind 已具备涡扇发动机 RUL（Remaining Useful Life）预测能力，但监测 API 中以下字段仍为空：

```json
{
  "anomaly_score": null,
  "anomaly_type": null,
  "feature_attribution": null
}
```

本文用于明确问题边界，并提交一套**不重训现有 RUL 模型、改动最小、语义正确**的补全方案。

---

## 2. 问题定义

### 2.1 当前系统能回答的问题

现有 BiLSTM 模型可以回答：

> 根据最近 30 个周期的工况和传感器数据，设备预计还能运行多少 cycles？

当前有效输出：

- `rul_predicted`
- `rul_series`
- `pseudo_attribution`

其中 `pseudo_attribution` 通过 `Gradient × Input` 计算，解释的是：

> 哪些输入特征影响了本次 RUL 预测？

### 2.2 当前系统不能回答的问题

现有模型没有学习健康/异常分类，因此不能可靠回答：

1. 当前设备偏离健康状态的程度是多少？
2. 当前异常属于什么类型？
3. 哪些传感器导致了异常判断？

因此不能把 RUL、RUL 梯度或 RUL 阈值直接包装成异常概率。

### 2.3 必须区分的两个归因概念

| 字段 | 解释对象 | 当前状态 |
|------|----------|----------|
| `pseudo_attribution` | 哪些特征影响 RUL 预测 | 已实现 |
| `feature_attribution` | 哪些特征导致异常判断 | 未实现 |

两者语义不同，不能互相替代。

---

## 3. 现有代码状态

项目中已有 `degradation_analyzer.py`，包含 Z-score 残差分析的早期设计，但当前存在以下缺口：

- 未建立并持久化健康基线
- 未按工况分别统计健康分布
- 未计算经过校准的 `anomaly_score`
- 未接入当前 `api.py`
- 未生成正式 `feature_attribution`
- 未经过接口和边界测试

因此，线上 `monitor-v1.0` 仍只提供 RUL 推理。

---

## 4. 提交方案

### 4.1 方案名称

**Condition-aware Healthy Baseline Detector**

中文：**工况感知健康基线异常检测器**

### 4.2 方案原则

- 不修改现有 RUL 模型
- 不要求额外人工异常标签
- 不把 RUL 风险伪装成异常概率
- 复用当前 6 工况聚类与标准化结果
- 异常分数和特征归因必须来自同一统计体系

### 4.3 总体流程

```text
训练集健康窗口（RUL ≥ 125）
        ↓
按 6 个工况分别统计传感器健康均值与标准差
        ↓
保存 healthy_baseline.npz
        ↓
推理时取最近 30 点均值
        ↓
计算每个传感器相对对应工况基线的 Z-score
        ↓
生成 anomaly_score / anomaly_type / feature_attribution
```

---

## 5. 算法定义

### 5.1 健康样本定义

训练阶段使用：

```text
RUL ≥ 125 cycles
```

的窗口作为健康样本。

说明：

- 125 是 C-MAPSS 常用健康阶段截断值
- 该阈值是工程定义，不表示真实故障起始点
- 后续应通过验证集做敏感性分析

### 5.2 工况级健康基线

对每个工况 `c`、每个传感器 `i` 保存：

```text
healthy_mean[c, i]
healthy_std[c, i]
```

标准差为 0 或过小时设置下限，防止数值爆炸：

```python
healthy_std = max(healthy_std, 1e-6)
```

### 5.3 推理窗口

取最新 30 个时间点，并对每个传感器计算窗口均值：

```python
current_mean[i] = mean(latest_window[:, i])
```

### 5.4 Z-score

```python
z[i] = (current_mean[i] - healthy_mean[condition, i]) \
       / healthy_std[condition, i]
```

`z[i]` 的含义：

- `z > 0`：高于健康基线
- `z < 0`：低于健康基线
- `abs(z)`：偏离健康状态的程度

### 5.5 anomaly_score

取绝对 Z-score 最大的三个传感器：

```python
top3_mean = mean(top3(abs(z)))
anomaly_score = clip(top3_mean / 5.0, 0.0, 1.0)
```

字段定义：

> `anomaly_score` 是工况校正后的统计偏离分数，范围 0–1；不是故障概率。

### 5.6 anomaly_type

第一版只提供最小、可解释分类：

| 条件 | 返回值 |
|------|--------|
| `anomaly_score < 0.4` | `normal` |
| `anomaly_score >= 0.4` | `multivariate_anomaly` |

暂不输出 `trend_anomaly`，因为趋势类型需要多窗口异常分数序列，而不是单个最新窗口。

### 5.7 feature_attribution

每个传感器的贡献：

```python
contribution[i] = abs(z[i]) / sum(abs(z))
```

返回贡献最高的 5 个传感器。

方向：

```text
z > 0.1   → high
z < -0.1  → low
其他      → stable
```

该归因和异常分数使用同一 Z-score，因而可以正式填入 `feature_attribution`。

---

## 6. API 变更

### 6.1 变更前

```json
{
  "anomaly_score": null,
  "anomaly_type": null,
  "feature_attribution": null,
  "pseudo_attribution": [
    {
      "feature": "s3",
      "direction": "high",
      "contribution": 0.35
    }
  ]
}
```

### 6.2 变更后

```json
{
  "anomaly_score": 0.82,
  "anomaly_type": "multivariate_anomaly",
  "feature_attribution": [
    {
      "feature": "s3",
      "direction": "high",
      "contribution": 0.37
    },
    {
      "feature": "s4",
      "direction": "high",
      "contribution": 0.28
    }
  ],
  "pseudo_attribution": [
    {
      "feature": "s12",
      "direction": "low",
      "contribution": 0.31
    }
  ]
}
```

变更后两个归因字段同时保留：

- `feature_attribution`：解释统计异常
- `pseudo_attribution`：解释 RUL 预测

前端必须分别展示，不能合并。

---

## 7. 实施任务

### 7.1 离线基线生成

新增：

```text
build_healthy_baseline.py
```

输出：

```text
processed/healthy_baseline.npz
```

建议包含：

```text
healthy_mean
healthy_std
sensor_names
condition_ids
rul_threshold
score_scale
```

### 7.2 推理模块

新增：

```text
anomaly_detector.py
```

职责：

- 加载健康基线
- 计算 Z-score
- 生成 anomaly_score
- 生成 anomaly_type
- 生成 feature_attribution

### 7.3 API 接入

修改 `api.py`：

1. 服务启动时加载 `healthy_baseline.npz`
2. 复用当前工况识别结果
3. 对最新 30 点执行异常分析
4. 填充三个原为 `null` 的字段
5. 保留现有 RUL 与 pseudo attribution

### 7.4 文档

同步更新：

- `API_CONTRACT.md`
- `README.md`
- `MODEL_EVOLUTION.md`

---

## 8. 验收标准

### 8.1 功能验收

- [ ] 正常输入返回 `anomaly_score ∈ [0,1]`
- [ ] 返回 `normal` 或 `multivariate_anomaly`
- [ ] `feature_attribution` 最多 5 项
- [ ] 每项贡献在 `[0,1]`
- [ ] 贡献之和接近 1
- [ ] 正常数据不返回全 1 高分
- [ ] 人工放大某传感器后，该传感器进入 attribution Top5
- [ ] RUL 推理结果与改造前一致

### 8.2 数据安全验收

- [ ] 健康基线只由训练集拟合
- [ ] 不使用验证集统计量
- [ ] 按工况分别计算
- [ ] 标准差设置数值下限
- [ ] 缺失基线时 API 启动失败，不静默使用假数据

### 8.3 接口验收

- [ ] `/health` 显示 anomaly detector 已加载
- [ ] `/api/v1/monitor/analyze` 响应结构向后兼容
- [ ] 旧调用方仍可读取 RUL 字段
- [ ] 文档明确 anomaly score 不是故障概率

---

## 9. 风险与限制

### 9.1 它不是监督故障概率

当前没有真实异常/故障起始标签，因此输出只能定义为：

> 健康基线统计偏离分数

不能描述为：

> 82% 概率即将故障

### 9.2 健康窗口是弱定义

`RUL ≥ 125` 是工程阈值，并非真实故障注入时刻。

### 9.3 只能识别“偏离”，不能诊断具体部件

第一版类型只能是：

- `normal`
- `multivariate_anomaly`

要识别 HPC / Fan 等故障部件，需要带故障类别的数据和监督分类头。

---

## 10. 后续升级

当获得 N-CMAPSS 的 `health_state` 与故障类别后，可升级为多任务模型：

```text
Shared Temporal Encoder
  ├── RUL Regression Head
  ├── Anomaly Classification Head
  └── Fault Component Head
```

届时：

- `anomaly_score` 可升级为校准后的异常概率
- `anomaly_type` 可输出具体故障模式
- `feature_attribution` 可改为 Integrated Gradients 解释异常分类头

---

## 11. 提交结论

本次提交建议采用：

> **工况感知健康基线 + Z-score 异常检测 + 同源正式归因**

理由：

- 不重训现有 RUL 模型
- 不需要人工异常标签
- 算法和接口语义一致
- 实现与测试成本低
- 能真实填充当前三个 `null` 字段
- 保留未来升级为监督异常模型的空间

该方案是当前数据条件下最简单、最可解释、最不容易误导调用方的实现路径。

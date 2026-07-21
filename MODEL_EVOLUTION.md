# IndusMind 涡扇 RUL 模型：训练结果与进化过程

> 带图的项目入口请看根目录 [`README.md`](README.md)。  
> 本文是同一演进过程的纯文字详版。

> 从错误标签下的「假过拟合」，到整合全家族数据、工况感知归一化、端点评估与可调用监测 API。  
> 本文记录 **为什么改、改了什么、数字怎么变**。

---

## 0. 一句话结论

| 阶段 | 验证指标（原始 RUL，cycles） | 评价 |
|------|------------------------------|------|
| v0 初训（ModelArts V100） | **≈ 170** | 不可用：验证标签算反 |
| v1 数据与评估修好后（Bitahub 4090） | **≈ 26.3** | 可用基线：端点 RMSE |
| 相对提升 | **约 6.5× 误差下降** | 主要来自数据管道与评估协议，不是堆更大网络 |

当前线上模型：`monitor-v1.0`  
检查点：`model/saved/best_model.pt`（最佳轮次 epoch 1）  
结构：BiLSTM + 双池化头，约 **59.6 万** 参数，输入 **34** 维 × 窗口 **30**。

---

## 1. 进化总览（时间线）

```text
[数据] FD001 单集
   → FD001–004 + PHM08 整合三件套（927 训 / 707 验）
   → 工况聚类归一化 + 来源 one-hot + 发动机均衡采样

[标签] 验证 RUL 公式写反（大量负标签）
   → final_rul + max_cycle - current_cycle（全非负）

[评估] 全窗口 RMSE（长轨迹权重过大）
   → 每台发动机末窗口端点 RMSE（标准 CMAPSS 协议）

[训练] Mac MPS 过慢 / ModelArts 旧标签
   → Bitahub RTX 4090，~8–9 s/epoch，早停得到可用模型

[交付] 本地推理脚本
   → POST /api/v1/monitor/analyze 统一监测事件（含 pseudo_attribution）
```

---

## 2. 数据侧进化：从小样本到全家族

### 2.1 v0：只有 FD001

- 100 台训练 / 100 台测试  
- 单工况、单故障  
- 适合冒烟，不适合多工况泛化叙事  

### 2.2 v1：整合集（保留原子集语义）

| 来源 | 训练机数 | 角色 |
|------|----------|------|
| FD001 | 100 | 单工况入门 |
| FD002 | 260 | 六工况 |
| FD003 | 100 | 双故障 |
| FD004 | 249 | 六工况 + 双故障 |
| PHM08 train | 218 | 竞赛增广（无公开测试 RUL） |
| **合计** | **927** | 训练行数 ≈ 20.6 万 |

验证：FD001–004 官方测试合成，**707** 台带公开 RUL。  
原始列不变：`unit, cycle, op1–3, sensor1–21`。  
`unit` 全局重编号，溯源见 `integrated/integrated_unit_map.csv`。

### 2.3 预处理进化（决定性一步）

| 能力 | 旧 | 新 |
|------|----|----|
| 验证 RUL | `cycle + final - max`（错） | `final + max - cycle`（对） |
| 传感器归一化 | 全局 StandardScaler | **6 工况聚类**，工况内标准化 |
| 域信息 | 无 | `dataset` one-hot（FD001–004 / PHM08） |
| 工况信息 | 仅原始 op | 工况 ID one-hot |
| 特征维 | ≈ 23 | **34** |
| 采样 | 均匀滑窗（长寿命机占优） | **按发动机均衡** WeightedRandomSampler |
| 窗口元数据 | 未保存 | `unit_* / dataset_* / condition_*` |

处理后规模：

```text
X_train: (179394, 30, 34)
X_val:   (84478, 30, 34)
训练发动机: 927（均衡后每台 epoch 权重相等）
```

---

## 3. 训练侧进化：从「看起来过拟合」到可解释失败与可复现成功

### 3.1 v0 初训（ModelArts Tesla V100）— 失败但有价值

关键配置（日志摘要）：

- GPU：Tesla V100-PCIE-32GB  
- 模型：SimpleLSTM（日志里 Transformer 超参未真正使用）  
- batch 128，dropout 0.4，约 18–19 s/epoch  

结果：

```text
Best RMSE (norm): 0.3140
Best RMSE (original): 170.18   ← 以错误 max_rul=542 反算
Best epoch: 2，早停约 epoch 27
Train loss 持续下降至 ~0.04，Val 卡在 ~0.31～0.34
```

**根因（不是「模型太大」）：**

1. 验证集 RUL 公式符号错误 → **过半验证窗口为负标签**  
2. 输出层 ReLU 无法拟合负目标 → 验证误差有理论下界  
3. 训练/验证目标定义不一致 → 曲线像过拟合，实质是标签管道坏了  

这一阶段的意义：暴露了「只看 Train↓ Val↑」会误判；**先修数据契约，再谈结构**。

### 3.2 工程与评估协议补丁

| 改动 | 动机 |
|------|------|
| 断言 `y_train/y_val ≥ 0` | 防止错误标签静默上线 |
| 全局 RMSE（非 batch 平均 RMSE） | 指标可解释 |
| CUDA 不可用直接失败 | ModelArts/云上避免静默掉 CPU |
| **端点验证** | 每台发动机只评最后窗口；窗口数 84478 → 可用端点约 **690**（长度不足 30 的机被自然排除） |
| `final_model` 回载 best | 早停前最后一轮不再冒充最佳 |

### 3.3 v1 正式训练（Bitahub RTX 4090）— 可用基线

环境：

- PyTorch 2.11 + CUDA 12.8  
- GPU：NVIDIA GeForce RTX 4090  
- batch 256，num_workers 4，发动机均衡采样  
- 约 **6–9 秒/epoch**

结果：

```text
Best RMSE (norm):     0.0485
Best RMSE (original): 26.27 cycles
Best epoch:           1
Early stop:           epoch 26
Params:               ~596,097
Max RUL (归一化分母): 542
```

训练动态特征：

- 第 1 轮即取得最佳验证端点 RMSE  
- 之后 Train 持续下降（0.07 → 0.026），Val 在 **0.05–0.065** 徘徊  
- 说明：在当前特征与损失下，**进一步压训练误差未转化为端点泛化**；早停机制正确保住了 epoch 1  

与 v0 对比（同用「反算到 cycles」的口径）：

| | v0（坏标签） | v1（修好后） |
|--|-------------|-------------|
| 端点/有效 Val RMSE | ~170 cycles（不可信） | **26.3 cycles** |
| 特征 | ~23，全局缩放 | 34，工况感知 |
| 评估 | 全窗口 | 端点 |
| 可上线 | 否 | 是 |

---

## 4. 模型结构：刻意保持「中等」，把算力花在数据正确性上

当前生产结构（`SimpleLSTM`）：

```text
Input (B, 30, 34)
  → BiLSTM (hidden=128, layers=2, dropout=0.3)
  → Last state ∥ Mean pool
  → Linear 512→64→1 + ReLU
  → × max_rul → cycles
```

设计取舍：

- **未**上更重的 LSTM+Transformer 作为主训模型（参数与日志配置曾不一致）  
- 优先保证：标签正确、工况归一化、域特征、均衡采样、端点指标  
- 下一阶段若要进化网络，建议在 **v1 数据管道冻结** 后再换 TCN-GRU-Attention，并做消融  

---

## 5. 推理与产品化进化

### 5.1 离线推理

`infer.py`：加载 `best_model.pt`，对验证端点逐台预测。  
示例（随机 5 台）：MAE 约 **8.7 cycles**（小样本展示，非全量指标）。

### 5.2 在线监测 API（`monitor-v1.0`）

```http
POST /api/v1/monitor/analyze
```

能力矩阵：

| 能力 | 状态 |
|------|------|
| 滚动 `rul_series` + 最新 `rul_predicted` | ✅ |
| `pseudo_attribution`（梯度伪归因 Top5） | ✅ |
| `anomaly_score` / `anomaly_type` | ❌ → `null`（不伪造） |
| `feature_attribution`（正式归因） | ❌ → `null` |
| 必填 `operating_settings` + `dataset` | ✅ 缺则 422 |

契约详见 `API_CONTRACT.md`。  
部署：Bitahub 机内 `0.0.0.0:8000`；跨机经 SSH 隧道 + 前端代理。

---

## 6. 进化原则（可复用）

1. **先契约后模型**：标签/归一化/评估协议错误时，任何「调参」都是噪声。  
2. **指标与竞赛对齐**：联合训练可以，但报告要用端点 RMSE，并保留分子集评估空间。  
3. **不伪造能力**：没有异常检测头就返回 `null`，用 `pseudo_attribution` 明确降级。  
4. **算力匹配任务**：58 万参 BiLSTM + 正确数据，在 4090 上秒级出轮次，足够迭代。  
5. **最佳检查点 ≠ 最后一轮**：本任务最佳出现在第 1 轮，说明要信任早停与 val 端点，而非训练曲线。

---

## 7. 下一阶段进化路线（建议顺序）

| 优先级 | 方向 | 预期收益 |
|--------|------|----------|
| P0 | 按 FD001–004 **分组**报端点 RMSE / NASA Score | 看清多工况短板 |
| P1 | RUL cap（如 125）+ Huber 损失 | 降低健康段回归难度 |
| P2 | Condition-aware TCN-GRU-Attention | 在冻结数据管道上抠精度 |
| P3 | 真正的异常头 / 故障模式分类 | 填满 API 里现为 null 的字段 |
| P4 | 与 Agent 的 Tool/MCP 适配 | 「像调 LLM 一样」调监测 |

---

## 8. 关键产物路径

| 产物 | 路径 |
|------|------|
| 整合原始数据 | `integrated/` |
| 处理后张量 | `processed/` |
| 训练脚本 | `train.py` / `run_bitahub.sh` |
| 最佳权重 | `model/saved/best_model.pt` |
| 元数据 | `model/saved/metadata.json` |
| 推理示例 | `infer.py` |
| 监测 API | `api.py` |
| 调用约定 | `API_CONTRACT.md` |
| 数据集说明 | `integrated/DATASET.md` |

---

## 9. 收束

模型进化不是「网络一层层变深」的故事，而是：

1. **数据从 FD001 扩到全家族**  
2. **标签与评估从错误到标准**  
3. **训练从不可信的 170 cycles 到可用的 26.3 cycles**  
4. **交付从脚本到可跨服务调用的监测事件 API**  

v1 是可靠基线；下一跳应在分组指标和损失/结构消融上继续，而不是重复一次错误标签上的「猛训」。

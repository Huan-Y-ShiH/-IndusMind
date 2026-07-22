# 知识库与混合检索（当前实现）

## 1. 两条腿分工

| 存储 | 内容 | 检索 |
|------|------|------|
| **Dify** | 案例叙述、手册 chunk、文献摘要等文本 | 语义 / 向量（Retrieval API） |
| **本地** `knowledge/` | FMEA CSV/L2、工单 tickets、特征元信息、案例/手册结构化 JSON | 精确匹配 / Jaccard |

理由：FMEA 签名匹配、工单按 `device_id` 查询是结构化场景，进向量库会降精度。

## 2. 目录约定

见 [knowledge/README.md](../knowledge/README.md)。

冷启动建议顺序：`model_meta` → `fmea` → `cases` → `manuals/chunks` → `tickets` →（可选）`sources` 同步 Dify。

## 3. `hybrid_search` 契约

实现：`src/indusmind/rag/hybrid_search.py`。

输入（`DiagnosticQuery`）：

```text
device_id, device_model, anomaly_type,
top_features, symptoms[{feature, direction}],
symptom_text, natural_language
```

输出候选列表元素大致包含：

```text
case_id?, root_cause, mechanism, symptoms, score,
source ∈ {case_library, local_case_library, fmea, manual},
evidence_level?, ...
```

融合顺序（概念上）：Dify 案例语义 → 本地案例 Jaccard → FMEA Jaccard 兜底 → 手册佐证。

## 4. 写入时机

| 阶段 | 本地 | Dify |
|------|------|------|
| 冷启动 / 设备上线 | FMEA、元信息、手册 chunk、种子案例/工单 | sync 案例/手册叙述（`scripts/sync_dify_kb.py`） |
| 每次诊断 | **读** | **读**（ALWAYS_TOP1 弱匹配时额外查 Dify 写解释） |
| 故障闭环后（人工核实） | 追加 case JSON、ticket | 再 sync 该案例叙述 |

## 5. 传感器编号

统一 NASA CMAPSS Saxena Table 2：`s1`…`s21`。  
定义见 `knowledge/model_meta/cmapss-feature-definitions.json`。  
FMEA 匹配必须同时比较 **编号 + 方向**（↑/↓）。

## 6. 环境变量

```text
DIFY_BASE_URL=http://127.0.0.1/v1   # 勿用 localhost（易被系统代理劫持）
DIFY_DATASET_API_KEY=...
DIFY_CASES_DATASET_ID=...
DIFY_MANUALS_DATASET_ID=...
```

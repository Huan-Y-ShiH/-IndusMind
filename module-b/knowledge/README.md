# 知识库冷启动数据

按 [docs/knowledge-rag.md](../docs/knowledge-rag.md) 分层落盘：本地结构化精确匹配 +（可选）叙述文本同步 Dify。

## 目录

| 路径 | 角色 | 格式 | 存放 |
|------|------|------|------|
| `fmea/CMAPSS-Turbofan-fmea.csv` | FMEA 兜底（Jaccard，含方向） | CSV | 仅本地 |
| `fmea/CMAPSS-Turbofan-fmea-l2.json` | L1→L2 子模式展开 | JSON | 仅本地 |
| `cases/*.json` | 历史/种子故障案例 | JSON | 本地；叙述可 sync Dify |
| `manuals/chunks/*.json` | 手册段落 chunk | JSON | 本地；叙述可 sync Dify |
| `model_meta/cmapss-feature-definitions.json` | `s*` → 物理量 | JSON | 仅本地 |
| `tickets/*.json` | 维修工单 | JSON | 仅本地 |
| `sources/fmea_cmapss_rag/` | 原始文献（软链） | PDF/CSV/MD | 可上传 Dify |

## 传感器编号

统一 **NASA CMAPSS Saxena Table 2**：

- `s4` = T50（EGT 代理）
- `s12` = phi（燃油相关）
- `s10` = epr（压比）

别名见 `model_meta/cmapss-feature-definitions.json` → `semantic_alias_for_docs_examples`。

## 征兆签名格式

```text
s4↑;s12↑;s10↓
```

案例侧：

```json
{"feature": "s4", "direction": "high", "magnitude": 0.32}
```

## 建议入库顺序

1. `model_meta` → 特征翻译  
2. `fmea/*.csv` + `*-l2.json` → 兜底与展开  
3. `cases/*.json` → 主检索种子  
4. `manuals/chunks` → 机理佐证  
5. `tickets` → 决策处置  
6. `sources` / sync Dify → 全文语义检索  

## 同步 Dify

```bash
python scripts/sync_dify_kb.py --dry-run
python scripts/sync_dify_kb.py
```

只同步案例/手册叙述；FMEA、工单、元信息不上传。

# 架构（当前实现）

场景：航空发动机 / 燃气轮机运维诊断，传感器编号对齐 NASA CMAPSS Saxena Table 2（`s1`…`s21`）。

## 1. 四层流水线

编排：**CrewAI Flow**（`src/indusmind/flows/diagnostic_flow.py`），确定性状态机。

```text
异常事件 AnomalyEvent
    → monitor / semanticize_event
    → retrieve          # hybrid_search：Dify + 本地案例 + FMEA
    → diagnose_l1       # LLM 重排；失败则 RAG 分数直排
    → confidence_gate
         ├─ high_confidence → refine_l2l3 (Crew) → decide → report
         └─ human_review    → 报告并转人工（默认路径）
```

| 层 | 职责 | 主要代码 |
|----|------|----------|
| 监测 | 接收标准化异常事件（含特征归因） | `schemas/events.py`, `flows/query.py` |
| 诊断 | L1 候选根因；可选 L2/L3 专家细化 | `flows/`, `crews/l2l3_crew.py` |
| 决策 | 工单/处置历史 → 行动建议 | `knowledge/store.py`, `tools/ticket_tools.py` |
| 报告 | Markdown 诊断报告 | `diagnostic_flow._render_report` |

L2/L3 使用 **CrewAI Crew**（压气机/涡轮等角色），不用于核心四层管线。

## 2. LLM

- Qwen（DashScope 兼容）+ DeepSeek 双通道，经 CrewAI/LiteLLM  
- 复杂推理可走 `deepseek-reasoner`，常规重排走 `qwen-plus` / `qwen-turbo`  
- 无 Key 时自动降级为检索分数直排  

## 3. 运行开关

| 环境变量 | 含义 |
|----------|------|
| `DIAGNOSTIC_ALWAYS_TOP1=true` | 始终输出最可能根因 + 逻辑链；跳过低置信人工门禁；本地匹配弱时查 Dify 补解释 |
| `DIAGNOSTIC_ALWAYS_TOP1=false`（默认语义） | Top-1 置信不足 → `human_review` |

本地 `.env` 可按联调需要打开 ALWAYS_TOP1；严肃生产默认应关闭。

## 4. 与外部契约的边界

若存在三模块 API 契约（预测引擎 / Agent / 网关）：

- **本仓库 ≈ Module B（Agent 引擎）**：诊断、知识检索、工作流、方案叙述  
- 对外 HTTP：本地 `:8002` 异步诊断任务（见 [remote-api.md](./remote-api.md)），云端经隧道访问  
- Module A（RUL/异常）输出应映射为本仓库的 `AnomalyEvent`（`s*` 特征归因）  
- 传感器字段若为泵域示例（vibration_x 等），需在网关或适配层 remap 到 CMAPSS `s1`…`s21`  

## 5. 明确不做

- 不用 LangGraph / Hermes Agent 做核心编排  
- 不把 FMEA、工单、特征元信息塞进 Dify 向量库  
- SCADA / 波形工具未接入前返回 `available=false`，不得当证据  

# IndusMind AI 协作约定

项目技术结论以 `.cursor/rules/tech-stack.mdc`、`docs/` 与当前代码为准。

- 核心编排使用 CrewAI Flow；L2/L3 专家协作用 CrewAI Crew，不引入 LangGraph/Hermes。
- Qwen/DeepSeek 走双通道降级；Dify 只存案例/手册叙述文本。
- FMEA、工单、传感器元信息保持本地结构化查询。
- CMAPSS 传感器必须使用 NASA Saxena Table 2 的 `s1..s21` 编号。
- FMEA 匹配必须同时比较传感器编号与异常方向。
- 推断/seed/合成证据不可等同于真实维修案例，不得据此自动下发维修。
- SCADA 和波形工具未接入前返回 `available=false`，不得让 LLM 将占位值当证据。
- 不在 `.env.template`、文档、测试和日志里写真实密钥；真实值只放被忽略的 `.env`。
- 默认低置信度路径生成报告并转人工；仅当显式设置 `DIAGNOSTIC_ALWAYS_TOP1=true` 时才始终出 Top-1 结论（联调/演示）。

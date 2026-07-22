# IndusMind — 工业运维诊断 Agent

基于 Qwen/DeepSeek LLM + RAG 的工业运维诊断工作流（航空发动机/燃气轮机场景，对齐 NASA CMAPSS）。

**本目录（`indusmind_1`）为项目主文件夹。**

技术选型见 [.cursor/rules/tech-stack.mdc](./.cursor/rules/tech-stack.mdc)：
CrewAI Flow 编排四层状态机、CrewAI Crew 做 L2/L3 专家协作、Qwen/DeepSeek 双通道 LLM、
Dify 做语义知识库、FMEA/工单/特征元信息本地结构化存取。协作硬性约定见 [AGENTS.md](./AGENTS.md)。

## 四层诊断流程

1. **监测**：输入标准化异常事件（`AnomalyEvent`，传感器编号 `s1`…`s21`）
2. **诊断**：`hybrid_search` → L1 粗诊断 → L2/L3 Crew 细化
3. **决策**：查工单/维修历史，给出处置方案与紧急度
4. **报告**：生成 Markdown 诊断报告；低置信默认转人工复核

## 目录结构

```text
indusmind_1/
├── .cursor/rules/           # 技术选型记忆规则（供 AI 助手读取）
├── docs/                    # 设计文档与 PPT 文案
├── knowledge/               # RAG 冷启动知识（FMEA / 案例 / 手册 / 工单 / 特征元信息）
├── assets/ppt/              # PPT 原始图与演示文稿
├── IndusMind-PPT-Package/   # 可直接交付的 PPT 资料包（文档 + 图片 + PPT）
├── src/indusmind/           # 主代码包
│   ├── config.py            # 路径与环境变量加载
│   ├── api/                 # FastAPI :8002 异步诊断任务接口
│   ├── llm/                 # Qwen/DeepSeek 双通道封装 + 任务路由 + 降级
│   ├── knowledge/           # 本地结构化知识库加载器
│   ├── rag/                 # Dify Retrieval API + hybrid_search()
│   ├── schemas/             # 事件 / 诊断结果 / API 请求响应模型
│   ├── flows/               # CrewAI Flow：核心四层确定性状态机
│   ├── crews/               # CrewAI Crew：L2/L3 专家协作
│   ├── tools/               # expand_fmea / 工单 / 工况 / 波形 / 二次检索
│   ├── monitoring/          # 监测模型模拟器（联调用）
│   ├── notify/              # Server 酱等通知
│   └── eval/                # Top-1 / Top-3 / MRR / 幻觉率
├── config/paths.yaml        # 知识库文件路径配置
├── scripts/
│   ├── run_agent_api.py     # 启动本地 Agent HTTP 服务（:8002）
│   ├── run_stable_tunnel.sh # frp 隧道相关辅助脚本
│   ├── sync_dify_kb.py      # 案例/手册叙述同步到 Dify
│   ├── run_eval.py          # 回放标注事件，跑评估报告
│   └── run_e2e_check.py     # 端到端联调检查
└── tests/                   # pytest 单测 + 评估回放
```

## 知识库

见 [knowledge/README.md](./knowledge/README.md)。

分两条腿：Dify 存案例/手册叙述文本；FMEA、工单、传感器元信息保持本地精确查询，不上传向量库。

## 设计文档

| 文档 | 内容 |
|------|------|
| [docs/architecture.md](./docs/architecture.md) | 四层诊断 Flow、模块职责 |
| [docs/knowledge-rag.md](./docs/knowledge-rag.md) | 混合 RAG：语义检索 + 本地结构化匹配 |
| [docs/remote-api.md](./docs/remote-api.md) | 云端前端 → 本地 Agent（`:8002`）字段与调用规则 |
| [docs/frontend-handoff.md](./docs/frontend-handoff.md) | 前端联调与结果展示约定 |
| [docs/project-introduction-for-ppt.md](./docs/project-introduction-for-ppt.md) | 项目介绍、答辩文案、PPT 素材大纲 |

文档索引见 [docs/README.md](./docs/README.md)。

## PPT 与演示材料

完整可交付资料包：

[`IndusMind-PPT-Package/`](./IndusMind-PPT-Package/)

- `PPT/`：图片增强版（21 页，推荐）与纯结构化版（16 页）
- `DOCS/`：架构、RAG、远程 API、前端联调、PPT 文案
- `IMAGES/`：架构 / 混合 RAG / 云边部署 / 人工门禁等 PNG + SVG

源文件仍保留在 [`assets/ppt/`](./assets/ppt/)。资料包不含 `.env` 或任何密钥。

## 快速开始

```bash
cd ~/indusmind_1
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 配置 LLM / Dify / API 凭据（无凭据时 LLM 重排会降级为 RAG 分数直排）
cp .env.template .env
#   QWEN_API_KEY=...        DEEPSEEK_API_KEY=...
#   DIFY_DATASET_API_KEY=...
#   DIFY_CASES_DATASET_ID=...  DIFY_MANUALS_DATASET_ID=...
#   DIFY_BASE_URL=http://127.0.0.1/v1
#   API_KEY=...                 # 远程 API 鉴权
#   DIAGNOSTIC_ALWAYS_TOP1=false   # true=联调始终出 Top-1+逻辑链

pytest -q                        # 跑单测 + 冷启动评估回放
python scripts/run_eval.py       # 单独跑评估报告（Top-1/Top-3/MRR/幻觉率）
python scripts/sync_dify_kb.py --dry-run   # 预览 Dify 知识库同步内容
python scripts/run_e2e_check.py  # 监测模型模拟响应 → Dify/LLM → 报告
```

当前限制：SCADA 工况查询和原始波形分析仍是显式不可用的占位工具（`available=false`），
不会作为诊断支持证据。默认低置信会“待人工复核”；
仅当显式设置 `DIAGNOSTIC_ALWAYS_TOP1=true` 时始终输出最可能根因（仅联调/演示）。

## 远程 API（云端前端 → 本地 Agent）

本地 Agent 监听 **`:8002`**，经 frp 映射到阿里云 ECS 固定 HTTP 入口。
契约与示例见 [docs/remote-api.md](./docs/remote-api.md)。

```bash
# .env 设置 API_KEY 后
.venv/bin/python scripts/run_agent_api.py
```

前端调用：`POST /api/v1/diagnose/jobs` 提交 → `GET /api/v1/diagnose/jobs/{job_id}` 轮询。
鉴权 Header：`X-Api-Key`。`GET /health` 无需鉴权。

## 本地跑一次诊断 Flow

```python
import asyncio
from indusmind.flows import run_diagnostic_flow
from indusmind.schemas.events import AnomalyEvent, FeatureAttribution

event = AnomalyEvent(
    event_id="evt-demo-001",
    device_id="engine-CMAPSS-001",
    device_model="CMAPSS-Turbofan",
    timestamp="2026-07-20T14:32:18+08:00",
    model_version="demo",
    anomaly_type="trend_anomaly",
    feature_attribution=[
        FeatureAttribution(feature="s3", contribution=0.31, direction="high"),
        FeatureAttribution(feature="s4", contribution=0.28, direction="high"),
    ],
)
state = asyncio.run(run_diagnostic_flow(event))
print(state.report.markdown if state.report else "转人工复核")
```

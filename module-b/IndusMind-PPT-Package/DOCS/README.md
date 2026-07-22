# IndusMind 设计文档（以当前实现为准）

权威约定：

1. [AGENTS.md](../AGENTS.md) — AI/协作者硬性规则  
2. [.cursor/rules/tech-stack.mdc](../.cursor/rules/tech-stack.mdc) — 技术栈选型  
3. 本目录下文 — 与 `src/indusmind/` 对齐的简要说明  

| 文档 | 内容 |
|------|------|
| [architecture.md](./architecture.md) | 四层诊断 Flow、模块职责、运行模式 |
| [knowledge-rag.md](./knowledge-rag.md) | 本地结构化知识 vs Dify 语义知识 |
| [remote-api.md](./remote-api.md) | 云端前端 → 本地 Agent（:8002）字段与调用规则 |
| [project-introduction-for-ppt.md](./project-introduction-for-ppt.md) | 项目超详细介绍、答辩文案与 25 页 PPT 素材大纲 |

**已废弃并删除**：旧版盘古 / LangGraph / 华为 CSS / LlamaIndex 设计稿。若外部笔记仍引用那些文件名，一律以本文档与代码为准。

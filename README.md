# IndusMind - Agent驱动的智能工业运维全链路平台

> 北科大2026年生产实习 · 人工智能方向 · 三人团队

## 项目简介

给工业设备装上AI大脑——IoT数据入，Agent决策出，从"坏了再修"到"还没坏就知道该修什么"。

## 技术架构

```
module-a (人A): 数据与预测引擎 - LSTM+Transformer RUL预测 + FastAPI :8001
module-b (人B): Agent智能引擎 - 盘古RAG + 多Agent调度 + FastAPI :8002
module-c (人C): 平台与可视化 - React大屏 + API网关 + FastAPI :8003
```

## 快速启动

```bash
# 三模块联调
docker-compose up

# 访问
前端: http://localhost:5173
API网关: http://localhost:8003/docs
```

## 分支策略

- `main` — 受保护，仅PR合并
- `dev-a/*` — 人A开发分支
- `dev-b/*` — 人B开发分支
- `dev-c/*` — 人C开发分支

## 协作规范

见 `docs/IndusMind-完整对话规划书.md` 和 `api-contract.yaml`

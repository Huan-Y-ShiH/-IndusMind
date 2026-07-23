# IndusMind - Agent驱动的智能工业运维全链路平台

> 北科大2026年生产实习 · 人工智能方向 · 三人团队

## 项目简介

给工业设备装上AI大脑——IoT数据入，Agent决策出，从"坏了再修"到"还没坏就知道该修什么"。

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│ module-a (人A): 数据与预测引擎                            │
│   TCN-BiGRU 双头模型 | RUL预测 + 异常检测 + 双IG归因       │
│   部署: Bitahub RTX 4090 · uvicorn :8000                 │
│   线上版本: monitor-v2.0 | 端点RMSE: 26.17 cycles         │
├─────────────────────────────────────────────────────────┤
│ module-b (人B): Agent智能引擎                             │
│   盘古RAG + 多Agent调度 + FastAPI :8002                   │
├─────────────────────────────────────────────────────────┤
│ module-c (人C): 全栈平台与可视化                           │
│   React 18 监控大屏 + FastAPI 网关 :8003 + IoT模拟器        │
│   统一入口: docker-compose 4服务编排                         │
└─────────────────────────────────────────────────────────┘
```

## 预测模型（module-a）部署架构

```
Bitahub GPU 服务器 (RTX 4090)
  │
  ├─ /health ──────────────────────→ {"status":"ok","model_version":"monitor-v2.0"}
  ├─ POST /api/v1/monitor/analyze ─→ {rul_predicted, anomaly_score, feature_attribution, ...}
  │
  │  uvicorn api:app --host 0.0.0.0 --port 8000
  │  加载: model/saved/best_model.pt (schema v2)
  │
  │  ⚠️ 仅监听内网，不可公网直连
  │
  ▼ SSH 隧道 (角色C 维护)
┌─────────────────────────────┐
│ 角色C 前端服务器              │
│                              │
│ ssh -L 18000:localhost:8000  │  ← 加密隧道到 Bitahub
│     user@bitahub-server      │
│                              │
│ frontend_proxy.py :9000      │  ← 反向代理，加 CORS
│     ↓                        │
│ Browser → :9000/api/...      │
└─────────────────────────────┘
```

### 角色C 连接预测模型的方式

1. **建立 SSH 隧道**（一次性）：
   ```bash
   ssh -N -L 127.0.0.1:18000:127.0.0.1:8000 \
       -i ~/.ssh/id_ed25519 -p 42514 root@xj-member.bitahub.com
   ```
   这会把 Bitahub 上的 `localhost:8000` 映射到前端服务器的 `localhost:18000`

2. **启动前端代理**：
   ```bash
   uvicorn frontend_proxy:app --host 0.0.0.0 --port 9000
   ```
   前端代理把来自浏览器的请求转发到 SSH 隧道

3. **前端调用**：
   ```
   POST http://前端服务器:9000/api/v1/monitor/analyze
   → 代理转发 → localhost:18000 → SSH隧道 → Bitahub:8000 → 模型推理
   ```

> 详细 API 契约见 `module-a/API_CONTRACT.md`（v1 历史版）和 `module-a/README.md` 第 9 节（v2 实际行为）。

## v2 预测模型能力

| 能力 | v1 | v2 |
|------|:--:|:--:|
| RUL 预测 | ✅ | ✅ |
| 独立异常分数 | ❌ null | ✅ 工况分位数校准 |
| 异常类型 | ❌ null | ✅ normal / condition_representation_deviation |
| RUL 特征归因 | ❌ null | ✅ Integrated Gradients |
| 异常特征归因 | ❌ | ✅ Integrated Gradients |
| 归因可验证 | ❌ | ✅ completeness delta |
| 模型版本管理 | ✅ | ✅ (v1可回滚) |

详见 `module-a/README.md` — v0→v1→v2 完整进化史。

## module-c 平台能力

| 组件 | 技术栈 | 端口 | 说明 |
|------|--------|------|------|
| API 网关 | FastAPI + httpx + WebSocket | 8003 | 统一入口，透明转发 module-a/b，实时告警推送 |
| 前端大屏 | React 18 + TypeScript + Vite + Antd 5 + ECharts + Zustand | 5173 | Dashboard、设备树、告警中心、RUL仪表盘 |
| IoT 模拟器 | Python 3.11 + requests + PyYAML | — | 200台风机的传感器数据生成，可配故障场景 |

API 路由：
```
/api/v1/predict/*      → Module A (8001)   RUL预测 + 异常检测
/api/v1/diagnose/*     → Module B (8002)   故障诊断
/ws/alerts             → 本地 WebSocket    实时告警推送
/health                → 本地              健康检查
```

## 快速启动

```bash
# 方式一：Docker Compose 一键启动（推荐）
docker-compose up --build
# → 前端 http://localhost:5173 | 网关 http://localhost:8003/docs

# 方式二：分模块启动
# 角色A：启动预测模型（在 Bitahub 上）
cd module-a && bash run_api.sh
# → http://bitahub:8000/health

# 角色B：启动 Agent 引擎
cd module-b && uvicorn src.main:app --port 8002

# 角色C：启动网关 + 前端
cd module-c/backend && uvicorn api.main:app --reload --port 8003 &
cd module-c/frontend && pnpm install && pnpm dev &
cd module-c/iot-simulator && python simulator.py --interval 2 &

# 建立 SSH 隧道（角色C 维护）
ssh -N -L 18000:localhost:8000 user@bitahub &
uvicorn module-a/frontend_proxy:app --port 9000 &
```

## 待完成 (TODO)

- [ ] 搭建 Module A/B 的真实实现后，网关转发无缝切换
- [ ] 前端 ECharts 图表接入真实数据
- [ ] WebSocket 告警与后端 Agent 引擎联动
- [ ] IoT 模拟器添加更多故障场景（齿轮、叶片、发电机）
- [ ] 前端单元测试 + E2E 测试
- [ ] CI/CD pipeline (GitHub Actions)

## 分支策略

- `main` — 受保护，仅PR合并
- `dev-a/*` — 人A开发分支
- `dev-b/*` — 人B开发分支
- `dev-c/*` — 人C开发分支
- `module-b` — 人A部署分支（预测模型线上代码+权重）

## 协作规范

见 `docs/IndusMind-完整对话规划书.md` 和 `module-a/API_CONTRACT.md`

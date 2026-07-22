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
│ module-c (人C): 平台与可视化                               │
│   React大屏 + API网关 + FastAPI :8003                    │
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

## 快速启动

```bash
# 角色A：启动预测模型（在 Bitahub 上）
cd module-a && bash run_api.sh
# → http://bitahub:8000/health

# 角色C：建立隧道 + 代理（在前端服务器上）
ssh -N -L 18000:localhost:8000 user@bitahub &
uvicorn module-a/frontend_proxy:app --port 9000 &

# 访问
前端: http://localhost:5173
API网关: http://localhost:8003/docs
```

## 分支策略

- `main` — 受保护，仅PR合并
- `dev-a/*` — 人A开发分支
- `dev-b/*` — 人B开发分支
- `dev-c/*` — 人C开发分支
- `module-b` — 人A部署分支（预测模型线上代码+权重）

## 协作规范

见 `docs/IndusMind-完整对话规划书.md` 和 `module-a/API_CONTRACT.md`

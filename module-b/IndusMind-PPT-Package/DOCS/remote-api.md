# 云端前端 → 本地 Agent 远程调用

本地 Agent 引擎监听 **`:8002`**，当前经 frp 映射到阿里云 ECS 的固定 HTTP 入口，云端前端异步提交诊断任务并轮询结果。不依赖 Module C 回调。

内核仍是 `run_diagnostic_flow` + `AnomalyEvent`（CMAPSS `s1`…`s21`）。

## 1. 时序

```text
前端 POST /api/v1/diagnose/jobs  →  202 + job_id（<5s）
本地后台跑诊断 Flow
前端 GET  /api/v1/diagnose/jobs/{job_id}  轮询（建议 2–5s，总等待 ≤120s）
status=succeeded 时取 data.result
```

## 2. 统一响应

```json
{ "code": 0, "data": {}, "msg": "success" }
```

| 场景 | HTTP | code |
|------|------|------|
| 成功 | 200 / 202 | 0 |
| 未授权 | 401 | 401 |
| 参数错误 | 400 | 400 |
| 任务不存在 | 404 | 404 |
| 队列忙 | 429 | 429 |
| 服务错误 | 500 | 500 |

鉴权 Header：`X-Api-Key: <与本地 .env 中 API_KEY 一致>`

`GET /health` 无需鉴权（隧道探活）。

CORS：默认 `CORS_ORIGINS=*`，允许浏览器跨域与 `OPTIONS` 预检；请求体字段使用 **snake_case**。

## 3. 请求字段 `POST /api/v1/diagnose/jobs`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event_id` | string | 是 | 幂等键；未失败前重复提交返回原 job |
| `device_id` | string | 是 | |
| `device_model` | string | 否 | 默认 `CMAPSS-Turbofan` |
| `timestamp` | string | 是 | ISO8601 |
| `model_version` | string | 是 | 上游监测/RUL 模型版本 |
| `anomaly_type` | string | 是 | 如 `rul_anomaly` |
| `anomaly_score` | number | 否 | 0~1 |
| `rul_hours` | number | 否 | → 内核 `rul_predicted` |
| `rul_series` | number[] | 否 | |
| `risk_level` | string | 否 | `low/medium/high/critical`，透传 |
| `feature_attribution` | object[] | 条件 | `{feature, contribution, direction}` |
| `pseudo_attribution` | object[] | 条件 | 仅 RUL 时伪归因 |
| `window_start` / `window_end` | string | 否 | |
| `callback_url` | string | 否 | 预留，当前忽略 |

最低可跑：`event_id, device_id, timestamp, model_version, anomaly_type, rul_hours`（建议再带归因或 `rul_series`）。

## 4. 结果字段 `GET /api/v1/diagnose/jobs/{job_id}`

`data.status`：`queued` | `running` | `succeeded` | `failed`  
`data.progress`：queued=0，running=50，终态=100  

`succeeded` 时 `data.result` 含：

- 透传：`event_id/device_id/rul_hours/risk_level/anomaly_*`
- `diagnosis`：`root_cause/l1/l2/l3/confidence/need_human_review/logic_path/mechanism/evidence`
- `solution`：`urgency/action_plan/matched_tickets`
- `report_markdown`、`rag_hit_count`

## 5. 调用规则（给前端）

1. 当前 Base URL = ECS 固定 HTTP 入口，路径前缀 `/api/v1`；HTTPS 页面应由前端后端同源转发
2. 每个业务请求带 `X-Api-Key`
3. 提交必须快速返回；用轮询取结果，勿把 LLM 诊断做成同步长连接
4. 同一 `event_id` 幂等
5. 本地活跃任务过多返回 `429 busy`（默认最多 3 个 queued+running）
6. 传感器须为 CMAPSS `s*`；泵域字段请在云端 remap 后再提交
7. `NOTIFY_ENABLED=true` 时诊断结束仍旁路推 Server酱，与本 API 独立

## 6. 本地启动

```bash
# .env 中设置 API_KEY、AGENT_PORT=8002
.venv/bin/python scripts/run_agent_api.py
```

## 7. 固定 frp 隧道

- ECS：`frps 0.70.0` 由 systemd 守护，TLS 控制端口 `443`
- 本地：`frpc 0.70.0` 由 launchd 守护，把 `127.0.0.1:8002` 映射到 ECS `80`
- 固定 Base URL：`http://123.56.100.219`
- 本地恢复/检查：`./scripts/run_stable_tunnel.sh`

frp Token 存于本地受限配置和 ECS `/etc/frp/frps.toml`，不得写入仓库。

## 8. curl 示例

```bash
export BASE=http://123.56.100.219
export KEY='<由 Agent 侧私发>'

curl -sS -X POST "$BASE/api/v1/diagnose/jobs" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d '{
    "event_id": "evt-demo-001",
    "device_id": "engine-CMAPSS-001",
    "device_model": "CMAPSS-Turbofan",
    "timestamp": "2026-07-21T03:00:00+00:00",
    "model_version": "rul-v1",
    "anomaly_type": "rul_anomaly",
    "anomaly_score": 0.91,
    "rul_hours": 82,
    "rul_series": [100, 96, 91, 85, 78, 70],
    "risk_level": "high",
    "feature_attribution": [
      {"feature": "s3", "contribution": 0.35, "direction": "high"},
      {"feature": "s4", "contribution": 0.30, "direction": "high"},
      {"feature": "s12", "contribution": 0.22, "direction": "high"}
    ]
  }'

# 用返回的 job_id 轮询
curl -sS "$BASE/api/v1/diagnose/jobs/job_xxxx" -H "X-Api-Key: $KEY"
```

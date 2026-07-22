# IndusMind Agent — 前端联调包（直接转发即可）

> 本地 Agent 通过 frp 映射到阿里云 ECS 固定入口。  
> macOS launchd 守护 Agent/frpc，ECS systemd 守护 frps；电脑关机或休眠期间服务仍不可用。

---

## 联调参数

| 项 | 值 |
|----|-----|
| **Base URL** | `http://123.56.100.219` |
| **鉴权 Header** | `X-Api-Key: <由 Agent 侧私发>` |
| **探活** | `GET {Base URL}/health`（可不带 Key） |
| **提交诊断** | `POST {Base URL}/api/v1/diagnose/jobs` |
| **轮询结果** | `GET {Base URL}/api/v1/diagnose/jobs/{job_id}` |

统一响应：`{ "code": 0, "data": {...}, "msg": "success" }`

已开启 CORS（允许浏览器跨域 + `OPTIONS` 预检；请求头可带 `X-Api-Key`）。字段请用 **snake_case**（如 `event_id`、`rul_hours`），不要用 camelCase。

当前固定入口为 HTTP。若前端页面本身使用 HTTPS，请由前端服务器后端调用本接口并同源转发；浏览器会拦截 HTTPS 页面直接请求 HTTP 的混合内容。

---

## 调用方式（异步）

1. `POST /api/v1/diagnose/jobs` → 立即 `202`，拿到 `data.job_id`
2. 每 **2–5 秒** `GET /api/v1/diagnose/jobs/{job_id}`
3. 直到 `data.status` 为 `succeeded` 或 `failed`（建议总等待 ≤120s）
4. 成功时读 `data.result`

同一 `event_id` 未失败前重复提交会幂等返回原 `job_id`。  
队列忙时返回 HTTP `429`，`msg=busy`。

---

## 请求示例

```http
POST /api/v1/diagnose/jobs
Content-Type: application/json
X-Api-Key: <由 Agent 侧私发>
```

```json
{
  "event_id": "evt-frontend-001",
  "device_id": "engine-CMAPSS-001",
  "device_model": "CMAPSS-Turbofan",
  "timestamp": "2026-07-21T06:30:00+00:00",
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
}
```

**最低可跑字段**：`event_id, device_id, timestamp, model_version, anomaly_type, rul_hours`  
传感器编号用 NASA CMAPSS **`s1`…`s21`**（不要传 `vibration_x` 等泵域字段）。

提交成功示例：

```json
{
  "code": 0,
  "data": {
    "job_id": "job_xxxx",
    "event_id": "evt-frontend-001",
    "status": "queued",
    "poll_url": "/api/v1/diagnose/jobs/job_xxxx"
  },
  "msg": "accepted"
}
```

---

## 结果字段（status=succeeded 时的 data.result）

| 字段 | 说明 |
|------|------|
| `event_id` / `device_id` / `device_model` | 设备与事件 |
| `rul_hours` / `risk_level` / `anomaly_score` / `anomaly_type` | 入参透传 |
| `diagnosis.root_cause` | 根因结论 |
| `diagnosis.l1` / `l2` / `l3` | 分层诊断 |
| `diagnosis.confidence` | 0~1 |
| `diagnosis.need_human_review` | 是否需人工 |
| `diagnosis.logic_path` | 推理步骤数组 |
| `diagnosis.mechanism` / `evidence` | 机理与证据 |
| `solution.urgency` | `immediate` / `planned_within_7d` / `monitor` |
| `solution.action_plan` | 处置步骤 |
| `solution.matched_tickets` | 关联工单 ID |
| `report_markdown` | 完整 Markdown 报告 |
| `rag_hit_count` | 检索命中数 |

轮询 `data` 骨架：`job_id, event_id, status, progress, created_at, updated_at, error, result`  
`progress`：queued=0，running=50，终态=100。

---

## curl 自测

```bash
export BASE=http://123.56.100.219
export KEY='<由 Agent 侧私发>'

curl -sS "$BASE/health"

curl -sS -X POST "$BASE/api/v1/diagnose/jobs" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KEY" \
  -d @- <<'EOF'
{
  "event_id": "evt-frontend-001",
  "device_id": "engine-CMAPSS-001",
  "timestamp": "2026-07-21T06:30:00+00:00",
  "model_version": "rul-v1",
  "anomaly_type": "rul_anomaly",
  "rul_hours": 82,
  "risk_level": "high",
  "feature_attribution": [
    {"feature": "s3", "contribution": 0.35, "direction": "high"},
    {"feature": "s4", "contribution": 0.30, "direction": "high"}
  ]
}
EOF

# 把返回的 job_id 填入下一行
curl -sS "$BASE/api/v1/diagnose/jobs/JOB_ID" -H "X-Api-Key: $KEY"
```

---

## 错误码

| HTTP | 含义 |
|------|------|
| 401 | Key 错误或缺失 |
| 400 | 请求体校验失败 |
| 404 | job 不存在 |
| 429 | 本地忙（busy） |
| 500 | 服务端错误 |

有问题联系 Agent 侧同学；完整技术说明也可看仓库 `docs/remote-api.md`。

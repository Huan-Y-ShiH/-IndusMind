# IndusMind 监测 API 调用约定（给前端 / Agent / 后端）

版本：`monitor-v1.0`  
当前实现：只做 **RUL 推理 + pseudo 归因**，不做独立异常检测。

---

## 1. 服务地址

| 环境 | Base URL | 说明 |
|------|----------|------|
| Bitahub 本机 | `http://127.0.0.1:8000` | 模型服务器内部 |
| 前端另一台机 | `http://前端服务器:9000`（或 Nginx 同源 `/api`） | 需 SSH 隧道 + 反向代理，**不能直连 Bitahub:8000** |

健康检查：

```http
GET {BASE_URL}/health
```

成功示例：

```json
{
  "status": "ok",
  "model_version": "monitor-v1.0",
  "device": "cuda"
}
```

交互文档（若可访问）：

```text
{BASE_URL}/docs
```

---

## 2. 主接口

```http
POST {BASE_URL}/api/v1/monitor/analyze
Content-Type: application/json
```

- 超时建议：30–60 秒  
- CORS：已允许跨域（默认 `*`）；生产仍建议同源代理  
- 请求体 **禁止未知字段**（`extra=forbid`），多传字段会 422  

---

## 3. 请求体字段

### 3.1 顶层

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `device_id` | string | 是 | 1–128 字符 | 设备唯一 ID，原样回传 |
| `device_model` | string | 是 | 1–128 字符 | 设备型号，建议固定 `CMAPSS-Turbofan` |
| `sensor_data` | array | 是 | 长度 **30–2048** | 传感器时间序列；**推荐 128** |
| `operating_settings` | object | **是** | 见下表 | 三个工况设置；缺省会 422，**不会猜测** |
| `dataset` | string | **是** | 枚举见下 | 数据域来源；缺省会 422，**不会猜测** |
| `raw_data_ref` | string \| null | 否 | — | 原始数据引用；不传则响应为 `null` |

`dataset` 合法值（大小写必须一致）：

```text
FD001 | FD002 | FD003 | FD004 | PHM08
```

含义简述：

| 值 | 工况 | 故障模式 |
|----|------|----------|
| `FD001` | 1 | 1（HPC） |
| `FD002` | 6 | 1（HPC） |
| `FD003` | 1 | 2（HPC+Fan） |
| `FD004` | 6 | 2（HPC+Fan） |
| `PHM08` | 竞赛增广域 | 与 CMAPSS 同格式 |

### 3.2 `operating_settings`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `op1` | number | 是 | 工况设置 1（对应 CMAPSS `op_setting_1`） |
| `op2` | number | 是 | 工况设置 2 |
| `op3` | number | 是 | 工况设置 3 |

示例（单工况 FD001 常见）：

```json
"operating_settings": { "op1": 0.0, "op2": 0.0, "op3": 100.0 }
```

### 3.3 `sensor_data[]` 每一点

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timestamp` | string (ISO-8601) | 是 | 如 `2026-07-21T09:30:00Z`；服务端会按时间升序排序 |
| `s1` … `s21` | number | 是 | 21 路传感器原始读数（未归一化） |

传感器字段必须齐全，一个都不能少：

```text
s1, s2, s3, s4, s5, s6, s7, s8, s9, s10,
s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21
```

对应 CMAPSS 常用含义（便于展示，不影响调用）：

| 字段 | 含义（简） |
|------|------------|
| s1 | 风扇入口温度 |
| s2 | LPC 出口温度 |
| s3 | HPC 出口温度 |
| s4 | LPT 出口温度 |
| s5 | 风扇入口压力 |
| s6 | 旁通管道压力 |
| s7 | HPC 出口压力 |
| s8 | 物理风扇转速 |
| s9 | 物理核心转速 |
| s10 | 发动机压比 |
| s11 | HPC 出口静压 |
| s12 | 燃油流量比 |
| s13 | 校正风扇转速 |
| s14 | 校正核心转速 |
| s15 | 旁通比 |
| s16 | 燃烧室燃空比（训练时可能被当常量丢弃，但仍需传入） |
| s17 | 引气焓 |
| s18 | 需求风扇转速 |
| s19 | 需求校正风扇转速 |
| s20 | HPT 冷却气流 |
| s21 | LPT 冷却气流 |

### 3.4 窗口规则（调用方必须遵守）

| 规则 | 值 |
|------|----|
| 最少点数 | **30**（模型窗口长度） |
| 推荐点数 | **128** |
| 最多点数 | **2048** |
| 排序 | 建议按时间升序；服务端也会再排一次 |
| 滚动推理 | 每连续 30 点出一个 RUL → 组成 `rul_series` |
| `rul_series` 长度 | `len(sensor_data) - 29` |
| `rul_predicted` | `rul_series` 最后一项（最新时刻） |

---

## 4. 完整请求示例

```json
{
  "device_id": "engine-001",
  "device_model": "CMAPSS-Turbofan",
  "dataset": "FD001",
  "operating_settings": {
    "op1": 0.0,
    "op2": 0.0,
    "op3": 100.0
  },
  "sensor_data": [
    {
      "timestamp": "2026-07-21T09:30:00Z",
      "s1": 518.67,
      "s2": 642.15,
      "s3": 1589.7,
      "s4": 1400.6,
      "s5": 14.62,
      "s6": 21.61,
      "s7": 553.9,
      "s8": 2388.1,
      "s9": 9046.2,
      "s10": 1.3,
      "s11": 47.4,
      "s12": 521.6,
      "s13": 2388.0,
      "s14": 8138.6,
      "s15": 8.42,
      "s16": 0.03,
      "s17": 392,
      "s18": 2388,
      "s19": 100,
      "s20": 39.0,
      "s21": 23.4
    }
  ],
  "raw_data_ref": null
}
```

> 实际上线时 `sensor_data` 至少 30 条；上面只展示一条结构。

---

## 5. 成功响应

HTTP **200**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "event_id": "evt-20260721093000-ab12cd34",
    "device_id": "engine-001",
    "device_model": "CMAPSS-Turbofan",
    "timestamp": "2026-07-21T09:59:00Z",
    "model_version": "monitor-v1.0",
    "anomaly_score": null,
    "anomaly_type": null,
    "rul_predicted": 82.0,
    "rul_series": [100.0, 96.0, 91.0, 85.0, 82.0],
    "feature_attribution": null,
    "pseudo_attribution": [
      {
        "feature": "s3",
        "direction": "high",
        "contribution": 0.35
      }
    ],
    "raw_data_ref": null
  }
}
```

### 5.1 外壳字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | `0` 表示业务成功 |
| `msg` | string | 如 `success` |
| `data` | object | 监测事件 |

### 5.2 `data` 字段

| 字段 | 类型 | 当前是否有值 | 说明 |
|------|------|--------------|------|
| `event_id` | string | 有 | 事件 ID，格式 `evt-{UTC时间}-{8位hex}` |
| `device_id` | string | 有 | 回传请求中的设备 ID |
| `device_model` | string | 有 | 回传请求中的型号 |
| `timestamp` | string | 有 | **最后一条** `sensor_data.timestamp` |
| `model_version` | string | 有 | 当前 `monitor-v1.0` |
| `anomaly_score` | number \| null | **固定 null** | 无独立异常模型，不伪造 |
| `anomaly_type` | string \| null | **固定 null** | 无独立异常模型，不伪造 |
| `rul_predicted` | number | 有 | 最新 RUL，单位 **cycles**，`>= 0`，保留 2 位小数 |
| `rul_series` | number[] | 有 | 滚动 RUL 序列，单位 cycles，时间从旧到新 |
| `feature_attribution` | array \| null | **固定 null** | 无正式特征归因模型 |
| `pseudo_attribution` | array \| null | 通常有 | 梯度伪归因，最多 5 项；极端情况可能 `[]` |
| `raw_data_ref` | string \| null | 透传 | 请求没传则为 `null` |

### 5.3 `pseudo_attribution[]`

| 字段 | 类型 | 取值 | 说明 |
|------|------|------|------|
| `feature` | string | `s1`…`s21` | 传感器名 |
| `direction` | string | `high` / `low` / `stable` | 相对工况归一化后的偏高/偏低/平稳 |
| `contribution` | number | 0–1 | 相对贡献，同批 Top5 之和约为 1 |

前端展示建议：

- 主数字：`rul_predicted`
- 趋势图：`rul_series`
- 解释卡片：读 `pseudo_attribution`，**不要**读 `feature_attribution`
- 告警：当前没有 `anomaly_score`，可用业务规则（如 `rul_predicted < 阈值`）自行做

---

## 6. 错误响应

### 6.1 缺少必填工况 / 数据集

HTTP **422**

```json
{
  "detail": "This RUL model requires 'operating_settings' and 'dataset'. They are not inferable from sensor_data and will not be fabricated."
}
```

### 6.2 字段校验失败（点数不足、缺传感器、非法 dataset、多未知字段等）

HTTP **422**（FastAPI / Pydantic 标准结构）

```json
{
  "detail": [
    {
      "type": "...",
      "loc": ["body", "sensor_data"],
      "msg": "...",
      "input": "..."
    }
  ]
}
```

常见触发：

| 情况 | 结果 |
|------|------|
| `sensor_data.length < 30` | 422 |
| `sensor_data.length > 2048` | 422 |
| 缺 `s1`…`s21` 任一项 | 422 |
| `dataset` 不在枚举内 | 422 |
| 多传未定义字段 | 422 |
| 缺 `operating_settings` / `dataset` | 422（业务错误文案） |

### 6.3 服务异常

HTTP **5xx**  
前端应提示“监测服务暂不可用”，并支持重试。

---

## 7. TypeScript 类型（可直接用）

```ts
export type DatasetId = "FD001" | "FD002" | "FD003" | "FD004" | "PHM08";

export interface SensorPoint {
  timestamp: string; // ISO-8601
  s1: number; s2: number; s3: number; s4: number; s5: number;
  s6: number; s7: number; s8: number; s9: number; s10: number;
  s11: number; s12: number; s13: number; s14: number; s15: number;
  s16: number; s17: number; s18: number; s19: number; s20: number;
  s21: number;
}

export interface AnalyzeRequest {
  device_id: string;
  device_model: string;
  sensor_data: SensorPoint[]; // 30..2048, recommend 128
  operating_settings: { op1: number; op2: number; op3: number };
  dataset: DatasetId;
  raw_data_ref?: string | null;
}

export interface Attribution {
  feature: string;          // "s3"
  direction: "high" | "low" | "stable";
  contribution: number;     // 0..1
}

export interface MonitorEvent {
  event_id: string;
  device_id: string;
  device_model: string;
  timestamp: string;
  model_version: string;
  anomaly_score: number | null;          // always null for now
  anomaly_type: string | null;           // always null for now
  rul_predicted: number;                 // cycles
  rul_series: number[];                  // cycles, oldest -> newest
  feature_attribution: Attribution[] | null; // always null for now
  pseudo_attribution: Attribution[] | null;
  raw_data_ref: string | null;
}

export interface AnalyzeResponse {
  code: number; // 0
  msg: string;
  data: MonitorEvent;
}
```

---

## 8. 前端调用示例

```ts
async function analyzeEngine(payload: AnalyzeRequest): Promise<MonitorEvent> {
  const res = await fetch(`${import.meta.env.VITE_MONITOR_API}/api/v1/monitor/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(`monitor failed: ${res.status} ${JSON.stringify(err)}`);
  }

  const body: AnalyzeResponse = await res.json();
  if (body.code !== 0) throw new Error(body.msg);
  return body.data;
}
```

环境变量建议：

```text
VITE_MONITOR_API=http://你的前端服务器代理地址
# 或同源：VITE_MONITOR_API=
```

---

## 9. 给 Agent / 后端的硬约束（勿违反）

1. **不要**把该接口当成 DeepSeek 式 chat completion。  
2. **不要**伪造 `anomaly_score` / `anomaly_type` / `feature_attribution`。  
3. **不要**在缺少 `operating_settings` 或 `dataset` 时自行脑补。  
4. 解释信息只看 `pseudo_attribution`。  
5. RUL 单位是 **cycles**，不是小时。  
6. `sensor_data` 少于 30 条不要发。  
7. 跨机访问必须走前端服务器代理/隧道，不要假设公网 `Bitahub:8000` 可达。

---

## 10. 当前模型能力边界

| 能力 | 状态 |
|------|------|
| 滚动 RUL 预测 | ✅ |
| 最新 RUL | ✅ |
| 伪特征归因 | ✅（Top5） |
| 独立异常分数 | ❌ → `null` |
| 异常类型分类 | ❌ → `null` |
| 正式 feature_attribution | ❌ → `null` |

训练侧参考指标（端点验证）：最佳 RMSE ≈ **26.3 cycles**（归一化 0.0485）。  
推理结果会有误差，前端展示建议带不确定性提示。

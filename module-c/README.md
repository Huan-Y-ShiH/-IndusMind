# Module C — 队员C 开发笔记

> **角色：全栈平台与可视化工程师**
> **职责：API网关、WebSocket实时推送、React监控大屏、IoT数据模拟器、Docker Compose 编排**

---

## 🏗️ 项目结构

```
module-c/
├── docker-compose.yml          # 4服务编排: module-a/b/backend/frontend
├── docker-compose.prod.yml     # 生产环境编排
├── backend/                    # FastAPI 网关 (端口 8003)
│   ├── api/
│   │   ├── main.py             # FastAPI app + CORS + 生命周期
│   │   ├── config.py           # 环境变量: MONITOR_URL / API_TOKEN / DEV_MODE
│   │   ├── routers/
│   │   │   ├── gateway.py      # 透明转发 /api/v1/monitor/* → Module A
│   │   │   └── ws.py           # WebSocket /ws/alerts 实时告警推送
│   │   ├── middleware/
│   │   │   └── auth.py         # Bearer Token 鉴权（可配置开关）
│   │   └── services/
│   │       ├── proxy.py        # httpx 异步代理 + 路由表
│   │       └── ws_manager.py   # WebSocket 连接池管理
│   ├── Dockerfile
│   ├── pyproject.toml          # Poetry 依赖管理
│   └── tests/
│       └── test_gateway.py     # 基础冒烟测试
├── frontend/                   # React 18 + Vite (端口 5173)
│   ├── src/
│   │   ├── pages/              # Dashboard, DeviceDetail, AlertCenter, Settings
│   │   ├── components/         # Layout, RealTimeChart, RULGauge, DeviceTree,
│   │   │                       # AlertModal, AgentFlow, dashboard/(子组件)
│   │   ├── services/           # api.ts (axios), websocket.ts, mock.ts,
│   │   │                       # sensorSimulator.ts, alertDetailBuilder.ts
│   │   ├── stores/             # useDeviceStore.ts (Zustand)
│   │   ├── constants/          # devices.ts 设备清单
│   │   ├── hooks/              # useDiagnosisFlow.ts
│   │   ├── types/              # device.ts 类型定义
│   │   └── utils/              # riskLevel.ts 风险等级工具
│   ├── Dockerfile              # Nginx 生产镜像
│   ├── nginx.conf              # Nginx 反向代理配置
│   └── vite.config.ts
└── iot-simulator/              # 数据模拟器
    ├── simulator.py            # 21台风机传感器数据生成 + 异常注入
    └── config.yaml             # 设备配置（4个风场: 东海/西山/南岭/北原）
```

## 🔧 技术栈

| 层 | 技术 |
|----|------|
| 网关 | FastAPI + httpx（异步代理）+ WebSocket |
| 前端 | React 18 + TypeScript + Vite + Antd 5 + ECharts + Tailwind CSS + Zustand |
| 模拟器 | Python 3.11 + requests + PyYAML |
| 编排 | Docker Compose（4 services）|
| 包管理 | 后端 Poetry / 前端 npm |

## 🚀 本地启动

### 1. 启动后端网关
```bash
cd backend
poetry install
uvicorn api.main:app --reload --port 8003
```

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev              # http://localhost:5173
```

### 3. 启动数据模拟器
```bash
cd iot-simulator
pip install -r requirements.txt
python simulator.py --interval 2
```

### 4. 全栈启动 (Docker)
```bash
docker-compose up --build
```

## 📋 API 路由映射

| 请求路径 | 转发目标 | 说明 |
|----------|----------|------|
| `/api/v1/monitor/*` | Module A (MONITOR_URL, 默认 `127.0.0.1:18000`) | RUL预测 + 异常检测 |
| `/ws/alerts` | 本地 WebSocket | 实时告警推送 |
| `/ws/alerts/test` | 本地（DEV_MODE 仅） | 手动推送模拟告警 |
| `/health` | 本地 | 健康检查 |

> **注意**: gateway 目前仅转发 `/api/v1/monitor/*` 到 Module A。Module B 的 diagnose/knowledge/workflow 路由待 Module B 就绪后接入。

## 🎨 暗夜工控设计规范（NASA 控制中心风格）

| Token | 色值 | 用途 |
|-------|------|------|
| `--bg-base` | `#0a0e14` | 最深底色 |
| `--bg-panel` | `#111620` | 面板/卡片 |
| `--bg-header` | `#0d1117` | 顶栏 52px |
| `--bg-sidebar` | `#0c1016` | 侧边栏 210px |
| `--accent-primary` | `#00e676` | 霓虹绿数据主色 |
| `--status-danger` | `#ff1744` | 红色告警脉冲 |
| `--font-mono` | JetBrains Mono / Consolas | 等宽字体 |

## ⚠️ 协作铁律

1. 统一响应: `{"code": 0, "data": {...}, "msg": "success"}`
2. 错误响应: `{"code": 500, "data": null, "msg": "..."}`
3. 命名: Python→snake_case, TS→camelCase, API→kebab-case
4. 跨模块通信**只能通过 HTTP**，禁止 import 其他模块代码
5. 全项目统一 Python 3.11 + FastAPI + Poetry

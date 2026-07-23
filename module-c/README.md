# Module C — 全栈平台与可视化

> **角色：全栈平台与可视化工程师（队员C）**
> **职责：前端监控大屏、FastAPI API网关、WebSocket实时推送、IoT数据模拟器、阿里云ECS部署**
> **当前版本：v2.5（诊断历史功能 + 服务端持久化）**

---

## 项目结构

```
module-c/
├── docker-compose.yml              # 生产编排（仅2容器：frontend + backend）
├── docker-compose.prod.yml         # 生产版 docker-compose（含 history_data volume）
├── README.md
├── backend/                        # FastAPI 网关（端口 8003）
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── api/
│   │   ├── main.py                 # FastAPI app + lifespan（服务注入）
│   │   ├── config.py               # 环境变量配置
│   │   ├── routers/
│   │   │   ├── gateway.py          # 透明转发 Module A（catch-all，需在 history 之后注册）
│   │   │   ├── history.py          # 🆕 诊断历史 CRUD API（JSON 文件持久化）
│   │   │   └── ws.py               # WebSocket 告警推送
│   │   ├── services/
│   │   │   ├── proxy.py            # ProxyService：路由表 + httpx 连接池
│   │   │   └── ws_manager.py       # ConnectionManager：WS 连接管理 + 广播
│   │   └── middleware/
│   │       └── auth.py             # Bearer Token 鉴权
│   └── tests/
├── frontend/                       # React 18 + TypeScript + Vite
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                 # 路由表（/ /device/:id /alerts /history /diagnosis/:rid /settings）
│       ├── types/
│       │   └── device.ts           # DeviceInfo, AlertItem, SensorSnapshot, DiagnosisRecord
│       ├── constants/
│       │   └── devices.ts          # FARMS, MODELS, RUL 阈值
│       ├── utils/
│       │   └── riskLevel.ts        # rulToRiskLevel()
│       ├── hooks/
│       │   └── useDiagnosisFlow.ts # 诊断状态机（Monitor → Diagnose → 轮询 → 自动写入历史）
│       ├── stores/
│       │   ├── useDeviceStore.ts           # Zustand：设备列表 + 告警
│       │   └── useDiagnosisHistoryStore.ts # 🆕 Zustand：诊断历史（API 同步）
│       ├── services/
│       │   ├── api.ts              # axios 封装（monitorApi + diagnoseApi + historyApi）
│       │   ├── websocket.ts        # WebSocket 客户端（常驻 Layout）
│       │   ├── mock.ts             # Mock 数据生成
│       │   ├── sensorSimulator.ts  # CMAPSS 传感器数据模拟
│       │   └── alertDetailBuilder.ts
│       ├── pages/
│       │   ├── Dashboard.tsx               # 主监控大屏
│       │   ├── DeviceDetail.tsx            # 单设备详情 + 诊断 + 历史列表
│       │   ├── AlertCenter.tsx             # 告警中心
│       │   ├── DiagnosisHistory.tsx        # 🆕 全局诊断历史（表格 + 筛选）
│       │   ├── DiagnosisRecordView.tsx     # 🆕 诊断记录详情页（SOLUTION 为主体）
│       │   └── Settings.tsx                # 系统设置
│       └── components/
│           ├── Layout.tsx                  # 顶栏 + 侧栏（含诊断历史菜单项）
│           ├── RealTimeChart.tsx
│           ├── RULGauge.tsx
│           ├── DeviceTree.tsx
│           ├── AlertModal.tsx
│           ├── AgentFlow.tsx
│           └── dashboard/
│               ├── DeviceStatusDonut.tsx
│               ├── FarmHealthCard.tsx
│               └── AlertTimeline.tsx
└── iot-simulator/
    ├── simulator.py
    └── config.yaml
```

## 技术栈

| 层 | 技术 |
|----|------|
| 网关后端 | Python 3.11 + FastAPI + httpx + WebSocket |
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + ECharts + Tailwind CSS + Zustand |
| 模拟器 | Python 3.11 + requests + PyYAML |
| 编排 | Docker Compose（仅 module-c 两容器：frontend + backend）|
| 部署 | 阿里云 ECS (39.96.44.253) Ubuntu 22.04 |

## 设计风格

**暗夜工控（NASA 控制中心风格）**：
- 底色 `#0a0e14`，面板 `#111620`
- 霓虹绿强调色 `#00e676`
- monospace 字体，UTC 时钟
- 顶栏 52px + 绿色底线，侧栏 210px

## 本地启动

```bash
# 后端
cd backend && poetry install && uvicorn api.main:app --reload --port 8003

# 前端
cd frontend && npm install && npm run dev    # http://localhost:5173
```

## 诊断历史功能（v2.5 新增）

诊断完成后自动保存到服务端，跨设备/浏览器可访问：

```
诊断完成 → POST /api/v1/history → JSON 文件持久化（Docker volume）
     ↓
浏览 /history → 全局表格（筛选/排序/删除）
     ↓
点击 VIEW → /diagnosis/:recordId → SOLUTION 为主体页面
```

**持久化**：Docker named volume `history_data` → 容器内 `/app/data/diagnosis_history.json`，不随容器重建丢失。

## API 路由

| 路径 | 处理方式 | 说明 |
|------|----------|------|
| `/api/v1/monitor/*` | Nginx → SSH隧道 → Bitahub A:8000 | Module A RUL 预测 |
| `/diagnose/*` | Nginx → http://123.56.100.219/api/v1/diagnose/* | Module B 诊断 |
| `/api/v1/history` | Nginx → backend:8003 | 🆕 诊断历史 CRUD |
| `/api/*` | Nginx → backend:8003 | 网关通用路由 |
| `/ws/*` | Nginx → backend:8003 | WebSocket |
| `/health` | backend:8003 | 健康检查 |

## 生产部署

```bash
# 构建 + 部署
cd module-c/frontend && npm run build
scp -i ~/.ssh/indusmind_key -r dist/* root@39.96.44.253:/tmp/dist/
ssh root@39.96.44.253 "docker cp /tmp/dist/. module-c-module-c-frontend-1:/usr/share/nginx/html/"

# 后端更新
tar czf backend.tar.gz backend/
scp backend.tar.gz root@39.96.44.253:/tmp/
ssh root@39.96.44.253 "cd /opt/indusmind/module-c && tar xzf /tmp/backend.tar.gz && docker compose up -d --build module-c-backend"
```

## 协作铁律

1. 统一响应格式：`{"code": 0, "data": {...}, "msg": "success"}`
2. Python→snake_case, TypeScript→camelCase, API→kebab-case
3. 跨模块通信只走 HTTP API，禁止 import
4. GitHub: `Huan-Y-ShiH/-IndusMind.git`，main 受保护，仅 PR 合并

# Module C — 队员C 开发笔记

> **角色：全栈平台与可视化工程师**
> **职责：API网关、WebSocket实时推送、React监控大屏、IoT数据模拟器**

---

## 🏗️ 项目结构

```
module-c/
├── docker-compose.yml          # 4服务编排: A/B/backend/frontend
├── backend/                    # FastAPI 网关 (端口 8003)
│   ├── api/
│   │   ├── main.py             # FastAPI app + CORS + 生命周期
│   │   ├── config.py           # 环境变量配置
│   │   ├── routers/
│   │   │   ├── gateway.py      # 透明转发 Module A/B API
│   │   │   └── ws.py           # WebSocket 告警推送
│   │   └── middleware/
│   │       └── auth.py         # Bearer Token 鉴权
│   └── tests/
│       └── test_gateway.py     # 基础冒烟测试
├── frontend/                   # React 18 + Vite (端口 5173)
│   └── src/
│       ├── pages/              # Dashboard, DeviceDetail, AlertCenter, KnowledgeSearch, Settings
│       ├── components/         # Layout, RealTimeChart, RULGauge, DeviceTree, AlertModal, AgentFlow
│       ├── services/           # api.ts (axios), websocket.ts, mock.ts
│       └── stores/             # useDeviceStore.ts (Zustand)
└── iot-simulator/              # 数据模拟器
    ├── simulator.py            # 生成200台风机传感器数据
    └── config.yaml             # 设备配置
```

## 🔧 技术栈

| 层 | 技术 |
|----|------|
| 网关 | FastAPI + httpx (async proxy) + WebSocket |
| 前端 | React 18 + TypeScript + Vite + Antd 5 + ECharts + Tailwind CSS + Zustand |
| 模拟器 | Python 3.11 + requests + PyYAML |
| 编排 | Docker Compose (4 services) |

## 🚀 本地启动

### 1. 启动后端网关
```bash
cd backend
poetry install          # 或 pip install -e .
uvicorn api.main:app --reload --port 8003
```

### 2. 启动前端
```bash
cd frontend
pnpm install
pnpm dev                # http://localhost:5173
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
| `/api/v1/predict/*` | Module A (8001) | RUL预测 + 异常检测 |
| `/api/v1/diagnose/*` | Module B (8002) | 故障诊断 |
| `/api/v1/knowledge/*` | Module B (8002) | 知识库检索 |
| `/api/v1/workflow/*` | Module B (8002) | 完整工作流 |
| `/ws/alerts` | 本地 WebSocket | 实时告警推送 |
| `/health` | 本地 | 健康检查 |

## 🎨 国风科技蓝设计规范

- **Header**: `#111d32` 深蓝, 64px 固定高度
- **Sidebar**: `#0d1a2d` 深蓝黑, 240px 固定宽度
- **Active**: 左侧金色 `#c9a84c` 竖线 + 金色文字
- **Content**: `#f0f2f5` 浅灰蓝, 撑满可滚动
- **Primary**: `#2c6fce` 科技蓝
- **Gold**: `#c9a84c` 鎏金

## ⚠️ 协作铁律

1. ✅ 统一响应: `{"code": 0, "data": {...}, "msg": "success"}`
2. ✅ 错误响应: `{"code": 500, "data": null, "msg": "..."}`
3. ✅ 命名: Python→snake_case, TS→camelCase, API→kebab-case
4. ✅ 跨模块通信**只能通过 HTTP**，禁止 import 其他模块代码
5. ✅ 全项目统一 Python 3.11 + FastAPI + Poetry

## 📝 待完成 (TODO)

- [ ] 搭建 Module A/B 的真实实现后，网关转发无缝切换
- [ ] 前端 ECharts 图表接入真实数据
- [ ] WebSocket 告警与后端 Agent 引擎联动
- [ ] 模拟器添加更多故障场景（齿轮、叶片、发电机）
- [ ] 前端单元测试 + E2E 测试
- [ ] CI/CD pipeline (GitHub Actions)

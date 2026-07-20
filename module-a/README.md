# Module A - Data & Prediction Engine

> **人A（幻吟）负责** | Port: 8001 | Python 3.11 + PyTorch + FastAPI

## 职责

数据怎么进来 → 怎么洗干净 → 模型怎么训练 → 怎么预测

## 目录

```
module-a/
├── data/
│   ├── raw/                      # NASA CMAPSS FD001原始数据
│   ├── processed/                # 预处理特征（.npy）
│   ├── download_data.py          # 下载数据集脚本
│   └── data_preprocessing.py     # 特征工程+序列构建
├── model/
│   ├── lstm_transformer.py       # LSTM+Transformer混合模型
│   ├── train.py                  # 训练脚本
│   ├── evaluate.py               # 评估脚本
│   └── saved/                    # 训练好的模型权重
├── api/
│   ├── main.py                   # FastAPI入口
│   ├── routers/prediction.py     # 预测API（含Mock模式）
│   ├── schemas.py                # Pydantic数据模型
│   └── __init__.py
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## 快速开始

### 1. 安装依赖
```bash
cd module-a
pip install poetry  # 如果还没装
poetry install
```

### 2. 下载数据
```bash
python data/download_data.py
```
如果自动下载失败，手动下载：[NASA CMAPSS Dataset](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/)

### 3. 启动Mock API（并行开发用）
```bash
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

访问 http://localhost:8001/docs 查看Swagger文档。

### 4. 测试Mock API
```bash
curl -X POST http://localhost:8001/api/v1/predict/rul \
  -H "Content-Type: application/json" \
  -d '{"device_id":"WT-001","sensor_data":[{"timestamp":"2026-07-17T10:00:00Z","sensor_2":518.67}]}'
```

## Mock模式

当前 `api/routers/prediction.py` 中 `USE_MOCK=True`，返回模拟预测结果。
这样人B和人C可以并行开发，不需要等真实模型训练完毕。

训练完成后，将 `USE_MOCK` 改为 `False` 即可切换到真实模型。

## API端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/predict/rul` | 剩余寿命预测 |
| POST | `/api/v1/predict/anomaly` | 异常检测 |
| GET | `/api/v1/predict/health` | 健康检查 |

## 对外契约

见根目录 `api-contract.yaml`。改接口前必须先通知B和C。

## 铁律提醒

- ❌ 不要修改 module-b/ 和 module-c/
- ❌ 不要改接口签名
- ✅ 所有API返回 `{"code":0,"data":{...},"msg":"success"}`
- ✅ Python命名用 snake_case

# CMAPSS / 燃气轮机 故障模式 → 传感器征兆映射（RAG）

## 1. 官方故障模式定义（NASA CMAPSS）

| 子集 | 工况 | 故障模式 |
|------|------|----------|
| FD001 | 1 | HPC Degradation |
| FD002 | 6 | HPC Degradation |
| FD003 | 1 | HPC Degradation + Fan Degradation |
| FD004 | 6 | HPC Degradation + Fan Degradation |

## 2. 健康参数注入（Saxena Table 1）

故障通过修改：`*_eff_mod` / `*_flow_mod` / `*_PR_mod`（Fan, LPC, HPC, HPT, LPT）。

## 3. 传感器签名（摘要）

### HPC Degradation（FD001 主故障）

| 传感器 | 异常方向 | 说明 |
|--------|----------|------|
| T30 | ↑ | HPC 出口温度升高 |
| T50 | ↑ | EGT/涡轮出口温度升高 |
| T24 | ↑ | LPC 出口温度升高 |
| phi | ↑ | 燃油流量相对 Ps30 升高 |
| Nc / NRc | ↑ | 闭环保推力时核心机转速升高 |
| P30 | ↓（可能） | 压气机做功能力下降 |
| Ps30 / htBleed / W31 / W32 | ↑（常见） | 热端与冷却相关通道随劣化漂移 |

### Fan Degradation（FD003/FD004 附加）

| 传感器 | 异常方向 | 说明 |
|--------|----------|------|
| Nf / NRf | 异常（常↑） | 风扇转速通道 |
| BPR | ↓ | 旁通比下降 |
| T50 | ↑ | 保推力导致热端温度升高 |

### N-CMAPSS（Chao 2021 Table 2）

按数据集组合注入 Fan/LPC/HPC/HPT/LPT 的 **E（效率）/ F（流量）** 故障；DS02 为 HPT_E + LPT_E + LPT_F。

## 4. 轴承兜底（SKF）

| 故障模式 | 振动 | 温度 | 噪声 |
|----------|------|------|------|
| 润滑失效 | ↑ | ↑ | 异常 |
| 污染 | ↑ | ↑ | 异常 |
| 疲劳剥落 | ↑（特征频率） | ↑ | 异常 |
| 不对中 | ↑（1x/2x） | 可能↑ | 异常 |

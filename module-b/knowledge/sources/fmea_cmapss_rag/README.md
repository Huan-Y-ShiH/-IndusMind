# 航空发动机 / CMAPSS 相关 FMEA & 故障→传感器征兆资料包

下载目录：`~/Downloads/fmea_cmapss_rag/`

## 推荐用于 RAG 的文件优先级

| 优先级 | 文件 | 来源 | 是否含「故障→传感器征兆」 |
|--------|------|------|---------------------------|
| ★★★ | `CMAPSS_fault_sensor_signature_map.csv` | 基于下方 NASA/MDPI/SKF 文献整理的结构化映射 | **是**（故障模式→传感器→升高/降低） |
| ★★★ | `NASA_Saxena_2008_CMAPSS_DamagePropagation.pdf` | NASA / PHM’08（NTRS 20090029214 同文） | **部分**：故障用 flow/efficiency 注入；含全传感器 response surface（Fig.3/4 EGT 等） |
| ★★★ | `MDPI_Chao_2021_N-CMAPSS_Dataset.pdf` | MDPI Data 2021 | **部分**：Table 2 给出 7 类失效对应 Fan/LPC/HPC/HPT/LPT 的 E/F 组合 |
| ★★ | `NASA_TM_2007_CMAPSS_UsersGuide.pdf` | NASA TM-2007-215026 | 传感器/健康参数定义（Table 输入输出） |
| ★★ | `WJAETS_2023_Taurus60_GasTurbine_FMEA.pdf` | 公开 OA 燃气轮机 FMEA | **传统 FMEA**（失效模式/影响/RPN），传感器方向列较弱 |
| ★ | `SKF_Bearing_damage_and_failure_analysis.pdf` | SKF 公开轴承失效手册 | **是**：失效症状 ↔ 振动/温度/噪声（旋转机械兜底） |

## 直链（可重新下载）

- Saxena CMAPSS 损伤传播：https://ntrs.nasa.gov/api/citations/20090029214/downloads/20090029214.pdf  
  镜像：https://c3.ndc.nasa.gov/dashlink/static/media/publication/2008_IEEEPHM_CMAPPSDamagePropagation.pdf
- CMAPSS User’s Guide：https://ntrs.nasa.gov/api/citations/20070034949/downloads/20070034949.pdf
- N-CMAPSS 论文：https://mdpi-res.com/d_attachment/data/data-06-00005/article_deploy/data-06-00005-v2.pdf?version=1611240730
- Taurus 60 FMEA：https://wjaets.com/sites/default/files/fulltext_pdf/WJAETS-2023-0082.pdf
- SKF 轴承失效：本包内 PDF（公开手册镜像）
- CMAPSS 数据集：https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data

## 重要说明（对接 NASA CMAPSS）

公开文献里**几乎没有** CFM56/GE/P&W/RR 原厂 FMEA 全文。  
与 CMAPSS 对齐时，官方做法是：

1. **故障模式** = 旋转部件（Fan/LPC/HPC/HPT/LPT）的 **flow / efficiency** 健康参数劣化  
2. **传感器征兆** = CMAPSS 热力学模型对上述健康参数的 **response surface**（Saxena 文）  
3. 竞赛子集故障：FD001/FD002 = HPC；FD003/FD004 = HPC + Fan  

本包中的 CSV 把上述关系整理成 RAG 可用的「故障→传感器→方向」行；方向字段综合了论文物理机制与公开 FD001 趋势分析，`confidence` 标明可靠度。

## CMAPSS 21 传感器符号（Saxena Table 2）

T2, T24, T30, T50, P2, P15, P30, Nf, Nc, epr, Ps30, phi, NRf, NRc, BPR, farB, htBleed, Nf_dmd, PCNfR_dmd, W31, W32

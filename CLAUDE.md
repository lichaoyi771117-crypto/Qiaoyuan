# 程信霖咨询 · 企业财务报表自动分析系统

## 项目概述

为程信霖咨询开发的一款 Web 端企业财务报表自动分析程序，面向中小企业客户。客户上传财务报表（PDF/Excel/图片），系统自动计算核心财务指标，结合 LLM 生成结构化解读与优化建议报告。

## 技术栈 (实际运行 — 经 2026-06-07 全局审计核实)

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | **Streamlit** | Web 界面 |
| Excel 解析 | **openpyxl + xlrd** | 自研解析器，6 种格式 |
| PDF 解析 | **PyMuPDF** | pdf_parser.py 保留备用 |
| 科目映射 | **自建 AccountingMapper** | 80+ 中→英，difflib 模糊匹配 |
| 质量校验 | **自建 QualityChecker** | 4 项：平衡/负值/逻辑/极值 |
| 指标计算 | **自建 MetricCalculator** (100% 自研) | 7 大类 20+ 指标，EBITDA 三段式，Z-score 中国修正 |
| LLM 报告 | **DeepSeek-chat API** (via openai SDK) | 内嵌 Key |
| 行业基准 | 未接入（通用阈值） | — |

> ⚠️ **审计修正**: `source code/` 下 FinGPT/FinanceToolkit/MinerU/akshare/fin-ratios
> 均未被项目代码 import。所有指标计算为自研，非 FinanceToolkit 底层。
> 实际运行时依赖仅 5 个包: streamlit, pandas, numpy, openai, pymupdf。

## 自研独创性

- **毛利率**: `(营收 - 营业成本 - 税金及附加) / 营收` — 中国准则版
- **速动比率**: `(流动资产 - 存货) / 流动负债` — 中小企无有价证券
- **利息保障倍数**: `(利润总额 + abs(财务费用)) / abs(财务费用)` — 不单独列利息支出
- **EBITDA**: 三段式替代 `EBIT → +DA → +减值 → 兜底`
- **Altman Z**: X5 系数 0.999（中国学者修正），判据 1.81/2.99
- **科目映射**: 80+ 手写条目

## 架构 (实际)

```
[Excel (.xlsx/.xls)]
    ↓ 自研 excel_parser (行次检测 + 期初期末自动识别)
[科目名 + 金额 DataFrame]
    ↓ 自建 AccountingMapper (80+ 中→英 + 模糊匹配)
    ↓ 自建 QualityChecker (4 项 block/warn/ok)
[标准化财务数据]
    ↓ 自建 MetricCalculator (7 大类 20+ 指标)
[指标字典]
    ↓ DeepSeek API → ReportGenerator (5 模块 Prompt)
[专业分析报告] → Streamlit 前端展示 + HTML/CSV 导出
```

## 项目关键决策

1. **科目映射必须自建**：中国《企业会计准则》特有科目（税金及附加、营业外收支等），标准库不覆盖
2. **EBITDA 需替代估算**：中国中小企业财报常不单独列示折旧摊销，采用三段式替代逻辑
3. **Altman Z-score 参数需修正**：采用中国学者修正参数（X5=0.999），配置化可调
4. **LLM 仅解读不推导**：所有数值在计算引擎中确定，LLM 只负责自然语言解读
5. **行业基准需注明偏差**：AKShare 数据为 A 股上市公司均值，与中小企业有结构差异（尚未接入）
6. **MVP 阶段优先支持 Excel**：首批客户中 60%+ 能提供 Excel 格式
7. **全链路自研**：经审计确认，指标计算/科目映射/解析器均独立实现，未依赖 source code/ 开源项目

## 开发路线

- **Phase 1**：基础设施（Streamlit + 科目映射 + 质量校验层）✅ 已完成
- **Phase 2**：核心管线（FinanceToolkit 计算 + AKShare 基准）✅ 已完成
- **Phase 3**：LLM 集成（报告生成 Prompt 设计 + DeepSeek API）✅ 已完成
- **Phase 4**：打磨交付（PDF 导出 + 响应式 + 合规声明）✅ 已完成

## 项目状态（2026-06-07 · 全局审计后更新）

| 指标 | 状态 |
|------|:----:|
| Git 提交数 | **35** |
| 单元测试 | 14 PASS |
| 真实报表验证 | 8/8 BS Balance OK |
| Excel 解析 | ✅ (自研, 6 种真实格式, 全部 sheet 遍历, 千分位逗号兼容) |
| PDF 支持 | ❌ 已取消 (仅 Excel) |
| 科目映射 | ✅ (80+ 科目, 100% 自研) |
| 质量校验 | ✅ (4 项检查, 100% 自研) |
| 指标计算 | ✅ (7 大类 20+ 指标, 100% 自研, EBITDA 替代, Altman Z-score) |
| LLM 报告 | ✅ (DeepSeek-chat, 5 模块报告, 内嵌 Key) |
| 期初/期末列自动识别 | ✅ |
| PDF 报告导出 | ✅ (HTML + CSV) |
| Web 前端 | ✅ (Streamlit, 中文界面, 一键报告, 14 指标卡片) |
| 文件清除/重传 | ✅ (动态 key 重建 file_uploader) |
| 百分比显示 | ✅ (_fmt ×100, NaN→"—") |
| 多 sheet 解析 | ✅ (不限数量, 全部读取) |
| **全部 4 个 Phase** | ✅ **已完成** |
| **全局审计** | ✅ 2026-06-07 (7 个问题修复, 35 commits) |
| **存档文档** | ✅ [项目存档](docs/项目存档_2026-06-04.md) · [快速恢复](docs/快速恢复.md) |

## API 配置

- DeepSeek API Key 内嵌于 `app.py`（MVP 测试用）
- 生产部署时移入环境变量 `DEEPSEEK_API_KEY`

## 协议合规

所有实际依赖均为商用友好协议：
- Streamlit → Apache 2.0 ✅
- pandas → BSD 3-Clause ✅
- openpyxl → MIT ✅
- numpy → BSD 3-Clause ✅
- PyMuPDF → AGPL (仅本地使用) ✅
- openai → Apache 2.0 ✅

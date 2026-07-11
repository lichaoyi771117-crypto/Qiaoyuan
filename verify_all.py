#!/usr/bin/env python3
"""峤远 F-Analyzer 全模块验证脚本"""
import os, sys, ast

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

results = []

# 1. 核心模块导入
modules = [
    ("metric_calculator", "from src.metric_calculator import MetricCalculator"),
    ("excel_parser (multi)", "from src.excel_parser import parse_multiple_files"),
    ("enhanced_metrics", "from src.enhanced_metrics import EnhancedMetricCalculator"),
    ("dupont_analyzer", "from src.dupont_analyzer import DuPontAnalyzer"),
    ("piotroski_scorer", "from src.piotroski_scorer import PiotroskiScorer"),
    ("industry_benchmarks", "from src.industry_benchmarks import get_benchmark, evaluate_metric, get_industry_benchmarks"),
    ("report_generator", "from src.report_generator import ReportGenerator, markdown_to_docx, professional_report_to_docx"),
    ("accounting_mapper", "from src.accounting_mapper import AccountingMapper"),
    ("quality_checker", "from src.quality_checker import QualityChecker"),
]

for name, stmt in modules:
    try:
        exec(stmt)
        results.append((name, "OK"))
    except Exception as e:
        results.append((name, f"FAIL: {e}"))

# 2. API Key
api_key = os.getenv("DEEPSEEK_API_KEY", "")
if api_key and not api_key.startswith("your"):
    results.append(("DEEPSEEK_API_KEY", f"OK ({api_key[:8]}...)"))
else:
    results.append(("DEEPSEEK_API_KEY", "MISSING/PLACEHOLDER"))

# 3. app.py 语法检查
try:
    with open("app.py", "r", encoding="utf-8") as f:
        ast.parse(f.read())
    results.append(("app.py syntax", "OK"))
except Exception as e:
    results.append(("app.py syntax", f"FAIL: {e}"))

# 4. Enhanced metrics 功能测试
try:
    import pandas as pd
    dummy = {
        "流动比率": 1.5, "速动比率": 1.0, "资产负债率": 0.5,
        "净利润": 1000000, "营业收入": 10000000, "资产总额": 20000000,
        "所有者权益": 10000000, "流动资产": 8000000, "流动负债": 5000000,
        "存货": 3000000, "应收账款": 2000000, "应付账款": 1500000,
        "固定资产": 5000000, "负债总额": 10000000, "经营现金流": 2000000,
        "净利润率": 0.1, "ROE": 0.1, "ROA": 0.05,
        "资产周转率": 0.5, "毛利率": 0.3, "营业成本": 7000000,
        "销售费用": 500000, "管理费用": 800000, "财务费用": 200000,
        "所得税": 250000, "利润总额": 1250000, "非流动负债": 5000000,
        "现金及等价物": 3000000, "投资现金流": -1000000, "筹资现金流": -500000,
        "期末股东权益": 10000000, "期初股东权益": 9000000,
        "期末资产总额": 20000000, "期初资产总额": 18000000,
    }
    mapped_df = pd.DataFrame([dummy])
    calc = EnhancedMetricCalculator(mapped_df)
    metrics = calc.compute_by_dimensions(["偿债能力", "盈利能力"], dummy)
    results.append(("enhanced_metrics compute", f"OK ({len(metrics)} metrics)"))
except Exception as e:
    results.append(("enhanced_metrics compute", f"FAIL: {e}"))

# 5. DuPont 功能测试 (使用映射后的英文字段名)
try:
    dp_dummy = pd.DataFrame([{
        "net_profit": 1000000, "revenue": 10000000,
        "total_assets": 20000000, "total_equity": 6666667,
    }])
    dp = DuPontAnalyzer(dp_dummy)
    result = dp.analyze(None)
    has_error = "error" in result
    if has_error:
        results.append(("dupont analyze", f"FAIL: {result['error']}"))
    else:
        results.append(("dupont analyze", f"OK (roe={result.get('roe', 0):.4f})"))
except Exception as e:
    results.append(("dupont analyze", f"FAIL: {e}"))

# 6. Piotroski 功能测试
try:
    ps = PiotroskiScorer(mapped_df)
    score = ps.score(None)
    results.append(("piotroski score", f"OK (score={score['total_score']}/{score['max_score']})"))
except Exception as e:
    results.append(("piotroski score", f"FAIL: {e}"))

# 7. Industry benchmark 功能测试
try:
    bm = get_industry_benchmarks("制造业")
    eval_result = evaluate_metric("流动比率", 1.5, "制造业")
    results.append(("industry benchmark", f"OK (制造业={len(bm)} metrics, 流动比率1.5={eval_result})"))
except Exception as e:
    results.append(("industry benchmark", f"FAIL: {e}"))

# 输出报告
print("=" * 60)
print("峤远 F-Analyzer 全模块验证报告")
print("=" * 60)
all_ok = True
for name, status in results:
    icon = "OK" if status.startswith("OK") else "FAIL"
    if not status.startswith("OK"):
        all_ok = False
    print(f"  [{icon}] {name}: {status}")
print("=" * 60)
passed = sum(1 for _, s in results if s.startswith("OK"))
failed = sum(1 for _, s in results if not s.startswith("OK"))
print(f"总计: {len(results)} 项, 通过: {passed}, 失败: {failed}")
if all_ok:
    print("整体状态: 全部通过 -- 系统就绪")
else:
    print("整体状态: 存在失败项, 需修复")

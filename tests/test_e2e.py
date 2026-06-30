"""端到端测试：完整管线"""
import pandas as pd, tempfile, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from excel_parser import parse_financial_excel
from accounting_mapper import AccountingMapper
from quality_checker import QualityChecker


def test_e2e_pipeline():
    df = pd.DataFrame({"科目名称": ["货币资金","应收账款","存货","流动资产合计","固定资产","资产总计",
                     "短期借款","应付账款","流动负债合计","长期借款","负债合计","实收资本","未分配利润",
                     "所有者权益合计","营业收入","营业成本","税金及附加","销售费用","管理费用","财务费用",
                     "营业外收入","营业外支出","所得税费用","净利润"],
                     "期末余额": [500000,300000,200000,1000000,800000,2000000,300000,200000,500000,
                     300000,800000,800000,400000,1200000,5000000,3000000,50000,200000,300000,100000,
                     100000,50000,250000,1050000]})
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)

    raw = parse_financial_excel(tmp.name)
    # 新解析器对 2 列格式会正确解析
    assert len(raw) >= 12, f"Expected >=12 rows, got {len(raw)}"

    mapped = AccountingMapper().map_to_standard(raw)
    # 验证核心科目存在
    for col in ["cash_and_equivalents","revenue","net_profit","total_assets","total_liabilities","total_equity"]:
        assert col in mapped.columns, f"Missing {col}"

    results = QualityChecker().run_all_checks(mapped)
    blocks = [r for r in results if r.severity == "block"]
    assert len(blocks) == 0, f"Blockers: {[r.detail for r in blocks]}"

    # 验证平衡 (资产 = 负债 + 权益)
    a = mapped["total_assets"].iloc[0]
    l = mapped["total_liabilities"].iloc[0]
    e = mapped["total_equity"].iloc[0]
    assert abs(a - (l + e)) / a < 0.05, f"BS imbalance: {a} != {l}+{e}"

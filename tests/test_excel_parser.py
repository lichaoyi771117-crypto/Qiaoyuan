"""Excel 解析器测试"""
import pandas as pd, tempfile, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from excel_parser import parse_financial_excel


def test_parse_balance_sheet():
    df = pd.DataFrame({"科目名称": ["货币资金","应收账款","存货","流动资产合计","固定资产","资产总计",
                     "短期借款","应付账款","流动负债合计","长期借款","负债合计","实收资本","未分配利润","所有者权益合计"],
                     "期末余额": [500000,300000,200000,1000000,800000,2000000,300000,200000,500000,300000,800000,800000,400000,1200000]})
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    result = parse_financial_excel(tmp.name)
    assert isinstance(result, pd.DataFrame)
    assert len(result) >= 10

def test_parse_profit_statement():
    df = pd.DataFrame({"项目": ["一、营业收入","减：营业成本","税金及附加","销售费用","管理费用","财务费用",
                     "二、营业利润","三、利润总额","四、净利润"],
                     "本期金额": [5000000,3000000,50000,200000,300000,100000,1350000,1400000,1050000]})
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False)
    result = parse_financial_excel(tmp.name)
    assert isinstance(result, pd.DataFrame)
    assert len(result) >= 8
    assert "营业收入" in result["科目名称"].values

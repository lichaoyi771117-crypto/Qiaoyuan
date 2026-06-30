"""科目映射引擎单元测试"""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from accounting_mapper import AccountingMapper


def test_standard_mapping():
    mapper = AccountingMapper()
    df = pd.DataFrame({"科目名称": ["货币资金","营业收入","营业成本","应收账款"], "金额": [1000000,5000000,3000000,800000]})
    result = mapper.map_to_standard(df)
    assert "cash_and_equivalents" in result.columns
    assert "revenue" in result.columns
    assert "cost_of_goods_sold" in result.columns
    assert "accounts_receivable" in result.columns

def test_alias_mapping():
    mapper = AccountingMapper()
    df = pd.DataFrame({"科目名称": ["应收帐款","主营业务收入","应付工资"], "金额": [500000,2000000,300000]})
    result = mapper.map_to_standard(df)
    assert "accounts_receivable" in result.columns
    assert "revenue" in result.columns
    assert "wages_payable" in result.columns

def test_summary_row_detection():
    mapper = AccountingMapper()
    df = pd.DataFrame({"科目名称": ["货币资金","流动资产合计","资产总计"], "金额": [100000,500000,2000000]})
    result = mapper.map_to_standard(df)
    masks = result["_summary_mask"].iloc[0]
    assert sum(masks) >= 2

def test_unique_item_handling():
    mapper = AccountingMapper()
    df = pd.DataFrame({"科目名称": ["税金及附加","营业外收入","其他收益","资产减值损失"], "金额": [50000,30000,20000,10000]})
    result = mapper.map_to_standard(df)
    assert "tax_and_surcharge" in result.columns
    assert "non_operating_income" in result.columns
    assert "other_income" in result.columns
    assert "asset_impairment_loss" in result.columns

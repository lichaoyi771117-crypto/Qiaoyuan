"""质量校验层测试"""
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from quality_checker import QualityChecker, CheckResult


def test_balance_pass():
    df = pd.DataFrame({"total_assets":[2000000],"total_liabilities":[800000],"total_equity":[1200000]})
    r = QualityChecker().check_balance_sheet_balance(df)
    assert r.passed and r.severity == "ok"

def test_balance_fail():
    df = pd.DataFrame({"total_assets":[2000000],"total_liabilities":[500000],"total_equity":[500000]})
    r = QualityChecker().check_balance_sheet_balance(df)
    assert not r.passed and r.severity == "block"

def test_negative_cash():
    df = pd.DataFrame({"cash_and_equivalents":[-50000]})
    r = QualityChecker().check_negative_values(df)
    assert not r.passed and r.severity == "block"

def test_revenue_zero_profit():
    df = pd.DataFrame({"revenue":[0],"net_profit":[100000]})
    r = QualityChecker().check_logic_consistency(df)
    assert not r.passed

def test_negative_receivable_warn():
    df = pd.DataFrame({"accounts_receivable":[-80000]})
    r = QualityChecker().check_negative_values(df)
    assert not r.passed

def test_extreme_leverage():
    df = pd.DataFrame({"total_assets":[100000],"total_liabilities":[120000],"total_equity":[-20000]})
    r = QualityChecker().check_extreme_values(df)
    assert not r.passed

def test_all_checks_healthy_data():
    df = pd.DataFrame({"total_assets":[2000000],"total_liabilities":[800000],"total_equity":[1200000],
                       "cash_and_equivalents":[100000],"revenue":[5000000],"net_profit":[500000],
                       "accounts_receivable":[300000]})
    results = QualityChecker().run_all_checks(df)
    assert len(results) == 4
    assert all(r.passed for r in results)

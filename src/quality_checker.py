"""
财务数据质量校验层

数据质量校验规则：
- block: 阻断级，需用户确认或修正数据
- warn:  警告级，照常计算但报告中标注
- ok:    通过
"""
from dataclasses import dataclass
import pandas as pd


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    severity: str  # "block" | "warn" | "ok"
    detail: str = ""


class QualityChecker:
    BALANCE_TOLERANCE = 0.05
    INTER_STMT_TOLERANCE = 0.10

    def check_balance_sheet_balance(self, df: pd.DataFrame) -> CheckResult:
        """资产负债表平衡：资产 == 负债 + 权益"""
        if not all(c in df.columns for c in ["total_assets", "total_liabilities", "total_equity"]):
            return CheckResult("资产负债表平衡", True, "ok", "缺少资产/负债/权益数据，跳过校验")
        a = df["total_assets"].iloc[0]
        l = df["total_liabilities"].iloc[0]
        e = df["total_equity"].iloc[0]
        diff = abs(a - (l + e))
        ratio = diff / max(a, 1)
        if ratio > self.BALANCE_TOLERANCE:
            return CheckResult("资产负债表平衡", False, "block",
                f"资产总计({a:,.2f}) ≠ 负债({l:,.2f})+权益({e:,.2f}) 差异{ratio:.1%}")
        return CheckResult("资产负债表平衡", True, "ok", f"平衡，差异{ratio:.4%}")

    def check_negative_values(self, df: pd.DataFrame) -> CheckResult:
        """科目异常值检测（货币资金/存货 < 0 阻断，应收/应付 < 0 警告）"""
        blocking, warning = [], []
        for col, label in {"cash_and_equivalents": "货币资金", "inventory": "存货", "fixed_assets": "固定资产"}.items():
            if col in df.columns and (df[col] < 0).any():
                blocking.append(f"{label}为负({df[col].iloc[0]:,.2f})")
        for col, label in {"accounts_receivable": "应收账款", "accounts_payable": "应付账款"}.items():
            if col in df.columns and (df[col] < 0).any():
                warning.append(f"{label}为负({df[col].iloc[0]:,.2f})，可能需要重分类")
        if blocking:
            return CheckResult("科目异常值", False, "block", "; ".join(blocking))
        if warning:
            return CheckResult("科目异常值", False, "warn", "; ".join(warning))
        return CheckResult("科目异常值", True, "ok", "无异常负值")

    def check_logic_consistency(self, df: pd.DataFrame) -> CheckResult:
        """逻辑一致性（营收=0但净利润≠0）"""
        if "revenue" in df.columns and "net_profit" in df.columns:
            if df["revenue"].iloc[0] == 0 and df["net_profit"].iloc[0] != 0:
                return CheckResult("科目逻辑", False, "block", "营收为0但净利润不为0")
        return CheckResult("科目逻辑", True, "ok", "通过")

    def check_extreme_values(self, df: pd.DataFrame) -> CheckResult:
        """极值检测（资产负债率>100%，毛利率>95%）"""
        w = []
        if all(c in df.columns for c in ["total_assets", "total_liabilities"]):
            a, l = df["total_assets"].iloc[0], df["total_liabilities"].iloc[0]
            if a > 0 and l / a > 1.0:
                w.append(f"资产负债率{l/a:.1%} 超100%")
        if all(c in df.columns for c in ["revenue", "cost_of_goods_sold"]):
            r, c = df["revenue"].iloc[0], df["cost_of_goods_sold"].iloc[0]
            if r > 0 and (r - c) / r > 0.95:
                w.append(f"毛利率{(r-c)/r:.1%} 超95%")
        if w:
            return CheckResult("极值合理性", False, "warn", "; ".join(w))
        return CheckResult("极值合理性", True, "ok", "通过")

    def run_all_checks(self, df: pd.DataFrame) -> list[CheckResult]:
        return [self.check_balance_sheet_balance(df), self.check_negative_values(df),
                self.check_logic_consistency(df), self.check_extreme_values(df)]

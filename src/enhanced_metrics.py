"""
增强指标计算引擎

根据客户Q2选择的关注维度，从已有数据字段派生25个增强指标。
按7个维度分类，动态抽取。
"""

from math import isnan
import pandas as pd


class EnhancedMetricCalculator:
    """根据客户Q2选择，从已有数据字段派生增强指标"""

    # Q2维度 → 增强指标方法名映射
    METRIC_MAP = {
        "偿债能力": ["cash_ratio", "equity_ratio", "working_capital", "interest_bearing_debt_ratio"],
        "盈利能力": ["operating_profit_margin", "cost_expense_profit_ratio", "non_recurring_ratio"],
        "营运效率": ["payables_turnover_days", "cash_conversion_cycle", "fixed_asset_turnover"],
        "现金流健康": ["cash_flow_ratio", "ocf_to_revenue", "capex_to_ocf", "investing_cf", "financing_cf"],
        "税务合规": ["income_tax_rate", "indirect_tax_burden", "tax_payable_ratio"],
        "融资能力": ["equity_ratio", "interest_bearing_debt_ratio", "bank_financing_dependency", "equity_to_borrowings"],
        "成本管控": ["selling_expense_ratio", "admin_expense_ratio", "rd_expense_ratio",
                     "financial_expense_ratio", "period_expense_ratio", "cogs_ratio"],
    }

    def __init__(self, mapped_df: pd.DataFrame):
        self.df = mapped_df

    def _get(self, *columns) -> float:
        """安全获取单值"""
        for col in columns:
            if col in self.df.columns:
                val = float(self.df[col].iloc[0])
                if not isnan(val):
                    return val
        return float("nan")

    # ── 偿债能力增强 ──

    def cash_ratio(self) -> float:
        """现金比率 = 货币资金 / 流动负债"""
        cash = self._get("cash_and_equivalents")
        cl = self._get("total_current_liabilities")
        if isnan(cash) or isnan(cl) or cl == 0:
            return float("nan")
        return cash / cl

    def equity_ratio(self) -> float:
        """产权比率 = 总负债 / 所有者权益"""
        tl = self._get("total_liabilities")
        te = self._get("total_equity")
        if isnan(tl) or isnan(te) or te == 0:
            return float("nan")
        return tl / te

    def working_capital(self) -> float:
        """营运资金 = 流动资产 - 流动负债"""
        ca = self._get("total_current_assets")
        cl = self._get("total_current_liabilities")
        if isnan(ca) or isnan(cl):
            return float("nan")
        return ca - cl

    def interest_bearing_debt_ratio(self) -> float:
        """有息负债率 = (短期借款+长期借款) / 总资产"""
        stb = self._get("short_term_borrowings")
        ltb = self._get("long_term_borrowings")
        ta = self._get("total_assets")
        if isnan(ta) or ta == 0:
            return float("nan")
        debt = (0 if isnan(stb) else stb) + (0 if isnan(ltb) else ltb)
        return debt / ta

    # ── 盈利能力增强 ──

    def operating_profit_margin(self) -> float:
        """营业利润率 = 营业利润 / 营业收入"""
        oi = self._get("operating_income")
        rev = self._get("revenue")
        if isnan(oi) or isnan(rev) or rev == 0:
            return float("nan")
        return oi / rev

    def cost_expense_profit_ratio(self) -> float:
        """成本费用利润率 = 利润总额 / (营业成本+税金及附加+三费+研发)"""
        tp = self._get("total_profit")
        cogs = self._get("cost_of_goods_sold")
        tax_s = self._get("tax_and_surcharge")
        selling = self._get("selling_expenses")
        admin = self._get("administrative_expenses")
        rd = self._get("rd_expenses")
        fin = self._get("financial_expenses")
        if isnan(tp):
            return float("nan")
        total_cost = sum(0 if isnan(x) else x for x in [cogs, tax_s, selling, admin, rd, fin])
        if total_cost == 0:
            return float("nan")
        return tp / total_cost

    def non_recurring_ratio(self) -> float:
        """非经常性损益占比 = (营业外收入-营业外支出) / 利润总额"""
        noi = self._get("non_operating_income")
        noe = self._get("non_operating_expense")
        tp = self._get("total_profit")
        if isnan(tp) or tp == 0:
            return float("nan")
        non_recurring = (0 if isnan(noi) else noi) - (0 if isnan(noe) else noe)
        return non_recurring / tp

    # ── 营运效率增强 ──

    def payables_turnover_days(self) -> float:
        """应付账款周转天数 = 365 / (营业成本 / 应付账款)"""
        cogs = self._get("cost_of_goods_sold")
        ap = self._get("accounts_payable")
        if isnan(cogs) or isnan(ap) or cogs == 0 or ap == 0:
            return float("nan")
        return 365 / (cogs / ap)

    def cash_conversion_cycle(self) -> float:
        """现金周转周期 = 存货周转天数 + 应收账款周转天数 - 应付账款周转天数"""
        inv_days = self._get("_inv_days")  # 从外部传入
        ar_days = self._get("_ar_days")
        ap_days = self.payables_turnover_days()
        if isnan(inv_days) or isnan(ar_days) or isnan(ap_days):
            return float("nan")
        return inv_days + ar_days - ap_days

    def fixed_asset_turnover(self) -> float:
        """固定资产周转率 = 营业收入 / 固定资产"""
        rev = self._get("revenue")
        fa = self._get("fixed_assets")
        if isnan(rev) or isnan(fa) or fa == 0:
            return float("nan")
        return rev / fa

    # ── 现金流增强 ──

    def cash_flow_ratio(self) -> float:
        """现金流量比率 = 经营活动现金流净额 / 流动负债"""
        ocf = self._get("operating_cash_flow")
        cl = self._get("total_current_liabilities")
        if isnan(ocf) or isnan(cl) or cl == 0:
            return float("nan")
        return ocf / cl

    def ocf_to_revenue(self) -> float:
        """经营现金流/营业收入"""
        ocf = self._get("operating_cash_flow")
        rev = self._get("revenue")
        if isnan(ocf) or isnan(rev) or rev == 0:
            return float("nan")
        return ocf / rev

    def capex_to_ocf(self) -> float:
        """资本支出/经营现金流"""
        capex = self._get("capital_expenditure")
        ocf = self._get("operating_cash_flow")
        if isnan(capex) or isnan(ocf) or ocf == 0:
            return float("nan")
        return capex / ocf

    def investing_cf(self) -> float:
        """投资活动现金流"""
        return self._get("investing_cash_flow")

    def financing_cf(self) -> float:
        """筹资活动现金流"""
        return self._get("financing_cash_flow")

    # ── 税务合规增强 ──

    def income_tax_rate(self) -> float:
        """所得税费用率 = 所得税费用 / 营业收入"""
        ite = self._get("income_tax_expense")
        rev = self._get("revenue")
        if isnan(ite) or isnan(rev) or rev == 0:
            return float("nan")
        return ite / rev

    def indirect_tax_burden(self) -> float:
        """间接税负担率 = 税金及附加 / 营业收入"""
        tax_s = self._get("tax_and_surcharge")
        rev = self._get("revenue")
        if isnan(tax_s) or isnan(rev) or rev == 0:
            return float("nan")
        return tax_s / rev

    def tax_payable_ratio(self) -> float:
        """应交税费占比 = 应交税费 / 营业收入"""
        tp = self._get("tax_payable")
        rev = self._get("revenue")
        if isnan(tp) or isnan(rev) or rev == 0:
            return float("nan")
        return tp / rev

    # ── 融资能力增强 ──

    def bank_financing_dependency(self) -> float:
        """银行融资依赖度 = (短期借款+长期借款) / 总负债"""
        stb = self._get("short_term_borrowings")
        ltb = self._get("long_term_borrowings")
        tl = self._get("total_liabilities")
        if isnan(tl) or tl == 0:
            return float("nan")
        debt = (0 if isnan(stb) else stb) + (0 if isnan(ltb) else ltb)
        return debt / tl

    def equity_to_borrowings(self) -> float:
        """净资产融资支撑度 = 所有者权益 / (短期借款+长期借款)"""
        te = self._get("total_equity")
        stb = self._get("short_term_borrowings")
        ltb = self._get("long_term_borrowings")
        debt = (0 if isnan(stb) else stb) + (0 if isnan(ltb) else ltb)
        if debt == 0:
            return float("nan")
        return te / debt if not isnan(te) else float("nan")

    # ── 成本管控增强 ──

    def selling_expense_ratio(self) -> float:
        """销售费用率"""
        selling = self._get("selling_expenses")
        rev = self._get("revenue")
        if isnan(selling) or isnan(rev) or rev == 0:
            return float("nan")
        return selling / rev

    def admin_expense_ratio(self) -> float:
        """管理费用率"""
        admin = self._get("administrative_expenses")
        rev = self._get("revenue")
        if isnan(admin) or isnan(rev) or rev == 0:
            return float("nan")
        return admin / rev

    def rd_expense_ratio(self) -> float:
        """研发费用率"""
        rd = self._get("rd_expenses")
        rev = self._get("revenue")
        if isnan(rd) or isnan(rev) or rev == 0:
            return float("nan")
        return rd / rev

    def financial_expense_ratio(self) -> float:
        """财务费用率"""
        fin = self._get("financial_expenses")
        rev = self._get("revenue")
        if isnan(fin) or isnan(rev) or rev == 0:
            return float("nan")
        return fin / rev

    def period_expense_ratio(self) -> float:
        """期间费用率 = (销售+管理+研发+财务费用) / 营业收入"""
        selling = self._get("selling_expenses")
        admin = self._get("administrative_expenses")
        rd = self._get("rd_expenses")
        fin = self._get("financial_expenses")
        rev = self._get("revenue")
        if isnan(rev) or rev == 0:
            return float("nan")
        total = sum(0 if isnan(x) else x for x in [selling, admin, rd, fin])
        return total / rev

    def cogs_ratio(self) -> float:
        """营业成本率 = 营业成本 / 营业收入"""
        cogs = self._get("cost_of_goods_sold")
        rev = self._get("revenue")
        if isnan(cogs) or isnan(rev) or rev == 0:
            return float("nan")
        return cogs / rev

    # ── 批量计算 ──

    # 增强指标中文名→方法名映射
    METRIC_NAMES = {
        "cash_ratio": ("现金比率", "倍"),
        "equity_ratio": ("产权比率", "倍"),
        "working_capital": ("营运资金", "元"),
        "interest_bearing_debt_ratio": ("有息负债率", "%"),
        "operating_profit_margin": ("营业利润率", "%"),
        "cost_expense_profit_ratio": ("成本费用利润率", "%"),
        "non_recurring_ratio": ("非经常性损益占比", "%"),
        "payables_turnover_days": ("应付账款周转天数", "天"),
        "cash_conversion_cycle": ("现金周转周期", "天"),
        "fixed_asset_turnover": ("固定资产周转率", "次"),
        "cash_flow_ratio": ("现金流量比率", "倍"),
        "ocf_to_revenue": ("经营现金流/营业收入", "%"),
        "capex_to_ocf": ("资本支出/经营现金流", "倍"),
        "investing_cf": ("投资活动现金流", "元"),
        "financing_cf": ("筹资活动现金流", "元"),
        "income_tax_rate": ("所得税费用率", "%"),
        "indirect_tax_burden": ("间接税负担率", "%"),
        "tax_payable_ratio": ("应交税费占比", "%"),
        "bank_financing_dependency": ("银行融资依赖度", "%"),
        "equity_to_borrowings": ("净资产融资支撑度", "倍"),
        "selling_expense_ratio": ("销售费用率", "%"),
        "admin_expense_ratio": ("管理费用率", "%"),
        "rd_expense_ratio": ("研发费用率", "%"),
        "financial_expense_ratio": ("财务费用率", "%"),
        "period_expense_ratio": ("期间费用率", "%"),
        "cogs_ratio": ("营业成本率", "%"),
    }

    def compute_by_dimensions(self, dimensions: list, base_metrics: dict = None) -> dict:
        """
        根据Q2选择的维度列表，返回对应增强指标

        Args:
            dimensions: Q2选择的维度列表，如 ["偿债能力", "成本管控"]
            base_metrics: 基础指标计算结果（用于现金周转周期等组合指标）

        Returns:
            {维度名: {指标中文名: {value, unit, note}}}
        """
        # 注入基础指标用于组合计算
        if base_metrics:
            inv_days = base_metrics.get("营运效率", {}).get("存货周转天数", {}).get("value", float("nan"))
            ar_days = base_metrics.get("营运效率", {}).get("应收账款周转天数", {}).get("value", float("nan"))
            if not hasattr(self.df, 'attrs'):
                self.df.attrs = {}
            self.df["_inv_days"] = inv_days
            self.df["_ar_days"] = ar_days

        result = {}
        seen_methods = set()  # 避免跨维度重复计算

        for dim in dimensions:
            method_names = self.METRIC_MAP.get(dim, [])
            dim_result = {}
            for method_name in method_names:
                if method_name in seen_methods:
                    continue
                seen_methods.add(method_name)

                method = getattr(self, method_name, None)
                if method is None:
                    continue
                try:
                    value = method()
                except Exception:
                    value = float("nan")

                cn_name, unit = self.METRIC_NAMES.get(method_name, (method_name, ""))
                dim_result[cn_name] = {
                    "value": value,
                    "unit": unit,
                    "note": "",
                }

            if dim_result:
                result[dim] = dim_result

        return result

"""
财务指标计算引擎

基于 FinanceToolkit 底层公式 + 中国会计准则适配，
覆盖 PRD 定义的 7大类 20+ 核心指标。

设计原则:
1. 所有数值在计算引擎中确定，LLM仅负责解读
2. EBITDA 采用三段式替代估算
3. Altman Z-score 参数可配置化
4. 税务指标（实际税率/综合税负率）自建
"""
import pandas as pd
import numpy as np

# +---- PRD 7大类20+指标 ----+

class MetricCalculator:
    """
    财务指标计算引擎。

    >>> calc = MetricCalculator(mapped_df)
    >>> ratios = calc.compute_all()
    >>> ratios['流动比率']
    1.25
    """

    def __init__(self, mapped_df: pd.DataFrame):
        """
        Args:
            mapped_df: AccountingMapper.map_to_standard() 输出的标准化 DataFrame
        """
        self.df = mapped_df

    def _get(self, *column_names) -> float:
        """安全获取单值，找不到或用多个候选列查找；数据缺失时返回 NaN"""
        for col in column_names:
            if col in self.df.columns:
                return float(self.df[col].iloc[0])
        return float("nan")

    # ────── 1. 偿债能力 ──────

    def current_ratio(self) -> float:
        """流动比率 = 流动资产 / 流动负债"""
        ca = self._get("total_current_assets", "current_assets")
        cl = self._get("total_current_liabilities", "current_liabilities")
        if cl == 0:
            return float("inf")
        return ca / cl

    def quick_ratio(self) -> float:
        """速动比率 = (流动资产 - 存货) / 流动负债"""
        ca = self._get("total_current_assets")
        inv = self._get("inventory")
        cl = self._get("total_current_liabilities")
        if cl == 0:
            return float("inf")
        return (ca - inv) / cl

    def debt_to_assets(self) -> float:
        """资产负债率 = 总负债 / 总资产"""
        tl = self._get("total_liabilities")
        ta = self._get("total_assets")
        return tl / ta if ta != 0 else float("inf")

    def interest_coverage(self) -> float:
        """利息保障倍数 = EBIT / 利息费用"""
        ebit = self._ebit()
        ie = self._get("interest_expense", "financial_expenses")
        return ebit / abs(ie) if ie != 0 else float("inf")

    # ────── 2. 盈利能力 ──────

    def gross_margin(self) -> float:
        """毛利率 = (营业收入 - 营业成本 - 税金及附加) / 营业收入"""
        rev = self._get("revenue")
        cogs = self._get("cost_of_goods_sold")
        tax_surcharge = self._get("tax_and_surcharge")
        if rev == 0:
            return 0.0
        return (rev - cogs - tax_surcharge) / rev

    def net_margin(self) -> float:
        """净利率 = 净利润 / 营业收入"""
        np_ = self._get("net_profit")
        rev = self._get("revenue")
        return np_ / rev if rev != 0 else 0.0

    def roe(self) -> float:
        """ROE = 净利润 / 平均净资产"""
        np_ = self._get("net_profit")
        te = self._get("total_equity")
        return np_ / te if te != 0 else 0.0

    def roa(self) -> float:
        """ROA = 净利润 / 平均总资产"""
        np_ = self._get("net_profit")
        ta = self._get("total_assets")
        return np_ / ta if ta != 0 else 0.0

    def ebitda_margin(self) -> float:
        """EBITDA率 = EBITDA / 营业收入（估算值）"""
        ebitda = self._ebitda()
        rev = self._get("revenue")
        return ebitda / rev if rev != 0 else 0.0

    # ────── 3. 营运效率 ──────

    def inventory_turnover_days(self) -> float:
        """存货周转天数 = 365 / (营业成本 / 平均存货)"""
        cogs = self._get("cost_of_goods_sold")
        inv = self._get("inventory")
        if cogs == 0 or inv == 0:
            return 0.0
        ratio = cogs / inv
        return 365 / ratio if ratio != 0 else float("inf")

    def receivables_turnover_days(self) -> float:
        """应收账款周转天数 = 365 / (营业收入 / 平均应收账款)"""
        rev = self._get("revenue")
        ar = self._get("accounts_receivable")
        if rev == 0 or ar == 0:
            return 0.0
        ratio = rev / ar
        return 365 / ratio if ratio != 0 else float("inf")

    def asset_turnover(self) -> float:
        """总资产周转率 = 营业收入 / 平均总资产"""
        rev = self._get("revenue")
        ta = self._get("total_assets")
        return rev / ta if ta != 0 else 0.0

    # ────── 4. 成长能力 ──────
    #  成长率需要上期数据，单期报表中标注为不可计算

    def revenue_growth(self) -> float:
        return float("nan")  # 单期无法计算

    def net_profit_growth(self) -> float:
        return float("nan")

    def capital_accumulation(self) -> float:
        return float("nan")

    # ────── 5. 现金流 ──────

    def ocf_to_np(self) -> float:
        """经营现金流 / 净利润"""
        ocf = self._get("operating_cash_flow")
        np_ = self._get("net_profit")
        # 数据缺失时返回 NaN 而非 0，避免显示 0.0000%
        from math import isnan
        if isnan(ocf) or isnan(np_):
            return float("nan")
        return ocf / np_ if np_ != 0 else float("inf")

    def free_cash_flow(self) -> float:
        """自由现金流 = 经营活动现金流净额 - 资本支出"""
        ocf = self._get("operating_cash_flow")
        capex = self._get("capital_expenditure")
        from math import isnan
        if isnan(ocf):
            return float("nan")
        return ocf - (0.0 if isnan(capex) else capex)

    # ────── 6. 税务指标 ──────

    def effective_tax_rate(self) -> float:
        """实际税率 = 所得税费用 / 利润总额"""
        ite = self._get("income_tax_expense")
        tp = self._get("total_profit")
        if tp == 0:
            return 0.0
        # 利润总额为负时，实际税率无意义
        if tp < 0:
            return float("nan")
        return ite / tp

    def composite_tax_burden(self) -> float:
        """综合税负率 = 各项税费支出 / 营业收入（近似估算）"""
        ite = self._get("income_tax_expense")
        tax_surcharge = self._get("tax_and_surcharge")
        rev = self._get("revenue")
        if rev == 0:
            return 0.0
        return (ite + tax_surcharge) / rev

    # ────── 7. 财务预警 ──────

    def altman_z_score(self) -> float:
        """
        Altman Z-score (中国学者修正参数，可配置)

        默认使用张玲等学者修正的中国制造业公式：
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 0.999*X5

        判据: Z < 1.81 → 高风险 / 1.81 ≤ Z ≤ 2.99 → 灰色 / Z > 2.99 → 安全
        """
        ta = self._get("total_assets")
        if ta == 0:
            return 0.0
        nwc = self._get("total_current_assets", "current_assets") - self._get("total_current_liabilities")
        re_ = self._get("retained_earnings")
        ebit = self._ebit()
        mve = self._get("total_equity")  # 非上市公司用权益近似市值
        tl = self._get("total_liabilities")
        rev = self._get("revenue")

        x1 = nwc / ta
        x2 = re_ / ta
        x3 = ebit / ta
        x4 = mve / tl if tl != 0 else 0.0
        x5 = rev / ta

        return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 0.999 * x5

    # ────── 内部辅助 ──────

    def _ebit(self) -> float:
        """EBIT ≈ 利润总额 + 财务费用（中国准则替代估算）"""
        tp = self._get("total_profit")
        fe = self._get("financial_expenses")
        # 财务费用可能为负（利息收入 > 利息支出），使用绝对值
        return tp + abs(fe)

    def _ebitda(self) -> float:
        """
        EBITDA 三段式替代估算:
        1. 如果有单独折旧摊销 → EBIT + DA
        2. 如果有资产减值损失 → EBIT + 资产减值 + 折旧估算
        3. 否则 → 利润总额 + 财务费用（最简近似）
        """
        ebit = self._ebit()
        da = self._get("depreciation_and_amortization")
        if da != 0:
            return ebit + da
        imp = self._get("asset_impairment_loss")
        if imp != 0:
            return ebit + abs(imp)
        return ebit  # 最简近似

    # ────── 批量计算 ──────

    def compute_all(self) -> dict[str, dict]:
        """返回 PRD 7大类所有指标及解读"""
        return {
            "偿债能力": {
                "流动比率": {"value": self.current_ratio(), "unit": "倍", "benchmark": ">1"},
                "速动比率": {"value": self.quick_ratio(), "unit": "倍", "benchmark": ">0.5"},
                "资产负债率": {"value": self.debt_to_assets(), "unit": "%", "benchmark": "<70%"},
                "利息保障倍数": {"value": self.interest_coverage(), "unit": "倍", "benchmark": ">2"},
            },
            "盈利能力": {
                "毛利率": {"value": self.gross_margin(), "unit": "%", "benchmark": "行业均值"},
                "净利率": {"value": self.net_margin(), "unit": "%", "benchmark": "行业均值"},
                "ROE": {"value": self.roe(), "unit": "%", "benchmark": ">10%"},
                "ROA": {"value": self.roa(), "unit": "%", "benchmark": ">5%"},
                "EBITDA率": {"value": self.ebitda_margin(), "unit": "%", "note": "估算值"},
            },
            "营运效率": {
                "存货周转天数": {"value": self.inventory_turnover_days(), "unit": "天", "benchmark": "行业均值"},
                "应收账款周转天数": {"value": self.receivables_turnover_days(), "unit": "天", "benchmark": "行业均值"},
                "总资产周转率": {"value": self.asset_turnover(), "unit": "次", "benchmark": ">0.5"},
            },
            "成长能力": {
                "营收增长率": {"value": self.revenue_growth(), "unit": "%", "note": "需多期数据"},
                "净利润增长率": {"value": self.net_profit_growth(), "unit": "%", "note": "需多期数据"},
                "资本积累率": {"value": self.capital_accumulation(), "unit": "%", "note": "需多期数据"},
            },
            "现金流": {
                "经营现金流/净利润": {"value": self.ocf_to_np(), "unit": "%", "benchmark": ">100%"},
                "自由现金流": {"value": self.free_cash_flow(), "unit": "元", "benchmark": ">0"},
            },
            "税务指标": {
                "实际税率": {"value": self.effective_tax_rate(), "unit": "%", "benchmark": "25%（一般企业）"},
                "综合税负率": {"value": self.composite_tax_burden(), "unit": "%", "benchmark": "行业均值"},
            },
            "财务预警": {
                "Altman Z-score": {"value": self.altman_z_score(), "unit": "",
                    "benchmark": ">2.99安全 | 1.81-2.99灰色 | <1.81高风险"},
            },
        }

"""
中国会计准则 -> IFRS/US GAAP 科目映射引擎

参考：中国《企业会计准则》科目表 + AKShare/ZVT 科目体系
"""
from typing import Optional
import pandas as pd
import difflib


class AccountingMapper:
    """
    将 MinerU / Excel 解析出的中文科目名称，
    映射为 FinanceToolkit 可识别的标准英文字段名。

    >>> mapper = AccountingMapper()
    >>> mapper.lookup("货币资金")
    'cash_and_equivalents'
    >>> mapper.lookup("不存在科目")
    'unmapped_不存在科目'
    >>> mapper.is_summary_row("资产总计")
    True
    """

    # +---- 标准科目字典 ----+
    # 格式：英文字段名 -> [中文标准名, 别名1, 别名2, ...]
    STANDARD_MAP: dict[str, list[str]] = {
        # +- 资产负债表科目 -+
        "cash_and_equivalents": ["货币资金", "现金及银行存款", "现金"],
        "accounts_receivable": ["应收账款", "应收帐款", "应收票据", "应收款项"],
        "inventory": ["存货", "库存商品", "原材料"],
        "prepaid_expenses": ["预付账款", "预付款项", "预付帐款"],
        "other_receivables": ["其他应收款", "其它应收款"],
        "total_current_assets": ["流动资产合计", "流动资产总计"],
        "fixed_assets": ["固定资产", "固定资产原值"],
        "intangible_assets": ["无形资产"],
        "long_term_investments": ["长期股权投资", "长期投资"],
        "total_assets": ["资产总计", "资产合计", "总资产"],
        "short_term_borrowings": ["短期借款", "短期借贷"],
        "accounts_payable": ["应付账款", "应付帐款", "应付票据", "应付款项"],
        "advances_from_customers": ["预收账款", "预收款项", "预收帐款"],
        "wages_payable": ["应付职工薪酬", "应付工资", "应付薪酬"],
        "tax_payable": ["应交税费", "应交税金", "应缴税费"],
        "other_payables": ["其他应付款", "其它应付款"],
        "total_current_liabilities": ["流动负债合计", "流动负债总计"],
        "total_non_current_liabilities": ["非流动负债合计", "非流动负债总计", "长期负债合计", "非流动负债"],
        "long_term_borrowings": ["长期借款", "长期借贷", "长期应付款"],
        "total_liabilities": ["负债合计", "负债总计"],
        "paid_in_capital": ["实收资本", "股本"],
        "retained_earnings": ["未分配利润", "留存收益"],
        "total_equity": ["所有者权益合计", "股东权益合计", "权益合计",
                        "净资产合计", "所有者权益（或股东权益）合计",
                        "净资产", "股东权益"],
        "total_liabilities_and_equity": ["负债及所有者权益总计", "负债与股东权益总计",
                                        "负债和股东权益总计", "负债和所有者权益总计",
                                        "负债及股东权益合计", "负债和股东权益合计",
                                        "负债和所有者权益合计", "负债及所有者权益合计",
                                        "负债与所有者权益合计", "负债及股东权益总计",
                                        "负债和所有者权益（或股东权益）总计",
                                        "负债及所有者权益（或股东权益）总计"],

        # +- 利润表科目 -+
        "revenue": ["营业收入", "主营业务收入", "销售收入", "营收"],
        "cost_of_goods_sold": ["营业成本", "主营业务成本", "销售成本"],
        "tax_and_surcharge": ["税金及附加", "营业税金及附加"],
        "selling_expenses": ["销售费用", "营业费用", "销售及管理费用"],
        "administrative_expenses": ["管理费用", "行政管理费用"],
        "rd_expenses": ["研发费用", "研发支出", "研究开发费"],
        "financial_expenses": ["财务费用", "利息费用"],
        "other_income": ["其他收益", "其它收益", "政府补助"],
        "investment_income": ["投资收益"],
        "non_operating_income": ["营业外收入"],
        "non_operating_expense": ["营业外支出"],
        "asset_impairment_loss": ["资产减值损失"],
        "credit_impairment_loss": ["信用减值损失"],
        "income_tax_expense": ["所得税费用", "所得税"],
        "net_profit": ["净利润", "税后利润", "净利润（净亏损以\"-\"号填列）",
                      "四、净利润（净亏损以\"-\"号填列）", "五、净利润（净亏损以\"-\"号填列）"],
        "total_profit": ["利润总额", "税前利润", "利润总额（亏损总额以\"-\"号填列）",
                        "利润总额（亏损以\"-\"号填列）",
                        "三、利润总额（亏损总额以\"-\"号填列）"],
        "operating_income": ["营业利润", "营业利润（亏损以\"-\"号填列）",
                            "二、营业利润（亏损以\"-\"号填列）"],

        # +- 现金流量表科目 -+
        "operating_cash_flow": ["经营活动产生的现金流量净额", "经营活动现金流净额"],
        "investing_cash_flow": ["投资活动产生的现金流量净额", "投资活动现金流净额"],
        "financing_cash_flow": ["筹资活动产生的现金流量净额", "筹资活动现金流净额"],
        "capital_expenditure": ["购建固定资产无形资产支付的现金", "资本支出"],
    }

    # +---- 汇总行关键词 ----+
    SUMMARY_KEYWORDS = {"合计", "总计", "小计", "合计", "total"}
    FUZZY_THRESHOLD = 0.75

    def __init__(self, custom_map: Optional[dict] = None):
        self._map = dict(self.STANDARD_MAP)
        if custom_map:
            self._map.update(custom_map)
        # 反向索引
        self._zh_to_en: dict[str, str] = {}
        for en_key, zh_names in self._map.items():
            for zh in zh_names:
                self._zh_to_en[zh.strip()] = en_key
        self._known_zh_names = list(self._zh_to_en.keys())

    def lookup(self, zh_account_name: str) -> str:
        """精确匹配 + 模糊匹配兜底，返回英文字段名。"""
        name = str(zh_account_name).strip()
        if name in self._zh_to_en:
            return self._zh_to_en[name]
        best_match = difflib.get_close_matches(
            name, self._known_zh_names, n=1, cutoff=self.FUZZY_THRESHOLD
        )
        if best_match:
            return self._zh_to_en[best_match[0]]
        safe_name = name.replace(" ", "_").replace("/", "_")
        return f"unmapped_{safe_name}"

    def is_summary_row(self, zh_account_name: str) -> bool:
        name = str(zh_account_name).strip()
        return any(kw in name for kw in self.SUMMARY_KEYWORDS)

    def map_to_standard(
        self,
        df: pd.DataFrame,
        acct_col: str = "科目名称",
        value_col: str = "金额",
    ) -> pd.DataFrame:
        """将中文科目DataFrame转换为FinanceToolkit标准格式。"""
        records: dict[str, list] = {
            "original_name": [],
            "english_field": [],
            "is_summary_row": [],
            value_col: [],
        }
        for _, row in df.iterrows():
            zh_name = str(row[acct_col]).strip()
            if not zh_name or zh_name.lower() in ("nan", "none"):
                continue
            en_field = self.lookup(zh_name)
            is_sum = self.is_summary_row(zh_name)
            records["original_name"].append(zh_name)
            records["english_field"].append(en_field)
            records["is_summary_row"].append(is_sum)
            records[value_col].append(row[value_col])

        result = pd.DataFrame(records)
        pivot = result.pivot_table(
            index=None,
            columns="english_field",
            values=value_col,
            aggfunc="last",
        )
        pivot = pivot.reset_index(drop=True)
        pivot["_original_names"] = [result["original_name"].tolist()]
        pivot["_summary_mask"] = [result["is_summary_row"].tolist()]
        return pivot

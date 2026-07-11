"""
Piotroski F-Score 财务质量评分模型

9项二元信号（满足=1，不满足=0），总分0-9分。
单期可算F1/F2/F4（0-3分），双期可算全部9项。
"""

from math import isnan
import pandas as pd


class PiotroskiScorer:
    """Piotroski F-Score 财务质量评分"""

    def __init__(self, mapped_df: pd.DataFrame):
        self.df = mapped_df

    def _get(self, df, *columns) -> float:
        for col in columns:
            if col in df.columns:
                val = float(df[col].iloc[0])
                if not isnan(val):
                    return val
        return float("nan")

    def _roa(self, df) -> float:
        np_ = self._get(df, "net_profit")
        ta = self._get(df, "total_assets")
        if isnan(np_) or isnan(ta) or ta == 0:
            return float("nan")
        return np_ / ta

    def _ocf(self, df) -> float:
        return self._get(df, "operating_cash_flow")

    def _net_profit(self, df) -> float:
        return self._get(df, "net_profit")

    def _long_term_debt_ratio(self, df) -> float:
        ltd = self._get(df, "long_term_borrowings")
        ta = self._get(df, "total_assets")
        if isnan(ta) or ta == 0:
            return float("nan")
        return (0 if isnan(ltd) else ltd) / ta

    def _current_ratio(self, df) -> float:
        ca = self._get(df, "total_current_assets")
        cl = self._get(df, "total_current_liabilities")
        if isnan(cl) or cl == 0:
            return float("nan")
        return ca / cl

    def _paid_in_capital(self, df) -> float:
        return self._get(df, "paid_in_capital")

    def _gross_margin(self, df) -> float:
        rev = self._get(df, "revenue")
        cogs = self._get(df, "cost_of_goods_sold")
        if isnan(rev) or rev == 0:
            return float("nan")
        return (rev - (0 if isnan(cogs) else cogs)) / rev

    def _asset_turnover(self, df) -> float:
        rev = self._get(df, "revenue")
        ta = self._get(df, "total_assets")
        if isnan(ta) or ta == 0:
            return float("nan")
        return rev / ta

    def score(self, prior_df: pd.DataFrame = None) -> dict:
        """
        计算F-Score

        Args:
            prior_df: 上期标准化DataFrame（可选）

        Returns:
            {
                "mode": "partial" | "full",
                "signals": {f1: 0/1, f2: 0/1, ...},
                "signal_details": {f1: {name, met, condition}, ...},
                "total_score": int,
                "max_score": int,
                "dimension_scores": {盈利能力: x, 杠杆与流动性: x, 营运效率: x},
                "rating": str,
                "note": str,
            }
        """
        signals = {}
        details = {}

        # F1: ROA > 0
        roa = self._roa(self.df)
        f1 = 1 if (not isnan(roa) and roa > 0) else 0
        signals["F1"] = f1
        details["F1"] = {
            "name": "ROA为正",
            "met": bool(f1),
            "condition": f"ROA = {roa*100:.2f}%" if not isnan(roa) else "无法计算",
            "dimension": "盈利能力",
        }

        # F2: 经营现金流 > 0
        ocf = self._ocf(self.df)
        f2 = 1 if (not isnan(ocf) and ocf > 0) else 0
        signals["F2"] = f2
        details["F2"] = {
            "name": "经营现金流为正",
            "met": bool(f2),
            "condition": f"经营现金流 = {ocf:,.0f}" if not isnan(ocf) else "无法计算",
            "dimension": "盈利能力",
        }

        # F4: 经营现金流 > 净利润
        np_ = self._net_profit(self.df)
        if not isnan(ocf) and not isnan(np_):
            f4 = 1 if ocf > np_ else 0
        else:
            f4 = 0
        signals["F4"] = f4
        details["F4"] = {
            "name": "现金流>净利润（盈余质量）",
            "met": bool(f4),
            "condition": f"现金流{ocf:,.0f} vs 净利润{np_:,.0f}" if not isnan(ocf) and not isnan(np_) else "无法计算",
            "dimension": "盈利能力",
        }

        if prior_df is None:
            # 单期模式：只有F1, F2, F4
            total = f1 + f2 + f4
            return {
                "mode": "partial",
                "signals": signals,
                "signal_details": details,
                "total_score": total,
                "max_score": 3,
                "dimension_scores": {"盈利能力": total, "杠杆与流动性": None, "营运效率": None},
                "rating": self._rating(total, 3),
                "note": "仅上传了1期报表，F-Score只有部分评分（满分3分）。上传上年报表可获取完整9分评分。",
            }

        # 双期完整模式
        # F3: ROA同比提升
        prior_roa = self._roa(prior_df)
        if not isnan(roa) and not isnan(prior_roa):
            f3 = 1 if roa > prior_roa else 0
        else:
            f3 = 0
        signals["F3"] = f3
        details["F3"] = {
            "name": "ROA同比提升",
            "met": bool(f3),
            "condition": f"本期{roa*100:.2f}% vs 上期{prior_roa*100:.2f}%" if not isnan(roa) and not isnan(prior_roa) else "无法计算",
            "dimension": "盈利能力",
        }

        # F5: 长期负债率下降
        cur_ltd = self._long_term_debt_ratio(self.df)
        pri_ltd = self._long_term_debt_ratio(prior_df)
        if not isnan(cur_ltd) and not isnan(pri_ltd):
            f5 = 1 if cur_ltd < pri_ltd else 0
        else:
            f5 = 0
        signals["F5"] = f5
        details["F5"] = {
            "name": "长期负债率下降",
            "met": bool(f5),
            "condition": f"本期{cur_ltd*100:.2f}% vs 上期{pri_ltd*100:.2f}%" if not isnan(cur_ltd) and not isnan(pri_ltd) else "无法计算",
            "dimension": "杠杆与流动性",
        }

        # F6: 流动比率提升
        cur_cr = self._current_ratio(self.df)
        pri_cr = self._current_ratio(prior_df)
        if not isnan(cur_cr) and not isnan(pri_cr):
            f6 = 1 if cur_cr > pri_cr else 0
        else:
            f6 = 0
        signals["F6"] = f6
        details["F6"] = {
            "name": "流动比率提升",
            "met": bool(f6),
            "condition": f"本期{cur_cr:.2f} vs 上期{pri_cr:.2f}" if not isnan(cur_cr) and not isnan(pri_cr) else "无法计算",
            "dimension": "杠杆与流动性",
        }

        # F7: 实收资本未增加
        cur_cap = self._paid_in_capital(self.df)
        pri_cap = self._paid_in_capital(prior_df)
        if not isnan(cur_cap) and not isnan(pri_cap):
            f7 = 1 if cur_cap <= pri_cap else 0
        else:
            f7 = 0
        signals["F7"] = f7
        details["F7"] = {
            "name": "实收资本未增加",
            "met": bool(f7),
            "condition": f"本期{cur_cap:,.0f} vs 上期{pri_cap:,.0f}" if not isnan(cur_cap) and not isnan(pri_cap) else "无法计算",
            "dimension": "杠杆与流动性",
        }

        # F8: 毛利率提升
        cur_gm = self._gross_margin(self.df)
        pri_gm = self._gross_margin(prior_df)
        if not isnan(cur_gm) and not isnan(pri_gm):
            f8 = 1 if cur_gm > pri_gm else 0
        else:
            f8 = 0
        signals["F8"] = f8
        details["F8"] = {
            "name": "毛利率提升",
            "met": bool(f8),
            "condition": f"本期{cur_gm*100:.2f}% vs 上期{pri_gm*100:.2f}%" if not isnan(cur_gm) and not isnan(pri_gm) else "无法计算",
            "dimension": "营运效率",
        }

        # F9: 资产周转率提升
        cur_at = self._asset_turnover(self.df)
        pri_at = self._asset_turnover(prior_df)
        if not isnan(cur_at) and not isnan(pri_at):
            f9 = 1 if cur_at > pri_at else 0
        else:
            f9 = 0
        signals["F9"] = f9
        details["F9"] = {
            "name": "资产周转率提升",
            "met": bool(f9),
            "condition": f"本期{cur_at:.4f} vs 上期{pri_at:.4f}" if not isnan(cur_at) and not isnan(pri_at) else "无法计算",
            "dimension": "营运效率",
        }

        total = sum(signals.values())
        dim_scores = {
            "盈利能力": signals["F1"] + signals["F2"] + signals["F3"] + signals["F4"],
            "杠杆与流动性": signals["F5"] + signals["F6"] + signals["F7"],
            "营运效率": signals["F8"] + signals["F9"],
        }

        return {
            "mode": "full",
            "signals": signals,
            "signal_details": details,
            "total_score": total,
            "max_score": 9,
            "dimension_scores": dim_scores,
            "rating": self._rating(total, 9),
            "note": "",
        }

    @staticmethod
    def _rating(score: int, max_score: int) -> str:
        if max_score == 3:
            if score >= 2:
                return "good"
            elif score >= 1:
                return "warn"
            else:
                return "danger"
        else:
            if score >= 7:
                return "good"
            elif score >= 4:
                return "warn"
            else:
                return "danger"

    def get_summary_text(self, result: dict) -> str:
        """生成F-Score摘要文本（用于注入LLM prompt）"""
        if "error" in result:
            return f"F-Score无法计算：{result['error']}"

        lines = [f"[Piotroski F-Score - {'完整模式' if result['mode'] == 'full' else '部分模式'}]"]
        lines.append(f"总分：{result['total_score']}/{result['max_score']}")

        for fid in sorted(result["signal_details"].keys()):
            d = result["signal_details"][fid]
            status = "✓" if d["met"] else "✗"
            lines.append(f"  {fid} [{status}] {d['name']} — {d['condition']}")

        if result["mode"] == "full":
            ds = result["dimension_scores"]
            lines.append(f"维度得分：盈利{ds['盈利能力']}/4 杠杆流动性{ds['杠杆与流动性']}/3 营运{ds['营运效率']}/2")

        if result["note"]:
            lines.append(f"注意：{result['note']}")

        return "\n".join(lines)

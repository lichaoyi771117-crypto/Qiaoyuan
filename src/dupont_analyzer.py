"""
杜邦分析模型 (DuPont Analysis)

ROE三因素分解：ROE = 净利率 × 总资产周转率 × 权益乘数
支持单期静态分解和双期动态对比。
"""

from math import isnan
import pandas as pd


class DuPontAnalyzer:
    """杜邦分析模型 — ROE三因素分解"""

    def __init__(self, mapped_df: pd.DataFrame):
        self.df = mapped_df

    def _get(self, *columns) -> float:
        for col in columns:
            if col in self.df.columns:
                val = float(self.df[col].iloc[0])
                if not isnan(val):
                    return val
        return float("nan")

    def _compute_factors(self, df=None) -> dict:
        """计算单期三因素"""
        source = self if df is None else DuPontAnalyzer(df)

        net_profit = source._get("net_profit")
        revenue = source._get("revenue")
        total_assets = source._get("total_assets")
        total_equity = source._get("total_equity")

        if any(isnan(x) for x in [net_profit, revenue, total_assets, total_equity]):
            return {"error": "缺少核心数据（净利润/营业收入/总资产/所有者权益）"}

        if revenue == 0 or total_assets == 0 or total_equity == 0:
            return {"error": "核心数据为零，无法计算"}

        npm = net_profit / revenue            # 净利率
        ato = revenue / total_assets          # 总资产周转率
        em = total_assets / total_equity      # 权益乘数
        roe = npm * ato * em                  # ROE

        return {
            "roe": roe,
            "npm": npm,
            "ato": ato,
            "em": em,
            "net_profit": net_profit,
            "revenue": revenue,
            "total_assets": total_assets,
            "total_equity": total_equity,
        }

    def analyze(self, prior_df: pd.DataFrame = None) -> dict:
        """
        杜邦分析

        Args:
            prior_df: 上期标准化DataFrame（可选，有则做动态对比）

        Returns:
            {
                "mode": "static" | "dynamic",
                "current": {roe, npm, ato, em, ...},
                "prior": {...} | None,     # 双期模式时有值
                "changes": {...} | None,    # 双期模式时的变化值
                "driver": str,              # 主要驱动因子
                "weakness": str,            # 最弱因子
            }
        """
        current = self._compute_factors()

        if "error" in current:
            return {"error": current["error"]}

        if prior_df is None:
            # 单期静态模式
            driver, weakness = self._identify_driver_weakness(current, current)
            return {
                "mode": "static",
                "current": current,
                "prior": None,
                "changes": None,
                "driver": driver,
                "weakness": weakness,
            }

        # 双期动态对比模式
        prior = self._compute_factors(prior_df)
        if "error" in prior:
            driver, weakness = self._identify_driver_weakness(current, current)
            return {
                "mode": "static",
                "current": current,
                "prior": None,
                "changes": None,
                "driver": driver,
                "weakness": weakness,
                "prior_error": prior["error"],
            }

        changes = {
            "roe": current["roe"] - prior["roe"],
            "npm": current["npm"] - prior["npm"],
            "ato": current["ato"] - prior["ato"],
            "em": current["em"] - prior["em"],
        }

        driver, weakness = self._identify_driver_weakness(current, prior, changes)

        return {
            "mode": "dynamic",
            "current": current,
            "prior": prior,
            "changes": changes,
            "driver": driver,
            "weakness": weakness,
        }

    def _identify_driver_weakness(self, current: dict, prior: dict, changes: dict = None) -> tuple:
        """识别主要驱动因子和最弱因子"""
        factors = {
            "净利率（卖得贵不贵）": current["npm"],
            "资产周转率（卖得快不快）": current["ato"],
            "权益乘数（杠杆大不大）": current["em"],
        }

        # 最弱因子：三个因子中相对行业基准偏离最大的
        # 简化处理：取三个中绝对值最小的作为"最弱"
        weakness = min(factors, key=factors.get)

        if changes:
            # 双期模式：驱动因子是变化最大的那个
            change_factors = {
                "净利率（卖得贵不贵）": abs(changes["npm"]),
                "资产周转率（卖得快不快）": abs(changes["ato"]),
                "权益乘数（杠杆大不大）": abs(changes["em"]),
            }
            driver = max(change_factors, key=change_factors.get)
            # 判断方向
            driver_change = changes[{"净利率（卖得贵不贵）": "npm",
                                      "资产周转率（卖得快不快）": "ato",
                                      "权益乘数（杠杆大不大）": "em"}[driver]]
            direction = "提升" if driver_change > 0 else "下降"
            driver = f"{driver}（{direction}）"
        else:
            # 单期模式：驱动因子是三个中绝对值最大的
            driver = max(factors, key=factors.get)

        return driver, weakness

    def get_graphviz_source(self, result: dict) -> str:
        """
        生成Graphviz DOT源码用于st.graphviz_chart()

        单期：单棵分解树
        双期：并排两棵树
        """
        if "error" in result:
            return f'digraph G {{ label="杜邦分析数据不足"; }}'

        cur = result["current"]

        def _fmt_pct(v):
            return f"{v*100:.2f}%" if not isnan(v) else "N/A"

        def _fmt_num(v):
            return f"{v:.4f}" if not isnan(v) and abs(v) < 100 else f"{v:,.0f}"

        if result["mode"] == "static":
            dot = f'''digraph DuPont {{
                rankdir=TB;
                node [shape=box, style="rounded,filled", fontname="Microsoft YaHei", fontsize=12];
                edge [color="#666"];

                ROE [label="ROE\\n{_fmt_pct(cur['roe'])}", fillcolor="#e3f2fd", color="#1976d2"];

                NPM [label="净利率\\n{_fmt_pct(cur['npm'])}", fillcolor="#f3e5f5", color="#7b1fa2"];
                ATO [label="资产周转率\\n{_fmt_pct(cur['ato'])}次", fillcolor="#e8f5e9", color="#388e3c"];
                EM  [label="权益乘数\\n{_fmt_pct(cur['em'])}倍", fillcolor="#fff3e0", color="#e65100"];

                NP  [label="净利润 {_fmt_num(cur['net_profit'])}\\n营业收入 {_fmt_num(cur['revenue'])}", fillcolor="#fafafa"];
                REV [label="营业收入 {_fmt_num(cur['revenue'])}\\n总资产 {_fmt_num(cur['total_assets'])}", fillcolor="#fafafa"];
                TA  [label="总资产 {_fmt_num(cur['total_assets'])}\\n所有者权益 {_fmt_num(cur['total_equity'])}", fillcolor="#fafafa"];

                ROE -> NPM;
                ROE -> ATO;
                ROE -> EM;
                NPM -> NP;
                ATO -> REV;
                EM -> TA;
            }}'''
            return dot.replace("_fmt_pct", "").replace("_fmt_num", "")  # cleanup

        # 双期模式
        pri = result.get("prior", {})
        chg = result.get("changes", {})

        def _change_str(val):
            if val is None or isnan(val):
                return ""
            sign = "+" if val >= 0 else ""
            return f"({sign}{val*100:.2f}%)" if abs(val) < 10 else f"({sign}{val:.2f})"

        dot = f'''digraph DuPont {{
            rankdir=TB;
            node [shape=box, style="rounded,filled", fontname="Microsoft YaHei", fontsize=11];
            edge [color="#666"];
            compound=true;

            subgraph cluster_current {{
                label="本期";
                style=dashed;
                color="#1976d2";
                ROE_C [label="ROE\\n{_fmt_pct(cur['roe'])}", fillcolor="#e3f2fd"];
                NPM_C [label="净利率\\n{_fmt_pct(cur['npm'])}", fillcolor="#f3e5f5"];
                ATO_C [label="周转率\\n{cur['ato']:.4f}次", fillcolor="#e8f5e9"];
                EM_C  [label="权益乘数\\n{cur['em']:.4f}倍", fillcolor="#fff3e0"];
                ROE_C -> NPM_C; ROE_C -> ATO_C; ROE_C -> EM_C;
            }}

            subgraph cluster_prior {{
                label="上期";
                style=dashed;
                color="#999";
                ROE_P [label="ROE\\n{_fmt_pct(pri.get('roe', float('nan')))} {_change_str(chg.get('roe'))}", fillcolor="#f5f5f5"];
                NPM_P [label="净利率\\n{_fmt_pct(pri.get('npm', float('nan')))} {_change_str(chg.get('npm'))}", fillcolor="#f5f5f5"];
                ATO_P [label="周转率\\n{pri.get('ato', 0):.4f}次", fillcolor="#f5f5f5"];
                EM_P  [label="权益乘数\\n{pri.get('em', 0):.4f}倍", fillcolor="#f5f5f5"];
                ROE_P -> NPM_P; ROE_P -> ATO_P; ROE_P -> EM_P;
            }}
        }}'''
        return dot

    def get_summary_text(self, result: dict) -> str:
        """生成杜邦分析摘要文本（用于注入LLM prompt）"""
        if "error" in result:
            return f"杜邦分析无法计算：{result['error']}"

        cur = result["current"]
        mode_label = "单期静态分解" if result["mode"] == "static" else "双期动态对比"
        lines = [f"[杜邦分析 - {mode_label}]"]
        lines.append(f"ROE = {cur['roe']*100:.2f}%")
        lines.append(f"  净利率 = {cur['npm']*100:.2f}%（卖得贵不贵）")
        lines.append(f"  资产周转率 = {cur['ato']:.4f}次（卖得快不快）")
        lines.append(f"  权益乘数 = {cur['em']:.4f}倍（杠杆大不大）")
        lines.append(f"主要驱动因子：{result['driver']}")
        lines.append(f"最弱因子：{result['weakness']}")

        if result["mode"] == "dynamic" and result.get("changes"):
            chg = result["changes"]
            lines.append(f"ROE同比变化：{chg['roe']*100:+.2f}%")
            lines.append(f"  净利率变化：{chg['npm']*100:+.2f}%")
            lines.append(f"  周转率变化：{chg['ato']:+.4f}次")
            lines.append(f"  权益乘数变化：{chg['em']:+.4f}倍")

        return "\n".join(lines)

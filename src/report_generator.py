"""
LLM 报告生成模块

将财务指标计算结果转换为自然语言解读报告，
覆盖 PRD 4.3 定义的 6 个报告模块。

设计原则（来自财务审核报告 V1.1）:
1. 所有数值在计算引擎中确定，LLM 仅负责解读
2. 严禁 LLM 自行推导或引用数据
3. 原型阶段使用 OpenAI / DeepSeek API，生产可切换 FinGPT
"""
import os
import json
import logging
from typing import Optional

_logger = logging.getLogger(__name__)

# +---- 5 模块 Prompt 模板 ----+

_REPORT_SECTIONS = {

    "财务数据摘要": {
        "template": """你是程信霖咨询公司的高级财务分析师。以下是一家中型企业的财务数据摘要，请用自然语言生成一段精炼的财务概况（200-300字）。

**企业信息**
报告期: {report_period}
分析目标: {analysis_goal}

**关键科目一览**
{key_accounts_text}

**数据质量**
{quality_notes}

**撰写要求**
1. 语言简洁专业，面向中小企业主，避免过度学术化
2. 直接输出报告正文，不要以"好的"作为开头
3. 如果你发现资产负债率超过70%、应收账款周转天数超过180天这两个信号，要特别标注
4. 如果勾稽关系不平衡，必须在概况中首句提示"数据存在异常"
5. 如果「经营现金流/净利润」低于80%或「自由现金流」为负，要在概况中明确指出"利润含金量不足"或"现金流紧张"
6. 不要编造任何数字，只使用下面提供的数值""",

        "variables": ["report_period", "analysis_goal", "key_accounts_text", "quality_notes"]
    },

    "异常诊断": {
        "template": """你是程信霖咨询公司的财务诊断专家。请基于以下财务指标，诊断该企业可能存在的财务异常。

**偿债能力**
{偿债能力_text}

**盈利能力**
{盈利能力_text}

**营运效率**
{营运效率_text}

**现金流**
{现金流_text}

**财务预警**
{财务预警_text}

**税务指标**
{税务指标_text}

**行业参考值**
{benchmark_notes}

**诊断要求**
1. 直接输出诊断内容，不要以"好的"作为开头
2. 每条诊断包含三个要素：(a) 指标值 (b) 偏离参考值的幅度 (c) 可能的财务原因
3. 按异常严重程度从高到低排列，最多5条
4. 不要编造不存在的财务关系，每条结论必须有指标数据支撑
5. 输出格式：每条一行，用「异常信号」「原因分析」两个标签标识""",

        "variables": ["偿债能力_text", "盈利能力_text", "营运效率_text", "现金流_text",
                       "财务预警_text", "税务指标_text", "benchmark_notes"]
    },

    "优化建议": {
        "template": """你是程信霖咨询公司的财务优化顾问。客户选择的分析目标是「{analysis_goal}」，请基于以下指标数据，给出具体可落地的优化建议。

**当前财务指标**
{all_ratios_text}

**撰写要求**
1. 每条建议必须跟客户的「{analysis_goal}」目标挂钩
2. 建议必须具体可操作，例如"建议将客户信用账期从120天缩短至60天"而非"加强应收账款管理"
3. 直接输出建议内容，不要以"好的"作为开头
4. 如果客户的经营现金流差（经营现金流/净利润 < 80% 或自由现金流为负），首条建议须聚焦"加速回款、压缩账期、盘活存货以改善现金流"
5. 如果财务健康检查发现存在资不抵债风险，首条建议须是"尽快清偿高息债务"
6. 如果融资能力评估发现资产负债率过高，首条建议须是"通过增资扩股或引入战投降低杠杆"
7. 如果降本增效发现毛利率显著低于同行业，首条建议须是"从低毛利产品逐步转向高毛利领域"
8. 输出 3-5 条建议，按重要性和可行性排序""",

        "variables": ["analysis_goal", "all_ratios_text"]
    },

    "税务风险提示": {
        "template": """你是程信霖咨询公司的税务专家。请根据以下指标，评估企业税务健康状况。

**税务核心指标**
实际税率: {实际税率}%
综合税负率: {综合税负率}%
毛利率: {毛利率}%
资产减值损失: {资产减值损失元}

**异常检测**
{anomaly_flags}

**撰写要求**
1. 直接输出风险提示内容，不要以"好的"作为开头
2. 如果实际税率偏离了 25% 的标准，解释可能原因（小微企业优惠/前期亏损弥补/虚列费用等）
3. 如果综合税负率过低，提示可能被税务机关质疑的风险
4. 如果费用率同比大幅度增长，提示"可能存在虚列费用的税务风险"
5. 输出 2-4 条明确的风险提示和建议""",

        "variables": ["实际税率", "综合税负率", "毛利率", "资产减值损失元", "anomaly_flags"]
    },

    "免责与合规声明": {
        "template": None,  # 静态文本，不需要 LLM
    },
}


class ReportGenerator:
    """
    财务分析报告生成器。

    使用方式:
        gen = ReportGenerator(api_key=os.getenv("OPENAI_API_KEY"))
        report = gen.generate(ratios_dict, analysis_goal="财务健康检查")
        for section in report:
            print(section.title, section.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url
        self._model = model
        self._client = None

    def _ensure_client(self):
        if self._client is None and self._api_key:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)

    @staticmethod
    def _ratios_to_text(ratios: dict, category: str) -> str:
        """将指标字典的某一类别格式化为可读文本"""
        items = ratios.get(category, {})
        lines = []
        for name, info in items.items():
            v = info["value"]
            if isinstance(v, float) and (v != v):  # NaN
                continue
            if v == float("inf"):
                continue
            unit = info.get("unit", "")
            benchmark = info.get("benchmark", "")
            note = info.get("note", "")
            if isinstance(v, float) and abs(v) > 1e6:
                v_str = f"{v:,.0f}"
            elif isinstance(v, float):
                v_str = f"{v:.4f}"
            else:
                v_str = str(v)
            parts = [f"  {name}: {v_str}{unit}"]
            if benchmark:
                parts.append(f"(参考值: {benchmark})")
            if note:
                parts.append(f"[{note}]")
            lines.append(" ".join(parts))
        return "\n".join(lines)

    @staticmethod
    def _all_ratios_to_text(ratios: dict) -> str:
        """所有指标格式化为文本"""
        lines = []
        for category, items in ratios.items():
            for name, info in items.items():
                v = info["value"]
                if isinstance(v, float) and (v != v):
                    continue
                if v == float("inf"):
                    continue
                unit = info.get("unit", "")
                if isinstance(v, float) and abs(v) > 1e6:
                    v_str = f"{v:,.0f}"
                elif isinstance(v, float):
                    v_str = f"{v:.4f}"
                else:
                    v_str = str(v)
                lines.append(f"  [{category}] {name}: {v_str}{unit}")
        return "\n".join(lines)

    @staticmethod
    def _make_quality_notes(check_results) -> str:
        """从质量校验结果生成注解文本"""
        notes = []
        for r in check_results:
            if r.severity == "block":
                notes.append(f"[阻断] {r.check_name}: {r.detail}")
            elif r.severity == "warn":
                notes.append(f"[警告] {r.check_name}: {r.detail}")
            elif r.passed:
                notes.append(f"[通过] {r.check_name}: {r.detail}")
        return "\n".join(notes) if notes else "所有质量校验通过"

    def generate(
        self,
        ratios: dict,
        mapped_df=None,
        check_results=None,
        analysis_goal: str = "财务健康检查",
        report_period: str = "未指定报告期",
    ) -> dict[str, str]:
        """
        生成完整分析报告。

        Args:
            ratios: MetricCalculator.compute_all() 的输出
            mapped_df: 标准化后的科目 DataFrame（用于提取关键科目）
            check_results: 质量校验结果列表
            analysis_goal: 客户选择的分析目标
            report_period: 报告来源文件名/说明

        Returns:
            dict: 模块名 → 内容
        """
        # 关键科目文本
        key_items = []
        if mapped_df is not None:
            for col in ["total_assets", "total_liabilities", "total_equity",
                        "revenue", "net_profit", "cash_and_equivalents"]:
                if col in mapped_df.columns:
                    val = mapped_df[col].iloc[0]
                    key_items.append(f"  {col}: {val:,.2f}")
        key_accounts_text = "\n".join(key_items) if key_items else "暂无科目数据"

        # 质量注解
        quality_notes = self._make_quality_notes(check_results) if check_results else "暂无质量校验数据"

        # 异常检测标记
        anomaly_flags = []
        if ratios:
            for cat in ["偿债能力", "盈利能力", "营运效率"]:
                for name, info in ratios.get(cat, {}).items():
                    v = info["value"]
                    if isinstance(v, float) and v == v and v != float("inf"):
                        bench = info.get("benchmark", "")
                        if ">1" in bench and v < 1:
                            anomaly_flags.append(f"[偏低] {name} = {v:.2f}, 参考值: {bench}")
                        elif ">2" in bench and v < 2:
                            anomaly_flags.append(f"[偏低] {name} = {v:.2f}, 参考值: {bench}")
                        elif "<70%" in bench and v > 0.7:
                            anomaly_flags.append(f"[偏高] {name} = {v:.2f}, 参考值: {bench}")
            zs = ratios.get("财务预警", {}).get("Altman Z-score", {}).get("value", 0)
            if isinstance(zs, float) and zs < 1.81:
                anomaly_flags.append(f"[高危] Altman Z-score = {zs:.2f}, 破产风险较高")
        anomaly_flags_text = "\n".join(anomaly_flags) if anomaly_flags else "无异常标记"

        # 指标提取 — 给 Prompt 模板用
        ratio_vars = {}
        if ratios:
            ratio_vars["偿债能力_text"] = self._ratios_to_text(ratios, "偿债能力")
            ratio_vars["盈利能力_text"] = self._ratios_to_text(ratios, "盈利能力")
            ratio_vars["营运效率_text"] = self._ratios_to_text(ratios, "营运效率")
            ratio_vars["现金流_text"] = self._ratios_to_text(ratios, "现金流")
            ratio_vars["财务预警_text"] = self._ratios_to_text(ratios, "财务预警")
            ratio_vars["税务指标_text"] = self._ratios_to_text(ratios, "税务指标")
            ratio_vars["all_ratios_text"] = self._all_ratios_to_text(ratios)
            ratio_vars["实际税率"] = ratios.get("税务指标", {}).get("实际税率", {}).get("value", "N/A")
            ratio_vars["综合税负率"] = ratios.get("税务指标", {}).get("综合税负率", {}).get("value", "N/A")
            ratio_vars["毛利率"] = ratios.get("盈利能力", {}).get("毛利率", {}).get("value", "N/A")
            ratio_vars["资产减值损失元"] = "0"  # 从科目数据中提取

        report = {
            "report_period": report_period,
            "analysis_goal": analysis_goal,
            "财务数据摘要": None,
            "财务指标明细": self._all_ratios_to_text(ratios) if ratios else "",
            "指标雷达图数据": "",
            "异常诊断": None,
            "优化建议": None,
            "税务风险提示": None,
            "免责与合规声明": self._get_disclaimer(),
        }

        # 尝试 LLM 生成 4 个模块，失败则用静态替代
        if self._api_key:
            self._ensure_client()
            for section_name in ["财务数据摘要", "异常诊断", "优化建议", "税务风险提示"]:
                try:
                    spec = _REPORT_SECTIONS[section_name]
                    prompt = spec["template"]
                    vars_dict = {
                        "report_period": report_period,
                        "analysis_goal": analysis_goal,
                        "key_accounts_text": key_accounts_text,
                        "quality_notes": quality_notes,
                        "anomaly_flags": anomaly_flags_text,
                        "benchmark_notes": "所有参考值均为 A 股同行业上市公司均值，与中小企业存在结构性差异，仅供参考",
                    }
                    vars_dict.update(ratio_vars)
                    prompt = prompt.format(**{k: vars_dict.get(k, "") for k in spec["variables"]})
                    response = self._client.chat.completions.create(
                        model=self._model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=2000,
                    )
                    report[section_name] = response.choices[0].message.content
                except Exception as e:
                    _logger.warning(f"LLM 生成 [{section_name}] 失败: {e}")
                    report[section_name] = self._fallback_section(section_name, ratios, analysis_goal)
        else:
            # 无 API key：全用静态报告
            for section_name in ["财务数据摘要", "异常诊断", "优化建议", "税务风险提示"]:
                report[section_name] = self._fallback_section(section_name, ratios, analysis_goal)

        # 生成雷达图 JSON 数据
        report["指标雷达图数据"] = self._make_radar_data(ratios)

        return report

    @staticmethod
    def _fallback_section(section_name: str, ratios: dict, goal: str) -> str:
        """无 LLM API 时的静态报告"""
        return f"[{section_name}]\n本模块需 API 连接（OpenAI/DeepSeek）生成自然语言解读。当前展示指标计算值。\n"

    @staticmethod
    def _make_radar_data(ratios: dict) -> str:
        """生成雷达图 JSON 数据（供 Plotly 渲染）"""
        radar = {}
        for cat_name, items in ratios.items():
            for name, info in items.items():
                v = info["value"]
                if isinstance(v, float) and v == v and v != float("inf"):
                    # 归一化到 0-100 的近似分数
                    if name in ("资产负债率",):
                        radar[name] = min(100, max(0, (1 - v) * 100))
                    elif name in ("流动比率", "速动比率"):
                        radar[name] = min(100, max(0, v * 50))
                    elif "margin" in name.lower() or "率" in name:
                        radar[name] = min(100, max(0, v * 100))
                    else:
                        radar[name] = min(100, max(0, v * 20))
        return json.dumps(radar, ensure_ascii=False)

    @staticmethod
    def _get_disclaimer() -> str:
        return """**免责与合规声明**

1. 本报告由 程信霖咨询 · F-Analyzer 系统自动生成，不构成专业财务意见。
2. 所有指标数值由财务计算引擎确定，仅用于参考，不应作为投资或信贷决策的唯一依据。
3. 程信霖咨询 · F-Analyzer 生成的解读文本可能存在偏差或错误，请以计算引擎输出的数值为准。
4. 行业对标数据来源于 A 股上市公司均值（AKShare），与中小企业存在结构性差异，仅供参考。
5. 重大财务决策请咨询持牌专业顾问，程信霖咨询可提供人工复核服务。"""

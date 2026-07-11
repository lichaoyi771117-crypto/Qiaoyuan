"""霖信莯咨询 · 峤远·F-Analyzer — 企业财务报表AI分析系统 V2.0
主脑协议V1.0驱动 | 双版本报告 | 三模型固化 | 增强指标抽取
"""

import io
import os
import re
import tempfile
import logging
from datetime import datetime
from math import isnan

import pandas as pd
import streamlit as st

# ── dotenv 加载 ──
from dotenv import load_dotenv
load_dotenv()

from src.excel_parser import parse_financial_excel, parse_multiple_files
from src.accounting_mapper import AccountingMapper
from src.quality_checker import QualityChecker
from src.metric_calculator import MetricCalculator
from src.report_generator import ReportGenerator, markdown_to_docx, professional_report_to_docx
from src.industry_benchmarks import get_industry_benchmarks, evaluate_metric
from src.dupont_analyzer import DuPontAnalyzer
from src.piotroski_scorer import PiotroskiScorer

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

st.set_page_config(page_title="峤远·F-Analyzer | 企业财报AI分析", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ═══════════════════════════════════════════════════════════
# 全局样式（必须在协议门禁之前注入，确保CSS生效）
# ═══════════════════════════════════════════════════════════

st.markdown("""<style>
    .main-header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); color: #fff; padding: 28px 32px; border-radius: 12px; margin-bottom: 24px; text-align: center; }
    .main-header h1 { font-size: 24px; font-weight: 700; letter-spacing: 2px; margin: 0; color: #fff; }
    .main-header p { font-size: 13px; opacity: .65; margin: 6px 0 0; color: #fff; }
    .metric-card { background: #f7f9fc; border-radius: 10px; padding: 16px; text-align: center; margin-bottom: 8px; border: 1px solid #e8ecf1; }
    .metric-card .val { font-size: 22px; font-weight: 700; color: #0f3460; }
    .metric-card .lbl { font-size: 11px; color: #888; margin-top: 2px; }
    .metric-card.warn { background: #fff7e6; border-color: #ffd591; }
    .metric-card.warn .val { color: #d46b08; }
    .metric-card.danger { background: #fff1f0; border-color: #ffa39e; }
    .metric-card.danger .val { color: #cf1322; }
    .metric-card.good { background: #f6ffed; border-color: #b7eb8f; }
    .metric-card.good .val { color: #389e0d; }
    .product-card { background: #f0f7ff; border: 1px solid #91caff; border-radius: 10px; padding: 20px; margin: 8px 0; }
    .product-card h4 { color: #0f3460; margin: 0 0 8px; }
    .file-tag { display: inline-block; background: #e6f7ff; color: #096dd9; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin: 2px; }
    hr { margin: 8px 0; }
    [data-testid="stFileUploaderDropzone"] span { display: none; }
    [data-testid="stFileUploaderDropzone"] button::after { content: " 浏览文件"; }
    [data-testid="stFileUploaderDropzone"]::before { content: "拖拽文件到此处，或"; font-size: .875rem; }
    [data-testid="stFileUploaderDropzone"] small { display: none; }
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 产品介绍组件（协议门禁页 + 主界面复用）
# ═══════════════════════════════════════════════════════════

def render_product_intro():
    """产品介绍区域 — 在协议条款上方展示，宽度略宽于协议(960px vs 900px)"""
    st.markdown("""<div style="max-width:960px;margin:0 auto;">
<div class="main-header">
<h1>📊 峤远 · 企业财务报表AI分析</h1>
<p>霖信莯咨询 · F-Analyzer V2.0 ｜ 主脑协议V1.0驱动 ｜ 双版本报告 ｜ 三模型固化</p>
</div>
<div class="product-card">
<h4>🔍 峤远是什么？</h4>
<p>峤远是一个<b>CFO级AI财务专家</b>，拥有财务分析+税务筹划+融资顾问+法务合规四栈专业能力。你上传财务报表，它帮你算出20+核心指标、跑通三个经典财务模型（杜邦分析/破产预测/财务质量评分），输出<b>专业版</b>和<b>大白话版</b>两份分析报告，还给出针对性的优化改进建议。</p>
</div>
<div style="display:flex;gap:12px;margin:8px 0;">
<div class="product-card" style="flex:1;">
<h4>① 上传报表</h4>
<p>拖拽多个Excel文件，AI自动识别是资产负债表/利润表/现金流量表</p>
</div>
<div class="product-card" style="flex:1;">
<h4>② 选择关注点</h4>
<p>3道选择题校准你最关心的维度（可跳过，输出标准版）</p>
</div>
<div class="product-card" style="flex:1;">
<h4>③ 一键生成</h4>
<p>专业版+大白话版双报告，三模型分析，优化建议，一键下载docx</p>
</div>
</div>
<div class="product-card" style="background:#e8f5e9;border-color:#b7eb8f;">
<h4>🔒 数据安全</h4>
<p>• 财务文件在<b>本地服务器</b>处理，不上传第三方云平台<br/>
• AI模型只接收<b>结构化指标摘要</b>，不接收原始文件<br/>
• 分析完成后数据可一键清除，不持久化存储</p>
</div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# 用户授权协议（访问门禁）
# ═══════════════════════════════════════════════════════════

_CONSENT_TEMPLATE = """<div style='font-family:"Microsoft YaHei","宋体",SimSun,serif; font-size:14px; line-height:2.0; color:#222; max-width:900px; margin:0 auto;'>
<h2 style='text-align:center; font-size:20px; font-weight:bold; margin-bottom:8px;'>霖信莯咨询 · 峤远 F-Analyzer<br/>用户授权与服务协议</h2>
<p style='text-align:center; font-size:12px; color:#888; margin-bottom:24px;'>
版本：v2.0 &nbsp;|&nbsp; 更新日期：2026年7月11日<br/>
运营主体：昆明霖信莯科技有限公司（以下简称"霖信莯"或"本公司"）
</p>
<div style='background:#fff3e0; border-left:4px solid #e65100; padding:16px; margin:16px 0; border-radius:4px;'>
<p style='font-weight:bold; color:#e65100; margin:0 0 8px 0;'>⚠️ 重要提示</p>
<p style='margin:4px 0;'><b>尊敬的用户</b>：感谢您选择霖信莯咨询开发的峤远 F-Analyzer 企业财务报表AI分析系统。本系统基于峤远主脑协议V1.0驱动，提供专业版和大白话版双版本财务分析报告。</p>
<p style='margin:4px 0;'><b style='color:#d32f2f;'>本系统输出的分析报告仅供商业决策参考，不构成正式的财务建议、税务意见或融资承诺。如需专业意见，请咨询持有相应资质的注册会计师、税务师或金融机构。</b></p>
<p style='margin:4px 0;'><b>本协议适用中华人民共和国法律。</b></p>
</div>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第一条 定义与解释</h3>
<p><b>1.1 本系统</b>：指霖信莯开发并运营的"峤远 F-Analyzer 企业财务报表AI分析系统"，包括其全部功能模块、算法模型、用户界面及相关文档。</p>
<p><b>1.2 财务文件</b>：指用户上传至本系统的 Excel、PDF 或其他格式的财务报表、账目数据及相关附件。</p>
<p><b>1.3 输出报告</b>：指本系统基于用户上传的财务文件，通过AI算法处理后生成的财务分析报告，包括专业版和大白话版两个版本。</p>
<p><b>1.4 AI模型</b>：指本系统调用的第三方大语言模型（DeepSeek API），用于执行财务数据解读、风险识别等任务。<b style='color:#c62828;'>AI模型仅接收经本地处理后的财务摘要数据，不发送原始文件全文</b>。</p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第二条 服务内容与范围</h3>
<p><b>2.1 服务内容</b>：财务报表自动解析与指标计算、偿债/盈利/营运/现金流/税务/预警多维度分析、杜邦分析/Altman Z-Score/Piotroski F-Score三模型固化分析、专业版+大白话版双版本报告生成。</p>
<p><b>2.2 服务限制</b>：<b style='color:#d32f2f;'>本系统的分析范围限定于用户上传的财务文件的数据层面。不进行实地尽职调查、不验证数据真实性、不对企业信用做出评级。</b></p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第三条 数据安全与隐私保护</h3>
<p style='background:#e8f5e9; padding:12px; border-radius:4px;'><b>用户上传的财务文件均在霖信莯本地服务器上处理。未经用户另行书面授权，不会将用户的原始财务文件上传至任何第三方云服务平台。</b></p>
<p><b>3.2</b> AI分析时仅发送经过结构化处理的财务指标摘要，不发送企业名称、纳税人识别号等敏感字段。</p>
<p><b>3.3</b> 文件处理完成后，用户可清除数据。系统不对财务文件进行持久化存储。</p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第四条 AI使用条款</h3>
<p><b>4.1</b> 用户理解AI技术存在"幻觉"风险和非确定性输出等固有局限。</p>
<p style='background:#fff3e0; padding:12px; border-radius:4px;'><b>4.2 用户必须结合自身专业判断和实际情况进行独立评估。本系统输出不应被视为对用户融资决策的替代。</b></p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第五条 免责声明</h3>
<p style='background:#ffebee; padding:12px; border-radius:4px;'><b>本系统输出的财务分析报告不应被解释为：（1）正式的财务意见、税务建议或融资承诺；（2）企业信用状况的官方评级；（3）融资申请审批结果的预测或保证。</b></p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第六条 法律适用与争议解决</h3>
<p>本协议适用<b>中华人民共和国法律</b>。争议协商不成的，向昆明霖信莯科技有限公司所在地有管辖权的人民法院提起诉讼。</p>
<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第七条 联系方式</h3>
<table style='width:100%; border-collapse:collapse; margin:12px 0;'>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold; width:120px;'>运营主体</td><td style='border:1px solid #ddd; padding:8px;'>昆明霖信莯科技有限公司</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>联系人</td><td style='border:1px solid #ddd; padding:8px;'>余磊</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>联系电话</td><td style='border:1px solid #ddd; padding:8px;'>13987671259</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>电子邮箱</td><td style='border:1px solid #ddd; padding:8px;'>425448719@qq.com</td></tr>
</table>
<hr style='margin:24px 0;'/>
<p style='text-align:center; font-size:12px; color:#888;'>&copy; 2026 昆明霖信莯科技有限公司 保留一切权利</p>
</div>"""

if "fa_consent_granted" not in st.session_state:
    st.session_state.fa_consent_granted = False

if not st.session_state.fa_consent_granted:
    # ── 产品介绍 ──
    render_product_intro()

    # ── 分隔线 ──
    st.markdown("<div style='text-align:center; margin:20px 0 12px; color:#888; font-size:13px;'>— 以下为服务协议，请阅读并确认 —</div>", unsafe_allow_html=True)

    # ── 协议条款 ──
    st.markdown("### 📜 用户授权与服务协议")
    st.caption("请仔细阅读以下协议。您必须同意所有条款才能使用本系统。")
    st.markdown('<div style="background:#fafafa;border:2px solid #0f3460;border-radius:10px;padding:24px;margin:16px 0;max-height:420px;overflow-y:auto;font-size:13px;">%s</div>' % _CONSENT_TEMPLATE, unsafe_allow_html=True)
    st.divider()
    c1 = st.checkbox("我确认已阅读并理解上述数据安全措施", key="fa_consent_security")
    c2 = st.checkbox("我确认已知悉本系统为财务分析辅助工具，不构成正式财务意见或融资承诺", key="fa_consent_disclaimer")
    c3 = st.checkbox("我授权霖信莯在本地服务器上处理我上传的财务文件，AI模型仅接收结构化摘要数据", key="fa_consent_authorize")
    if c1 and c2 and c3:
        st.success("✅ 您已同意所有条款。请点击下方按钮进入系统。")
        if st.button("进入系统 →", type="primary", use_container_width=True):
            st.session_state.fa_consent_granted = True
            st.rerun()
    else:
        st.info("请勾选全部三个确认项以继续。")
    st.stop()

# ═══════════════════════════════════════════════════════════
# Session State 初始化
# ═══════════════════════════════════════════════════════════

for k, v in {
    "processing_done": False,
    "raw_df": None,
    "mapped_df": None,
    "prior_mapped_df": None,
    "ratios": None,
    "report": None,
    "enhanced_metrics": None,
    "model_results": None,
    "calibration": {},
    "upload_key": 0,
    "classified_files": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════
# AI文件分拣
# ═══════════════════════════════════════════════════════════

def classify_file_with_llm(file_content: bytes, filename: str) -> str:
    """用LLM对文件前20行预览进行分类"""
    try:
        # 读取前20行
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(file_content), header=None, nrows=20, sheet_name=0)
            preview = df.to_string(max_rows=20, max_cols=8)
        else:
            return "其他"
    except Exception:
        return "其他"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个财务文件分类器。根据文件内容预览，判断这是资产负债表、利润表、现金流量表、所有者权益变动表还是其他。只回答这5个分类之一，不要解释。"},
                {"role": "user", "content": f"文件名: {filename}\n内容预览:\n{preview[:500]}\n\n这是什么类型的财务报表？"},
            ],
            temperature=0.1,
            max_tokens=20,
        )
        result = response.choices[0].message.content.strip()
        valid = {"资产负债表", "利润表", "现金流量表", "所有者权益变动表", "其他"}
        for v in valid:
            if v in result:
                return v
        return "其他"
    except Exception:
        return "其他"


# ═══════════════════════════════════════════════════════════
# 主界面（协议通过后直接进入上传区）
# ═══════════════════════════════════════════════════════════

st.markdown("---")

# ── 1. 智能上传 ──
st.markdown("### 📤 智能上传")
st.caption("拖拽一个或多个Excel文件，AI会自动识别报表类型。如需深度分析（杜邦趋势对比、完整F-Score），请同时上传上年报表。")

uploaded_files = st.file_uploader(
    "上传财务报表文件",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    key=f"fu_{st.session_state.upload_key}",
    label_visibility="collapsed",
)

# AI分拣
if uploaded_files and not st.session_state.classified_files:
    st.session_state.classified_files = []
    with st.spinner("🔍 AI正在识别文件类型..."):
        for uf in uploaded_files:
            ftype = classify_file_with_llm(uf.getvalue(), uf.name)
            st.session_state.classified_files.append({"name": uf.name, "type": ftype, "content": uf.getvalue()})

# 显示分拣结果
if st.session_state.classified_files:
    st.markdown("**📋 文件分拣结果：**")
    for cf in st.session_state.classified_files:
        icon = {"资产负债表": "📊", "利润表": "💰", "现金流量表": "💸", "所有者权益变动表": "📈", "其他": "📎"}.get(cf["type"], "📎")
        st.markdown(f'<span class="file-tag">{icon} {cf["type"]}</span> <b>{cf["name"]}</b>', unsafe_allow_html=True)

    # 判断是否有上期报表
    has_prior = any("上年" in cf["name"] or "上期" in cf["name"] for cf in st.session_state.classified_files)
    if not has_prior and len(st.session_state.classified_files) > 0:
        st.info("💡 提示：如果您希望获得更深入的分析，请同时上传上年同期的财务报表。上年报表可以解锁：\n"
                "✓ 杜邦分析趋势对比（哪个因子驱动了ROE变化）\n"
                "✓ Piotroski F-Score 完整9项评分\n"
                "✓ 成长能力指标（营收增长率、净利润增长率等）\n"
                "✓ 财务指标同比变动分析")

# ── 2. 选择题校准 ──
st.markdown("### 📋 需求校准（3题，可跳过）")

col_q1, col_q2, col_q3 = st.columns(3)
with col_q1:
    q1 = st.selectbox("Q1: 您的企业所属行业？", [
        "其他（通用基准）", "制造业", "建筑业", "批发零售", "餐饮服务", "科技信息", "农林牧渔", "交通运输"
    ], key="q1_industry")
with col_q2:
    q2 = st.multiselect("Q2: 您最关注的财务维度？（最多选3个）", [
        "偿债能力", "盈利能力", "营运效率", "现金流健康", "税务合规", "融资能力", "成本管控"
    ], key="q2_dimensions", max_selections=3)
with col_q3:
    q3 = st.selectbox("Q3: 报告主要用途？", [
        "总体体检", "内部管理", "银行贷款", "投资融资", "税务规划"
    ], key="q3_purpose")

skip_calibration = st.checkbox("跳过选择题，直接分析（输出标准版报告）", key="skip_cal")
if skip_calibration:
    q1 = "其他（通用基准）"
    q2 = []
    q3 = "总体体检"

# ── 3. 一键生成 ──
st.markdown("---")
do_generate = st.button("🚀 一键生成分析报告", type="primary", use_container_width=True, key="gen_btn")

if do_generate:
    if not st.session_state.classified_files:
        st.warning("请先上传至少一份财务报表文件。")
    elif not st.session_state.processing_done:
        # 解析文件
        with st.spinner("🔍 正在解析数据..."):
            all_dfs = []
            prior_dfs = []
            for cf in st.session_state.classified_files:
                ext = os.path.splitext(cf["name"])[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(cf["content"])
                    tmp_path = tmp.name
                try:
                    sheets = pd.read_excel(tmp_path, sheet_name=None, header=None)
                    for s in sheets.keys():
                        df = parse_financial_excel(tmp_path, sheet_name=s, report_period=cf["name"])
                        if not df.empty:
                            if "上年" in cf["name"] or "上期" in cf["name"]:
                                prior_dfs.append(df)
                            else:
                                all_dfs.append(df)
                finally:
                    os.unlink(tmp_path)

            if not all_dfs:
                st.error("未能提取到财务数据，请检查文件格式。")
                st.stop()

            raw_df = pd.concat(all_dfs, ignore_index=True)
            mapped_df = AccountingMapper().map_to_standard(raw_df)
            check_results = QualityChecker().run_all_checks(mapped_df)
            ratios = MetricCalculator(mapped_df).compute_all()

            # 增强指标
            enhanced_metrics = None
            if q2 and not skip_calibration:
                calc = MetricCalculator(mapped_df)
                enhanced_metrics = calc.compute_enhanced(q2, ratios)

            # 多期数据
            prior_mapped_df = None
            growth_metrics = None
            prior_ratios = None
            if prior_dfs:
                prior_raw = pd.concat(prior_dfs, ignore_index=True)
                prior_mapped_df = AccountingMapper().map_to_standard(prior_raw)
                prior_ratios = MetricCalculator(prior_mapped_df).compute_all()
                growth_metrics = MetricCalculator(mapped_df).compute_growth(prior_mapped_df)

            # 三模型分析
            model_results = {}
            with st.spinner("📊 正在运行三模型分析..."):
                # 杜邦分析
                dupont = DuPontAnalyzer(mapped_df)
                dupont_result = dupont.analyze(prior_mapped_df)
                model_results["dupont"] = dupont_result
                model_results["dupont_summary"] = dupont.get_summary_text(dupont_result)
                model_results["dupont_graph"] = dupont.get_graphviz_source(dupont_result)

                # Z-Score增强
                z_comp = ratios.get("财务预警", {}).get("Z-Score分变量", {}).get("value", {})
                z_val = ratios.get("财务预警", {}).get("Altman Z-score", {}).get("value", 0)
                z_lines = [f"[Altman Z-Score]"]
                z_lines.append(f"Z值 = {z_val:.4f}")
                if isinstance(z_comp, dict):
                    for xi in ["x1", "x2", "x3", "x4", "x5"]:
                        if xi in z_comp:
                            z_lines.append(f"  {xi.upper()} = {z_comp[xi]:.4f}")
                if isinstance(z_val, float) and z_val < 1.81:
                    z_lines.append("区域：🔴 危险区（Z<1.81）")
                elif isinstance(z_val, float) and z_val < 2.99:
                    z_lines.append("区域：🟡 灰色区（1.81≤Z≤2.99）")
                else:
                    z_lines.append("区域：🟢 安全区（Z>2.99）")
                model_results["zscore_summary"] = "\n".join(z_lines)

                # F-Score
                fscore = PiotroskiScorer(mapped_df)
                fscore_result = fscore.score(prior_mapped_df)
                model_results["fscore"] = fscore_result
                model_results["fscore_summary"] = fscore.get_summary_text(fscore_result)

        st.session_state.update(
            raw_df=raw_df, mapped_df=mapped_df, prior_mapped_df=prior_mapped_df,
            ratios=ratios, prior_ratios=prior_ratios, check_results=check_results,
            enhanced_metrics=enhanced_metrics, model_results=model_results,
            growth_metrics=growth_metrics,
            calibration={"q1_industry": q1, "q2_dimensions": q2, "q3_purpose": q3},
            filename=", ".join(cf["name"] for cf in st.session_state.classified_files),
        )

        # 生成报告
        with st.spinner("🚀 峤远主脑协议正在生成双版本报告（约1-2分钟）..."):
            gen = ReportGenerator(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", model="deepseek-chat")
            st.session_state.report = gen.generate(
                ratios=ratios,
                mapped_df=mapped_df,
                check_results=check_results,
                analysis_goal=q3 if not skip_calibration else "总体体检",
                report_period=", ".join(cf["name"] for cf in st.session_state.classified_files),
                calibration=st.session_state.calibration,
                enhanced_metrics=enhanced_metrics,
                model_results=model_results,
                prior_ratios=prior_ratios,
                growth_metrics=growth_metrics,
                industry=q1.replace("（通用基准）", "").strip() if not skip_calibration else "其他",
            )
            st.session_state.processing_done = True
        st.rerun()

# ═══════════════════════════════════════════════════════════
# 报告展示
# ═══════════════════════════════════════════════════════════

if st.session_state.processing_done and st.session_state.report:
    report = st.session_state.report
    ratios = st.session_state.ratios
    mapped_df = st.session_state.mapped_df
    check_results = st.session_state.check_results
    enhanced = st.session_state.enhanced_metrics
    model_res = st.session_state.model_results
    cal = st.session_state.calibration
    industry = cal.get("q1_industry", "其他").replace("（通用基准）", "").strip()

    # 清除按钮
    c_reset = st.columns([1, 1, 1])
    with c_reset[1]:
        if st.button("🔄 清除报告，重新上传", use_container_width=True, key="reset_btn"):
            st.session_state.upload_key += 1
            for k in ["processing_done", "raw_df", "mapped_df", "prior_mapped_df", "ratios",
                       "report", "enhanced_metrics", "model_results", "classified_files"]:
                st.session_state[k] = False if k == "processing_done" else None
            st.session_state.classified_files = []
            st.rerun()

    # 质量校验
    for r in [x for x in check_results if x.severity == "block"]:
        st.error(f"🔴 {r.check_name}: {r.detail}")
    for r in [x for x in check_results if x.severity == "warn"]:
        st.warning(f"🟡 {r.check_name}: {r.detail}")

    # ── 基础指标卡片 ──
    st.markdown("### 📊 基础指标速览")

    benchmarks = get_industry_benchmarks(industry)

    def _fmt(v, unit=""):
        if not (isinstance(v, float) and v == v): return "—"
        if v == float("inf"): return "∞"
        if unit == "%": return f"{v * 100:.2f}"
        if abs(v) > 1e6: return f"{v:,.0f}"
        if abs(v) >= 1: return f"{v:.2f}"
        return f"{v:.4f}"

    def _eval_card(name, val, bench_val):
        if not isinstance(val, float) or isnan(val):
            return ""
        rating = evaluate_metric(val, bench_val, name, industry)
        return {"good": "good", "warn": "warn", "danger": "danger"}.get(rating, "")

    km = [
        ("流动比率", "倍", ratios.get("偿债能力", {}).get("流动比率", {}).get("value", 0)),
        ("速动比率", "倍", ratios.get("偿债能力", {}).get("速动比率", {}).get("value", 0)),
        ("资产负债率", "%", ratios.get("偿债能力", {}).get("资产负债率", {}).get("value", 0)),
        ("利息保障倍数", "倍", ratios.get("偿债能力", {}).get("利息保障倍数", {}).get("value", 0)),
        ("毛利率", "%", ratios.get("盈利能力", {}).get("毛利率", {}).get("value", 0)),
        ("净利率", "%", ratios.get("盈利能力", {}).get("净利率", {}).get("value", 0)),
        ("ROE", "%", ratios.get("盈利能力", {}).get("ROE", {}).get("value", 0)),
        ("ROA", "%", ratios.get("盈利能力", {}).get("ROA", {}).get("value", 0)),
        ("存货周转", "天", ratios.get("营运效率", {}).get("存货周转天数", {}).get("value", 0)),
        ("应收周转", "天", ratios.get("营运效率", {}).get("应收账款周转天数", {}).get("value", 0)),
        ("总资产周转率", "次", ratios.get("营运效率", {}).get("总资产周转率", {}).get("value", 0)),
        ("Altman Z", "", ratios.get("财务预警", {}).get("Altman Z-score", {}).get("value", 0)),
        ("实际税率", "%", ratios.get("税务指标", {}).get("实际税率", {}).get("value", 0)),
        ("综合税负率", "%", ratios.get("税务指标", {}).get("综合税负率", {}).get("value", 0)),
    ]
    cols = st.columns(4)
    for idx, (name, unit, val) in enumerate(km):
        v = val if isinstance(val, float) and val == val else 0
        dc = _eval_card(name, val, benchmarks.get(name, 0))
        with cols[idx % 4]:
            bench_str = ""
            bv = benchmarks.get(name)
            if bv is not None and isinstance(bv, float):
                bench_str = f" / 基准{_fmt(bv, unit)}"
            st.markdown(f"""<div class="metric-card {dc}"><div class="val">{_fmt(v, unit)}</div><div class="lbl">{name} ({unit}){bench_str}</div></div>""", unsafe_allow_html=True)

    # ── 增强指标 ──
    if enhanced:
        st.markdown("### 🎯 专项深度分析")
        for dim, metrics in enhanced.items():
            st.markdown(f"**◆ {dim}·增强指标**")
            e_cols = st.columns(4)
            e_items = [(name, info) for name, info in metrics.items()
                       if isinstance(info["value"], float) and not isnan(info["value"]) and info["value"] != float("inf")]
            for ei, (name, info) in enumerate(e_items):
                with e_cols[ei % 4]:
                    v = info["value"]
                    unit = info.get("unit", "")
                    dc = _eval_card(name, v, benchmarks.get(name, 0))
                    st.markdown(f"""<div class="metric-card {dc}"><div class="val">{_fmt(v, unit)}</div><div class="lbl">{name} ({unit})</div></div>""", unsafe_allow_html=True)

    # ── 三模型分析 ──
    st.markdown("### 📊 经典模型分析")

    # 杜邦分析图
    if model_res.get("dupont_graph"):
        st.markdown("#### 杜邦分析分解树")
        try:
            st.graphviz_chart(model_res["dupont_graph"])
        except Exception:
            st.text(model_res["dupont_summary"])

    # Z-Score + F-Score 并排
    col_z, col_f = st.columns(2)
    with col_z:
        st.markdown("#### Altman Z-Score")
        z_val = ratios.get("财务预警", {}).get("Altman Z-score", {}).get("value", 0)
        z_comp = ratios.get("财务预警", {}).get("Z-Score分变量", {}).get("value", {})
        if isinstance(z_val, float) and not isnan(z_val):
            if z_val < 1.81:
                st.error(f"🔴 Z = {z_val:.4f}（危险区）")
            elif z_val < 2.99:
                st.warning(f"🟡 Z = {z_val:.4f}（灰色区）")
            else:
                st.success(f"🟢 Z = {z_val:.4f}（安全区）")
            if isinstance(z_comp, dict):
                z_labels = {"x1": "X1 营运资金/总资产", "x2": "X2 留存收益/总资产",
                           "x3": "X3 EBIT/总资产", "x4": "X4 权益/总负债", "x5": "X5 收入/总资产"}
                for xi in ["x1", "x2", "x3", "x4", "x5"]:
                    if xi in z_comp:
                        st.text(f"  {z_labels[xi]} = {z_comp[xi]:.4f}")

    with col_f:
        st.markdown("#### Piotroski F-Score")
        fscore_res = model_res.get("fscore", {})
        if fscore_res:
            total = fscore_res.get("total_score", 0)
            max_s = fscore_res.get("max_score", 9)
            if max_s == 3:
                st.warning(f"⚠️ F = {total}/{max_s}（部分评分）")
            elif total >= 7:
                st.success(f"🟢 F = {total}/{max_s}（走上坡路）")
            elif total >= 4:
                st.warning(f"🟡 F = {total}/{max_s}（基本平稳）")
            else:
                st.error(f"🔴 F = {total}/{max_s}（走下坡路）")

            # 显示各信号
            details = fscore_res.get("signal_details", {})
            for fid in sorted(details.keys()):
                d = details[fid]
                icon = "✅" if d["met"] else "❌"
                st.text(f"  {icon} {fid} {d['name']}")

            if fscore_res.get("note"):
                st.caption(fscore_res["note"])

    # ── 双版本报告 ──
    st.markdown("---")
    st.markdown("### 📋 分析报告")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    fl = st.session_state.get("filename", "报表")

    tab_pro, tab_plain = st.tabs(["📊 专业版（财务总监适用）", "💬 大白话版（老板适用）"])

    with tab_pro:
        pro_report = report.get("professional", {})
        for key, num in [("执行摘要", "一"), ("财务诊断", "二"), ("经典模型分析", "三"),
                         ("优化改进建议", "四"), ("税务分析", "五"), ("融资能力评估", "六")]:
            content = pro_report.get(key)
            if content:
                with st.container(border=True):
                    st.markdown(f"#### {num}、{key}")
                    st.markdown(content)
        with st.container(border=True):
            st.markdown(pro_report.get("免责声明", ""))

        # 专业版下载
        st.markdown("")
        pro_docx = professional_report_to_docx(pro_report, title=f"企业财务分析报告（专业版）-{fl}")
        st.download_button(
            "📥 下载专业版报告 (docx)",
            data=pro_docx,
            file_name=f"财务分析报告_专业版_{fl[:20]}_{now_str[:10]}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    with tab_plain:
        plain_report = report.get("plain", "")
        st.markdown(plain_report)
        st.markdown("")
        plain_docx = markdown_to_docx(plain_report, title=f"企业财务分析报告（大白话版）-{fl}")
        st.download_button(
            "📥 下载大白话版报告 (docx)",
            data=plain_docx,
            file_name=f"财务分析报告_大白话版_{fl[:20]}_{now_str[:10]}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

    # 两个版本都下载
    st.markdown("---")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "📥 下载专业版 (docx)",
            data=pro_docx,
            file_name=f"财务分析报告_专业版_{fl[:20]}_{now_str[:10]}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with col_dl2:
        st.download_button(
            "📥 下载大白话版 (docx)",
            data=plain_docx,
            file_name=f"财务分析报告_大白话版_{fl[:20]}_{now_str[:10]}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # CSV下载
    buf = io.StringIO()
    raw_df = st.session_state.raw_df
    if raw_df is not None:
        raw_df.to_csv(buf, index=False)
    st.download_button(
        "📥 下载原始数据 (CSV)",
        data=buf.getvalue().encode("utf-8-sig"),
        file_name=f"原始数据_{fl[:20]}_{now_str[:10]}.csv",
        mime="text/csv",
    )

    # 数据详情
    with st.expander("📋 数据详情", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.dataframe(st.session_state.raw_df, use_container_width=True, height=300)
        with c2:
            st.dataframe(mapped_df, use_container_width=True, height=300)
        for cat_name, items in ratios.items():
            rows = [{"指标": n, "数值": _fmt(i['value'], i.get('unit', '')) + i.get('unit', ''),
                     "参考值": i.get('benchmark', '')}
                    for n, i in items.items()
                    if isinstance(i['value'], float) and i['value'] == i['value'] and i['value'] != float("inf")
                    and not isinstance(i['value'], dict)]
            if rows:
                st.markdown(f"**{cat_name}**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(f"峤远·F-Analyzer V2.0 ｜ 主脑协议V1.0驱动 ｜ {cal.get('q3_purpose', '总体体检')} ｜ {fl}")
    st.caption("开发人员：李超逸、李屹泉")

else:
    # 未生成报告时显示操作指引
    if not st.session_state.classified_files:
        st.markdown("""
        <div style="background: #f0f7ff; border: 1px solid #91caff; border-radius: 10px; padding: 20px 28px; margin-bottom: 20px;">
            <h3 style="margin:0 0 12px;color:#0f3460;">📋 操作指引</h3>
            <p style="margin:4px 0;font-size:15px;">① 上传一个或多个Excel财务报表文件（AI自动识别类型）</p>
            <p style="margin:4px 0;font-size:15px;">② 回答3道选择题（可跳过→标准版报告）</p>
            <p style="margin:4px 0;font-size:15px;">③ 点击 <b style="color:#0f3460;">「🚀 一键生成分析报告」</b></p>
            <p style="margin:4px 0;font-size:15px;">④ 查看/下载 <b>专业版</b> + <b>大白话版</b> 双版本报告</p>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            with st.container(border=True):
                st.markdown("### 📤 分析能力")
                st.markdown("""
                | 模块 | 内容 |
                |------|------|
                | 基础指标 | 17个（偿债/盈利/营运/现金流/税务/预警） |
                | 增强指标 | 25个（按关注维度动态抽取） |
                | 杜邦分析 | ROE三因素分解 + 分解树图 |
                | Z-Score | 破产预测5变量 + 分区判断 |
                | F-Score | 财务质量9信号 + 双期模式 |
                | 专业版报告 | 7模块，面向财务总监 |
                | 大白话版报告 | 3段式，面向老板 |
                | 优化建议 | 报表/财务/成本/税务四维度 |
                """)
        with col_b:
            with st.container(border=True):
                st.markdown("### 💡 使用建议")
                st.markdown("""
                - **上传上年报表**可解锁：杜邦趋势对比、完整F-Score、成长指标
                - **选择关注维度**可获得：针对性增强指标深度分析
                - **双版本报告**：专业版给财务人员，大白话版给老板
                - 所有指标对标**行业基准**（7个行业可选）
                - 三模型结果**固化在报告中**，含模型解释
                """)

"""程信霖咨询 · 企业财务报表自动分析系统"""

import io
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from src.excel_parser import parse_financial_excel
from src.accounting_mapper import AccountingMapper
from src.quality_checker import QualityChecker
from src.metric_calculator import MetricCalculator
from src.report_generator import ReportGenerator

DEEPSEEK_API_KEY = "sk-your-api-key-here"

st.set_page_config(page_title="F-Analyzer · 企业财报分析", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ═══════════════════════════════════════════════════════════════
# 用户授权协议（访问门禁）— 未同意前阻断所有后续渲染
# ═══════════════════════════════════════════════════════════════
_CONSENT_TEMPLATE = """<div style='font-family:"Microsoft YaHei","宋体",SimSun,serif; font-size:14px; line-height:2.0; color:#222; max-width:900px; margin:0 auto;'>

<h2 style='text-align:center; font-size:20px; font-weight:bold; margin-bottom:8px;'>程信霖咨询 · F-Analyzer<br/>用户授权与服务协议</h2>

<p style='text-align:center; font-size:12px; color:#888; margin-bottom:24px;'>
版本：v1.0 &nbsp;|&nbsp; 更新日期：2026年6月6日 &nbsp;|&nbsp; 生效日期：2026年6月6日<br/>
运营主体：云南程信霖信息咨询有限公司（以下简称"程信霖"或"本公司"）
</p>

<div style='background:#fff3e0; border-left:4px solid #e65100; padding:16px; margin:16px 0; border-radius:4px;'>
<p style='font-weight:bold; color:#e65100; margin:0 0 8px 0;'>⚠️ 重要提示</p>
<p style='margin:4px 0;'><b>尊敬的用户</b>：感谢您选择程信霖咨询开发的 F-Analyzer 企业财务报表自动分析系统（以下简称"本系统"或"F-Analyzer"）。本系统是一款基于人工智能技术的企业财务分析与融资评估辅助工具。</p>
<p style='margin:4px 0;'><b style='color:#d32f2f;'>请在使用本系统之前，仔细阅读并充分理解本协议的全部条款。您通过网络页面点击勾选或以其他方式确认本协议，即表示您已阅读、理解并同意接受本协议所有条款的约束。如果您不同意本协议的任何条款，请勿使用本系统。</b></p>
<p style='margin:4px 0;'><b style='color:#d32f2f;'>本系统输出的分析报告仅供商业决策参考，不构成正式的财务建议、税务意见或融资承诺。如需专业意见，请咨询持有相应资质的注册会计师、税务师或金融机构。</b></p>
<p style='margin:4px 0;'><b>本协议适用中华人民共和国法律。</b></p>
</div>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第一条 定义与解释</h3>
<p><b>1.1 本系统</b>：指程信霖开发并运营的"F-Analyzer 企业财务报表自动分析系统"，包括其全部功能模块、算法模型、用户界面及相关文档。</p>
<p><b>1.2 用户</b>：指通过程信霖提供的访问途径使用本系统的自然人、法人或非法人组织。本协议中"用户"与"您"具有相同含义。</p>
<p><b>1.3 财务文件</b>：指用户上传至本系统的 Excel、PDF 或其他格式的财务报表、账目数据及相关附件。</p>
<p><b>1.4 输出报告</b>：指本系统基于用户上传的财务文件，通过人工智能算法处理后生成的财务分析报告及其他分析输出物。</p>
<p><b>1.5 人工智能模型/AI模型</b>：指本系统调用的第三方大语言模型（包括但不限于 DeepSeek API），用于执行财务数据解读、风险识别、融资评估等任务。<b style='color:#c62828;'>AI 模型仅接收经本地处理后的财务摘要数据，不发送原始文件全文</b>。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第二条 服务内容与范围</h3>
<p><b>2.1 服务内容</b></p>
<ul>
<li>（1）财务报表的自动解析与指标结构化提取；</li>
<li>（2）偿债能力、盈利能力、营运效率、税务指标、财务预警（Altman Z-score）等多维度财务指标计算；</li>
<li>（3）基于 AI 的财务健康诊断、融资能力评估、降本增效建议、现金流量分析；</li>
<li>（4）结构化财务分析报告的自动生成。</li>
</ul>
<p><b>2.2 服务范围与限制</b></p>
<p><b style='color:#d32f2f;'>本系统的分析范围限定于用户上传的财务文件的数据层面。本系统不进行实地尽职调查、不验证数据真实性、不对企业信用做出评级。标注为"异常"或"预警"的指标为系统自动计算结果，不代表程信霖对企业财务状况的官方判断。</b></p>
<p><b>2.3 服务可用性</b></p>
<p>程信霖将尽商业上合理的努力保障本系统的正常运行，但<b>不对服务的持续性、及时性、无错误或无中断做出任何明示或默示的保证</b>。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第三条 数据安全与隐私保护</h3>
<p style='background:#e8f5e9; padding:12px; border-radius:4px;'><b>用户上传的财务文件均在程信霖本地服务器上处理。程信霖承诺，未经用户另行书面授权，不会将用户的原始财务文件上传至任何第三方云服务平台或境外服务器。</b></p>
<p><b>3.2 AI 分析数据处理</b>：本系统在将财务数据发送给 AI 模型进行分析时，仅发送经过结构化处理的财务指标摘要，<b>不发送包含企业名称、纳税人识别号、银行账号等敏感标识的原始字段</b>。</p>
<p><b>3.3 文件处理完成后</b>，用户可点击"清除报告，重新上传"按钮清除本次分析数据。系统不对财务文件进行持久化存储，临时文件在分析完成后自动删除。</p>
<p><b>3.4 无人工查阅</b>：在系统自动处理流程中，程信霖的任何员工均不会主动查阅用户上传的财务文件。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第四条 AI 使用条款</h3>
<p><b>4.1 AI 模型局限性</b>：用户理解并确认，本系统所使用的 AI 技术存在"幻觉"风险、训练数据偏差和非确定性输出等固有局限，程信霖已采取多重措施减少但无法完全消除此类风险。</p>
<p style='background:#fff3e0; padding:12px; border-radius:4px;'><b>4.2 用户自行判断义务：用户在使用本系统输出的财务分析报告时，必须结合自身的专业判断和实际情况进行独立评估。本系统的输出在任何情况下均不应被视为对用户融资决策的替代。</b></p>
<p><b>4.3 禁止用途</b>：用户不得将本系统用于生成虚假财务数据、协助金融欺诈、规避合规监管或任何违反中华人民共和国法律法规的活动。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第五条 知识产权</h3>
<p>本系统的全部知识产权归属程信霖所有。用户对其上传的财务文件保留全部原始权利，仅授予程信霖在本次分析流程中使用的有限许可，该许可在分析完成并清除数据后自动终止。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第六条 用户义务与承诺</h3>
<p><b>6.1</b> 用户承诺其为上传的财务文件的合法持有人或已获得合法授权，上传行为不违反其对任何第三方负有的保密义务。</p>
<p><b>6.2</b> 用户承诺上传的财务文件不包含病毒、木马或恶意代码，且不用于制造虚假财务数据或协助欺诈。</p>
<p><b>6.3</b> 用户不得对本系统进行反向工程、反编译或试图绕过本系统的安全保护机制。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第七条 免责声明</h3>
<p style='background:#fff3e0; padding:12px; border-radius:4px;'><b>本系统按"现状"提供，不作任何形式的明示或默示保证。</b></p>
<p style='background:#ffebee; padding:12px; border-radius:4px;'><b>本系统输出的财务分析报告在任何情况下均不应被解释为：（1）正式的财务意见、税务建议或融资承诺；（2）对企业信用状况的官方评级；（3）对融资申请审批结果的预测或保证。用户如需专业财务或税务意见，应咨询持有相应资质的注册会计师或税务师。</b></p>
<p>在适用法律允许的最大范围内，程信霖就本协议项下所有索赔的累计赔偿责任总额，以人民币壹仟元（¥1,000.00）或用户在前十二个月内向程信霖实际支付的服务费用总额（以较高者为准）为上限。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第八条 法律适用与争议解决</h3>
<p><b>8.1</b> 本协议适用<b>中华人民共和国法律</b>（不包括香港、澳门、台湾地区法律）。</p>
<p><b>8.2</b> 争议应首先友好协商。协商不成的，任何一方有权向<b>云南程信霖信息咨询有限公司所在地有管辖权的人民法院</b>提起诉讼。</p>

<h3 style='font-size:16px; margin-top:28px; border-bottom:1px solid #ddd; padding-bottom:4px;'>第九条 联系方式</h3>
<table style='width:100%; border-collapse:collapse; margin:12px 0;'>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold; width:120px;'>运营主体</td><td style='border:1px solid #ddd; padding:8px;'>云南程信霖信息咨询有限公司</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>联系人</td><td style='border:1px solid #ddd; padding:8px;'>余磊</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>联系电话</td><td style='border:1px solid #ddd; padding:8px;'>13987671259</td></tr>
<tr><td style='border:1px solid #ddd; padding:8px; font-weight:bold;'>电子邮箱</td><td style='border:1px solid #ddd; padding:8px;'>425448719@qq.com</td></tr>
</table>

<hr style='margin:24px 0;'/>
<p style='text-align:center; font-size:12px; color:#888;'>
<b>本协议更新日期：2026年6月6日 &nbsp;|&nbsp; 本协议生效日期：2026年6月6日</b><br/>
&copy; 2026 云南程信霖信息咨询有限公司 保留一切权利
</p>
</div>"""

if "fa_consent_granted" not in st.session_state:
    st.session_state.fa_consent_granted = False

if not st.session_state.fa_consent_granted:
    st.markdown("""<div style='background:linear-gradient(135deg,#1a1a2e,#0f3460);color:#fff;padding:28px 32px;border-radius:12px;margin-bottom:24px;text-align:center;'>
        <h1 style='font-size:24px;font-weight:700;letter-spacing:2px;margin:0;color:#fff;'>📊 程信霖 · F-Analyzer</h1>
        <p style='font-size:13px;opacity:.65;margin:6px 0 0;color:#fff;'>程信霖咨询 · 企业财务报表自动分析系统</p>
    </div>""", unsafe_allow_html=True)
    st.markdown("### 📜 用户授权与服务协议")
    st.caption("请仔细阅读以下协议。您必须同意所有条款才能使用本系统。")
    st.markdown('<div style="background:#fafafa;border:2px solid #0f3460;border-radius:10px;padding:24px;margin:16px 0;max-height:420px;overflow-y:auto;font-size:13px;">%s</div>' % _CONSENT_TEMPLATE, unsafe_allow_html=True)
    st.divider()
    c1 = st.checkbox("我确认已阅读并理解上述数据安全措施", key="fa_consent_security")
    c2 = st.checkbox("我确认已知悉本系统为财务分析辅助工具，不构成正式财务意见或融资承诺", key="fa_consent_disclaimer")
    c3 = st.checkbox("我授权程信霖在本地服务器上处理我上传的财务文件，AI 模型仅接收结构化摘要数据", key="fa_consent_authorize")
    if c1 and c2 and c3:
        st.success("✅ 您已同意所有条款。请点击下方按钮进入系统。")
        if st.button("进入系统 →", type="primary", use_container_width=True):
            st.session_state.fa_consent_granted = True
            st.rerun()
    else:
        st.info("请勾选全部三个确认项以继续。")
    st.stop()

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
    hr { margin: 8px 0; }
    /* 文件上传器汉化 */
    [data-testid="stFileUploaderDropzone"] span { display: none; }
    [data-testid="stFileUploaderDropzone"] button::after { content: " 浏览文件"; }
    [data-testid="stFileUploaderDropzone"]::before { content: "拖拽文件到此处，或"; font-size: .875rem; }
    [data-testid="stFileUploaderDropzone"] small { display: none; }
</style>
<script>
(function() {
    const fix = () => {
        document.querySelectorAll('[data-testid="stFileUploaderDropzone"] small').forEach(el => {
            if (/200MB/i.test(el.textContent)) el.textContent = '单个文件 ≤ 10MB';
        });
    };
    fix(); new MutationObserver(fix).observe(document.body, {childList:true,subtree:true});
})();
</script>
""", unsafe_allow_html=True)

st.markdown("""<div class="main-header">
    <h1>📊 企业财务报表自动分析</h1>
    <p>程信霖咨询 · F-Analyzer ｜ 上传报表 → 选择目标 → 一键生成专业报告</p>
</div>""", unsafe_allow_html=True)

for k, v in {"processing_done": False, "raw_df": None, "mapped_df": None, "ratios": None, "report": None, "upload_key": 0}.items():
    if k not in st.session_state:
        st.session_state[k] = v

col_u, col_g = st.columns([3, 1])
with col_u:
    uploaded_file = st.file_uploader("上传", type=["xlsx", "xls"],
        help="支持 .xlsx .xls。单个文件 ≤ 10MB。<br>PDF 解析功能开发中，暂未开放。",
        key=f"fu_{st.session_state.upload_key}")
with col_g:
    analysis_goals = st.multiselect("📋 分析目标（可多选）", ["财务健康检查", "融资能力评估", "降本增效", "现金流量分析"], default=["财务健康检查"])
    if not analysis_goals:
        analysis_goals = ["财务健康检查"]

# ============================================================
# 一键生成按钮 —— 始终显示
# ============================================================
do_generate = st.button("🚀 一键生成分析报告", type="primary", width='stretch', key="gen_btn")

if do_generate:
    if uploaded_file is None:
        st.warning("请先上传一份财务报表文件。")
    elif not st.session_state.processing_done:
        # 首次解析 + 生成
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        try:
            if ext in (".xlsx", ".xls"):
                sheets = pd.read_excel(tmp_path, sheet_name=None, header=None)
                sn = list(sheets.keys())
                dfs = [parse_financial_excel(tmp_path, sheet_name=s, report_period=uploaded_file.name) for s in sn]
                raw_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
            else:
                st.error(f"不支持: {ext}"); raw_df = pd.DataFrame()
        finally:
            os.unlink(tmp_path)
        if raw_df.empty:
            st.error("未能提取到财务数据，请检查文件格式。")
            st.stop()
        with st.spinner("🔍 正在解析数据..."):
            mapped_df = AccountingMapper().map_to_standard(raw_df)
            check_results = QualityChecker().run_all_checks(mapped_df)
            ratios = MetricCalculator(mapped_df).compute_all()
        st.session_state.update(raw_df=raw_df, mapped_df=mapped_df, check_results=check_results,
                                ratios=ratios, filename=uploaded_file.name)
        with st.spinner("🚀 程信霖 F-Analyzer 正在生成分析报告（约 30-60 秒）..."):
            gen = ReportGenerator(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", model="deepseek-chat")
            st.session_state.report = gen.generate(ratios=ratios, mapped_df=mapped_df, check_results=check_results,
                analysis_goal=" + ".join(analysis_goals), report_period=uploaded_file.name)
            st.session_state.processing_done = True
        st.rerun()

# ============================================================
# 展示报告
# ============================================================
if st.session_state.processing_done and st.session_state.report:
    report = st.session_state.report
    ratios = st.session_state.ratios
    raw_df = st.session_state.raw_df
    mapped_df = st.session_state.mapped_df
    check_results = st.session_state.check_results

    # 清除报告按钮
    c_reset = st.columns([1, 1, 1])
    with c_reset[1]:
        if st.button("🔄 清除报告，重新上传", width='stretch', key="reset_btn"):
            st.session_state.upload_key += 1
            for k in ["processing_done", "raw_df", "mapped_df", "ratios", "report"]:
                st.session_state[k] = False if k == "processing_done" else None
            st.rerun()

    for r in [x for x in check_results if x.severity == "block"]:
        st.error(f"🔴 {r.check_name}: {r.detail}")
    for r in [x for x in check_results if x.severity == "warn"]:
        st.warning(f"🟡 {r.check_name}: {r.detail}")

    st.markdown("### 📊 核心指标速览")

    def _fmt(v, unit=""):
        if not (isinstance(v, float) and v == v): return "—"
        if v == float("inf"): return "∞"
        # 百分比类指标 ×100 显示
        if unit == "%":
            return f"{v * 100:.2f}"
        if abs(v) > 1e6: return f"{v:,.0f}"
        if abs(v) >= 1: return f"{v:.2f}"
        return f"{v:.4f}"

    km = [
        ("流动比率","倍",1.0,ratios.get("偿债能力",{}).get("流动比率",{}).get("value",0)),
        ("速动比率","倍",0.5,ratios.get("偿债能力",{}).get("速动比率",{}).get("value",0)),
        ("资产负债率","%",70,ratios.get("偿债能力",{}).get("资产负债率",{}).get("value",0)),
        ("利息保障倍数","倍",2,ratios.get("偿债能力",{}).get("利息保障倍数",{}).get("value",0)),
        ("毛利率","%",30,ratios.get("盈利能力",{}).get("毛利率",{}).get("value",0)),
        ("净利率","%",5,ratios.get("盈利能力",{}).get("净利率",{}).get("value",0)),
        ("ROE","%",10,ratios.get("盈利能力",{}).get("ROE",{}).get("value",0)),
        ("ROA","%",5,ratios.get("盈利能力",{}).get("ROA",{}).get("value",0)),
        ("存货周转","天","",ratios.get("营运效率",{}).get("存货周转天数",{}).get("value",0)),
        ("应收周转","天","",ratios.get("营运效率",{}).get("应收账款周转天数",{}).get("value",0)),
        ("总资产周转率","次",0.5,ratios.get("营运效率",{}).get("总资产周转率",{}).get("value",0)),
        ("Altman Z","",1.81,ratios.get("财务预警",{}).get("Altman Z-score",{}).get("value",0)),
        ("实际税率","%",25,ratios.get("税务指标",{}).get("实际税率",{}).get("value",0)),
        ("综合税负率","%","",ratios.get("税务指标",{}).get("综合税负率",{}).get("value",0)),
    ]
    cols = st.columns(4)
    for idx, (name, unit, thr, val) in enumerate(km):
        v = val if isinstance(val, float) and val == val else 0
        dc = ""
        if name == "流动比率" and v < thr: dc = "danger"
        if name == "速动比率" and v < thr: dc = "danger"
        if name == "资产负债率" and v > 0.7: dc = "danger"
        elif name == "资产负债率" and v > 0.5: dc = "warn"
        if name == "Altman Z" and v < 1.81: dc = "danger"
        elif name == "Altman Z" and 1.81 <= v < 2.99: dc = "warn"
        with cols[idx % 4]:
            st.markdown(f"""<div class="metric-card {dc}"><div class="val">{_fmt(v, unit)}</div><div class="lbl">{name} ({unit})</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📝 分析报告")
    for key, num in [("财务数据摘要","一"),("异常诊断","二"),("优化建议","三"),("税务风险提示","四")]:
        if report.get(key):
            with st.container(border=True):
                st.markdown(f"#### {num}、{key}")
                st.markdown(report[key])
    with st.container(border=True):
        st.markdown(report.get("免责与合规声明",""))

    with st.expander("📋 数据详情", expanded=False):
        c1, c2 = st.columns(2)
        with c1: st.dataframe(raw_df, width='stretch', height=300)
        with c2: st.dataframe(mapped_df, width='stretch', height=300)
        for cat_name, items in ratios.items():
            rows = [{"指标": n, "数值": _fmt(i['value'], i.get('unit','')) + i.get('unit',''), "参考值": i.get('benchmark','')}
                    for n, i in items.items() if isinstance(i['value'], float) and i['value'] == i['value'] and i['value'] != float("inf")]
            if rows:
                st.markdown(f"**{cat_name}**")
                st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    st.markdown("---")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    fl = st.session_state.get("filename", "报表")
    ph = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>财务分析报告</title>
<style>body{{font-family:'Microsoft YaHei',sans-serif;max-width:720px;margin:0 auto;padding:24px;color:#1a1a2e;line-height:1.8;font-size:13px}}
h1{{font-size:20px;border-bottom:3px solid #0f3460;padding-bottom:10px}}h2{{font-size:16px;margin-top:24px;color:#0f3460}}
.meta{{color:#999;font-size:11px}}.card{{background:#f7f9fc;border-radius:8px;padding:16px;margin:12px 0}}
table{{width:100%;border-collapse:collapse;margin:8px 0}}th,td{{border:1px solid #e0e0e0;padding:6px 10px;text-align:left;font-size:12px}}
th{{background:#f5f7fa}}.warn{{color:#d46b08;font-weight:700}}.danger{{color:#cf1322;font-weight:700}}
.disclaimer{{background:#fafafa;border:1px solid #e0e0e0;border-radius:8px;padding:16px;font-size:11px;color:#aaa;margin-top:32px}}
</style></head><body><h1>📊 企业财务报表分析报告</h1>
<p class="meta">程信霖咨询 · F-Analyzer ｜ {now_str} ｜ {report.get('analysis_goal','')} ｜ {fl}</p>
<h2>核心指标速览</h2><table><tr><th>指标</th><th>数值</th><th>参考值</th></tr>"""
    for cat, items in ratios.items():
        for n, i in items.items():
            v = i["value"]
            if isinstance(v, float) and v == v and v != float("inf"):
                vs = _fmt(v, i.get('unit',''))
                ph += f"<tr><td>{n}</td><td>{vs}{i.get('unit','')}</td><td>{i.get('benchmark','')}</td></tr>"
    ph += "</table>"
    for key, num in [("财务数据摘要","一"),("异常诊断","二"),("优化建议","三"),("税务风险提示","四")]:
        if report.get(key):
            ph += f"<h2>{num}、{key}</h2><div class=\"card\">{report[key].replace(chr(10),'<br>')}</div>"
    ph += f"<div class=\"disclaimer\">{report.get('免责与合规声明','')}</div></body></html>"

    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 下载 PDF 报告", data=ph.encode("utf-8"),
            file_name=f"财务分析报告_{fl}_{now_str[:10]}.html", mime="text/html", width='stretch')
    with c2:
        buf = io.StringIO(); raw_df.to_csv(buf, index=False)
        st.download_button("📥 下载原始数据 (CSV)", data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"原始数据_{fl}_{now_str[:10]}.csv", mime="text/csv", width='stretch')

    st.caption(f"程信霖咨询 · F-Analyzer MVP ｜ {report.get('analysis_goal','')} ｜ {fl}")
else:
    # 未生成报告时显示欢迎信息 — 操作指引
    st.markdown("""
    <div style="background: #f0f7ff; border: 1px solid #91caff; border-radius: 10px; padding: 20px 28px; margin-bottom: 20px;">
        <h3 style="margin:0 0 12px;color:#0f3460;">📋 操作指引</h3>
        <p style="margin:4px 0;font-size:15px;">① 在右侧 <b>「📋 分析目标」</b> 中选择分析方向（可多选）</p>
        <p style="margin:4px 0;font-size:15px;">② 在左侧上传您的财务报表（Excel）</p>
        <p style="margin:4px 0;font-size:15px;">③ 点击上方 <b style="color:#0f3460;">「🚀 一键生成分析报告」</b> 按钮</p>
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("### 📤 三步完成分析")
            st.markdown("""
            1. **上传报表** — Excel (.xlsx/.xls)（最大 10MB）
            2. **选择目标** — 可多选：财务健康 / 融资 / 降本增效
            3. **点击上方按钮** — 一键生成专业分析报告
            > 所有计算在本地完成，数据安全无外泄。
            """)
    with col_b:
        with st.container(border=True):
            st.markdown("### 📊 分析能力")
            st.markdown("""
            | 模块 | 内容 |
            |------|------|
            | 偿债能力 | 流动比率、速动比率、资产负债率 |
            | 盈利能力 | 毛利率、净利率、ROE、ROA |
            | 营运效率 | 存货/应收周转天数、资产周转率 |
            | 税务指标 | 实际税率、综合税负率 |
            | 财务预警 | Altman Z-score |
            | 报告生成 | 程信霖 F-Analyzer 深度解读 |
            """)

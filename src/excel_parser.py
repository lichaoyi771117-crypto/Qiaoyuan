"""
Excel 财务报表解析引擎 v4

支持的客户报表格式:
1. 巨和物业：左右两栏式 [资产, 期末, 年初, 负债权益, 期末, 年初]  — 无行次
2. 磊鑫学校：带行次 [资产, 行次, 期初, 期末, 负债净资产, 行次, 期初, 期末]  — 有行次
"""
import re
from typing import Optional

import pandas as pd


def _is_row_number_series(series) -> bool:
    """检测列是否为行次编号 (1-200 小整数占比>=70%)"""
    nums = pd.to_numeric(series, errors="coerce").dropna()
    if len(nums) < 3:
        return False
    return ((nums == nums.astype(int)) & (nums >= 1) & (nums <= 200)).sum() >= 0.7 * len(nums)


def _is_numeric(val) -> bool:
    try:
        float(str(val).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _is_section_header(name: str) -> bool:
    """检测分类标题行，如 '流动资产：' '非流动资产：' '固定资产：'"""
    t = str(name).strip()
    for kw in ["流动资产", "非流动资产", "流动负债", "非流动负债",
               "固定资产", "无形资产", "长期投资", "所有者权益",
               "净资产", "股东权益"]:
        # 仅当关键字后面紧跟冒号时才判定为分类标题
        if t == kw + "：" or t == kw + ":":
            return True
    return False


def _is_meta(name: str) -> bool:
    t = str(name).strip()
    if not t or t.lower() == "nan":
        return True
    exact = {"资产", "负债", "行次", "年初数", "期末数", "期初数", "所有者权益",
             "股东权益", "净资产", "项目", "负债与所有者权益", "负债和所有者权益",
             "负债及净资产", "负债和净资产", "负债及所有者权益（或股东权益）",
             "负债和股东权益", "会企01表", "会企02表", "会企03表",
             "项    目", "行   次", "本期金额", "上期金额", "本年累计", "年末数",
             "附注", "附    注", "流动资产", "流动负债", "非流动资产", "非流动负债",
             "负债总计", "负债及所有者权益总计"}
    if t in exact:
        return True
    if "\n" in t:
        return True  # 跨行合并标题（如光华报表R0）
    for tt in ["资产负债表", "利润表", "现金流量表", "损益表",
               "资 产 负 债 表", "损 益 表", "所有者权益变动表"]:
        if tt in t:
            return True
    if t.startswith("编制单位") or t.startswith("编制："):
        return True
    if re.match(r"^\d{1,5}$", t) or re.match(r"^\d{4}-\d{2}-\d{2}", t):
        return True
    return False


def _classify_column_period(series) -> Optional[bool]:
    """
    扫描列的前 5 行，根据关键词判断是否为期末列。

    Returns:
        True: 期末列（期末数、年末数、期末余额等）
        False: 期初列（年初数、期初数、期初余额等）
        None: 无法判定
    """
    qimo_kw = {"期末", "年末", "期末数", "年末数", "期末余额", "本期", "本期金额", "本月数", "本年累计"}
    qichu_kw = {"年初", "期初", "年初数", "期初数", "期初余额", "上年", "上年数"}

    for i in range(min(5, len(series))):
        v = str(series.iloc[i]).strip() if pd.notna(series.iloc[i]) else ""
        for kw in qimo_kw:
            if kw in v:
                return True
        for kw in qichu_kw:
            if kw in v:
                return False
    return None


def _is_data_cell(name, val) -> bool:
    if not name or str(name).strip().lower() == "nan":
        return False
    if _is_meta(str(name)):
        return False
    if _is_section_header(str(name)):
        return False
    if not _is_numeric(val):
        return False
    try:
        v = float(str(val).replace(",", ""))
        if v == int(v) and 1 <= int(v) <= 200:
            return False
    except (ValueError, TypeError):
        return False
    return True


def _strip_name(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r"^[-–—]+", "", s)
    s = re.sub(r"^[一二三四五六七八九十]+[、.、．]\s*", "", s)
    s = re.sub(r"^(减：|减:|其中：|其中:|加：|加:|以下空白)", "", s)
    s = s.replace("　", "")
    s = re.sub(r"^\s+", "", s)
    return s


def parse_financial_excel(
    file_path: str,
    report_period: str = "未指定",
    sheet_name=0,
) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None, sheet_name=sheet_name).dropna(how="all")
    cols = df.shape[1]
    all_rows: list[dict] = []

    # +---- 1. 扫描前 5 行检测列含义（期初 vs 期末） ----+
    # 在小微企业报表中期初期末列位置经常互换，必须根据表头文字判断
    col_is_qimo = {}  # True = 期末/年末列, False = 期初/年初列, None = 未知
    for c in range(cols):
        col_is_qimo[c] = _classify_column_period(df[c])

    # +---- 2. 检测是否有行次列 ----+
    col_is_rn = {c: _is_row_number_series(df[c]) for c in range(cols)}
    has_rn = any(col_is_rn.values())

    if cols >= 5 and has_rn:
        # 有行次格式: col(0,1,2,3), col(4,5,6,7)
        for _, row in df.iterrows():
            for name_col, value_cols in [(0, [2, 3]), (4, [6, 7])]:
                if name_col >= cols:
                    continue
                name = row.iloc[name_col]
                if _is_meta(str(name)) or _is_section_header(str(name)):
                    continue
                # 优先选期末列，找不到再用期初列
                qimo_cols = [vc for vc in value_cols if col_is_qimo.get(vc) is True]
                qichu_cols = [vc for vc in value_cols if col_is_qimo.get(vc) is False]
                ordered_cols = qimo_cols + qichu_cols + value_cols
                for vc in ordered_cols:
                    if vc >= cols:
                        continue
                    val = row.iloc[vc]
                    if isinstance(val, str):
                        val = val.replace(",", "")
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        continue
                    if pd.notna(val):
                        all_rows.append({
                            "科目名称": _strip_name(name),
                            "金额": float(val),
                            "报告期": report_period,
                        })
    elif cols >= 5:
        # 无行次格式（巨和物业、艾维集团合并等 6 列报表）
        for _, row in df.iterrows():
            for name_col in [0, 3]:
                if name_col >= cols:
                    continue
                name = row.iloc[name_col]
                # 在 name_col 右边的两列中优先选期末列
                val_cols = [c for c in [name_col + 1, name_col + 2, name_col + 3] if c < cols]
                qimo_first = sorted(val_cols, key=lambda c: 0 if col_is_qimo.get(c) is True else 1)
                for vc in qimo_first:
                    val = row.iloc[vc]
                    if isinstance(val, str):
                        val = val.replace(",", "")
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        continue
                    if pd.notna(val) and _is_data_cell(name, val):
                        all_rows.append({"科目名称": _strip_name(name),
                                         "金额": float(val),
                                         "报告期": report_period})
                        break
    else:
        for _, row in df.iterrows():
            name = row.iloc[0]
            for c in range(1, cols):
                if _is_data_cell(name, row.iloc[c]):
                    val = row.iloc[c]
                    if isinstance(val, str):
                        val = val.replace(",", "")
                    all_rows.append({
                        "科目名称": _strip_name(name),
                        "金额": float(val),
                        "报告期": report_period,
                    })

    result = pd.DataFrame(all_rows)
    if not result.empty and "科目名称" in result.columns:
        result = result[["科目名称", "金额", "报告期"]]
    return result

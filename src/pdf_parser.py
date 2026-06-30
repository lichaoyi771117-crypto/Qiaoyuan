"""
PDF 财务报表解析引擎 v2

基于 PyMuPDF 的电子版 PDF 解析，支持两类布局：
- ROW_NUM: 有行次编号列，科目/行次/数值分列清晰
- SPLIT_LINE: 无行次号，左右双栏，科目与数字跨行交替

设计原则:
1. 电子版 PDF (有文本层)，不做 OCR
2. 复用 excel_parser 的工具函数 (节标题过滤、期初期末识别、科目名清洗)
3. 通过前 5 行自动检测布局模式，无需人工指定
"""
import os
import re
from collections import defaultdict
from typing import List, Optional, Tuple

import pandas as pd
import pymupdf

from src.excel_parser import (  # type: ignore[import-untyped]
    _is_section_header,
    _is_meta,
    _classify_column_period,
    _strip_name,
)

_NUM = re.compile(r"^-?[\d,]+\.?\d+$")
_RN = re.compile(r"^\d{1,3}$")  # 行次号: 1-3位纯数字


def _is_row_number(token: str) -> bool:
    """判断 token 是否为行次编号 (1-200 的整数, 不带千分位逗号)。"""
    if not _RN.match(token):
        return False
    try:
        v = int(token)
        return 1 <= v <= 200
    except ValueError:
        return False

# ---- 扫描件检测 ----


def _is_scanned(file_path: str, sample_pages: int = 3) -> bool:
    """检测 PDF 是否为扫描件 (无文本层)。"""
    doc = pymupdf.open(file_path)
    try:
        total = 0
        n = min(sample_pages, len(doc))
        for p in range(n):
            total += len(doc[p].get_text().strip())
        avg = total / n if n > 0 else 0
        return avg < 50  # 平均每页 < 50 字符 → 扫描件
    finally:
        doc.close()


# ---- 布局模式检测 ----


def _detect_layout_mode(pages: list[pymupdf.Page], max_check_lines: int = 40) -> str:
    """检测 PDF 布局模式: ROW_NUM (有行次号列) 或 SPLIT_LINE (无行次号)。

    扫描前 max_check_lines 行: 如果存在 ≥3 行的纯数字 token
    且分布在 50-250 的 x 范围内 → ROW_NUM 模式, 否则 → SPLIT_LINE 模式。
    """
    row_num_hits = 0

    for page in pages[:1]:  # 只查首页
        blocks = page.get_text("dict").get("blocks", [])
        line_count = 0
        for b in blocks:
            if b.get("type") != 0:
                continue
            for line in b["lines"]:
                if line_count >= max_check_lines:
                    break
                line_count += 1
                for span in line["spans"]:
                    x = round(span["bbox"][0])
                    for t in span["text"].strip().split():
                        t = t.strip()
                        if re.match(r"^\d{1,3}$", t) and 50 < x < 250:
                            row_num_hits += 1
                            if row_num_hits >= 3:
                                return "ROW_NUM"
            if line_count >= max_check_lines:
                break

    return "SPLIT_LINE"


# ---- 核心解析 ----


def _extract_rows(page: pymupdf.Page) -> list[dict]:
    """从一页提取所有 (y, x, token) 三元组 并按 y 层分组。

    Returns:
        [(y, [(x, token)])] — y 层按升序排列。
    """
    y_map: dict[int, list[tuple[float, str]]] = defaultdict(list)

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            y_center = round((line["bbox"][1] + line["bbox"][3]) / 2)
            for span in line["spans"]:
                x = round(span["bbox"][0])
                text = span["text"].strip()
                if not text or text == "-":
                    continue
                # 拆分 span 中的 token
                for token in text.split():
                    token = token.strip()
                    if not token or token == "-":
                        continue
                    y_map[y_center].append((x, token))

    # 去重: 同一 y 层同一 token 只保留 x 最小的
    deduped: list[tuple[int, list[tuple[float, str]]]] = []
    for y in sorted(y_map.keys()):
        seen_tokens: set[str] = set()
        uniq: list[tuple[float, str]] = []
        for x, t in sorted(y_map[y], key=lambda item: item[0]):
            if t not in seen_tokens:
                seen_tokens.add(t)
                uniq.append((x, t))
        if uniq:
            deduped.append((y, uniq))

    return deduped


def _x_clusters(x_values: list[float], tolerance: int = 30) -> list[float]:
    """将 x 坐标聚类，返回各簇的中心值。"""
    if not x_values:
        return []
    xs = sorted(set(round(x) for x in x_values))
    clusters: list[list[int]] = [[xs[0]]]
    for x in xs[1:]:
        if x - clusters[-1][-1] <= tolerance:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [round(sum(c) / len(c)) for c in clusters]


def _account_column_split(rows: list, mid: float) -> tuple[float, float]:
    """Based on科目名 token x positions, find better L/R split than geometric mid.

    Returns (left_max_x, right_min_x) where:
    - Tokens with x < left_max_x belong to LEFT side
    - Tokens with x >= right_min_x belong to RIGHT side
    """
    import re as _re
    _num = _re.compile(r"^-?[\d,]+\.?\d+$")
    _rn = _re.compile(r"^\d{1,3}$")

    account_xs: list[float] = []
    for _, items in rows:
        for x, t in items:
            if not _num.match(t) and not _rn.match(t) and not _is_meta(t) and not _is_section_header(t):
                account_xs.append(x)

    if not account_xs:
        return mid, mid

    ac_clusters = _x_clusters(account_xs, tolerance=50)
    if len(ac_clusters) >= 2:
        sorted_ac = sorted(ac_clusters)
        divide = (sorted_ac[0] + sorted_ac[-1]) / 2
        return divide, divide
    return mid, mid


# === ROW_NUM 解析 ===


def _parse_page_row_num(pages: list[pymupdf.Page]) -> list[dict]:
    """ROW_NUM 模式: 当 PDF 有行次编号列时使用。

    策略:
    1. x 聚类 → 自动发现列结构
    2. 期初期末列: 扫描表头行识别
    3. 行次列跳过
    4. 科目名-数字配对: 同行, 左侧科目 + 右侧最近的数字
    """
    records: list[dict] = []

    for page in pages:
        rows = _extract_rows(page)
        if not rows:
            continue

        # --- 列分析 ---
        all_x: list[float] = []
        for _, items in rows:
            for x, _ in items:
                all_x.append(x)
        clusters = _x_clusters(all_x)

        # 找行次列: 簇中心在 50-250 且对应 token 全是 1-200 纯数字的那一列
        rn_cluster_idx: Optional[int] = None
        for ci, cx in enumerate(clusters):
            if 50 < cx < 250:
                # 采样验证
                rn_count = 0
                for _, items in rows[:30]:
                    for x, t in items:
                        if abs(x - cx) <= 30 and _is_row_number(t):
                            rn_count += 1
                if rn_count >= 3:
                    rn_cluster_idx = ci
                    break

        # 期初期末列: 扫描前 10 行的 token 内容
        col_is_qimo: dict[int, Optional[bool]] = {}
        for ci in range(len(clusters)):
            col_is_qimo[ci] = None
            for _, items in rows[:10]:
                for x, t in items:
                    if abs(x - clusters[ci]) <= 30:
                        qimo_kw = {"期末", "年末", "期末数", "年末数", "期末余额", "本期", "本期金额", "本年累计"}
                        qichu_kw = {"年初", "期初", "年初数", "期初数", "期初余额", "上年", "上年数"}
                        for kw in qimo_kw:
                            if kw in t:
                                col_is_qimo[ci] = True
                                break
                        if col_is_qimo[ci] is None:
                            for kw in qichu_kw:
                                if kw in t:
                                    col_is_qimo[ci] = False
                                    break
                if col_is_qimo[ci] is not None:
                    break

        # --- 解析行 ---
        # 用科目名 x 聚类找左右分界 (比几何中缝更可靠)
        mid = _account_column_split(rows, (clusters[0] + clusters[-1]) / 2 if clusters else 350.0)[0]
        for y, items in rows:
            # ROW_NUM 模式: 左右栏的科目名和数字通过 x 聚类自然分离
            # 左侧 = x < mid, 右侧 = x >= mid
            # 但关键: 负债侧数字可能在科目名的左侧 (如时代鑫控中 '短期借款'x=352, 数字x=309)
            # 所以配对时, 左右栏数字均取该侧 x 范围内的 NUM token

            # 先找出本行的科目名候选(每侧各一个)
            left_names = [(x, t) for x, t in items if x < mid and not _NUM.match(t) and not _is_row_number(t) and not _is_meta(t) and not _is_section_header(t)]
            right_names = [(x, t) for x, t in items if x >= mid and not _NUM.match(t) and not _is_row_number(t) and not _is_meta(t) and not _is_section_header(t)]

            # 同侧的数字 (排除行次号)
            left_nums = [(x, t) for x, t in items if x < mid and _NUM.match(t) and not _is_row_number(t)]
            right_nums = [(x, t) for x, t in items if x >= mid and _NUM.match(t) and not _is_row_number(t)]

            for side_names, side_nums in [(left_names, left_nums), (right_names, right_nums)]:
                if not side_names:
                    continue
                name_x, name = side_names[0]  # 取最左边科目

                if not side_nums:
                    continue

                # 在同侧数字中优先期末列，否则期初列，兜底取第一个
                best = None
                for x, t in side_nums:
                    ci = min(range(len(clusters)), key=lambda i: abs(x - clusters[i]))
                    if col_is_qimo.get(ci) is True:
                        best = t
                        break
                if best is None:
                    for x, t in side_nums:
                        ci = min(range(len(clusters)), key=lambda i: abs(x - clusters[i]))
                        if col_is_qimo.get(ci) is False:
                            best = t
                            break
                if best is None:
                    best = side_nums[0][1]

                value = float(best.replace(",", ""))
                records.append({
                    "科目名称": _strip_name(name),
                    "金额": value,
                })

    return records


def _parse_page_split_line(pages: list[pymupdf.Page]) -> list[dict]:
    """SPLIT_LINE 模式: 无行次号, 科目与数字可能分在同一行或相邻行。

    策略:
    1. x 聚类 → 分割左右栏
    2. y 层扫描:
       - 如果同 y 层有科目+数字 → 直接配对 (同行型)
       - 如果只有科目 → 向下查找最近数字层 (跨行型)
    3. 左侧数字配对左侧科目, 右侧数字配对右侧科目
    """
    records: list[dict] = []

    for page in pages:
        rows = _extract_rows(page)
        if not rows:
            continue

        # --- 列分析 ---
        all_x: list[float] = []
        for _, items in rows:
            for x, _ in items:
                all_x.append(x)
        clusters = _x_clusters(all_x)
        mid = _account_column_split(rows, (clusters[0] + clusters[-1]) / 2 if clusters else 350.0)[0]

        # 期初期末识别 (扫描表头)
        qimo_x_ranges: list[tuple[float, float]] = []  # 期末列的 x 区间
        qichu_x_ranges: list[tuple[float, float]] = []
        for ci, cx in enumerate(clusters):
            # 通过表头 token 判定
            for _, items in rows[:10]:
                for x, t in items:
                    if abs(x - cx) <= 30:
                        if any(kw in t for kw in ["期末", "年末", "本期金额", "本年累计"]):
                            qimo_x_ranges.append((cx - 30, cx + 30))
                            break
                        if any(kw in t for kw in ["年初", "期初", "上年数", "上期金额"]):
                            qichu_x_ranges.append((cx - 30, cx + 30))
                            break
                if qimo_x_ranges or qichu_x_ranges:
                    break

        def _is_qimo_col(x: float) -> Optional[bool]:
            if any(lo <= x <= hi for lo, hi in qimo_x_ranges):
                return True
            if any(lo <= x <= hi for lo, hi in qichu_x_ranges):
                return False
            return None

        # --- y 层索引构建 (跳过表头) ---
        # 找到第一个数据行: 包含纯数字且 y > 表头区
        header_max_y = 80
        data_start_idx = 0
        for i, (y, items) in enumerate(rows):
            if y <= header_max_y:
                continue
            has_num = any(_NUM.match(t) for _, t in items)
            if has_num:
                data_start_idx = i
                break

        data_rows = rows[data_start_idx:]

        # --- 配对: 分两层处理 ---
        # Layer A: 同行有科目+数字 → 直接配对
        # Layer B: 同行只有科目 → 向下找最近的数字行配对

        i = 0
        while i < len(data_rows):
            y, items = data_rows[i]
            left_names = [(x, t) for x, t in items if x < mid and not _NUM.match(t) and not _is_row_number(t) and not _is_meta(t) and not _is_section_header(t)]
            right_names = [(x, t) for x, t in items if x >= mid and not _NUM.match(t) and not _is_row_number(t) and not _is_meta(t) and not _is_section_header(t)]
            left_nums = [(x, t) for x, t in items if x < mid and _NUM.match(t)]
            right_nums = [(x, t) for x, t in items if x >= mid and _NUM.match(t)]

            # 为每个科目找数字
            for name_list, num_list, side in [
                (left_names, left_nums, "left"),
                (right_names, right_nums, "right"),
            ]:
                if not name_list:
                    continue
                for name_x, name in name_list:
                    # SPLIT_LINE: 艾维模式 — 数字在科目名的右侧、同行
                    # 巨和物业模式 — 数字在科目名的上一行(先行后名)
                    if num_list:
                        # 同行有数字
                        candidates = [(x, t) for x, t in num_list if x > name_x]
                        if not candidates:
                            candidates = num_list
                        best_val = None
                        for x, t in candidates:
                            qf = _is_qimo_col(x)
                            if qf is True:
                                best_val = t
                                break
                        if best_val is None:
                            best_val = candidates[0][1]
                        records.append({"科目名称": _strip_name(name), "金额": float(best_val.replace(",", ""))})
                    else:
                        # 跨行: 先查上一行(巨和模式: 数字在科目上方)
                        # 再查下一行(磊鑫模式: 数字在科目下方)
                        best_val = None
                        # 向上查
                        for j in range(i - 1, max(i - 4, -1), -1):
                            y2, items2 = data_rows[j]
                            for x, t in items2:
                                if _NUM.match(t):
                                    if side == "left" and x < mid or side == "right" and x >= mid:
                                        best_val = t
                                        break
                            if best_val: break
                        # 向下查
                        if best_val is None:
                            for j in range(i + 1, min(i + 4, len(data_rows))):
                                y2, items2 = data_rows[j]
                                for x, t in items2:
                                    if _NUM.match(t):
                                        if side == "left" and x < mid or side == "right" and x >= mid:
                                            best_val = t
                                            break
                                if best_val: break

                        if best_val:
                            records.append({"科目名称": _strip_name(name), "金额": float(best_val.replace(",", ""))})

            i += 1

    return records


# === 公共入口 ===


def parse_pdf(file_path: str, max_pages: int = 3) -> pd.DataFrame:
    """解析电子版 PDF 财务报表 (资产负债表/利润表/现金流量表)。

    自动检测布局模式 (行次型 vs 无行次双栏型) 并选择对应策略。

    Args:
        file_path: PDF 文件路径
        max_pages: 最多读取页数

    Returns:
        DataFrame with columns: 科目名称, 金额, 报告期

    Raises:
        RuntimeError: 检测为扫描件 (无文本层)
    """
    # 门禁
    if _is_scanned(file_path):
        raise RuntimeError(
            "该 PDF 为扫描件/图片格式，暂不支持解析。\n"
            "请提供电子版 PDF (如税务局导出的报税文件) 或 Excel 格式的财务报表。"
        )

    doc = pymupdf.open(file_path)
    try:
        pages = [doc[i] for i in range(min(max_pages, len(doc)))]

        # 自动检测布局模式
        mode = _detect_layout_mode(pages)

        if mode == "ROW_NUM":
            records = _parse_page_row_num(pages)
        else:
            records = _parse_page_split_line(pages)

    finally:
        doc.close()

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["科目名称", "金额", "报告期"])

    df["报告期"] = f"PDF-{os.path.basename(file_path)[:30]}"
    return df[["科目名称", "金额", "报告期"]]

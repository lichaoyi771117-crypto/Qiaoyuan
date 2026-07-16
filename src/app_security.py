"""峤远 · 应用层安全工具模块

提供：
- API Key 启动校验
- 基于 Streamlit session 的请求限流
- 文件上传大小 / 类型校验（Magic Bytes）
- 统一错误信息脱敏
- 安全删除临时文件
"""
import io
import os
import time
import logging
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

_logger = logging.getLogger(__name__)

# ── 常量 ──
LLM_TIMEOUT_SECONDS = 120
MAX_SINGLE_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_TOTAL_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_UPLOAD_FILES = 10
ALLOWED_EXCEL_EXTENSIONS = {".xlsx", ".xls"}

# Excel 文件 Magic Bytes 校验（基于 OLE2 / OOXML 起始签名）
# .xlsx 是 ZIP 文件，起始为 50 4B 03 04； .xls 是 OLE 复合文档，起始为 D0 CF 11 E0
_EXCEL_MAGIC = {
    b"PK\x03\x04": ".xlsx",  # OOXML
    b"PK\x05\x06": ".xlsx",  # 空 xlsx 也可能是这个
    b"PK\x07\x08": ".xlsx",
    b"\xd0\xcf\x11\xe0": ".xls",  # OLE2
}


# ── API Key 校验 ──

def validate_api_key(key: str) -> None:
    """启动时校验 DeepSeek API Key 是否已配置。"""
    if not key or not key.strip():
        st.error("⚠️ 未配置 DEEPSEEK_API_KEY。请在 .env 文件中设置有效的 API Key 后重启服务。")
        st.stop()
    if not key.startswith("sk-"):
        st.error("⚠️ DEEPSEEK_API_KEY 格式不正确，应以 sk- 开头。")
        st.stop()


# ── 请求限流 ──

def check_rate_limit(action: str, max_calls: int = 5, window_seconds: int = 60) -> bool:
    """基于 Streamlit session_state 的简单限流。

    Args:
        action: 动作标识，如 'analyze' / 'classify'
        max_calls: 时间窗口内最大调用次数
        window_seconds: 时间窗口（秒）

    Returns:
        True: 允许执行；False: 已触发限流
    """
    now = time.time()
    key = f"rate_limit_{action}"
    if key not in st.session_state:
        st.session_state[key] = []
    history: List[float] = st.session_state[key]
    # 清理过期记录
    history[:] = [ts for ts in history if now - ts < window_seconds]
    if len(history) >= max_calls:
        return False
    history.append(now)
    return True


# ── 文件上传校验 ──

def validate_uploaded_file(file_object) -> Tuple[bool, str]:
    """校验单个上传文件：大小、扩展名、Magic Bytes。

    Returns:
        (is_valid, error_message)
    """
    name = getattr(file_object, "name", "unknown")
    size = getattr(file_object, "size", 0)
    ext = os.path.splitext(name)[1].lower()

    if size <= 0:
        return False, f"文件 {name} 为空或无法读取。"
    if size > MAX_SINGLE_FILE_SIZE:
        return False, f"文件 {name} 超过单文件大小限制（{MAX_SINGLE_FILE_SIZE // 1024 // 1024} MB）。"
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        return False, f"文件 {name} 类型不被允许，仅支持 .xlsx / .xls。"

    # 读取前 8 字节做 Magic Bytes 校验
    try:
        first_bytes = file_object.read(8)
        file_object.seek(0)  # 必须重置指针，否则后续读取会失败
        if not first_bytes:
            return False, f"文件 {name} 无法读取内容。"
        for magic, expected_ext in _EXCEL_MAGIC.items():
            if first_bytes.startswith(magic):
                # 进一步确认扩展名与魔数一致
                if ext == expected_ext or (expected_ext == ".xlsx" and ext in ALLOWED_EXCEL_EXTENSIONS):
                    return True, ""
                return False, f"文件 {name} 扩展名与真实格式不一致。"
        return False, f"文件 {name} 不是有效的 Excel 文件。"
    except Exception as exc:
        _logger.warning(f"Magic bytes validation failed for {name}: {exc}")
        return False, f"文件 {name} 校验失败，请检查文件是否损坏。"


def validate_uploaded_files(file_objects) -> Tuple[bool, str, List]:
    """批量校验上传文件并返回（是否通过、错误信息、通过的文件列表）。"""
    if not file_objects:
        return False, "请先上传至少一份财务报表。", []
    if len(file_objects) > MAX_UPLOAD_FILES:
        return False, f"一次最多上传 {MAX_UPLOAD_FILES} 个文件。", []

    total_size = 0
    valid_files = []
    for f in file_objects:
        ok, msg = validate_uploaded_file(f)
        if not ok:
            return False, msg, []
        total_size += getattr(f, "size", 0)
        valid_files.append(f)

    if total_size > MAX_TOTAL_UPLOAD_SIZE:
        return False, f"上传文件总大小超过 {MAX_TOTAL_UPLOAD_SIZE // 1024 // 1024} MB 限制。", []
    return True, "", valid_files


# ── 错误信息脱敏 ──

def safe_user_error() -> str:
    """返回给用户的统一错误信息，不暴露内部异常。"""
    return "系统处理失败，请稍后重试或联系管理员。"


# ── 安全删除文件 ──

def secure_delete(filepath: str) -> None:
    """安全删除临时文件：完整覆写后再删除。"""
    try:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            if size > 0:
                with open(filepath, "wb") as f:
                    f.write(os.urandom(size))
            os.unlink(filepath)
    except Exception as exc:
        _logger.warning(f"Secure delete failed for {filepath}: {exc}")

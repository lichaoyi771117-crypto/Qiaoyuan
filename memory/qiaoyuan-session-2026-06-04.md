---
name: qiaoyuan-session-2026-06-04
description: 2026-06-04 工作进度全量记录 — 31次commit, 6项用户反馈修复, 14测试绿
metadata:
  type: project
---

# 霖信莯咨询 F-Analyzer · 2026-06-04 工作进度

## 当前状态

- **Git 提交数**: 31
- **测试**: 14 PASS
- **最后 commit**: `77c81d3` — docs: 更新CLAUDE.md至31次commit
- **Streamlit 服务**: http://localhost:8501 (后台运行中，PID: bcua25gi8)

## 本轮修改 (commit `7874b47`)

### 用户反馈修复 (6项)

1. **Prompt 回滚** — "优化建议""税务风险提示"两个模块的 Prompt 之前被改得过严（"严禁…等客套话开头，不要写…等开场白"），报告风格变得过于严肃、缺乏亲切感。已回滚为仅禁止"好的"开头，恢复原有写作风格。

2. **LLM 字样替换** — 免责声明第3条中 "LLM 生成的解读文本" → "霖信莯咨询 · F-Analyzer 生成的解读文本"

3. **百分比显示修复** — `_fmt()` 增加 `unit` 参数，当 `unit=="%"` 时自动 `×100` 显示。资产负债率 0.4698 → 46.98%，毛利率、净利率等同理。同时修复了 HTML 导出报告和"数据详情"展开区中的显示。

4. **指标卡片扩容** — 从 8 个扩展到 14 个：
   - 偿债能力：+速动比率、+利息保障倍数（原仅有流动比率、资产负债率）
   - 盈利能力：+ROA（原仅有毛利率、净利率、ROE）
   - 营运效率：+存货周转天、+总资产周转率（原仅有应收周转）
   - 税务指标：+综合税负率（原仅有实际税率）
   - 预警阈值同步更新（速动比率<0.5 标红）

5. **数据缺失 NaN 修复** — `MetricCalculator._get()` 找不到数据时返回 `float("nan")` 而非 `0.0`，`ocf_to_np()` 和 `free_cash_flow()` 增加 NaN 检查。解决了"经营现金流/净利润 0.0000%"这种假数据问题（缺少现金流量表数据时直接显示"—"）。

6. **文件清除/重传功能**：
   - 上传区下方：文件名旁显示 "✕ 清除已上传文件" 按钮
   - 报告区上方：居中的 "🔄 清除报告，重新上传" 按钮
   - 实现方式：`st.session_state.upload_key` 计数器 + `file_uploader(key=f"fu_{key}")`，每次清除后 `upload_key+=1` 强制重建控件，无需刷新页面

### UI 优化
- `file_uploader` label 简化："上传财务报表（Excel）" → "上传"
- `.streamlit/config.toml` 新建：`maxUploadSize = 10`（服务端限制 10MB）
- JS MutationObserver 注入：替换 Streamlit 硬编码英文 "Limit 200MB per file" → "单个文件 ≤ 10MB"
- CSS 注入：汉化拖拽区文本、浏览文件按钮

## 启动命令
```bash
cd "d:\Ai RAG\Qiaoyuan"
python -m streamlit run app.py --server.port 8501
```

## 测试命令
```bash
cd "d:\Ai RAG\Qiaoyuan"
python -m pytest tests/ -x -q
```

## 关键配置
- DeepSeek API Key: 内嵌于 `app.py` (sk-5661d358e06b4a46b4f856d7c78f65a1)
- 模型: `deepseek-chat`，base_url: `https://api.deepseek.com`
- 文件限制: 10MB (.xlsx/.xls)

## 已知注意事项
- Streamlit `file_uploader` 的 "Drag and drop file here" 文本是前端硬编码，CSS 可部分覆盖但不如 JS 彻底
- `_get()` 返回 NaN 后，依赖该值的比率也会变为 NaN，展示为 "—"
- 百分比指标的计算值仍是小数（0.4698），仅在前端 `_fmt()` 中 ×100 显示
- 提交数 31 中包含了 source code 目录（FinGPT/MinerU/akshare 源码参考）

import pandas as pd
path = 'test documents/艾维集团合并24年4季度报表.xlsx'
xls = pd.ExcelFile(path)
print(f"Sheets: {xls.sheet_names}")
# 查看资产负债表 sheet (第一个)
df = pd.read_excel(path, sheet_name=0, header=None)
print(f"Shape: {df.shape}")
print(f"Columns: {df.shape[1]}")
# 打印前 15 行所有列
for i in range(min(25, len(df))):
    vals = [str(v)[:50] if pd.notna(v) else "NaN" for v in df.iloc[i, :min(7,df.shape[1])]]
    print(f"R{i}: {vals}")

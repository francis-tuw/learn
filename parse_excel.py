import pandas as pd

# 读取Excel文件
file_path = '/workspace/SQL智能纠错系统V0.5/test输出示例.xlsx'
df_dict = pd.read_excel(file_path, sheet_name=None)

# 打印所有sheet名称
print('Sheet names:', list(df_dict.keys()))

# 打印每个sheet的内容
for sheet_name, df in df_dict.items():
    print('\nSheet:', sheet_name)
    print('Columns:', list(df.columns))
    print('Data preview:')
    print(df.head())
    print('Shape:', df.shape)
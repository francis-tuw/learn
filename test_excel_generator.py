import sys
import os
from io import BytesIO
import pandas as pd

# 添加项目路径
sys.path.append('/workspace/SQL智能纠错系统V0.5')

from tools.report_formatter import ReportFormatter

# 测试数据
test_dataset_results = {
    'groups': [
        {
            'group_id': 'MP1',
            'source_tables': 'T:表1、\nT1:表2',
            'relations': [
                {
                    'compare_module': '表间关联',
                    'content': '表1与表2关联',
                    'sql_content': 'From 表1 left join 表2 on col1=col2 and …',
                    'is_consistent': '是',
                    'remark': ''
                },
                {
                    'compare_module': '表间关联',
                    'content': '表1与表2关联',
                    'sql_content': '...........',
                    'is_consistent': '是',
                    'remark': ''
                }
            ],
            'filters': [
                {
                    'compare_module': '筛选条件',
                    'content': '条件1',
                    'sql_content': 'where condition1',
                    'is_consistent': '是',
                    'remark': ''
                }
            ]
        }
    ]
}

test_datamap_results = [
    {
        'group_id': 'MP1',
        'field_seq': 1,
        'target_field_cn': '数据键值',
        'target_field_en': 'UUID',
        'extract_method': '函数',
        'source_table': '',
        'source_field_en': '',
        'source_field_cn': '',
        'default_value': '',
        'transform_logic': '',
        'sql_expression': 'UUID() AS UUID',
        'is_consistent': '是',
        'remark': ''
    },
    {
        'group_id': 'MP1',
        'field_seq': 2,
        'target_field_cn': '加载时间',
        'target_field_en': 'LOAD_TIME',
        'extract_method': '函数',
        'source_table': '',
        'source_field_en': '',
        'source_field_cn': '',
        'default_value': '',
        'transform_logic': '',
        'sql_expression': 'LOAD_TIME() AS LOAD_TIME',
        'is_consistent': '是',
        'remark': ''
    },
    {
        'group_id': 'MP1',
        'field_seq': 3,
        'target_field_cn': '数据日期',
        'target_field_en': 'DATA_DATE',
        'extract_method': '变量',
        'source_table': '',
        'source_field_en': '',
        'source_field_cn': '',
        'default_value': '',
        'transform_logic': '',
        'sql_expression': 'SHOT_DATA AS DATA_DATE',
        'is_consistent': '是',
        'remark': '跑批基准日期变量为SHOT_DATA'
    },
    {
        'group_id': 'MP1',
        'field_seq': 4,
        'target_field_cn': '机构编号',
        'target_field_en': 'ORG_NO',
        'extract_method': '字段',
        'source_table': 'T',
        'source_field_en': 'ORG',
        'source_field_cn': '机构',
        'default_value': '',
        'transform_logic': '',
        'sql_expression': 'T.ORG AS ORG_NO',
        'is_consistent': '否',
        'remark': 'IT-Mapping中原表字段为BRANCH'
    },
    {
        'group_id': 'MP1',
        'field_seq': 5,
        'target_field_cn': '机构类型',
        'target_field_en': 'ORG_TYPE',
        'extract_method': '变量',
        'source_table': '',
        'source_field_en': '',
        'source_field_cn': '',
        'default_value': '',
        'transform_logic': '',
        'sql_expression': 'SHOT_ORG AS ORG_TYPE',
        'is_consistent': '否',
        'remark': '逻辑转换与IT-Mapping不符'
    }
]

# 生成Excel报告
excel_data = ReportFormatter.generate_excel_report(test_dataset_results, test_datamap_results)

# 保存到文件
output_path = '/workspace/test_output.xlsx'
with open(output_path, 'wb') as f:
    f.write(excel_data.getvalue())

print(f"Excel report generated successfully at: {output_path}")

# 验证生成的Excel文件
print("\nVerifying the generated Excel file:")
df_dict = pd.read_excel(output_path, sheet_name=None)
print('Sheet names:', list(df_dict.keys()))

for sheet_name, df in df_dict.items():
    print(f'\nSheet: {sheet_name}')
    print(f'Columns: {list(df.columns)}')
    print(f'Rows: {len(df)}')
    print('Data preview:')
    print(df.head())
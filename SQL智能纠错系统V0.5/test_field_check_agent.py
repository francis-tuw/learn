#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sql_correction_engine import FieldCheckAgent

# 测试 SQL 代码
test_sql = """
INSERT INTO target_table (
    id,
    name,
    email,
    phone
) VALUES (
    1,
    'John Doe',
    'john@example.com',
    '123-456-7890'
);
"""

# 测试字段信息
test_field_info = {
    'target_field': 'name',
    'source_field': '',
    'source_table_alias': '',
    'transformation_logic': '',
    'data_type': 'VARCHAR(100)',
    'extract_method': '',
    'sheet': 'Sheet1'
}

# 创建 FieldCheckAgent 实例
config = {
    'host': 'http://localhost:11434',
    'model': 'qwen2.5:7b',
    'timeout': 60
}

agent = FieldCheckAgent(config)

# 测试 _locate_field_in_sql 方法
print("Testing _locate_field_in_sql method...")
sql_snippet, position_info = agent._locate_field_in_sql(test_field_info, test_sql)
print(f"SQL Snippet: {sql_snippet}")
print(f"Position Info: {position_info}")
print()

# 测试 analyze 方法（模拟）
print("Testing analyze method...")
try:
    result = agent.analyze(test_field_info, test_sql)
    print(f"Analysis Result: {result}")
    print(f"Position Info in Result: {result.get('position_info', {})}")
except Exception as e:
    print(f"Error during analysis: {e}")

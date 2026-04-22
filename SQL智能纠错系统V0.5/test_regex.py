#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试正则表达式是否能正确匹配包含注释的SQL
"""
import re

# 测试包含注释的SQL
sql = """
INSERT INTO test_table (id, -- 字段1
                       name, -- 字段2
                       age) -- 字段3
SELECT
"""

# 测试正则表达式
pattern = r'INSERT\s+INTO\s+\w+(?:\s+PARTITION\s*\([^)]*\))?\s*\(([\s\S]*?)\)\s*(?:--[\s\S]*?)?\s*SELECT'
match = re.search(pattern, sql, re.IGNORECASE)

print('Match found:', match is not None)
if match:
    print('Captured fields:')
    print(repr(match.group(1)))
    
    # 测试字段解析
    fields_str = match.group(1)
    lines = fields_str.split('\n')
    print('\n解析每行:')
    for line in lines:
        clean_line = re.sub(r'--.*$', '', line).strip()
        print(f'原始行: {repr(line)}')
        print(f'清理后: {repr(clean_line)}')
        if clean_line:
            line_fields = [f.strip() for f in clean_line.split(',') if f.strip()]
            print(f'字段: {line_fields}')

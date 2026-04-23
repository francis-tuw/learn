#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试字段位置信息记录功能
"""

from sql_group_parser import parse_grouped_sql

# 测试SQL文件
SQL_FILE = 'SP_DWD_DM_T02_CUST_ADDR_INFO.sql'

def test_field_positions():
    """测试字段位置信息记录"""
    print("=== 测试字段位置信息记录功能 ===")
    
    try:
        # 读取SQL文件
        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 解析SQL
        result = parse_grouped_sql(sql_content, debug=True)
        
        # 输出解析结果
        print(f"存储过程名称: {result['procedure_name']}")
        print(f"INSERT块数量: {result['total_blocks']}")
        
        # 检查字段位置信息
        if result['insert_blocks']:
            for i, block in enumerate(result['insert_blocks']):
                print(f"\n=== 块 {i+1} ===")
                print(f"分组ID: {block['group_id']}")
                print(f"目标表: {block['target_table']}")
                print(f"字段数量: {len(block['insert_fields'])}")
                print(f"字段位置信息: {block['field_positions']}")
                
                # 检查是否有字段位置信息
                if block['field_positions']:
                    print("\n字段位置详情:")
                    for field, position in block['field_positions'].items():
                        print(f"- {field}: 插入位置 (行{position['insert_line']}, 列{position['insert_col']}), 选择位置 (行{position['select_line']}, 列{position['select_col']})")
                else:
                    print("无字段位置信息")
        else:
            print("未解析到INSERT块")
        
        print("\n测试完成")
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_field_positions()

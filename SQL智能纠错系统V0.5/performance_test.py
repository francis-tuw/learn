#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL解析性能测试脚本
用于测试大SQL文件的解析性能，验证缓存机制的效果
"""
import os
import time
import random
from sql_group_parser import SQLGroupParser, FieldLocator


def generate_large_sql_file(file_path, num_insert_blocks=100, fields_per_block=50):
    """生成大SQL文件用于性能测试"""
    with open(file_path, 'w', encoding='utf-8') as f:
        # 存储过程头部
        f.write("CREATE OR REPLACE PROCEDURE test_large_sql()\n")
        f.write("BEGIN\n")
        
        # 生成多个INSERT块
        for i in range(num_insert_blocks):
            # 分组注释
            f.write(f"-- 分组 {i+1} - MP{i+1:03d} (测试分组{i+1})\n")
            f.write("-- 插入数据: 测试数据\n")
            
            # INSERT语句
            f.write(f"INSERT INTO test_table PARTITION (p{i+1:03d}) (\n")
            
            # 生成多个字段
            fields = []
            for j in range(fields_per_block):
                field_name = f"field_{i+1:03d}_{j+1:03d}"
                fields.append(f"  {field_name}")
            f.write(",\n".join(fields))
            f.write("\n) SELECT\n")
            
            # 生成SELECT表达式
            select_exprs = []
            for j in range(fields_per_block):
                select_exprs.append(f"  source_table.field_{j+1:03d}")
            f.write(",\n".join(select_exprs))
            f.write("\nFROM source_table\n")
            f.write("WHERE 1=1\n")
            f.write("AND source_table.id = 1\n")
            f.write(";\n\n")
        
        # 存储过程尾部
        f.write("END;\n")


def test_sql_group_parser_performance(sql_file):
    """测试SQLGroupParser的性能"""
    print(f"测试SQLGroupParser性能，文件: {sql_file}")
    print(f"文件大小: {os.path.getsize(sql_file) / 1024 / 1024:.2f} MB")
    
    # 读取SQL内容
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 第一次解析（冷缓存）
    parser = SQLGroupParser()
    start_time = time.time()
    result1 = parser.parse(sql_content)
    first_parse_time = time.time() - start_time
    print(f"第一次解析时间: {first_parse_time:.2f} 秒")
    print(f"解析出 {result1.total_blocks} 个INSERT块")
    
    # 第二次解析（热缓存）
    start_time = time.time()
    result2 = parser.parse(sql_content)
    second_parse_time = time.time() - start_time
    print(f"第二次解析时间: {second_parse_time:.2f} 秒")
    print(f"缓存效果: {first_parse_time / second_parse_time:.2f}x 速度提升")
    
    return first_parse_time, second_parse_time


def test_field_locator_performance(sql_file, num_fields=100):
    """测试FieldLocator的性能"""
    print(f"\n测试FieldLocator性能，文件: {sql_file}")
    
    # 读取SQL内容
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 创建FieldLocator实例
    locator = FieldLocator(sql_content)
    
    # 生成测试字段名
    test_fields = []
    for i in range(1, num_fields + 1):
        block_id = random.randint(1, 100)
        field_id = random.randint(1, 50)
        test_fields.append(f"field_{block_id:03d}_{field_id:03d}")
    
    # 第一次定位（冷缓存）
    start_time = time.time()
    for field in test_fields:
        locator.get_position(field, context="INSERT")
    first_locate_time = time.time() - start_time
    print(f"第一次定位时间: {first_locate_time:.2f} 秒")
    print(f"平均每个字段定位时间: {first_locate_time / num_fields * 1000:.2f} 毫秒")
    
    # 第二次定位（热缓存）
    start_time = time.time()
    for field in test_fields:
        locator.get_position(field, context="INSERT")
    second_locate_time = time.time() - start_time
    print(f"第二次定位时间: {second_locate_time:.2f} 秒")
    print(f"平均每个字段定位时间: {second_locate_time / num_fields * 1000:.2f} 毫秒")
    print(f"缓存效果: {first_locate_time / second_locate_time:.2f}x 速度提升")
    
    return first_locate_time, second_locate_time


def main():
    """主测试函数"""
    # 生成测试文件
    test_file = "large_test_sql.sql"
    print(f"生成测试SQL文件: {test_file}")
    generate_large_sql_file(test_file, num_insert_blocks=100, fields_per_block=50)
    
    try:
        # 测试SQLGroupParser性能
        test_sql_group_parser_performance(test_file)
        
        # 测试FieldLocator性能
        test_field_locator_performance(test_file, num_fields=100)
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\n清理测试文件: {test_file}")


if __name__ == "__main__":
    main()

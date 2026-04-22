#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面的SQL解析测试脚本
用于测试各种场景下的SQL解析和字段定位功能
"""
from sql_group_parser import FieldLocator, SQLGroupParser


def test_empty_sql():
    """测试空SQL内容"""
    print("测试空SQL内容...")
    
    sql_content = ""
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    position = locator.get_position('id')
    assert position is None, "空SQL应该返回None"
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert len(result.parse_errors) > 0, "空SQL应该有解析错误"
    assert result.total_blocks == 0, "空SQL应该解析出0个块"
    
    print("  测试通过")
    return True


def test_simple_insert():
    """测试简单的INSERT语句"""
    print("\n测试简单的INSERT语句...")
    
    sql_content = """
    INSERT INTO test_table (id, name) 
    SELECT id, name 
    FROM source_table;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    
    # 测试字段定位
    id_pos = locator.get_position('id', context='INSERT')
    name_pos = locator.get_position('name', context='INSERT')
    
    assert id_pos is not None, "应该找到id字段"
    assert name_pos is not None, "应该找到name字段"
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert result.total_blocks == 1, "应该解析出1个INSERT块"
    assert len(result.insert_blocks[0].insert_fields) == 2, "应该有2个字段"
    
    print("  测试通过")
    return True


def test_multiple_insert_blocks():
    """测试多个INSERT块"""
    print("\n测试多个INSERT块...")
    
    sql_content = """
    -- 分组 1 - MP001 (基础信息)
    INSERT INTO test_table1 (id, name) 
    SELECT id, name 
    FROM source_table1;
    
    -- 分组 2 - MP002 (详细信息)
    INSERT INTO test_table2 (id, address, phone) 
    SELECT id, address, phone 
    FROM source_table2;
    """
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert result.total_blocks == 2, "应该解析出2个INSERT块"
    assert len(result.insert_blocks[0].insert_fields) == 2, "第一个块应该有2个字段"
    assert len(result.insert_blocks[1].insert_fields) == 3, "第二个块应该有3个字段"
    
    print("  测试通过")
    return True


def test_complex_sql_with_joins():
    """测试包含JOIN的复杂SQL"""
    print("\n测试包含JOIN的复杂SQL...")
    
    sql_content = """
    INSERT INTO test_table (id, name, address, phone) 
    SELECT t1.id, t1.name, t2.address, t3.phone 
    FROM source_table1 t1 
    LEFT JOIN source_table2 t2 ON t1.id = t2.user_id 
    INNER JOIN source_table3 t3 ON t1.id = t3.user_id 
    WHERE t1.status = 'active';
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    
    # 测试字段定位
    id_pos = locator.get_position('id', context='INSERT')
    name_pos = locator.get_position('name', context='INSERT')
    address_pos = locator.get_position('address', context='INSERT')
    phone_pos = locator.get_position('phone', context='INSERT')
    
    assert id_pos is not None, "应该找到id字段"
    assert name_pos is not None, "应该找到name字段"
    assert address_pos is not None, "应该找到address字段"
    assert phone_pos is not None, "应该找到phone字段"
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert result.total_blocks == 1, "应该解析出1个INSERT块"
    assert len(result.insert_blocks[0].insert_fields) == 4, "应该有4个字段"
    assert len(result.insert_blocks[0].join_clauses) == 2, "应该有2个JOIN子句"
    
    print("  测试通过")
    return True


def test_sql_with_partition():
    """测试带分区的SQL"""
    print("\n测试带分区的SQL...")
    
    sql_content = """
    INSERT INTO test_table PARTITION (p202401) (id, name) 
    SELECT id, name 
    FROM source_table 
    WHERE date >= '2024-01-01';
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    id_pos = locator.get_position('id', context='INSERT')
    assert id_pos is not None, "应该找到id字段"
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert result.total_blocks == 1, "应该解析出1个INSERT块"
    assert result.insert_blocks[0].partition_clause == 'p202401', "应该正确解析分区"
    
    print("  测试通过")
    return True


def test_sql_with_comments():
    """测试包含注释的SQL"""
    print("\n测试包含注释的SQL...")
    
    sql_content = """
    -- 这是一个注释
    INSERT INTO test_table (id, -- 字段1
                           name, -- 字段2
                           age) -- 字段3
    SELECT id, -- 源字段1
           name, -- 源字段2
           age -- 源字段3
    FROM source_table 
    WHERE id > 100; -- 筛选条件
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    id_pos = locator.get_position('id', context='INSERT')
    name_pos = locator.get_position('name', context='INSERT')
    age_pos = locator.get_position('age', context='INSERT')
    
    assert id_pos is not None, "应该找到id字段"
    assert name_pos is not None, "应该找到name字段"
    assert age_pos is not None, "应该找到age字段"
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    assert result.total_blocks == 1, "应该解析出1个INSERT块"
    assert len(result.insert_blocks[0].insert_fields) == 3, "应该有3个字段"
    
    print("  测试通过")
    return True


def test_get_all_field_positions():
    """测试get_all_field_positions方法"""
    print("\n测试get_all_field_positions方法...")
    
    sql_content = """
    INSERT INTO test_table (id, name, age) 
    SELECT t1.id, t1.name, t1.age 
    FROM source_table t1 
    WHERE t1.id > 100;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content)
    
    # 测试获取所有字段位置
    all_fields = locator.get_all_field_positions()
    assert 'id' in all_fields, "应该包含id字段"
    assert 'name' in all_fields, "应该包含name字段"
    assert 'age' in all_fields, "应该包含age字段"
    
    # 测试在特定上下文中获取字段位置
    insert_fields = locator.get_all_field_positions(context='INSERT')
    assert 'id' in insert_fields, "INSERT上下文中应该包含id字段"
    
    print("  测试通过")
    return True


def main():
    """主测试函数"""
    print("开始全面的SQL解析测试...\n")
    
    # 运行所有测试
    tests = [
        test_empty_sql,
        test_simple_insert,
        test_multiple_insert_blocks,
        test_complex_sql_with_joins,
        test_sql_with_partition,
        test_sql_with_comments,
        test_get_all_field_positions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  测试失败: {e}")
            failed += 1
    
    print(f"\n测试完成: {passed} 个通过, {failed} 个失败")


if __name__ == "__main__":
    main()

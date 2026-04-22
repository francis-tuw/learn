#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库方言兼容性测试脚本
用于测试不同数据库方言的SQL解析和字段定位兼容性
"""
from sql_group_parser import FieldLocator, SQLGroupParser


def test_mysql_dialect():
    """测试MySQL方言"""
    print("测试MySQL方言...")
    
    # MySQL风格的SQL
    sql_content = """
    INSERT INTO `test_table` (`id`, `name`, `age`) 
    SELECT t1.`id`, t1.`name`, t1.`age` 
    FROM `source_table` t1 
    WHERE t1.`id` > 100;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content, dialect='mysql')
    
    # 测试字段定位
    positions = {
        'id': locator.get_position('id', context='INSERT'),
        'name': locator.get_position('name', context='INSERT'),
        'age': locator.get_position('age', context='INSERT'),
        'source_table.id': locator.get_position('id', context='SELECT')
    }
    
    print("MySQL字段定位结果:")
    for field, pos in positions.items():
        if pos:
            print(f"  {field}: 第{pos.line}行, 第{pos.column}列")
        else:
            print(f"  {field}: 未找到")
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    print(f"MySQL解析出 {result.total_blocks} 个INSERT块")
    
    return True


def test_postgresql_dialect():
    """测试PostgreSQL方言"""
    print("\n测试PostgreSQL方言...")
    
    # PostgreSQL风格的SQL
    sql_content = """
    INSERT INTO "test_table" ("id", "name", "age") 
    SELECT t1."id", t1."name", t1."age" 
    FROM "source_table" t1 
    WHERE t1."id" > 100;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content, dialect='postgresql')
    
    # 测试字段定位
    positions = {
        'id': locator.get_position('id', context='INSERT'),
        'name': locator.get_position('name', context='INSERT'),
        'age': locator.get_position('age', context='INSERT'),
        'source_table.id': locator.get_position('id', context='SELECT')
    }
    
    print("PostgreSQL字段定位结果:")
    for field, pos in positions.items():
        if pos:
            print(f"  {field}: 第{pos.line}行, 第{pos.column}列")
        else:
            print(f"  {field}: 未找到")
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    print(f"PostgreSQL解析出 {result.total_blocks} 个INSERT块")
    
    return True


def test_oracle_dialect():
    """测试Oracle方言"""
    print("\n测试Oracle方言...")
    
    # Oracle风格的SQL
    sql_content = """
    INSERT INTO "TEST_TABLE" ("ID", "NAME", "AGE") 
    SELECT t1."ID", t1."NAME", t1."AGE" 
    FROM "SOURCE_TABLE" t1 
    WHERE t1."ID" > 100;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content, dialect='oracle')
    
    # 测试字段定位
    positions = {
        'ID': locator.get_position('ID', context='INSERT'),
        'NAME': locator.get_position('NAME', context='INSERT'),
        'AGE': locator.get_position('AGE', context='INSERT'),
        'SOURCE_TABLE.ID': locator.get_position('ID', context='SELECT')
    }
    
    print("Oracle字段定位结果:")
    for field, pos in positions.items():
        if pos:
            print(f"  {field}: 第{pos.line}行, 第{pos.column}列")
        else:
            print(f"  {field}: 未找到")
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    print(f"Oracle解析出 {result.total_blocks} 个INSERT块")
    
    return True


def test_sqlserver_dialect():
    """测试SQL Server方言"""
    print("\n测试SQL Server方言...")
    
    # SQL Server风格的SQL
    sql_content = """
    INSERT INTO [test_table] ([id], [name], [age]) 
    SELECT t1.[id], t1.[name], t1.[age] 
    FROM [source_table] t1 
    WHERE t1.[id] > 100;
    """
    
    # 测试FieldLocator
    locator = FieldLocator(sql_content, dialect='sqlserver')
    
    # 测试字段定位
    positions = {
        'id': locator.get_position('id', context='INSERT'),
        'name': locator.get_position('name', context='INSERT'),
        'age': locator.get_position('age', context='INSERT'),
        'source_table.id': locator.get_position('id', context='SELECT')
    }
    
    print("SQL Server字段定位结果:")
    for field, pos in positions.items():
        if pos:
            print(f"  {field}: 第{pos.line}行, 第{pos.column}列")
        else:
            print(f"  {field}: 未找到")
    
    # 测试SQLGroupParser
    parser = SQLGroupParser()
    result = parser.parse(sql_content)
    print(f"SQL Server解析出 {result.total_blocks} 个INSERT块")
    
    return True


def test_dialect_support():
    """测试方言支持功能"""
    print("\n测试方言支持功能...")
    
    locator = FieldLocator("", dialect='mysql')
    
    test_dialects = ['mysql', 'postgresql', 'oracle', 'sqlserver', 'invalid']
    for dialect in test_dialects:
        supported = locator.support_dialect(dialect)
        print(f"  {dialect}: {'支持' if supported else '不支持'}")
    
    return True


def main():
    """主测试函数"""
    print("开始数据库方言兼容性测试...\n")
    
    # 运行所有测试
    tests = [
        test_mysql_dialect,
        test_postgresql_dialect,
        test_oracle_dialect,
        test_sqlserver_dialect,
        test_dialect_support
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
            print(f"测试失败: {e}")
            failed += 1
    
    print(f"\n测试完成: {passed} 个通过, {failed} 个失败")


if __name__ == "__main__":
    main()

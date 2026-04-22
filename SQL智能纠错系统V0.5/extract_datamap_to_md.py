#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel数据映射提取脚本
从ITMapping Excel文件中提取数据映射信息，生成结构化的Markdown文档
并将数据存入数据库的dataset_comparison_results和datamap_comparison_results表
"""

import argparse
import os
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl


class ITMappingDatabaseStorage:
    """IT-Mapping数据库存储类"""
    
    def __init__(self, db_path='data/review_history.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dataset_comparison_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                source_tables TEXT,
                compare_module TEXT NOT NULL,
                mapping_item TEXT,
                sql_content TEXT,
                is_consistent TEXT DEFAULT '',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_dataset_task_id 
            ON dataset_comparison_results(task_id)
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datamap_comparison_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                field_seq INTEGER NOT NULL,
                target_field_cn TEXT,
                target_field_en TEXT,
                extract_method TEXT,
                source_table TEXT,
                source_field_en TEXT,
                source_field_cn TEXT,
                default_value TEXT,
                transform_logic TEXT,
                sql_expression TEXT,
                is_consistent TEXT DEFAULT '',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_datamap_task_id 
            ON datamap_comparison_results(task_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_dataset_results(self, task_id, dataset_results):
        """保存数据源对比结果
        
        Args:
            task_id: 任务ID
            dataset_results: 数据源结果列表，每个元素包含:
                - group_id: 组别编号
                - source_tables: 源表信息
                - compare_module: 对比模块（数据源/表间关联/筛选条件）
                - mapping_item: IT-Mapping中的内容
                - sql_content: SQL内容（初始为空）
                - is_consistent: 是否一致（初始为空）
                - remark: 备注（初始为空）
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for r in dataset_results:
                cursor.execute('''
                    INSERT INTO dataset_comparison_results 
                    (task_id, group_id, source_tables, compare_module, mapping_item, sql_content, is_consistent, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id,
                    r.get('group_id', ''),
                    r.get('source_tables', ''),
                    r.get('compare_module', ''),
                    r.get('mapping_item', ''),
                    r.get('sql_content', ''),
                    r.get('is_consistent', ''),
                    r.get('remark', '')
                ))
            
            conn.commit()
            conn.close()
            print(f'[ITMappingDatabaseStorage] 保存数据源结果: task_id={task_id}, 共{len(dataset_results)}条')
            return True
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 保存数据源结果失败: {e}')
            return False
    
    def save_datamap_results(self, task_id, datamap_results):
        """保存数据映射对比结果
        
        Args:
            task_id: 任务ID
            datamap_results: 数据映射结果列表，每个元素包含:
                - group_id: 组别编号
                - field_seq: 字段序号
                - target_field_cn: 目标字段中文名
                - target_field_en: 目标字段英文名
                - extract_method: 取数方式
                - source_table: 源表
                - source_field_en: 源字段英文名
                - source_field_cn: 源字段中文名
                - default_value: 默认值
                - transform_logic: 字段加工逻辑
                - sql_expression: SQL表达式（初始为空）
                - is_consistent: 是否一致（初始为空）
                - remark: 备注（初始为空）
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for r in datamap_results:
                field_seq = r.get('field_seq', 0)
                try:
                    field_seq = int(field_seq) if field_seq else 0
                except (ValueError, TypeError):
                    field_seq = 0
                
                cursor.execute('''
                    INSERT INTO datamap_comparison_results 
                    (task_id, group_id, field_seq, target_field_cn, target_field_en, 
                     extract_method, source_table, source_field_en, source_field_cn,
                     default_value, transform_logic, sql_expression, is_consistent, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id,
                    r.get('group_id', ''),
                    field_seq,
                    r.get('target_field_cn', ''),
                    r.get('target_field_en', ''),
                    r.get('extract_method', ''),
                    r.get('source_table', ''),
                    r.get('source_field_en', ''),
                    r.get('source_field_cn', ''),
                    r.get('default_value', ''),
                    r.get('transform_logic', ''),
                    r.get('sql_expression', ''),
                    r.get('is_consistent', ''),
                    r.get('remark', '')
                ))
            
            conn.commit()
            conn.close()
            print(f'[ITMappingDatabaseStorage] 保存数据映射结果: task_id={task_id}, 共{len(datamap_results)}条')
            return True
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 保存数据映射结果失败: {e}')
            return False
    
    def clear_task_results(self, task_id):
        """清除指定任务的所有结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM dataset_comparison_results WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM datamap_comparison_results WHERE task_id = ?', (task_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 清除任务结果失败: {e}')
            return False
    
    def update_datamap_sql_and_comparison(self, task_id, group_id, field_seq, sql_expression, is_consistent, remark):
        """更新数据映射的SQL表达式和对比结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE datamap_comparison_results 
                SET sql_expression = ?, is_consistent = ?, remark = ?
                WHERE task_id = ? AND group_id = ? AND field_seq = ?
            ''', (sql_expression, is_consistent, remark, task_id, group_id, field_seq))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 更新数据映射结果失败: {e}')
            return False
    
    def update_dataset_sql_and_comparison(self, task_id, group_id, compare_module, mapping_item, sql_content, is_consistent, remark):
        """更新数据源的SQL内容和对比结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE dataset_comparison_results 
                SET sql_content = ?, is_consistent = ?, remark = ?
                WHERE task_id = ? AND group_id = ? AND compare_module = ? AND mapping_item = ?
            ''', (sql_content, is_consistent, remark, task_id, group_id, compare_module, mapping_item))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 更新数据源结果失败: {e}')
            return False
    
    def get_datamap_results(self, task_id):
        """获取指定任务的数据映射结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM datamap_comparison_results 
                WHERE task_id = ? 
                ORDER BY group_id, field_seq ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            return results
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 获取数据映射结果失败: {e}')
            return []
    
    def get_dataset_results(self, task_id):
        """获取指定任务的数据源结果"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM dataset_comparison_results 
                WHERE task_id = ? 
                ORDER BY group_id, id ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            return results
        except Exception as e:
            print(f'[ITMappingDatabaseStorage] 获取数据源结果失败: {e}')
            return []


def fuzzy_match_sheet(workbook, keywords):
    """
    模糊匹配sheet名称
    Args:
        workbook: openpyxl workbook对象
        keywords: 关键词列表，如 ['数据映射', 'DataMap']
    Returns:
        匹配的sheet对象，未找到返回None
    """
    for name in workbook.sheetnames:
        for keyword in keywords:
            if keyword in name:
                return workbook[name]
    return None


def load_excel(file_path):
    """
    加载Excel文件
    Args:
        file_path: Excel文件路径
    Returns:
        openpyxl workbook对象
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    if not file_path.lower().endswith('.xlsx'):
        raise ValueError("只支持.xlsx格式的Excel文件")
    
    return openpyxl.load_workbook(file_path, read_only=True, data_only=True)


def extract_table_list(sheet):
    """
    提取数据表清单
    Args:
        sheet: 数据源sheet对象
    Returns:
        数据表清单列表
    """
    tables = []
    for row_idx, row in enumerate(sheet.iter_rows(min_row=3, max_row=15, values_only=True), 3):
        if row[0] is not None and isinstance(row[0], int):
            table_info = {
                '序号': row[0],
                '所属系统': row[1],
                '数据表名_英文': row[2],
                '数据表别名': row[3],
                '数据表名_中文': row[4],
                '说明': row[5] if len(row) > 5 else None
            }
            tables.append(table_info)
    return tables


def extract_table_relations(sheet):
    """
    提取表间关联关系及筛选条件
    Args:
        sheet: 数据源sheet对象
    Returns:
        关联关系列表
    """
    relations = []
    for row_idx, row in enumerate(sheet.iter_rows(min_row=1, values_only=True), 1):
        if row[0] is not None and str(row[0]).startswith('MP'):
            relation_info = {
                '组别编号': row[0],
                '组别名称': row[1],
                '表间关联关系及筛选条件': row[3] if len(row) > 3 else None
            }
            relations.append(relation_info)
    return relations


def extract_data_source_sheet(workbook):
    """
    提取数据源sheet的所有信息
    Args:
        workbook: openpyxl workbook对象
    Returns:
        包含数据表清单和关联关系的字典
    """
    sheet = fuzzy_match_sheet(workbook, ['数据源', 'DataSet'])
    if sheet is None:
        raise ValueError("未找到数据源sheet")
    
    return {
        'table_list': extract_table_list(sheet),
        'relations': extract_table_relations(sheet)
    }


def extract_data_map_sheet(workbook):
    """
    提取数据映射sheet的所有信息
    Args:
        workbook: openpyxl workbook对象
    Returns:
        字段映射列表
    """
    sheet = fuzzy_match_sheet(workbook, ['数据映射', 'DataMap'])
    if sheet is None:
        raise ValueError("未找到数据映射sheet")
    
    headers = list(sheet.iter_rows(min_row=3, max_row=3, values_only=True))[0]
    
    field_mappings = []
    for row_idx, row in enumerate(sheet.iter_rows(min_row=4, values_only=True), 4):
        non_empty_count = sum(1 for c in row if c is not None)
        if non_empty_count < 3:
            continue
        
        field_info = {'_excel_row': row_idx}
        for idx, val in enumerate(row):
            if idx < len(headers) and headers[idx] is not None:
                field_info[headers[idx]] = val
        
        if field_info.get('字段中文名称') or field_info.get('字段英文名'):
            field_mappings.append(field_info)
    
    return field_mappings


def group_fields_by_group_id(field_mappings):
    """
    按组别编号分组字段
    Args:
        field_mappings: 字段映射列表
    Returns:
        按组别编号分组的字典
    """
    grouped = defaultdict(list)
    for field in field_mappings:
        group_id = field.get('组别编号', '未分组')
        if group_id and not str(group_id).startswith('='):
            grouped[group_id].append(field)
    return grouped


def generate_markdown(excel_path, data_source, field_mappings, output_path):
    """
    生成Markdown文档
    Args:
        excel_path: 原Excel文件路径
        data_source: 数据源信息
        field_mappings: 字段映射列表
        output_path: 输出文件路径
    """
    grouped_fields = group_fields_by_group_id(field_mappings)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# ITMapping 数据映射文档\n\n")
        f.write(f"**源文件**: {os.path.basename(excel_path)}\n\n")
        f.write("---\n\n")
        
        f.write("## 一、数据表清单\n\n")
        f.write("| 序号 | 所属系统 | 数据表名（英文） | 别名 | 数据表名（中文） |\n")
        f.write("|------|----------|------------------|------|------------------|\n")
        for table in data_source['table_list']:
            f.write(f"| {table['序号']} | {table['所属系统'] or ''} | {table['数据表名_英文'] or ''} | {table['数据表别名'] or ''} | {table['数据表名_中文'] or ''} |\n")
        f.write("\n---\n\n")
        
        f.write("## 二、表间关联关系及筛选条件\n\n")
        for relation in data_source['relations']:
            f.write(f"### 组别 {relation['组别编号']}: {relation['组别名称'] or ''}\n\n")
            if relation['表间关联关系及筛选条件']:
                content = relation['表间关联关系及筛选条件']
                content = content.replace('\n', '\n\n')
                f.write(f"```\n{content}\n```\n\n")
        f.write("---\n\n")
        
        f.write("## 三、字段映射详情\n\n")
        field_counter = 0
        for group_id in sorted(grouped_fields.keys()):
            fields = grouped_fields[group_id]
            f.write(f"### 组别 {group_id}\n\n")
            
            for field in fields:
                field_counter += 1
                cn_name = field.get('字段中文名称', '')
                en_name = field.get('字段英文名', '')
                excel_row = field.get('_excel_row', '')
                f.write(f"#### {field_counter}. {cn_name} ({en_name})\n\n")
                f.write(f"- **Excel行号**: 第{excel_row}行\n")
                

                

                
                description = field.get('数据项说明')
                if description:
                    desc_text = description.replace('\n', '\n  ')
                    f.write(f"- **数据项说明**: {desc_text}\n")
                
                extract_method = field.get('取数方式')
                if extract_method:
                    f.write(f"- **取数方式**: {extract_method}\n")
                
                source_system = field.get('源系统编码')
                if source_system:
                    f.write(f"- **源系统编码**: {source_system}\n")
                
                source_table = field.get('数据表')
                if source_table:
                    f.write(f"- **源数据表**: {source_table}\n")
                
                source_field_en = field.get('字段名（英文）')
                if source_field_en:
                    f.write(f"- **源字段名（英文）**: {source_field_en}\n")
                
                source_field_cn = field.get('字段名（中文）')
                if source_field_cn:
                    f.write(f"- **源字段名（中文）**: {source_field_cn}\n")
                
                default_value = field.get('默认值')
                if default_value:
                    f.write(f"- **默认值**: {default_value}\n")
                
                transform_logic = field.get('字段加工逻辑')
                if transform_logic:
                    logic_text = transform_logic.replace('\n', '\n  ')
                    f.write(f"- **字段加工逻辑**: {logic_text}\n")
                
                remark = field.get('备注/说明')
                if remark:
                    remark_text = remark.replace('\n', '\n  ')
                    f.write(f"- **备注/说明**: {remark_text}\n")
                
                f.write("\n")
            
            f.write("---\n\n")
        
        f.write("## 四、取数方式统计\n\n")
        extract_methods = defaultdict(int)
        for field in field_mappings:
            method = field.get('取数方式', '未指定')
            if method and not str(method).startswith('='):
                extract_methods[method] += 1
        
        f.write("| 取数方式 | 字段数量 |\n")
        f.write("|----------|----------|\n")
        for method, count in sorted(extract_methods.items(), key=lambda x: -x[1]):
            f.write(f"| {method} | {count} |\n")
        f.write("\n")


def prepare_dataset_results(data_source, task_id):
    """准备数据源对比结果数据
    
    Args:
        data_source: 数据源信息
        task_id: 任务ID
        
    Returns:
        数据源对比结果列表
    """
    results = []
    
    for relation in data_source.get('relations', []):
        group_id = relation.get('组别编号', '')
        group_name = relation.get('组别名称', '')
        relation_text = relation.get('表间关联关系及筛选条件', '')
        
        tables_for_group = []
        for table in data_source.get('table_list', []):
            tables_for_group.append(f"{table.get('数据表别名', '')}:{table.get('数据表名_中文', '')}")
        source_tables = '、\n'.join(tables_for_group) if tables_for_group else ''
        
        if relation_text:
            lines = relation_text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if '表间关联' in line:
                    current_section = '表间关联'
                    continue
                elif '筛选条件' in line:
                    current_section = '筛选条件'
                    continue
                
                if current_section and (line.startswith('A、') or line.startswith('B、') or 
                                        line.startswith('C、') or line.startswith('D、') or
                                        line.startswith('E、') or line.startswith('F、')):
                    results.append({
                        'task_id': task_id,
                        'group_id': group_id,
                        'source_tables': source_tables,
                        'compare_module': current_section,
                        'mapping_item': line,
                        'sql_content': '',
                        'is_consistent': '未检查',
                        'remark': ''
                    })
    
    return results


def prepare_datamap_results(field_mappings, task_id):
    """准备数据映射对比结果数据
    
    Args:
        field_mappings: 字段映射列表
        task_id: 任务ID
        
    Returns:
        数据映射对比结果列表
    """
    results = []
    
    for field in field_mappings:
        group_id = field.get('组别编号', '')
        field_seq = field.get('字段序号', 0)
        
        try:
            field_seq = int(field_seq) if field_seq else 0
        except (ValueError, TypeError):
            field_seq = 0
        
        results.append({
            'task_id': task_id,
            'group_id': str(group_id),
            'field_seq': field_seq,
            'target_field_cn': str(field.get('字段中文名称', '') or ''),
            'target_field_en': str(field.get('字段英文名', '') or ''),
            'extract_method': str(field.get('取数方式', '') or ''),
            'source_table': str(field.get('数据表', '') or ''),
            'source_field_en': str(field.get('字段名（英文）', '') or ''),
            'source_field_cn': str(field.get('字段名（中文）', '') or ''),
            'default_value': str(field.get('默认值', '') or ''),
            'transform_logic': str(field.get('字段加工逻辑', '') or ''),
            'sql_expression': '',
            'is_consistent': '未检查',
            'remark': ''
        })
    
    return results


def extract_and_store_to_db(excel_path, task_id=None, db_path='data/review_history.db'):
    """从IT-Mapping Excel文件提取数据并存储到数据库
    
    这是第一步的核心功能：
    1. 解析IT-Mapping Excel文件
    2. 生成MD文件
    3. 将数据存入dataset_comparison_results和datamap_comparison_results表
    4. 保持"存储过程SQL"、"是否一致"、"备注"三列为空
    
    Args:
        excel_path: Excel文件路径
        task_id: 任务ID（可选，不提供则自动生成）
        db_path: 数据库路径
        
    Returns:
        dict: 包含task_id、md文件路径、存储结果等信息
    """
    if task_id is None:
        task_id = str(uuid.uuid4())
    
    excel_path = os.path.abspath(excel_path)
    output_dir = os.path.dirname(excel_path)
    base_name = os.path.splitext(os.path.basename(excel_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.md")
    
    print(f"[第一步] 正在加载Excel文件: {excel_path}")
    workbook = load_excel(excel_path)
    
    print("[第一步] 正在提取数据源信息...")
    data_source = extract_data_source_sheet(workbook)
    
    print("[第一步] 正在提取数据映射信息...")
    field_mappings = extract_data_map_sheet(workbook)
    
    workbook.close()
    
    print(f"[第一步] 正在生成Markdown文档: {output_path}")
    generate_markdown(excel_path, data_source, field_mappings, output_path)
    
    print("[第一步] 正在准备数据库存储数据...")
    dataset_results = prepare_dataset_results(data_source, task_id)
    datamap_results = prepare_datamap_results(field_mappings, task_id)
    
    print(f"[第一步] 正在存储到数据库: task_id={task_id}")
    db_storage = ITMappingDatabaseStorage(db_path)
    db_storage.clear_task_results(task_id)
    
    dataset_success = db_storage.save_dataset_results(task_id, dataset_results)
    datamap_success = db_storage.save_datamap_results(task_id, datamap_results)
    
    result = {
        'task_id': task_id,
        'excel_path': excel_path,
        'md_path': output_path,
        'field_mappings_count': len(field_mappings),
        'dataset_results_count': len(dataset_results),
        'datamap_results_count': len(datamap_results),
        'dataset_save_success': dataset_success,
        'datamap_save_success': datamap_success,
        'success': dataset_success and datamap_success
    }
    
    print(f"[第一步] 完成! 共提取 {len(field_mappings)} 个字段映射")
    print(f"[第一步] 数据源结果: {len(dataset_results)} 条")
    print(f"[第一步] 数据映射结果: {len(datamap_results)} 条")
    print(f"[第一步] MD文件: {output_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='从ITMapping Excel文件提取数据映射信息并生成Markdown文档，同时存入数据库')
    parser.add_argument('excel_file', help='Excel文件路径')
    parser.add_argument('-o', '--output', help='输出目录（默认与Excel文件同目录）', default=None)
    parser.add_argument('--task-id', help='任务ID（可选，不提供则自动生成）', default=None)
    parser.add_argument('--db', help='数据库路径', default='data/review_history.db')
    parser.add_argument('--skip-db', action='store_true', help='跳过数据库存储，仅生成MD文件')
    
    args = parser.parse_args()
    
    excel_path = os.path.abspath(args.excel_file)
    
    if args.skip_db:
        if args.output:
            output_dir = os.path.abspath(args.output)
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = os.path.dirname(excel_path)
        
        base_name = os.path.splitext(os.path.basename(excel_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}.md")
        
        print(f"正在加载Excel文件: {excel_path}")
        workbook = load_excel(excel_path)
        
        print("正在提取数据源信息...")
        data_source = extract_data_source_sheet(workbook)
        
        print("正在提取数据映射信息...")
        field_mappings = extract_data_map_sheet(workbook)
        
        workbook.close()
        
        print(f"正在生成Markdown文档: {output_path}")
        generate_markdown(excel_path, data_source, field_mappings, output_path)
        
        print(f"完成! 共提取 {len(field_mappings)} 个字段映射")
        print(f"输出文件: {output_path}")
    else:
        result = extract_and_store_to_db(
            excel_path=excel_path,
            task_id=args.task_id,
            db_path=args.db
        )
        
        if result['success']:
            print(f"\n任务ID: {result['task_id']}")
            print(f"MD文件: {result['md_path']}")
        else:
            print("\n存储到数据库失败!")
            return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

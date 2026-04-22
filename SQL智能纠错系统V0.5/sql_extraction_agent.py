# -*- coding: utf-8 -*-
"""
SQL提取和对比Agent模块
实现第二步（SQL提取）和第三步（一致性对比）的核心功能
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SQLExtractionResult:
    """SQL提取结果"""
    group_id: str
    field_seq: int
    target_field: str
    sql_expression: str
    found: bool
    error_message: str = ""


@dataclass
class ComparisonResult:
    """对比结果"""
    group_id: str
    field_seq: int
    target_field: str
    is_consistent: str
    remark: str
    mapping_info: Dict = field(default_factory=dict)
    sql_info: Dict = field(default_factory=dict)


class SQLFieldExtractorAgent:
    """SQL字段提取Agent
    
    第二步的核心实现：
    根据数据表中的单行信息，从SQL文件中按照分组查找对应的SQL取值
    格式：{源表字段加工信息} AS {目标表字段名}
    """
    
    def __init__(self, sql_content: str):
        self.sql_content = sql_content
        self.insert_blocks = self._parse_insert_blocks()
    
    def _parse_insert_blocks(self) -> List[Dict]:
        """解析SQL文件中的所有INSERT块"""
        blocks = []
        
        insert_pattern = re.compile(
            r'INSERT\s+INTO\s+(\w+)(?:\s+PARTITION\s*\(([^)]+)\))?\s*\(([\s\S]*?)\)\s*SELECT\s+([\s\S]*?)\s+FROM\s+([\s\S]*?)(?:WHERE\s+([\s\S]*?))?(?:;|$)',
            re.IGNORECASE
        )
        
        for match in insert_pattern.finditer(self.sql_content):
            target_table = match.group(1)
            partition = match.group(2) or ''
            insert_fields_str = match.group(3)
            select_values_str = match.group(4)
            from_clause_str = match.group(5)
            where_clause_str = match.group(6) or ''
            
            insert_fields = self._parse_field_list(insert_fields_str)
            select_values = self._parse_select_values(select_values_str)
            from_clause, join_clauses = self._parse_from_clause(from_clause_str)
            
            field_mapping = self._build_field_mapping_by_alias(select_values)
            
            group_id = self._extract_group_id(match.start())
            
            blocks.append({
                'target_table': target_table,
                'partition': partition,
                'group_id': group_id,
                'insert_fields': insert_fields,
                'select_values': select_values,
                'field_mapping': field_mapping,
                'from_clause': from_clause,
                'join_clauses': join_clauses,
                'where_clause': where_clause_str.strip(),
                'start_pos': match.start(),
                'end_pos': match.end()
            })
        
        return blocks
    
    def _build_field_mapping_by_alias(self, select_values: List[str]) -> Dict[str, str]:
        """根据AS别名构建字段映射
        
        关键改进：不再依赖位置索引，而是根据AS后面的别名来匹配字段
        这样即使SQL中缺少某个字段，也不会导致后续字段全部错位
        
        Args:
            select_values: SELECT值列表
            
        Returns:
            Dict[str, str]: 别名 -> SQL表达式的映射
        """
        field_mapping = {}
        
        for expr in select_values:
            alias = self._extract_alias_from_expression(expr)
            if alias:
                field_mapping[alias] = expr
        
        return field_mapping
    
    def _extract_alias_from_expression(self, expression: str) -> Optional[str]:
        """从SQL表达式中提取AS别名
        
        支持以下格式：
        - T.FIELD_NAME AS ALIAS
        - T.FIELD_NAME AS "ALIAS"
        - FUNCTION() AS ALIAS
        - CASE ... END AS ALIAS
        - 'literal' AS ALIAS
        - NULL AS ALIAS
        
        Args:
            expression: SQL表达式
            
        Returns:
            Optional[str]: 提取的别名，如果无法提取则返回None
        """
        expression = expression.strip()
        
        as_pattern = re.compile(r'\bAS\s+([\'"]?)(\w+)\1\s*$', re.IGNORECASE)
        match = as_pattern.search(expression)
        
        if match:
            return match.group(2)
        
        parts = expression.split()
        if len(parts) >= 2:
            for i in range(len(parts) - 1, -1, -1):
                if parts[i].upper() == 'AS' and i + 1 < len(parts):
                    alias = parts[i + 1].strip('\'"')
                    if re.match(r'^\w+$', alias):
                        return alias
        
        return None
    
    def _parse_field_list(self, fields_str: str) -> List[str]:
        """解析INSERT字段列表"""
        fields = []
        for line in fields_str.split('\n'):
            clean_line = re.sub(r'--.*$', '', line).strip()
            if clean_line:
                field = clean_line.rstrip(',').strip()
                if field:
                    fields.append(field)
        return fields
    
    def _parse_select_values(self, select_str: str) -> List[str]:
        """解析SELECT值列表，处理嵌套括号和CASE语句"""
        values = []
        current = ''
        paren_depth = 0
        case_depth = 0
        
        for char in select_str:
            if char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == ',' and paren_depth == 0 and case_depth == 0:
                if current.strip():
                    values.append(current.strip())
                current = ''
            else:
                current += char
            
            if current.upper().endswith('CASE'):
                case_depth += 1
            elif case_depth > 0 and current.upper().rstrip().endswith('END'):
                case_depth -= 1
        
        if current.strip():
            values.append(current.strip())
        
        return values
    
    def _parse_from_clause(self, from_str: str) -> Tuple[str, List[Dict]]:
        """解析FROM子句和JOIN条件"""
        from_str = from_str.strip()
        
        from_match = re.search(r'^(\w+(?:\s+\w+)?)', from_str, re.IGNORECASE)
        from_clause = from_match.group(1) if from_match else ''
        
        join_clauses = []
        join_pattern = re.compile(
            r'(LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|JOIN)\s+(\w+(?:\s+\w+)?)\s+ON\s+([\s\S]*?)(?=(?:LEFT|RIGHT|INNER|JOIN|WHERE|;|$))',
            re.IGNORECASE
        )
        
        for match in join_pattern.finditer(from_str):
            join_clauses.append({
                'type': match.group(1).upper(),
                'table': match.group(2).strip(),
                'condition': match.group(3).strip().rstrip('AND').strip()
            })
        
        return from_clause, join_clauses
    
    def _extract_group_id(self, position: int) -> str:
        """从SQL内容中提取分组ID"""
        before_sql = self.sql_content[:position]
        lines = before_sql.split('\n')[-20:]
        
        for line in reversed(lines):
            match = re.search(r'(MP\d+)', line, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return ''
    
    def get_block_by_group_id(self, group_id: str) -> Optional[Dict]:
        """根据分组ID获取INSERT块"""
        for block in self.insert_blocks:
            if block['group_id'].upper() == group_id.upper():
                return block
        return None
    
    def extract_sql_expression(self, group_id: str, target_field: str) -> SQLExtractionResult:
        """提取指定分组和目标字段的SQL表达式
        
        Args:
            group_id: 分组ID
            target_field: 目标字段名
            
        Returns:
            SQLExtractionResult: 提取结果
        """
        block = self.get_block_by_group_id(group_id)
        
        if block is None:
            return SQLExtractionResult(
                group_id=group_id,
                field_seq=0,
                target_field=target_field,
                sql_expression='',
                found=False,
                error_message=f'未找到分组 {group_id} 对应的INSERT块'
            )
        
        field_mapping = block.get('field_mapping', {})
        
        if target_field in field_mapping:
            return SQLExtractionResult(
                group_id=group_id,
                field_seq=0,
                target_field=target_field,
                sql_expression=field_mapping[target_field],
                found=True
            )
        
        for field_name, expression in field_mapping.items():
            if field_name.upper() == target_field.upper():
                return SQLExtractionResult(
                    group_id=group_id,
                    field_seq=0,
                    target_field=target_field,
                    sql_expression=expression,
                    found=True
                )
        
        return SQLExtractionResult(
            group_id=group_id,
            field_seq=0,
            target_field=target_field,
            sql_expression='',
            found=False,
            error_message=f'在分组 {group_id} 中未找到字段 {target_field}'
        )
    
    def extract_all_for_group(self, group_id: str) -> Dict[str, str]:
        """提取指定分组的所有字段映射
        
        Args:
            group_id: 分组ID
            
        Returns:
            Dict[str, str]: 字段名到SQL表达式的映射
        """
        block = self.get_block_by_group_id(group_id)
        if block:
            return block.get('field_mapping', {})
        return {}
    
    def get_group_ids(self) -> List[str]:
        """获取所有分组ID"""
        return list(set(block['group_id'] for block in self.insert_blocks if block['group_id']))


class ConsistencyComparatorAgent:
    """一致性对比Agent
    
    第三步的核心实现：
    对单行信息的IT-Mapping信息与存储过程SQL列信息进行对比，
    检查是否一致，如果错误，在"备注列"说明原因
    """
    
    def __init__(self):
        self.comparison_rules = self._init_comparison_rules()
    
    def _init_comparison_rules(self) -> List[Dict]:
        """初始化对比规则"""
        return [
            {
                'name': 'source_field_check',
                'description': '检查源字段是否在SQL表达式中出现',
                'severity': 'high'
            },
            {
                'name': 'transform_logic_check',
                'description': '检查转换逻辑是否与SQL表达式匹配',
                'severity': 'medium'
            },
            {
                'name': 'default_value_check',
                'description': '检查默认值是否与SQL表达式匹配',
                'severity': 'medium'
            },
            {
                'name': 'case_when_check',
                'description': '检查CASE WHEN逻辑是否匹配',
                'severity': 'high'
            }
        ]
    
    def compare_field(self, mapping_info: Dict, sql_expression: str) -> ComparisonResult:
        """对比单个字段的一致性
        
        Args:
            mapping_info: IT-Mapping中的字段信息，包含:
                - group_id: 分组ID
                - field_seq: 字段序号
                - target_field_en: 目标字段英文名
                - source_field_en: 源字段英文名
                - transform_logic: 字段加工逻辑
                - default_value: 默认值
                - extract_method: 取数方式
            sql_expression: SQL表达式
            
        Returns:
            ComparisonResult: 对比结果
        """
        group_id = mapping_info.get('group_id', '')
        field_seq = mapping_info.get('field_seq', 0)
        target_field = mapping_info.get('target_field_en', '')
        
        discrepancies = []
        
        if not sql_expression:
            return ComparisonResult(
                group_id=group_id,
                field_seq=field_seq,
                target_field=target_field,
                is_consistent='否',
                remark='SQL表达式中未找到对应字段',
                mapping_info=mapping_info,
                sql_info={'sql_expression': ''}
            )
        
        source_field = mapping_info.get('source_field_en', '')
        transform_logic = mapping_info.get('transform_logic', '')
        default_value = mapping_info.get('default_value', '')
        extract_method = mapping_info.get('extract_method', '')
        
        if source_field and source_field.strip():
            if not self._check_source_field_in_sql(source_field, sql_expression):
                discrepancies.append(f'源字段"{source_field}"未在SQL表达式中找到')
        
        if transform_logic and transform_logic.strip():
            logic_result = self._check_transform_logic(transform_logic, sql_expression)
            if not logic_result['match']:
                discrepancies.append(logic_result['message'])
        
        if extract_method:
            method_result = self._check_extract_method(extract_method, sql_expression, mapping_info)
            if not method_result['match']:
                discrepancies.append(method_result['message'])
        elif default_value and default_value.strip():
            if not self._check_default_value_enhanced(default_value, sql_expression):
                discrepancies.append(f'默认值"{default_value}"未在SQL表达式中找到')
        
        is_consistent = '是' if len(discrepancies) == 0 else '否'
        remark = '; '.join(discrepancies) if discrepancies else ''
        
        return ComparisonResult(
            group_id=group_id,
            field_seq=field_seq,
            target_field=target_field,
            is_consistent=is_consistent,
            remark=remark,
            mapping_info=mapping_info,
            sql_info={'sql_expression': sql_expression}
        )
    
    def _check_source_field_in_sql(self, source_field: str, sql_expression: str) -> bool:
        """检查源字段是否在SQL表达式中"""
        patterns = [
            rf'\b{re.escape(source_field)}\b',
            rf'\.{re.escape(source_field)}\b',
            rf'\b{re.escape(source_field)}\s*,',
            rf'\b{re.escape(source_field)}\s+AS',
        ]
        return any(re.search(p, sql_expression, re.IGNORECASE) for p in patterns)
    
    def _check_transform_logic(self, transform_logic: str, sql_expression: str) -> Dict:
        """检查转换逻辑是否匹配"""
        logic_lower = transform_logic.lower()
        sql_lower = sql_expression.lower()
        
        if '=>' in transform_logic or '->' in transform_logic or '＝' in transform_logic:
            mapping_rules = self._parse_mapping_rules(transform_logic)
            if mapping_rules:
                return self._compare_mapping_rules(mapping_rules, sql_expression)
        
        if 'substr' in logic_lower or '截取' in logic_lower:
            if 'substr' not in sql_lower and 'substring' not in sql_lower:
                return {
                    'match': False,
                    'message': f'转换逻辑包含截取操作，但SQL表达式中未找到SUBSTR/SUBSTRING函数'
                }
        
        if 'nvl' in logic_lower or 'coalesce' in logic_lower or '空值' in logic_lower:
            if 'nvl' not in sql_lower and 'coalesce' not in sql_lower:
                return {
                    'match': False,
                    'message': f'转换逻辑包含空值处理，但SQL表达式中未找到NVL/COALESCE函数'
                }
        
        if 'case' in logic_lower or '条件' in logic_lower or '判断' in logic_lower:
            if 'case' not in sql_lower:
                return {
                    'match': False,
                    'message': f'转换逻辑包含条件判断，但SQL表达式中未找到CASE WHEN语句'
                }
        
        if 'concat' in logic_lower or '拼接' in logic_lower or '连接' in logic_lower:
            if 'concat' not in sql_lower and '||' not in sql_expression:
                return {
                    'match': False,
                    'message': f'转换逻辑包含字符串拼接，但SQL表达式中未找到CONCAT或||操作'
                }
        
        if 'trim' in logic_lower or '去空格' in logic_lower:
            if 'trim' not in sql_lower:
                return {
                    'match': False,
                    'message': f'转换逻辑包含去空格操作，但SQL表达式中未找到TRIM函数'
                }
        
        return {'match': True, 'message': ''}
    
    def _parse_mapping_rules(self, transform_logic: str) -> List[Dict]:
        """解析IT-Mapping中的码值转换规则
        
        支持格式:
        - M => 01 -主管分行
        - B => 02-业务分行
        - A->值1
        - A＝值1
        """
        rules = []
        
        patterns = [
            r"(['\"]?)(\w+)\1\s*=>\s*(['\"]?)(\w+)\3",
            r"(['\"]?)(\w+)\1\s*->\s*(['\"]?)(\w+)\3",
            r"(['\"]?)(\w+)\1\s*＝\s*(['\"]?)(\w+)\3",
            r"(['\"]?)(\w+)\1\s*=\s*(['\"]?)(\w+)\3",
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, transform_logic):
                source_value = match.group(2)
                target_value = match.group(4)
                rules.append({
                    'source': source_value,
                    'target': target_value
                })
        
        return rules
    
    def _compare_mapping_rules(self, mapping_rules: List[Dict], sql_expression: str) -> Dict:
        """对比IT-Mapping码值规则与SQL CASE WHEN是否一致"""
        sql_lower = sql_expression.lower()
        
        if 'case' not in sql_lower:
            return {
                'match': False,
                'message': 'IT-Mapping包含码值转换规则，但SQL表达式中未找到CASE WHEN语句'
            }
        
        sql_rules = self._extract_case_when_rules(sql_expression)
        
        if not sql_rules:
            return {'match': True, 'message': ''}
        
        discrepancies = []
        
        for mapping_rule in mapping_rules:
            source_val = mapping_rule['source']
            target_val = mapping_rule['target']
            
            found = False
            for sql_rule in sql_rules:
                if sql_rule['condition'].upper() == source_val.upper():
                    found = True
                    if sql_rule['result'] != target_val:
                        discrepancies.append(
                            f'码值转换不一致: 源值"{source_val}"在IT-Mapping中应为"{target_val}"，'
                            f'但SQL中为"{sql_rule["result"]}"'
                        )
                    break
            
            if not found:
                discrepancies.append(f'码值转换缺失: 源值"{source_val}"在SQL的CASE WHEN中未找到对应条件')
        
        if discrepancies:
            return {
                'match': False,
                'message': '; '.join(discrepancies)
            }
        
        return {'match': True, 'message': ''}
    
    def _extract_case_when_rules(self, sql_expression: str) -> List[Dict]:
        """从SQL CASE WHEN表达式中提取转换规则"""
        rules = []
        
        when_pattern = re.compile(
            r"WHEN\s+(.+?)\s*=\s*['\"]?(\w+)['\"]?\s+THEN\s+['\"]?(\w+)['\"]?",
            re.IGNORECASE
        )
        
        for match in when_pattern.finditer(sql_expression):
            condition_field = match.group(1).strip()
            condition_value = match.group(2)
            result_value = match.group(3)
            
            rules.append({
                'field': condition_field,
                'condition': condition_value,
                'result': result_value
            })
        
        return rules
    
    def _check_default_value(self, default_value: str, sql_expression: str) -> bool:
        """检查默认值是否匹配（旧方法，保留兼容）"""
        default_clean = default_value.strip().strip("'\"")
        sql_lower = sql_expression.lower()
        
        if f"'{default_clean.lower()}'" in sql_lower:
            return True
        if default_clean.lower() in sql_lower:
            return True
        if f'"{default_clean}"' in sql_expression:
            return True
        
        return False
    
    def _check_default_value_enhanced(self, default_value: str, sql_expression: str) -> bool:
        """检查默认值是否匹配（增强版，包含变量映射规则）"""
        VARIABLE_EQUIVALENT = {
            '跑批基准日期': ['V_SHORT_DATE', 'V_LONG_DATE', 'P_I_DATE'],
            '当前时间': ['CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NOW()'],
            '批次ID': ['P_I_BATCHID', 'V_BATCH_ID'],
            'JOBID': ['P_I_JOBID', 'V_JOB_ID'],
        }
        
        FUNCTION_EQUIVALENT = ['UUID', 'UUID()', 'UUID（）', 'CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP()']
        
        default_upper = default_value.upper().replace('（', '(').replace('）', ')')
        sql_upper = sql_expression.upper().replace('（', '(').replace('）', ')')
        
        for func in FUNCTION_EQUIVALENT:
            func_clean = func.replace('（', '(').replace('）', ')')
            if default_upper.strip() == func_clean or default_upper.strip() == func_clean.replace('()', ''):
                if func_clean in sql_upper or func.replace('()', '') in sql_upper:
                    return True
        
        for mapping_key, sql_vars in VARIABLE_EQUIVALENT.items():
            if default_value == mapping_key:
                for sql_var in sql_vars:
                    if sql_var in sql_expression:
                        return True
        
        default_clean = default_value.replace('（', '(').replace('）', ')')
        sql_clean = sql_expression.replace('（', '(').replace('）', ')')
        
        patterns = [
            rf"'{re.escape(default_clean)}'",
            rf'"{re.escape(default_clean)}"',
            rf'\b{re.escape(default_clean)}\b',
        ]
        for pattern in patterns:
            if re.search(pattern, sql_clean, re.IGNORECASE):
                return True
        
        return False
    
    def _check_extract_method(self, extract_method: str, sql_expression: str, mapping_info: Dict) -> Dict:
        """检查取数方式是否匹配"""
        method_lower = extract_method.lower()
        sql_lower = sql_expression.lower()
        
        VARIABLE_EQUIVALENT = {
            '跑批基准日期': ['V_SHORT_DATE', 'V_LONG_DATE', 'P_I_DATE'],
            '当前时间': ['CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NOW()'],
            '批次ID': ['P_I_BATCHID', 'V_BATCH_ID'],
            'JOBID': ['P_I_JOBID', 'V_JOB_ID'],
        }
        
        FUNCTION_EQUIVALENT = ['UUID', 'UUID()', 'UUID（）', 'CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP()']
        
        if '留空' in method_lower or '置空' in method_lower or '为空' in method_lower:
            if sql_lower.strip() == 'null' or sql_expression.strip() == 'NULL AS':
                return {'match': True, 'message': ''}
            if 'null' in sql_lower and 'as' in sql_lower:
                null_check = re.search(r'\bNULL\s+AS\b', sql_expression, re.IGNORECASE)
                if null_check:
                    return {'match': True, 'message': ''}
            return {
                'match': False,
                'message': f'取数方式为"留空"，但SQL表达式不是NULL，实际为: {sql_expression}'
            }
        
        if '直接取值' in method_lower or '直接映射' in method_lower or '字段直取' in method_lower:
            source_field = mapping_info.get('source_field_en', '')
            if source_field and source_field in sql_expression:
                return {'match': True, 'message': ''}
            return {
                'match': False,
                'message': f'取数方式为直接取值，但源字段"{source_field}"未在SQL表达式中直接出现'
            }
        
        if '默认值' in method_lower:
            default_value = mapping_info.get('default_value', '')
            if default_value:
                default_upper = default_value.upper().replace('（', '(').replace('）', ')')
                sql_upper = sql_expression.upper().replace('（', '(').replace('）', ')')
                
                for func in FUNCTION_EQUIVALENT:
                    func_clean = func.replace('（', '(').replace('）', ')')
                    if default_upper.strip() == func_clean or default_upper.strip() == func_clean.replace('()', ''):
                        if func_clean in sql_upper or func.replace('()', '') in sql_upper:
                            return {'match': True, 'message': ''}
                
                for mapping_key, sql_vars in VARIABLE_EQUIVALENT.items():
                    if default_value == mapping_key:
                        for sql_var in sql_vars:
                            if sql_var in sql_expression:
                                return {'match': True, 'message': ''}
                
                default_clean = default_value.replace('（', '(').replace('）', ')')
                sql_clean = sql_expression.replace('（', '(').replace('）', ')')
                
                patterns = [
                    rf"'{re.escape(default_clean)}'",
                    rf'"{re.escape(default_clean)}"',
                    rf'\b{re.escape(default_clean)}\b',
                ]
                for pattern in patterns:
                    if re.search(pattern, sql_clean, re.IGNORECASE):
                        return {'match': True, 'message': ''}
                
                return {
                    'match': False,
                    'message': f'取数方式为默认值，但默认值"{default_value}"未在SQL表达式中找到'
                }
            return {'match': True, 'message': ''}
        
        if '加工' in method_lower or '转换' in method_lower or '码值转换' in method_lower:
            transform_logic = mapping_info.get('transform_logic', '')
            if transform_logic:
                return self._check_transform_logic(transform_logic, sql_expression)
        
        return {'match': True, 'message': ''}


class SQLExtractionAndComparisonPipeline:
    """SQL提取和对比流水线
    
    整合第二步和第三步的完整流程
    """
    
    def __init__(self, sql_content: str, db_storage):
        self.sql_extractor = SQLFieldExtractorAgent(sql_content)
        self.comparator = ConsistencyComparatorAgent()
        self.db_storage = db_storage
    
    def process_single_record(self, task_id: str, record: Dict) -> ComparisonResult:
        """处理单条记录
        
        Args:
            task_id: 任务ID
            record: 数据库中的单条记录
            
        Returns:
            ComparisonResult: 对比结果
        """
        group_id = record.get('group_id', '')
        target_field = record.get('target_field_en', '')
        
        extraction_result = self.sql_extractor.extract_sql_expression(group_id, target_field)
        
        mapping_info = {
            'group_id': group_id,
            'field_seq': record.get('field_seq', 0),
            'target_field_en': target_field,
            'target_field_cn': record.get('target_field_cn', ''),
            'source_field_en': record.get('source_field_en', ''),
            'source_field_cn': record.get('source_field_cn', ''),
            'transform_logic': record.get('transform_logic', ''),
            'default_value': record.get('default_value', ''),
            'extract_method': record.get('extract_method', ''),
            'source_table': record.get('source_table', '')
        }
        
        comparison_result = self.comparator.compare_field(mapping_info, extraction_result.sql_expression)
        
        self.db_storage.update_datamap_sql_and_comparison(
            task_id=task_id,
            group_id=group_id,
            field_seq=record.get('field_seq', 0),
            sql_expression=extraction_result.sql_expression,
            is_consistent=comparison_result.is_consistent,
            remark=comparison_result.remark
        )
        
        return comparison_result
    
    def process_all_records(self, task_id: str) -> Dict:
        """处理指定任务的所有记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 处理结果统计
        """
        records = self.db_storage.get_datamap_results(task_id)
        
        results = {
            'total': len(records),
            'consistent': 0,
            'inconsistent': 0,
            'errors': 0,
            'details': []
        }
        
        for record in records:
            try:
                comparison_result = self.process_single_record(task_id, record)
                
                if comparison_result.is_consistent == '是':
                    results['consistent'] += 1
                else:
                    results['inconsistent'] += 1
                
                results['details'].append({
                    'group_id': comparison_result.group_id,
                    'field_seq': comparison_result.field_seq,
                    'target_field': comparison_result.target_field,
                    'is_consistent': comparison_result.is_consistent,
                    'remark': comparison_result.remark
                })
                
            except Exception as e:
                results['errors'] += 1
                results['details'].append({
                    'group_id': record.get('group_id', ''),
                    'field_seq': record.get('field_seq', 0),
                    'target_field': record.get('target_field_en', ''),
                    'is_consistent': '否',
                    'remark': f'处理错误: {str(e)}'
                })
        
        return results
    
    def process_dataset_records(self, task_id: str, sql_content: str) -> Dict:
        """处理数据源记录（表间关联和筛选条件）
        
        Args:
            task_id: 任务ID
            sql_content: SQL内容
            
        Returns:
            Dict: 处理结果统计
        """
        records = self.db_storage.get_dataset_results(task_id)
        
        results = {
            'total': len(records),
            'consistent': 0,
            'inconsistent': 0,
            'errors': 0
        }
        
        for record in records:
            try:
                group_id = record.get('group_id', '')
                compare_module = record.get('compare_module', '')
                mapping_item = record.get('mapping_item', '')
                
                sql_snippet = self._extract_sql_snippet_for_dataset(
                    group_id, compare_module, mapping_item, sql_content
                )
                
                is_consistent, remark = self._compare_dataset_item(
                    compare_module, mapping_item, sql_snippet
                )
                
                self.db_storage.update_dataset_sql_and_comparison(
                    task_id=task_id,
                    group_id=group_id,
                    compare_module=compare_module,
                    mapping_item=mapping_item,
                    sql_content=sql_snippet,
                    is_consistent=is_consistent,
                    remark=remark
                )
                
                if is_consistent == '是':
                    results['consistent'] += 1
                else:
                    results['inconsistent'] += 1
                    
            except Exception as e:
                results['errors'] += 1
        
        return results
    
    def _extract_sql_snippet_for_dataset(self, group_id: str, compare_module: str, 
                                          mapping_item: str, sql_content: str) -> str:
        """为数据源记录提取SQL片段"""
        block = self.sql_extractor.get_block_by_group_id(group_id)
        
        if block is None:
            return ''
        
        if compare_module == '表间关联':
            return self._extract_join_snippet(mapping_item, block)
        elif compare_module == '筛选条件':
            return self._extract_where_snippet(mapping_item, block)
        
        return ''
    
    def _extract_join_snippet(self, mapping_item: str, block: Dict) -> str:
        """提取JOIN相关的SQL片段"""
        join_clauses = block.get('join_clauses', [])
        
        for join in join_clauses:
            join_type = join.get('type', '')
            table = join.get('table', '')
            condition = join.get('condition', '')
            
            if any(alias in mapping_item for alias in ['T1', 'T2', 'T3', 'T4']):
                return f"{join_type} {table} ON {condition}"
        
        return ''
    
    def _extract_where_snippet(self, mapping_item: str, block: Dict) -> str:
        """提取WHERE相关的SQL片段"""
        where_clause = block.get('where_clause', '')
        
        if not where_clause:
            return ''
        
        field_match = re.search(r'【([A-Za-z_][A-Za-z0-9_]*)】', mapping_item)
        if field_match:
            field_name = field_match.group(1)
            
            conditions = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
            for cond in conditions:
                if field_name in cond:
                    return cond.strip()
        
        return where_clause[:200] if len(where_clause) > 200 else where_clause
    
    def _compare_dataset_item(self, compare_module: str, mapping_item: str, 
                              sql_snippet: str) -> Tuple[str, str]:
        """对比数据源项"""
        if not sql_snippet:
            return '否', 'SQL中未找到对应内容'
        
        if compare_module == '表间关联':
            return self._compare_join_item(mapping_item, sql_snippet)
        elif compare_module == '筛选条件':
            return self._compare_filter_item(mapping_item, sql_snippet)
        
        return '是', ''
    
    def _compare_join_item(self, mapping_item: str, sql_snippet: str) -> Tuple[str, str]:
        """对比表间关联项"""
        if '左关联' in mapping_item and 'LEFT' not in sql_snippet.upper():
            return '否', '关联类型不匹配：Mapping为左关联，SQL中未找到LEFT JOIN'
        
        if '右关联' in mapping_item and 'RIGHT' not in sql_snippet.upper():
            return '否', '关联类型不匹配：Mapping为右关联，SQL中未找到RIGHT JOIN'
        
        if '内关联' in mapping_item and 'INNER' not in sql_snippet.upper():
            return '否', '关联类型不匹配：Mapping为内关联，SQL中未找到INNER JOIN'
        
        field_pattern = r'【([A-Za-z_][A-Za-z0-9_]*)】'
        fields = re.findall(field_pattern, mapping_item)
        
        missing_fields = []
        for field in fields:
            if field not in sql_snippet:
                missing_fields.append(field)
        
        if missing_fields:
            return '否', f'关联字段未在SQL中找到: {", ".join(missing_fields)}'
        
        return '是', ''
    
    def _compare_filter_item(self, mapping_item: str, sql_snippet: str) -> Tuple[str, str]:
        """对比筛选条件项"""
        VARIABLE_MAPPING = {
            '跑批基准日期': ['V_SHORT_DATE', 'V_LONG_DATE', 'P_I_DATE'],
            '当前时间': ['CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NOW()'],
            '批次ID': ['P_I_BATCHID', 'V_BATCH_ID'],
            'JOBID': ['P_I_JOBID', 'V_JOB_ID'],
        }
        
        field_pattern = r'【([A-Za-z_][A-Za-z0-9_]*)】'
        fields = re.findall(field_pattern, mapping_item)
        
        if fields:
            field = fields[0]
            if field not in sql_snippet:
                return '否', f'筛选字段"{field}"未在SQL WHERE条件中找到'
        
        if '=' in mapping_item:
            value_match = re.search(r'=\s*(\S+)', mapping_item)
            if value_match:
                value = value_match.group(1).strip()
                if value:
                    value_found = value in sql_snippet
                    
                    if not value_found:
                        for mapping_key, sql_vars in VARIABLE_MAPPING.items():
                            if mapping_key in value or value in mapping_key:
                                for sql_var in sql_vars:
                                    if sql_var in sql_snippet:
                                        value_found = True
                                        break
                                if value_found:
                                    break
                    
                    if not value_found:
                        return '否', f'筛选值"{value}"未在SQL条件中找到'
        
        return '是', ''


def run_step2_and_step3(task_id: str, sql_content: str, db_path: str = 'data/review_history.db', 
                        enable_agent_review: bool = True, ollama_config: Dict = None) -> Dict:
    """运行第二步和第三步
    
    Args:
        task_id: 任务ID
        sql_content: SQL文件内容
        db_path: 数据库路径
        enable_agent_review: 是否启用Agent复核
        ollama_config: Ollama配置
        
    Returns:
        Dict: 处理结果
    """
    from extract_datamap_to_md import ITMappingDatabaseStorage
    
    db_storage = ITMappingDatabaseStorage(db_path)
    pipeline = SQLExtractionAndComparisonPipeline(sql_content, db_storage)
    
    print(f"[第二步] 正在提取SQL表达式...")
    print(f"[第二步] 发现 {len(pipeline.sql_extractor.get_group_ids())} 个分组")
    
    print(f"[第三步] 正在进行一致性对比（规则引擎）...")
    datamap_results = pipeline.process_all_records(task_id)
    
    print(f"[第三步] 正在处理数据源记录...")
    dataset_results = pipeline.process_dataset_records(task_id, sql_content)
    
    if enable_agent_review and datamap_results.get('inconsistent', 0) > 0:
        print(f"\n[Agent复核] 发现 {datamap_results['inconsistent']} 条不一致，启动Agent复核...")
        
        try:
            reviewer = OllamaAgentReviewer(ollama_config)
            review_results = reviewer.review_inconsistent_items(task_id, db_storage, sql_content)
            
            datamap_results['agent_reviewed'] = True
            datamap_results['review_results'] = review_results
            
            print(f"[Agent复核] 完成，复核了 {review_results.get('reviewed_count', 0)} 条记录")
            
        except Exception as e:
            print(f"[Agent复核] 失败: {e}")
            datamap_results['agent_reviewed'] = False
            datamap_results['review_error'] = str(e)
    
    return {
        'task_id': task_id,
        'datamap': datamap_results,
        'dataset': dataset_results,
        'success': True
    }


class OllamaAgentReviewer:
    """Ollama Agent复核器
    
    对规则引擎检查出的不一致项进行Agent复核
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or self._load_default_config()
        self.host = self.config.get('host', 'http://localhost:11434')
        self.model = self.config.get('model', 'qwen2.5:7b')
        self.timeout = int(self.config.get('timeout', 120))
    
    def _load_default_config(self) -> Dict:
        """加载默认配置"""
        import json
        import os
        
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'ollama_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[OllamaAgentReviewer] 加载配置失败: {e}")
        
        return {
            'host': 'http://localhost:11434',
            'model': 'qwen2.5:7b',
            'timeout': 120
        }
    
    def _call_ollama(self, prompt: str, system_prompt: str = '') -> Dict:
        """调用Ollama API"""
        import json
        import urllib.request
        import urllib.error
        
        url = f"{self.host}/api/generate"
        
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': 0.1,
                'num_predict': 1024
            }
        }
        
        if system_prompt:
            payload['system'] = system_prompt
        
        try:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                return {
                    'success': True,
                    'response': result.get('response', '')
                }
                
        except urllib.error.URLError as e:
            return {
                'success': False,
                'error': f'Ollama连接失败: {e}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Ollama调用失败: {e}'
            }
    
    def review_single_field(self, field_info: Dict, sql_expression: str, 
                            rule_result: Dict, sql_content: str) -> Dict:
        """复核单个字段
        
        Args:
            field_info: 字段信息
            sql_expression: SQL表达式
            rule_result: 规则引擎检查结果
            sql_content: 完整SQL内容
            
        Returns:
            Dict: 复核结果
        """
        target_field = field_info.get('target_field_en', '')
        target_field_cn = field_info.get('target_field_cn', '')
        extract_method = field_info.get('extract_method', '')
        source_field = field_info.get('source_field_en', '')
        transform_logic = field_info.get('transform_logic', '')
        default_value = field_info.get('default_value', '')
        
        system_prompt = """【强制要求 - 必须严格遵守】

【语言约束（最高优先级）】：
- 所有输出内容必须使用中文
- 【绝对禁止】在输出中使用英文说明文字

【输出格式强制规范】：
- 只返回JSON，不要包含任何其他文字
- JSON格式：{"is_consistent": "是/否", "confidence": 0.0-1.0, "remark": "复核说明", "suggestion": "修改建议"}

你是SQL字段映射复核专家。你的任务是严格复核规则引擎的检查结果，判断字段映射是否一致。

【严格复核原则 - 必须遵守】：
1. 【严格对比】：即使漏掉一个字符、一个字，只要两边不一致，就都算不一致
2. 【码值精确匹配】：CASE WHEN中的每个分支值必须精确匹配，如"01"和"011"是不一致的
3. 【字段名精确匹配】：字段名必须完全一致，大小写敏感
4. 【默认值精确匹配】：默认值必须完全一致，包括空格、引号等

【唯一允许的变量映射】以下变量与业务术语是等价的（仅限这些）：
- V_SHORT_DATE = 跑批基准日期
- V_LONG_DATE = 跑批基准日期（YYYY-MM-DD格式）
- P_I_DATE = 跑批基准日期
- CURRENT_TIMESTAMP() = 当前时间
- uuid() = uuid()（忽略中文/英文括号差异）

【严格检查项】：
- 码值转换：如IT-Mapping写"01"，SQL写"011"，这是不一致
- 默认值：如IT-Mapping写"留空"，SQL写"'123411'"，这是不一致
- 字段名：如IT-Mapping写"CREATE_DATE"，SQL写"CREATE_DAT"，这是不一致
- 函数参数：函数参数必须完全一致

【输出要求】：
- is_consistent: "是"或"否"
- confidence: 0.0-1.0的置信度
- remark: 复核说明（中文），指出具体差异
- suggestion: 如果不一致，给出修改建议"""

        prompt = f"""请复核以下字段的映射一致性：

【字段信息】
- 目标字段: {target_field} ({target_field_cn})
- 取数方式: {extract_method}
- 源字段: {source_field}
- 转换逻辑: {transform_logic}
- 默认值: {default_value}

【SQL表达式】
{sql_expression}

【规则引擎检查结果】
- 是否一致: {rule_result.get('is_consistent', '否')}
- 检查备注: {rule_result.get('remark', '')}

请严格按照复核原则判断该字段映射是否一致。注意：即使是细微差异（如"01"vs"011"、"留空"vs"有值"），都应判定为不一致。"""

        result = self._call_ollama(prompt, system_prompt)
        
        if not result.get('success'):
            return {
                'success': False,
                'error': result.get('error', 'Ollama调用失败'),
                'is_consistent': rule_result.get('is_consistent', '否'),
                'remark': f"Agent复核失败: {result.get('error', '')}"
            }
        
        try:
            import json
            response_text = result.get('response', '')
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                review_result = json.loads(json_match.group())
            else:
                review_result = {
                    'is_consistent': '否',
                    'confidence': 0.5,
                    'remark': response_text[:200] if response_text else '无法解析Agent响应'
                }
            
            return {
                'success': True,
                'is_consistent': review_result.get('is_consistent', '否'),
                'confidence': review_result.get('confidence', 0.5),
                'remark': review_result.get('remark', ''),
                'suggestion': review_result.get('suggestion', ''),
                'raw_response': response_text
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'解析Agent响应失败: {e}',
                'is_consistent': rule_result.get('is_consistent', '否'),
                'remark': f"Agent响应解析失败"
            }
    
    def review_inconsistent_items(self, task_id: str, db_storage, sql_content: str) -> Dict:
        """复核所有不一致项
        
        Args:
            task_id: 任务ID
            db_storage: 数据库存储对象
            sql_content: 完整SQL内容
            
        Returns:
            Dict: 复核结果统计
        """
        records = db_storage.get_datamap_results(task_id)
        
        inconsistent_records = [
            r for r in records 
            if r.get('is_consistent') == '否'
        ]
        
        results = {
            'total_inconsistent': len(inconsistent_records),
            'reviewed_count': 0,
            'confirmed_count': 0,
            'overturned_count': 0,
            'failed_count': 0,
            'details': []
        }
        
        for record in inconsistent_records:
            try:
                field_info = {
                    'target_field_en': record.get('target_field_en', ''),
                    'target_field_cn': record.get('target_field_cn', ''),
                    'extract_method': record.get('extract_method', ''),
                    'source_field_en': record.get('source_field_en', ''),
                    'source_field_cn': record.get('source_field_cn', ''),
                    'transform_logic': record.get('transform_logic', ''),
                    'default_value': record.get('default_value', ''),
                    'source_table': record.get('source_table', '')
                }
                
                sql_expression = record.get('sql_expression', '')
                rule_result = {
                    'is_consistent': record.get('is_consistent', '否'),
                    'remark': record.get('remark', '')
                }
                
                print(f"[Agent复核] 正在复核字段: {field_info['target_field_en']}")
                
                review_result = self.review_single_field(
                    field_info, sql_expression, rule_result, sql_content
                )
                
                results['reviewed_count'] += 1
                
                if review_result.get('success'):
                    agent_is_consistent = review_result.get('is_consistent', '否')
                    agent_remark = review_result.get('remark', '')
                    
                    if agent_is_consistent == '是':
                        results['overturned_count'] += 1
                        final_remark = f"[Agent复核通过] {agent_remark}"
                    else:
                        results['confirmed_count'] += 1
                        suggestion = review_result.get('suggestion', '')
                        final_remark = f"{record.get('remark', '')}"
                        if suggestion:
                            final_remark += f" | Agent建议: {suggestion}"
                    
                    db_storage.update_datamap_sql_and_comparison(
                        task_id=task_id,
                        group_id=record.get('group_id', ''),
                        field_seq=record.get('field_seq', 0),
                        sql_expression=sql_expression,
                        is_consistent=agent_is_consistent,
                        remark=final_remark
                    )
                    
                    results['details'].append({
                        'field': field_info['target_field_en'],
                        'rule_result': rule_result.get('is_consistent', '否'),
                        'agent_result': agent_is_consistent,
                        'confidence': review_result.get('confidence', 0.5),
                        'remark': agent_remark
                    })
                else:
                    results['failed_count'] += 1
                    results['details'].append({
                        'field': field_info['target_field_en'],
                        'rule_result': rule_result.get('is_consistent', '否'),
                        'agent_result': '复核失败',
                        'error': review_result.get('error', '')
                    })
                    
            except Exception as e:
                results['failed_count'] += 1
                print(f"[Agent复核] 复核字段 {record.get('target_field_en', '')} 失败: {e}")
        
        dataset_records = db_storage.get_dataset_results(task_id)
        dataset_inconsistent = [
            r for r in dataset_records 
            if r.get('is_consistent') == '否'
        ]
        
        results['dataset_total_inconsistent'] = len(dataset_inconsistent)
        results['dataset_reviewed_count'] = 0
        results['dataset_confirmed_count'] = 0
        results['dataset_overturned_count'] = 0
        
        for record in dataset_inconsistent:
            try:
                mapping_item = record.get('mapping_item', '')
                sql_content_snippet = record.get('sql_content', '')
                compare_module = record.get('compare_module', '')
                
                print(f"[Agent复核] 正在复核数据源: {compare_module} - {mapping_item[:30]}...")
                
                review_result = self.review_dataset_item(
                    mapping_item, sql_content_snippet, compare_module, sql_content
                )
                
                results['dataset_reviewed_count'] += 1
                
                if review_result.get('success'):
                    agent_is_consistent = review_result.get('is_consistent', '否')
                    agent_remark = review_result.get('remark', '')
                    
                    if agent_is_consistent == '是':
                        results['dataset_overturned_count'] += 1
                        final_remark = f"[Agent复核通过] {agent_remark}"
                    else:
                        results['dataset_confirmed_count'] += 1
                        final_remark = f"{record.get('remark', '')}"
                    
                    db_storage.update_dataset_sql_and_comparison(
                        task_id=task_id,
                        group_id=record.get('group_id', ''),
                        compare_module=compare_module,
                        mapping_item=mapping_item,
                        sql_content=sql_content_snippet,
                        is_consistent=agent_is_consistent,
                        remark=final_remark
                    )
            except Exception as e:
                print(f"[Agent复核] 复核数据源记录失败: {e}")
        
        return results
    
    def review_dataset_item(self, mapping_item: str, sql_snippet: str, 
                           compare_module: str, full_sql: str) -> Dict:
        """复核数据源项
        
        Args:
            mapping_item: IT-Mapping中的项
            sql_snippet: SQL片段
            compare_module: 对比模块（表间关联/筛选条件）
            full_sql: 完整SQL内容
            
        Returns:
            Dict: 复核结果
        """
        system_prompt = """【强制要求 - 必须严格遵守】

【语言约束（最高优先级）】：
- 所有输出内容必须使用中文

【输出格式强制规范】：
- 只返回JSON，不要包含任何其他文字
- JSON格式：{"is_consistent": "是/否", "confidence": 0.0-1.0, "remark": "复核说明"}

你是SQL数据源对比复核专家。你的任务是严格复核规则引擎的检查结果，判断数据源映射是否一致。

【严格复核原则 - 必须遵守】：
1. 【严格对比】：即使漏掉一个字符、一个字，只要两边不一致，就都算不一致
2. 【关联条件精确匹配】：表间关联条件必须完全一致
3. 【筛选条件精确匹配】：筛选条件必须完全一致

【唯一允许的变量映射】以下变量与业务术语是等价的（仅限这些）：
- V_SHORT_DATE = 跑批基准日期
- V_LONG_DATE = 跑批基准日期（YYYY-MM-DD格式）
- P_I_DATE = 跑批基准日期
- CURRENT_TIMESTAMP() = 当前时间
- P_I_BATCHID = 批次ID
- P_I_JOBID = JOBID

【严格检查项】：
- 关联类型：左关联/右关联/内关联必须完全匹配
- 关联字段：字段名必须完全一致
- 筛选条件：条件表达式必须完全一致"""

        prompt = f"""请复核以下数据源项的一致性：

【对比模块】{compare_module}

【IT-Mapping内容】
{mapping_item}

【SQL片段】
{sql_snippet}

请严格按照复核原则判断该项是否一致。注意：只有V_SHORT_DATE与跑批基准日期是等价的，其他任何差异都应判定为不一致。"""

        result = self._call_ollama(prompt, system_prompt)
        
        if not result.get('success'):
            return {
                'success': False,
                'error': result.get('error', 'Ollama调用失败'),
                'is_consistent': '否',
                'remark': f"Agent复核失败: {result.get('error', '')}"
            }
        
        try:
            import json
            response_text = result.get('response', '')
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                review_result = json.loads(json_match.group())
            else:
                review_result = {
                    'is_consistent': '否',
                    'confidence': 0.5,
                    'remark': response_text[:200] if response_text else '无法解析Agent响应'
                }
            
            return {
                'success': True,
                'is_consistent': review_result.get('is_consistent', '否'),
                'confidence': review_result.get('confidence', 0.5),
                'remark': review_result.get('remark', '')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'解析Agent响应失败: {e}',
                'is_consistent': '否',
                'remark': 'Agent响应解析失败'
            }


if __name__ == '__main__':
    import sys
    import os
    
    if len(sys.argv) < 3:
        print("用法: python sql_extraction_agent.py <task_id> <sql_file_path> [--no-agent]")
        sys.exit(1)
    
    task_id = sys.argv[1]
    sql_file = sys.argv[2]
    enable_agent = '--no-agent' not in sys.argv
    
    if not os.path.exists(sql_file):
        print(f"SQL文件不存在: {sql_file}")
        sys.exit(1)
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    result = run_step2_and_step3(task_id, sql_content, enable_agent_review=enable_agent)
    
    print(f"\n处理完成!")
    print(f"数据映射: 总计 {result['datamap']['total']} 条")
    print(f"  - 一致: {result['datamap']['consistent']} 条")
    print(f"  - 不一致: {result['datamap']['inconsistent']} 条")
    print(f"  - 错误: {result['datamap']['errors']} 条")
    
    if result['datamap'].get('agent_reviewed'):
        review = result['datamap'].get('review_results', {})
        print(f"\nAgent复核结果:")
        print(f"  - 复核数: {review.get('reviewed_count', 0)} 条")
        print(f"  - 确认不一致: {review.get('confirmed_count', 0)} 条")
        print(f"  - 推翻规则结果: {review.get('overturned_count', 0)} 条")
        print(f"  - 复核失败: {review.get('failed_count', 0)} 条")
    
    print(f"\n数据源: 总计 {result['dataset']['total']} 条")
    print(f"  - 一致: {result['dataset']['consistent']} 条")
    print(f"  - 不一致: {result['dataset']['inconsistent']} 条")
    print(f"  - 错误: {result['dataset']['errors']} 条")

# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class InsertBlock:
    group_id: str
    group_name: str
    start_line: int
    end_line: int
    raw_sql: str
    insert_fields: List[str] = field(default_factory=list)
    select_expressions: List[str] = field(default_factory=list)
    field_mapping: Dict[str, str] = field(default_factory=dict)
    from_clause: str = ''
    join_clauses: List[Dict] = field(default_factory=list)
    where_clause: str = ''
    target_table: str = ''
    partition_clause: str = ''


@dataclass
class GroupedSQLParseResult:
    procedure_name: str = ''
    procedure_desc: str = ''
    insert_blocks: List[InsertBlock] = field(default_factory=list)
    total_blocks: int = 0
    parse_errors: List[str] = field(default_factory=list)


class SQLGroupParser:
    """分组SQL解析器 - 支持识别存储过程中的多个INSERT语句块"""
    
    GROUP_PATTERN = re.compile(
        r'--\s*(?:分组\s*(\d+)\s*[-–]\s*)?(MP\d+)\s*(?:[（(]([^)）]+)[)）])?',
        re.IGNORECASE
    )
    
    COMMENT_PATTERN = re.compile(
        r'--\s*插入数据[（(]?\s*([^)）\n]*?)\s*[)）]?\s*[-–:：]?\s*([^\n]*)',
        re.IGNORECASE
    )
    
    INSERT_BLOCK_PATTERN = re.compile(
        r'INSERT\s+INTO\s+(\w+)(?:\s+PARTITION\s*\(([^)]+)\))?\s*\(([\s\S]*?)\)\s*SELECT\s+([\s\S]*?)\s+FROM\s+([\s\S]*?)(?:WHERE\s+([\s\S]*?))?(?:;|$)',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.debug = False
    
    def parse(self, sql_content: str) -> GroupedSQLParseResult:
        result = GroupedSQLParseResult()
        
        if not sql_content or not sql_content.strip():
            result.parse_errors.append('SQL内容为空')
            return result
        
        lines = sql_content.split('\n')
        result.procedure_name = self._extract_procedure_name(sql_content)
        result.procedure_desc = self._extract_procedure_desc(sql_content)
        
        insert_ranges = self._find_all_insert_blocks(lines)
        
        for i, (start_line, end_line) in enumerate(insert_ranges):
            block_sql = '\n'.join(lines[start_line:end_line + 1])
            
            group_info = self._extract_group_info(lines, start_line)
            
            block = self._parse_insert_block(
                block_sql=block_sql,
                start_line=start_line + 1,
                end_line=end_line + 1,
                group_info=group_info
            )
            
            if block:
                result.insert_blocks.append(block)
            else:
                result.parse_errors.append(f'第{start_line + 1}-{end_line + 1}行INSERT块解析失败')
        
        result.total_blocks = len(result.insert_blocks)
        
        if self.debug:
            self._print_parse_result(result)
        
        return result
    
    def _find_all_insert_blocks(self, lines: List[str]) -> List[Tuple[int, int]]:
        insert_ranges = []
        in_insert = False
        insert_start = -1
        found_where = False
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            stripped = line.strip()
            
            if not in_insert:
                if 'INSERT INTO' in line_upper:
                    in_insert = True
                    insert_start = i
                    found_where = False
            else:
                if 'WHERE' in line_upper:
                    found_where = True
                
                if found_where and ';' in line:
                    insert_ranges.append((insert_start, i))
                    in_insert = False
                    insert_start = -1
                    found_where = False
        
        if in_insert and insert_start >= 0:
            insert_ranges.append((insert_start, len(lines) - 1))
        
        return insert_ranges
    
    def _extract_group_info(self, lines: List[str], insert_line: int) -> Dict:
        group_info = {
            'group_id': '',
            'group_name': '',
            'comment_line': -1
        }
        
        for i in range(insert_line - 1, max(0, insert_line - 20), -1):
            line = lines[i]
            
            match = self.GROUP_PATTERN.search(line)
            if match:
                group_info['group_id'] = match.group(2) if match.group(2) else ''
                group_info['group_name'] = match.group(3).strip() if match.group(3) else ''
                group_info['comment_line'] = i
                return group_info
            
            comment_match = self.COMMENT_PATTERN.search(line)
            if comment_match:
                group_text = comment_match.group(1).strip() if comment_match.group(1) else ''
                group_name = comment_match.group(2).strip() if comment_match.group(2) else ''
                
                mp_match = re.search(r'MP\d+', group_text, re.IGNORECASE)
                if mp_match:
                    group_info['group_id'] = mp_match.group(0).upper()
                    group_info['group_name'] = group_name
                    group_info['comment_line'] = i
                    return group_info
        
        for i in range(insert_line, min(len(lines), insert_line + 5)):
            line = lines[i]
            mp_match = re.search(r"'(MP\d+)'", line, re.IGNORECASE)
            if mp_match:
                group_info['group_id'] = mp_match.group(1).upper()
                group_info['group_name'] = ''
                group_info['comment_line'] = i
                return group_info
        
        return group_info
    
    def _parse_insert_block(self, block_sql: str, start_line: int, end_line: int, 
                            group_info: Dict) -> Optional[InsertBlock]:
        try:
            block = InsertBlock(
                group_id=group_info.get('group_id', ''),
                group_name=group_info.get('group_name', ''),
                start_line=start_line,
                end_line=end_line,
                raw_sql=block_sql
            )
            
            target_table, partition = self._extract_target_table(block_sql)
            block.target_table = target_table
            block.partition_clause = partition
            
            insert_fields = self._extract_insert_fields(block_sql)
            block.insert_fields = insert_fields
            
            select_exprs = self._extract_select_expressions(block_sql)
            block.select_expressions = select_exprs
            
            if insert_fields and select_exprs:
                for i, field in enumerate(insert_fields):
                    if i < len(select_exprs):
                        block.field_mapping[field] = select_exprs[i]
            
            from_clause, join_clauses = self._extract_from_and_joins(block_sql)
            block.from_clause = from_clause
            block.join_clauses = join_clauses
            
            where_clause = self._extract_where_clause(block_sql)
            block.where_clause = where_clause
            
            return block
            
        except Exception as e:
            if self.debug:
                print(f'[解析错误] 第{start_line}-{end_line}行: {e}')
            return None
    
    def _extract_target_table(self, sql: str) -> Tuple[str, str]:
        pattern = r'INSERT\s+INTO\s+(\w+)(?:\s+PARTITION\s*\(([^)]+)\))?'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            table = match.group(1)
            partition = match.group(2) if match.group(2) else ''
            return table, partition
        return '', ''
    
    def _extract_insert_fields(self, sql: str) -> List[str]:
        pattern = r'INSERT\s+INTO\s+\w+(?:\s+PARTITION\s*\([^)]*\))?\s*\(([\s\S]*?)\)\s*SELECT'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            fields_str = match.group(1)
            fields = []
            for line in fields_str.split('\n'):
                clean_line = re.sub(r'--.*$', '', line).strip()
                if clean_line:
                    field = clean_line.rstrip(',').strip()
                    if field:
                        fields.append(field)
            return fields
        return []
    
    def _extract_select_expressions(self, sql: str) -> List[str]:
        select_pattern = r'SELECT\s+([\s\S]*?)\s+FROM\s+'
        match = re.search(select_pattern, sql, re.IGNORECASE)
        if match:
            select_str = match.group(1)
            return self._parse_select_values(select_str)
        return []
    
    def _parse_select_values(self, select_str: str) -> List[str]:
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
    
    def _extract_from_and_joins(self, sql: str) -> Tuple[str, List[Dict]]:
        from_pattern = r'FROM\s+([\w_]+(?:\s+\w+)?)'
        from_match = re.search(from_pattern, sql, re.IGNORECASE)
        
        from_clause = ''
        join_clauses = []
        
        if from_match:
            from_clause = from_match.group(1)
        
        join_pattern = r'(LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|JOIN)\s+(\w+(?:\s+\w+)?)\s+ON\s+([\s\S]*?)(?=(?:LEFT|RIGHT|INNER|JOIN|WHERE|;|$))'
        join_matches = re.finditer(join_pattern, sql, re.IGNORECASE)
        
        for match in join_matches:
            join_type = match.group(1).upper()
            table = match.group(2).strip()
            condition = match.group(3).strip()
            
            condition = re.sub(r'\s+', ' ', condition)
            condition = condition.rstrip('AND').strip()
            
            join_clauses.append({
                'type': join_type,
                'table': table,
                'condition': condition
            })
        
        return from_clause, join_clauses
    
    def _extract_where_clause(self, sql: str) -> str:
        where_pattern = r'WHERE\s+([\s\S]*?)(?:;|$)'
        match = re.search(where_pattern, sql, re.IGNORECASE)
        if match:
            where_clause = match.group(1).strip()
            where_clause = re.sub(r'\s+', ' ', where_clause)
            return where_clause
        return ''
    
    def _extract_procedure_name(self, sql: str) -> str:
        pattern = r'CREATE\s+OR\s+REPLACE\s+PROCEDURE\s+(\w+)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            return match.group(1)
        return ''
    
    def _extract_procedure_desc(self, sql: str) -> str:
        pattern = r'Description\s*:\s*([^\n]+)'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ''
    
    def _print_parse_result(self, result: GroupedSQLParseResult):
        print(f'\n{"="*60}')
        print(f'存储过程: {result.procedure_name}')
        print(f'描述: {result.procedure_desc}')
        print(f'INSERT块数量: {result.total_blocks}')
        print(f'{"="*60}')
        
        for block in result.insert_blocks:
            print(f'\n--- {block.group_id} ({block.group_name}) ---')
            print(f'位置: 第{block.start_line}-{block.end_line}行')
            print(f'目标表: {block.target_table}')
            print(f'分区: {block.partition_clause}')
            print(f'字段数量: {len(block.insert_fields)}')
            print(f'INSERT字段: {block.insert_fields[:5]}...' if len(block.insert_fields) > 5 else f'INSERT字段: {block.insert_fields}')
            print(f'FROM: {block.from_clause}')
            print(f'JOIN数量: {len(block.join_clauses)}')
            for join in block.join_clauses:
                print(f'  - {join["type"]} {join["table"]}')
            print(f'WHERE: {block.where_clause[:100]}...' if len(block.where_clause) > 100 else f'WHERE: {block.where_clause}')
    
    def get_block_by_group_id(self, result: GroupedSQLParseResult, group_id: str) -> Optional[InsertBlock]:
        for block in result.insert_blocks:
            if block.group_id.upper() == group_id.upper():
                return block
        return None
    
    def get_field_mapping_for_group(self, result: GroupedSQLParseResult, group_id: str) -> Dict[str, str]:
        block = self.get_block_by_group_id(result, group_id)
        if block:
            return block.field_mapping
        return {}
    
    def to_dict(self, result: GroupedSQLParseResult) -> Dict:
        return {
            'procedure_name': result.procedure_name,
            'procedure_desc': result.procedure_desc,
            'total_blocks': result.total_blocks,
            'parse_errors': result.parse_errors,
            'insert_blocks': [
                {
                    'group_id': block.group_id,
                    'group_name': block.group_name,
                    'start_line': block.start_line,
                    'end_line': block.end_line,
                    'target_table': block.target_table,
                    'partition_clause': block.partition_clause,
                    'insert_fields': block.insert_fields,
                    'select_expressions': block.select_expressions,
                    'field_mapping': block.field_mapping,
                    'from_clause': block.from_clause,
                    'join_clauses': block.join_clauses,
                    'where_clause': block.where_clause,
                    'raw_sql': block.raw_sql
                }
                for block in result.insert_blocks
            ]
        }


def parse_grouped_sql(sql_content: str, debug: bool = False) -> Dict:
    parser = SQLGroupParser()
    parser.debug = debug
    result = parser.parse(sql_content)
    return parser.to_dict(result)


if __name__ == '__main__':
    import sys
    import os
    
    sql_file = os.path.join(os.path.dirname(__file__), 'SP_DWD_DM_T02_CUST_ADDR_INFO.sql')
    
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]
    
    if os.path.exists(sql_file):
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print(f'正在解析SQL文件: {sql_file}')
        result = parse_grouped_sql(sql_content, debug=True)
        
        print(f'\n\n解析结果摘要:')
        print(f'- 存储过程名称: {result["procedure_name"]}')
        print(f'- INSERT块数量: {result["total_blocks"]}')
        print(f'- 解析错误: {result["parse_errors"] if result["parse_errors"] else "无"}')
        
        for block in result["insert_blocks"]:
            print(f'\n分组 {block["group_id"]} - {block["group_name"]}:')
            print(f'  字段数量: {len(block["insert_fields"])}')
            print(f'  JOIN数量: {len(block["join_clauses"])}')
    else:
        print(f'文件不存在: {sql_file}')

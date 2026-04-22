# -*- coding: utf-8 -*-
import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class FieldPosition:
    line: int
    column: int
    start_index: int
    end_index: int


class FieldLocator:
    """字段定位器 - 精确查找字段在SQL文件中的位置"""
    
    # 类级缓存，用于存储解析结果
    _cache = {}
    
    def __init__(self, sql_content: str, dialect: str = 'mysql'):
        self.sql_content = sql_content
        self.lines = sql_content.split('\n')
        self.line_starts = self._calculate_line_starts()
        self.dialect = dialect.lower()
        self.dialect_specifics = self._get_dialect_specifics()
        # 计算SQL内容的哈希值，用于缓存键
        self.sql_hash = hashlib.md5(sql_content.encode()).hexdigest()
    
    def _calculate_line_starts(self) -> List[int]:
        """计算每行的起始字符索引"""
        line_starts = [0]
        current = 0
        for line in self.lines:
            current += len(line) + 1  # +1 for the newline
            line_starts.append(current)
        return line_starts
    
    def _get_dialect_specifics(self) -> Dict[str, str]:
        """获取方言特定的语法规则"""
        dialect_specifics = {
            'mysql': {
                'identifier_quote': '`',
                'string_quote': "'",
                'date_format': '%Y-%m-%d'
            },
            'postgresql': {
                'identifier_quote': '"',
                'string_quote': "'",
                'date_format': 'YYYY-MM-DD'
            },
            'oracle': {
                'identifier_quote': '"',
                'string_quote': "'",
                'date_format': 'YYYY-MM-DD'
            },
            'sqlserver': {
                'identifier_quote': '[',
                'identifier_quote_end': ']',
                'string_quote': "'",
                'date_format': 'YYYY-MM-DD'
            }
        }
        return dialect_specifics.get(self.dialect, dialect_specifics['mysql'])
    
    def get_position(self, field_name: str, context: str = None, group_id: str = None, insert_blocks: List[InsertBlock] = None) -> Optional[FieldPosition]:
        """获取字段的位置信息
        
        Args:
            field_name: 字段名
            context: 上下文信息，如"INSERT", "SELECT", "WHERE"等
            group_id: 分组ID，用于基于分组的搜索
            insert_blocks: INSERT块列表，用于基于分组的搜索
            
        Returns:
            FieldPosition对象或None
        """
        # 构建缓存键
        cache_key = f"{self.sql_hash}:{field_name}:{context}:{group_id}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 基于分组的搜索策略
        if group_id and insert_blocks:
            for block in insert_blocks:
                if block.group_id == group_id:
                    position = self.locate_in_insert_block(field_name, block)
                    if position:
                        self._cache[cache_key] = position
                        return position
        
        # 构建匹配模式，考虑方言特定的标识符引用
        quote = self.dialect_specifics.get('identifier_quote', '`')
        quote_end = self.dialect_specifics.get('identifier_quote_end', quote)
        
        # 构建多种匹配模式
        patterns = [
            # 精确匹配
            rf'\b{re.escape(field_name)}\b',
            # 带引号的匹配
            rf'{re.escape(quote)}{re.escape(field_name)}{re.escape(quote_end)}',
            # 带表别名的匹配
            rf'\w+\.{re.escape(field_name)}\b',
            # 带表别名和引号的匹配
            rf'\w+\.{re.escape(quote)}{re.escape(field_name)}{re.escape(quote_end)}'
        ]
        
        matches = []
        for pattern in patterns:
            matches.extend(re.finditer(pattern, self.sql_content, re.IGNORECASE))
        
        if not matches:
            self._cache[cache_key] = None
            return None
        
        # 根据上下文筛选匹配结果
        if context:
            filtered_matches = []
            for match in matches:
                # 检查匹配位置是否在指定上下文中
                if self._is_in_context(match.start(), context):
                    filtered_matches.append(match)
            if filtered_matches:
                matches = filtered_matches
        
        # 按上下文优先级排序
        if matches:
            matches = self._rank_matches_by_context_relevance(matches, context)
            match = matches[0]
            line, column = self._get_line_column(match.start())
            position = FieldPosition(
                line=line,
                column=column,
                start_index=match.start(),
                end_index=match.end()
            )
            self._cache[cache_key] = position
            return position
        
        self._cache[cache_key] = None
        return None
    
    def _get_line_column(self, index: int) -> Tuple[int, int]:
        """根据字符索引计算行号和列号"""
        # 使用二分查找提高性能
        low = 0
        high = len(self.line_starts) - 1
        
        while low <= high:
            mid = (low + high) // 2
            if self.line_starts[mid] <= index < self.line_starts[mid + 1]:
                line = mid + 1  # 行号从1开始
                column = index - self.line_starts[mid] + 1
                return line, column
            elif index < self.line_starts[mid]:
                high = mid - 1
            else:
                low = mid + 1
        
        # 如果索引超出范围，返回最后一行
        line = len(self.lines)
        column = len(self.lines[-1]) + 1
        return line, column
    
    def _is_in_context(self, index: int, context: str) -> bool:
        """检查位置是否在指定上下文中"""
        # 构建缓存键
        cache_key = f"{self.sql_hash}:context:{context}:{index}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 查找上下文关键字的位置
        context_pattern = rf'{context}\b'
        context_matches = list(re.finditer(context_pattern, self.sql_content, re.IGNORECASE))
        
        if not context_matches:
            self._cache[cache_key] = False
            return False
        
        # 找到包含索引的上下文块
        for i, match in enumerate(context_matches):
            start = match.start()
            # 查找下一个上下文关键字或文件结束
            end = len(self.sql_content)
            
            # 查找下一个主要SQL子句
            next_clauses = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'LIMIT', 'OFFSET', 'INSERT', 'UPDATE', 'DELETE']
            for clause in next_clauses:
                if clause != context:
                    clause_pattern = rf'{clause}\b'
                    clause_matches = list(re.finditer(clause_pattern, self.sql_content[start:], re.IGNORECASE))
                    if clause_matches:
                        clause_end = start + clause_matches[0].start()
                        if clause_end < end:
                            end = clause_end
            
            if start <= index < end:
                self._cache[cache_key] = True
                return True
        
        self._cache[cache_key] = False
        return False
    
    def _rank_matches_by_context_relevance(self, matches: List, context: str) -> List:
        """根据上下文相关性对匹配结果进行排序"""
        # 构建缓存键
        # 使用匹配的起始位置列表作为缓存键的一部分
        matches_key = '-'.join([str(m.start()) for m in matches])
        cache_key = f"{self.sql_hash}:rank:{context}:{matches_key}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 简单的排序策略：优先选择距离上下文关键字更近的匹配
        ranked_matches = []
        
        context_pattern = rf'{context}\b'
        context_matches = list(re.finditer(context_pattern, self.sql_content, re.IGNORECASE))
        
        for match in matches:
            # 计算到最近的上下文关键字的距离
            min_distance = float('inf')
            for ctx_match in context_matches:
                distance = abs(match.start() - ctx_match.start())
                if distance < min_distance:
                    min_distance = distance
            ranked_matches.append((match, min_distance))
        
        # 按距离排序
        ranked_matches.sort(key=lambda x: x[1])
        result = [match for match, _ in ranked_matches]
        
        # 缓存结果
        self._cache[cache_key] = result
        return result
    
    def locate_in_insert_block(self, field_name: str, insert_block: InsertBlock) -> Optional[FieldPosition]:
        """在指定的INSERT块中定位字段"""
        # 首先检查insert_fields中的字段位置
        if field_name in insert_block.field_positions:
            return insert_block.field_positions[field_name]
        
        # 在INSERT块的原始SQL中查找
        block_start = insert_block.start_line - 1  # 转换为0-based索引
        block_end = insert_block.end_line
        
        # 构建块的内容
        block_content = '\n'.join(self.lines[block_start:block_end])
        block_start_index = self.line_starts[block_start]
        
        # 构建匹配模式
        quote = self.dialect_specifics.get('identifier_quote', '`')
        quote_end = self.dialect_specifics.get('identifier_quote_end', quote)
        
        patterns = [
            rf'\b{re.escape(field_name)}\b',
            rf'{re.escape(quote)}{re.escape(field_name)}{re.escape(quote_end)}',
            rf'\w+\.{re.escape(field_name)}\b',
            rf'\w+\.{re.escape(quote)}{re.escape(field_name)}{re.escape(quote_end)}'
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, block_content, re.IGNORECASE))
            if matches:
                match = matches[0]
                # 计算绝对位置
                absolute_start = block_start_index + match.start()
                line, column = self._get_line_column(absolute_start)
                return FieldPosition(
                    line=line,
                    column=column,
                    start_index=absolute_start,
                    end_index=absolute_start + len(match.group())
                )
        
        return None
    
    def support_dialect(self, dialect: str) -> bool:
        """检查是否支持指定的数据库方言"""
        # 支持的方言列表
        supported_dialects = ['mysql', 'postgresql', 'oracle', 'sqlserver']
        return dialect.lower() in supported_dialects
    
    def get_all_field_positions(self, context: str = None) -> Dict[str, List[FieldPosition]]:
        """获取指定上下文中所有字段的位置信息"""
        # 构建缓存键
        cache_key = f"{self.sql_hash}:all_fields:{context}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 简单的字段提取模式
        field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = list(re.finditer(field_pattern, self.sql_content, re.IGNORECASE))
        
        field_positions = {}
        for match in matches:
            field_name = match.group(1)
            # 过滤掉SQL关键字
            if self._is_sql_keyword(field_name):
                continue
            
            # 检查上下文
            if context and not self._is_in_context(match.start(), context):
                continue
            
            line, column = self._get_line_column(match.start())
            position = FieldPosition(
                line=line,
                column=column,
                start_index=match.start(),
                end_index=match.end()
            )
            
            if field_name not in field_positions:
                field_positions[field_name] = []
            field_positions[field_name].append(position)
        
        # 缓存结果
        self._cache[cache_key] = field_positions
        return field_positions
    
    def _is_sql_keyword(self, word: str) -> bool:
        """检查是否为SQL关键字"""
        keywords = {
            'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'OFFSET',
            'INSERT', 'INTO', 'VALUES', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
            'TABLE', 'VIEW', 'INDEX', 'PROCEDURE', 'FUNCTION', 'TRIGGER', 'CASE', 'WHEN',
            'THEN', 'ELSE', 'END', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS',
            'NULL', 'TRUE', 'FALSE', 'AS', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'USING', 'DISTINCT', 'ALL', 'TOP', 'FETCH', 'NEXT', 'WITH', 'AS'
        }
        return word.upper() in keywords

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
    field_positions: Dict[str, FieldPosition] = field(default_factory=dict)
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
    
    # 类级缓存，用于存储解析结果
    _cache = {}
    
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
        # 计算SQL内容的哈希值，用于缓存键
        sql_hash = hashlib.md5(sql_content.encode()).hexdigest()
        
        # 检查缓存
        if sql_hash in self._cache:
            return self._cache[sql_hash]
        
        result = GroupedSQLParseResult()
        
        if not sql_content or not sql_content.strip():
            result.parse_errors.append('SQL内容为空')
            self._cache[sql_hash] = result
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
        
        # 缓存结果
        self._cache[sql_hash] = result
        return result
    
    def _find_all_insert_blocks(self, lines: List[str]) -> List[Tuple[int, int]]:
        insert_ranges = []
        in_insert = False
        insert_start = -1
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            stripped = line.strip()
            
            if not in_insert:
                if 'INSERT INTO' in line_upper:
                    in_insert = True
                    insert_start = i
            else:
                # 检查是否遇到分号，无论是否有WHERE子句
                if ';' in line:
                    insert_ranges.append((insert_start, i))
                    in_insert = False
                    insert_start = -1
                # 检查是否遇到下一个INSERT语句（处理没有分号的情况）
                elif 'INSERT INTO' in line_upper:
                    insert_ranges.append((insert_start, i - 1))
                    insert_start = i
        
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
            
            insert_fields, field_positions = self._extract_insert_fields_with_positions(block_sql, start_line)
            block.insert_fields = insert_fields
            block.field_positions = field_positions
            
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
    
    def _extract_insert_fields_with_positions(self, sql: str, start_line: int) -> Tuple[List[str], Dict[str, FieldPosition]]:
        # 修改正则表达式，支持括号后有注释的情况
        pattern = r'INSERT\s+INTO\s+\w+(?:\s+PARTITION\s*\([^)]*\))?\s*\(([\s\S]*?)\)\s*(?:--[\s\S]*?)?\s*SELECT'
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            fields_str = match.group(1)
            fields = []
            field_positions = {}
            
            # 计算字段部分在整个SQL中的起始位置
            fields_start = match.start(1)
            
            # 解析每行的字段
            lines = fields_str.split('\n')
            current_line = start_line
            char_offset = 0
            
            # 计算INSERT语句开始到字段部分的行数
            insert_lines = sql[:fields_start].split('\n')
            current_line += len(insert_lines) - 1
            
            for line in lines:
                # 先保留原始行，用于计算位置
                original_line = line
                # 清理注释
                clean_line = re.sub(r'--.*$', '', line).strip()
                if clean_line:
                    # 分割行中的多个字段，注意处理行尾的逗号
                    clean_line = clean_line.rstrip(',')
                    line_fields = [f.strip() for f in clean_line.split(',') if f.strip()]
                    
                    # 计算每个字段的位置
                    line_start = fields_start + char_offset
                    
                    # 遍历字段并计算位置
                    current_pos = 0
                    for field in line_fields:
                        # 找到字段在清理后行中的位置
                        field_in_clean_line = clean_line.find(field, current_pos)
                        if field_in_clean_line >= 0:
                            # 找到字段在原始行中的位置
                            # 先找到清理部分在原始行中的位置
                            clean_part = clean_line[:field_in_clean_line + len(field)]
                            field_in_original_line = original_line.find(clean_part)
                            
                            if field_in_original_line >= 0:
                                field_abs_start = line_start + field_in_original_line
                                field_abs_end = field_abs_start + len(field)
                                
                                # 计算行号和列号
                                field_line = current_line
                                field_column = field_in_original_line + 1  # 列号从1开始
                                
                                # 创建FieldPosition对象
                                field_position = FieldPosition(
                                    line=field_line,
                                    column=field_column,
                                    start_index=field_abs_start,
                                    end_index=field_abs_end
                                )
                                
                                fields.append(field)
                                field_positions[field] = field_position
                                
                                # 更新当前位置，避免重复匹配
                                current_pos = field_in_clean_line + len(field)
                
                char_offset += len(line) + 1  # +1 for the newline
                current_line += 1
            
            return fields, field_positions
        return [], {}
    
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
            print(f'字段位置信息:')
            for field, pos in list(block.field_positions.items())[:5]:  # 只显示前5个字段的位置信息
                print(f'  - {field}: 第{pos.line}行, 第{pos.column}列')
            if len(block.field_positions) > 5:
                print(f'  ... 还有{len(block.field_positions) - 5}个字段')
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
                    'field_positions': {
                        field: {
                            'line': pos.line,
                            'column': pos.column,
                            'start_index': pos.start_index,
                            'end_index': pos.end_index
                        }
                        for field, pos in block.field_positions.items()
                    },
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

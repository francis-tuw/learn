#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel解析器模块
从ITMapping Excel文件中提取分组信息、数据源表、表间关联和筛选条件
"""

import os
import re
import hashlib
import threading
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from collections import defaultdict

import openpyxl


@dataclass
class TableInfo:
    """数据表信息"""
    序号: int
    所属系统: str
    数据表名_英文: str
    数据表别名: str
    数据表名_中文: str
    说明: Optional[str] = None
    所属分组: str = ""


@dataclass
class TableStructure:
    """表结构缓存信息"""
    表名: str
    表别名: str
    表中文名: str
    所属系统: str
    字段列表: List[Dict[str, Any]] = field(default_factory=list)
    解析时间: datetime = field(default_factory=datetime.now)
    命中次数: int = 0


@dataclass
class JoinCacheEntry:
    """JOIN条件缓存条目"""
    原始文本: str
    解析结果: List[Any]
    关联类型: str
    解析时间: datetime = field(default_factory=datetime.now)
    命中次数: int = 0


@dataclass
class CacheStatistics:
    """缓存统计信息"""
    table_cache_hits: int = 0
    table_cache_misses: int = 0
    join_cache_hits: int = 0
    join_cache_misses: int = 0
    total_requests: int = 0
    
    @property
    def table_hit_rate(self) -> float:
        total = self.table_cache_hits + self.table_cache_misses
        return self.table_cache_hits / total if total > 0 else 0.0
    
    @property
    def join_hit_rate(self) -> float:
        total = self.join_cache_hits + self.join_cache_misses
        return self.join_cache_hits / total if total > 0 else 0.0
    
    @property
    def overall_hit_rate(self) -> float:
        return (self.table_cache_hits + self.join_cache_hits) / self.total_requests if self.total_requests > 0 else 0.0


class DataSourceCache:
    """数据源表缓存管理器
    
    提供表结构和JOIN条件的缓存功能，避免重复解析相同的数据。
    支持多线程安全访问和缓存统计。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._table_cache: Dict[str, TableStructure] = {}
        self._join_cache: Dict[str, JoinCacheEntry] = {}
        self._filter_cache: Dict[str, List[Any]] = {}
        self._stats = CacheStatistics()
        self._cache_lock = threading.RLock()
        self._max_cache_size = 1000
        self._enabled = True
    
    @staticmethod
    def _generate_cache_key(content: str) -> str:
        """生成缓存键"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def enable(self):
        """启用缓存"""
        self._enabled = True
    
    def disable(self):
        """禁用缓存"""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """检查缓存是否启用"""
        return self._enabled
    
    def get_table_info(self, table_name: str, table_alias: str = "") -> Optional[TableStructure]:
        """获取表信息，缓存命中则直接返回
        
        Args:
            table_name: 表名
            table_alias: 表别名（可选）
            
        Returns:
            TableStructure 或 None
        """
        if not self._enabled:
            return None
            
        with self._cache_lock:
            self._stats.total_requests += 1
            cache_key = f"{table_name}:{table_alias}" if table_alias else table_name
            
            if cache_key in self._table_cache:
                self._stats.table_cache_hits += 1
                entry = self._table_cache[cache_key]
                entry.命中次数 += 1
                return entry
            
            self._stats.table_cache_misses += 1
            return None
    
    def set_table_info(self, table_name: str, table_info: TableStructure, table_alias: str = ""):
        """设置表信息到缓存
        
        Args:
            table_name: 表名
            table_info: 表结构信息
            table_alias: 表别名（可选）
        """
        if not self._enabled:
            return
            
        with self._cache_lock:
            cache_key = f"{table_name}:{table_alias}" if table_alias else table_name
            
            if len(self._table_cache) >= self._max_cache_size:
                self._evict_lru_table()
            
            self._table_cache[cache_key] = table_info
    
    def get_join_result(self, join_text: str) -> Optional[Tuple[List[Any], str]]:
        """获取JOIN条件解析结果
        
        Args:
            join_text: JOIN条件原始文本
            
        Returns:
            (解析结果列表, 关联类型) 或 None
        """
        if not self._enabled:
            return None
            
        with self._cache_lock:
            self._stats.total_requests += 1
            cache_key = self._generate_cache_key(join_text)
            
            if cache_key in self._join_cache:
                self._stats.join_cache_hits += 1
                entry = self._join_cache[cache_key]
                entry.命中次数 += 1
                return (entry.解析结果, entry.关联类型)
            
            self._stats.join_cache_misses += 1
            return None
    
    def set_join_result(self, join_text: str, result: List[Any], join_type: str = "左关联"):
        """设置JOIN条件解析结果到缓存
        
        Args:
            join_text: JOIN条件原始文本
            result: 解析结果列表
            join_type: 关联类型
        """
        if not self._enabled:
            return
            
        with self._cache_lock:
            cache_key = self._generate_cache_key(join_text)
            
            if len(self._join_cache) >= self._max_cache_size:
                self._evict_lru_join()
            
            self._join_cache[cache_key] = JoinCacheEntry(
                原始文本=join_text,
                解析结果=result,
                关联类型=join_type
            )
    
    def get_filter_result(self, filter_text: str) -> Optional[List[Any]]:
        """获取筛选条件解析结果"""
        if not self._enabled:
            return None
            
        with self._cache_lock:
            self._stats.total_requests += 1
            cache_key = self._generate_cache_key(filter_text)
            
            if cache_key in self._filter_cache:
                self._stats.table_cache_hits += 1
                return self._filter_cache[cache_key]
            
            self._stats.table_cache_misses += 1
            return None
    
    def set_filter_result(self, filter_text: str, result: List[Any]):
        """设置筛选条件解析结果到缓存"""
        if not self._enabled:
            return
            
        with self._cache_lock:
            cache_key = self._generate_cache_key(filter_text)
            
            if len(self._filter_cache) >= self._max_cache_size:
                self._evict_lru_filter()
            
            self._filter_cache[cache_key] = result
    
    def _evict_lru_table(self):
        """淘汰最少使用的表缓存"""
        if not self._table_cache:
            return
        
        lru_key = min(self._table_cache.keys(), 
                      key=lambda k: self._table_cache[k].命中次数)
        del self._table_cache[lru_key]
    
    def _evict_lru_join(self):
        """淘汰最少使用的JOIN缓存"""
        if not self._join_cache:
            return
        
        lru_key = min(self._join_cache.keys(), 
                      key=lambda k: self._join_cache[k].命中次数)
        del self._join_cache[lru_key]
    
    def _evict_lru_filter(self):
        """淘汰最少使用的筛选条件缓存"""
        if not self._filter_cache:
            return
        
        lru_key = min(self._filter_cache.keys(), 
                      key=lambda k: len(str(self._filter_cache[k])))
        del self._filter_cache[lru_key]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            包含命中率、缓存大小等统计信息的字典
        """
        with self._cache_lock:
            return {
                'table_cache': {
                    'size': len(self._table_cache),
                    'hits': self._stats.table_cache_hits,
                    'misses': self._stats.table_cache_misses,
                    'hit_rate': round(self._stats.table_hit_rate * 100, 2)
                },
                'join_cache': {
                    'size': len(self._join_cache),
                    'hits': self._stats.join_cache_hits,
                    'misses': self._stats.join_cache_misses,
                    'hit_rate': round(self._stats.join_hit_rate * 100, 2)
                },
                'filter_cache': {
                    'size': len(self._filter_cache)
                },
                'overall': {
                    'total_requests': self._stats.total_requests,
                    'total_hits': self._stats.table_cache_hits + self._stats.join_cache_hits,
                    'hit_rate': round(self._stats.overall_hit_rate * 100, 2),
                    'enabled': self._enabled,
                    'max_size': self._max_cache_size
                }
            }
    
    def get_cache_size(self) -> Dict[str, int]:
        """获取各缓存的大小"""
        with self._cache_lock:
            return {
                'table_cache_size': len(self._table_cache),
                'join_cache_size': len(self._join_cache),
                'filter_cache_size': len(self._filter_cache),
                'total_size': len(self._table_cache) + len(self._join_cache) + len(self._filter_cache)
            }
    
    def clear_table_cache(self):
        """清空表缓存"""
        with self._cache_lock:
            self._table_cache.clear()
    
    def clear_join_cache(self):
        """清空JOIN缓存"""
        with self._cache_lock:
            self._join_cache.clear()
    
    def clear_filter_cache(self):
        """清空筛选条件缓存"""
        with self._cache_lock:
            self._filter_cache.clear()
    
    def clear_all(self):
        """清空所有缓存"""
        with self._cache_lock:
            self._table_cache.clear()
            self._join_cache.clear()
            self._filter_cache.clear()
            self._stats = CacheStatistics()
    
    def reset_statistics(self):
        """重置统计信息"""
        with self._cache_lock:
            self._stats = CacheStatistics()
    
    def set_max_cache_size(self, size: int):
        """设置最大缓存大小"""
        with self._cache_lock:
            self._max_cache_size = max(1, size)
    
    def get_table_entries_by_name(self, table_name: str) -> List[TableStructure]:
        """根据表名获取所有缓存条目（包括不同别名）"""
        with self._cache_lock:
            return [entry for key, entry in self._table_cache.items() 
                    if key.startswith(f"{table_name}:") or key == table_name]
    
    def get_hot_tables(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """获取热点表（命中次数最多的表）"""
        with self._cache_lock:
            sorted_tables = sorted(
                self._table_cache.items(),
                key=lambda x: x[1].命中次数,
                reverse=True
            )
            return [(key, entry.命中次数) for key, entry in sorted_tables[:top_n]]
    
    def get_hot_joins(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """获取热点JOIN条件"""
        with self._cache_lock:
            sorted_joins = sorted(
                self._join_cache.items(),
                key=lambda x: x[1].命中次数,
                reverse=True
            )
            return [(entry.原始文本[:50] + '...' if len(entry.原始文本) > 50 else entry.原始文本, 
                     entry.命中次数) 
                    for _, entry in sorted_joins[:top_n]]


def get_cache_instance() -> DataSourceCache:
    """获取缓存单例实例"""
    return DataSourceCache()


@dataclass
class JoinRelation:
    """表间关联关系"""
    序号: str
    左表别名: str
    左表名称: str
    左字段名: str
    左字段中文名: str
    关联类型: str
    右表别名: str
    右表名称: str
    右字段名: str
    右字段中文名: str


@dataclass
class FilterCondition:
    """筛选条件"""
    序号: str
    表别名: str
    表名称: str
    字段名: str
    字段中文名: str
    条件: str
    值: str


@dataclass
class GroupInfo:
    """分组信息"""
    组别编号: str
    组别名称: str
    数据源表: list = field(default_factory=list)
    表间关联: list = field(default_factory=list)
    筛选条件: list = field(default_factory=list)
    原始关联文本: str = ""


@dataclass
class FieldMapping:
    """字段映射信息"""
    组别编号: str
    字段序号: int
    字段中文名称: str
    字段英文名: str
    数据类型: Optional[str] = None
    值域参考: Optional[str] = None
    数据项说明: Optional[str] = None
    取数方式: Optional[str] = None
    源系统编码: Optional[str] = None
    数据表: Optional[str] = None
    源字段名_英文: Optional[str] = None
    源字段名_中文: Optional[str] = None
    默认值: Optional[str] = None
    字段加工逻辑: Optional[str] = None
    码值映射: Optional[str] = None
    备注_说明: Optional[str] = None
    _excel_row: int = 0


@dataclass
class GroupFieldMapping:
    """分组字段映射"""
    组别编号: str
    组别名称: str
    字段列表: list = field(default_factory=list)


class GroupExtractor:
    """分组提取器
    
    从ITMapping Excel文件的"数据源"sheet中提取分组信息，
    包括组别编号、组别名称、数据源表、表间关联关系和筛选条件。
    支持数据源表缓存机制，避免重复解析相同的表和JOIN条件。
    """
    
    SHEET_KEYWORDS = ['数据源', 'DataSet']
    
    def __init__(self, workbook: openpyxl.Workbook, use_cache: bool = True):
        self.workbook = workbook
        self._sheet = None
        self._tables_cache = {}
        self._relation_start_row = None
        self._table_list_end_row = None
        self._use_cache = use_cache
        self._cache = get_cache_instance() if use_cache else None
        self._parsed_tables: Dict[str, TableInfo] = {}
        self._parsed_joins: Dict[str, List[JoinRelation]] = {}
        self._parsed_filters: Dict[str, List[FilterCondition]] = {}
    
    def _fuzzy_match_sheet(self) -> Optional[openpyxl.worksheet.worksheet.Worksheet]:
        if self._sheet is not None:
            return self._sheet
        
        for name in self.workbook.sheetnames:
            for keyword in self.SHEET_KEYWORDS:
                if keyword in name:
                    self._sheet = self.workbook[name]
                    return self._sheet
        return None
    
    def _find_section_boundaries(self, sheet) -> tuple:
        table_list_end = 15
        relation_start = 14
        
        for row_idx, row in enumerate(sheet.iter_rows(max_row=30, values_only=True), 1):
            first_cell = str(row[0]) if row[0] else ''
            if '数据映射' in first_cell or 'DataMap' in first_cell:
                table_list_end = row_idx - 1
                relation_start = row_idx + 1
                break
            if first_cell == '组别编号':
                relation_start = row_idx + 1
                table_list_end = row_idx - 2
        
        self._table_list_end_row = table_list_end
        self._relation_start_row = relation_start
        return table_list_end, relation_start
    
    def extract_all_groups(self) -> dict:
        sheet = self._fuzzy_match_sheet()
        if sheet is None:
            raise ValueError("未找到数据源sheet")
        
        table_list_end, relation_start = self._find_section_boundaries(sheet)
        
        tables = self._extract_table_list(sheet, table_list_end)
        relations = self._extract_group_relations(sheet, relation_start)
        
        has_group_marker = any(t.所属分组 for t in tables)
        
        groups = {}
        for relation in relations:
            group_id = relation['组别编号']
            group_name = relation['组别名称']
            raw_relation_text = relation.get('表间关联关系及筛选条件', '')
            
            if has_group_marker:
                group_tables = self._get_tables_for_group(tables, group_id)
            else:
                group_tables = tables
            
            joins, filters = self._parse_relation_text(raw_relation_text)
            
            groups[group_id] = GroupInfo(
                组别编号=group_id,
                组别名称=group_name,
                数据源表=group_tables,
                表间关联=joins,
                筛选条件=filters,
                原始关联文本=raw_relation_text
            )
        
        if not groups and tables:
            default_group_id = 'MP1'
            default_group_name = tables[0].数据表名_中文 if tables else '默认分组'
            raw_relation_text = ''
            
            joins, filters = self._parse_relation_text(raw_relation_text)
            
            groups[default_group_id] = GroupInfo(
                组别编号=default_group_id,
                组别名称=default_group_name,
                数据源表=tables,
                表间关联=joins,
                筛选条件=filters,
                原始关联文本=raw_relation_text
            )
        
        return groups
    
    def _extract_table_list(self, sheet, max_row: int = 15) -> list:
        tables = []
        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=3, max_row=max_row, values_only=True),
            3
        ):
            if row[0] is not None and isinstance(row[0], int):
                table_name_en = row[2] or ''
                table_alias = row[3] or ''
                
                # 提取所属分组信息，F列（索引5）可能包含分组标识
                group_id = ''
                if len(row) > 5 and row[5]:
                    # 尝试从说明列中提取分组标识，如"MP1"、"MP2"、"MP3"
                    description = str(row[5])
                    # 使用正则表达式提取分组标识，如"MP1"、"MP2"、"MP3"等
                    import re
                    match = re.search(r'MP\d+', description)
                    if match:
                        group_id = match.group(0)
                
                # 使用包含分组标识的缓存键，确保不同分组的表被视为不同的表
                cache_key = f"{table_name_en}:{table_alias}:{group_id}"
                
                if self._use_cache and cache_key in self._parsed_tables:
                    # 从缓存中获取表信息，但更新所属分组
                    table_info = self._parsed_tables[cache_key]
                    table_info.所属分组 = group_id
                    tables.append(table_info)
                    continue
                
                if self._use_cache and self._cache:
                    cached = self._cache.get_table_info(table_name_en, table_alias)
                    if cached:
                        table_info = TableInfo(
                            序号=row[0],
                            所属系统=cached.所属系统,
                            数据表名_英文=cached.表名,
                            数据表别名=cached.表别名,
                            数据表名_中文=cached.表中文名,
                            说明=None,
                            所属分组=group_id  # 使用提取的分组标识
                        )
                        self._parsed_tables[cache_key] = table_info
                        tables.append(table_info)
                        continue
                
                table_info = TableInfo(
                    序号=row[0],
                    所属系统=row[1] or '',
                    数据表名_英文=table_name_en,
                    数据表别名=table_alias,
                    数据表名_中文=row[4] or '',
                    说明=row[5] if len(row) > 5 else None,
                    所属分组=group_id
                )
                
                self._parsed_tables[cache_key] = table_info
                
                if self._use_cache and self._cache:
                    table_struct = TableStructure(
                        表名=table_name_en,
                        表别名=table_alias,
                        表中文名=row[4] or '',
                        所属系统=row[1] or ''
                    )
                    self._cache.set_table_info(table_name_en, table_struct, table_alias)
                
                tables.append(table_info)
        return tables
    
    def _extract_group_relations(self, sheet, start_row: int = 14) -> list:
        relations = []
        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=start_row, values_only=True),
            start_row
        ):
            if row[0] is not None and row[0] != '组别编号':
                relation_info = {
                    '组别编号': row[0],
                    '组别名称': row[1],
                    '表间关联关系及筛选条件': row[3] if len(row) > 3 else None
                }
                relations.append(relation_info)
        return relations
    
    def _get_tables_for_group(self, tables: list, group_id: str) -> list:
        group_tables = []
        for table in tables:
            if table.所属分组 == group_id:
                group_tables.append(table)
        return group_tables
    
    def _parse_relation_text(self, text: str) -> tuple:
        if not text:
            return [], []
        
        if self._use_cache and self._cache:
            cache_key = self._cache._generate_cache_key(text)
            if cache_key in self._parsed_joins and cache_key in self._parsed_filters:
                return self._parsed_joins[cache_key], self._parsed_filters[cache_key]
        
        joins = []
        filters = []
        
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '表间关联' in line:
                current_section = 'join'
                continue
            elif '筛选条件' in line:
                current_section = 'filter'
                continue
            
            if current_section == 'join':
                join = self._parse_join_line_with_cache(line)
                if join:
                    joins.append(join)
            elif current_section == 'filter':
                filter_cond = self._parse_filter_line_with_cache(line)
                if filter_cond:
                    filters.append(filter_cond)
        
        if self._use_cache:
            cache_key = self._cache._generate_cache_key(text) if self._cache else text
            self._parsed_joins[cache_key] = joins
            self._parsed_filters[cache_key] = filters
        
        return joins, filters
    
    def _parse_join_line_with_cache(self, line: str) -> Optional[JoinRelation]:
        if self._use_cache and self._cache:
            cached_result = self._cache.get_join_result(line)
            if cached_result:
                result_list, join_type = cached_result
                if result_list:
                    return result_list[0] if isinstance(result_list[0], JoinRelation) else None
        
        result = self._parse_join_line(line)
        
        if result and self._use_cache and self._cache:
            self._cache.set_join_result(line, [result], result.关联类型)
        
        return result
    
    def _parse_filter_line_with_cache(self, line: str) -> Optional[FilterCondition]:
        if self._use_cache and self._cache:
            cached_result = self._cache.get_filter_result(line)
            if cached_result:
                return cached_result[0] if isinstance(cached_result[0], FilterCondition) else None
        
        result = self._parse_filter_line(line)
        
        if result and self._use_cache and self._cache:
            self._cache.set_filter_result(line, [result])
        
        return result
    
    def _parse_join_line(self, line: str) -> Optional[JoinRelation]:
        seq_match = re.match(r'^([A-Z])、', line)
        if not seq_match:
            return None
        
        seq = seq_match.group(1)
        
        join_type = '左关联'
        if '左关联' in line:
            join_type = '左关联'
        elif '右关联' in line:
            join_type = '右关联'
        elif '内关联' in line:
            join_type = '内关联'
        
        alias_pattern = r'【([A-Z0-9]+)】'
        aliases = re.findall(alias_pattern, line)
        
        table_name_pattern = r'【([A-Z0-9]+)】([^【\.]+?)\.'
        table_names = re.findall(table_name_pattern, line)
        
        field_pattern = r'\.【([A-Za-z_][A-Za-z0-9_]*)】'
        fields = re.findall(field_pattern, line)
        
        left_alias = aliases[0] if len(aliases) > 0 else ''
        right_alias = aliases[1] if len(aliases) > 1 else ''
        
        left_table_name = ''
        right_table_name = ''
        for alias, name in table_names:
            if alias == left_alias:
                left_table_name = name.strip()
            elif alias == right_alias:
                right_table_name = name.strip()
        
        left_field = fields[0] if len(fields) > 0 else ''
        right_field = fields[1] if len(fields) > 1 else ''
        
        cn_pattern = r'\.【[A-Za-z_][A-Za-z0-9_]*】([^【\n]+?)(?=(?:左关联|右关联|内关联|【|$))'
        cn_matches = re.findall(cn_pattern, line)
        left_field_cn = cn_matches[0].strip() if len(cn_matches) > 0 else ''
        right_field_cn = cn_matches[1].strip() if len(cn_matches) > 1 else ''
        
        if left_alias and right_alias:
            return JoinRelation(
                序号=seq,
                左表别名=left_alias,
                左表名称=left_table_name,
                左字段名=left_field,
                左字段中文名=left_field_cn,
                关联类型=join_type,
                右表别名=right_alias,
                右表名称=right_table_name,
                右字段名=right_field,
                右字段中文名=right_field_cn
            )
        
        return self._parse_join_simple(line)
    
    def _extract_alias(self, line: str, seq: str, is_right: bool = False) -> str:
        alias_pattern = r'【([A-Z0-9]+)】'
        matches = re.findall(alias_pattern, line)
        if len(matches) >= 1:
            if is_right and len(matches) >= 2:
                return matches[-1]
            return matches[0]
        return ''
    
    def _parse_join_simple(self, line: str) -> Optional[JoinRelation]:
        seq_match = re.match(r'^([A-Z])、', line)
        if not seq_match:
            return None
        
        seq = seq_match.group(1)
        
        table_pattern = r'【([^】]+)】'
        tables = re.findall(table_pattern, line)
        
        alias_pattern = r'【([A-Z0-9]+)】'
        aliases = re.findall(alias_pattern, line)
        
        join_type = '左关联'
        if '左关联' in line:
            join_type = '左关联'
        elif '右关联' in line:
            join_type = '右关联'
        elif '内关联' in line:
            join_type = '内关联'
        
        if len(tables) >= 2:
            return JoinRelation(
                序号=seq,
                左表别名=aliases[0] if len(aliases) > 0 else '',
                左表名称=tables[0],
                左字段名='',
                左字段中文名='',
                关联类型=join_type,
                右表别名=aliases[1] if len(aliases) > 1 else '',
                右表名称=tables[1],
                右字段名='',
                右字段中文名=''
            )
        
        return None
    
    def _parse_filter_line(self, line: str) -> Optional[FilterCondition]:
        seq_match = re.match(r'^([A-Z])、', line)
        if not seq_match:
            seq = ''
        else:
            seq = seq_match.group(1)
        
        table_pattern = r'【([^】]+)】'
        tables = re.findall(table_pattern, line)
        
        alias_pattern = r'【([A-Z0-9]+)】'
        aliases = re.findall(alias_pattern, line)
        
        field_pattern = r'\.【([^】]+)】'
        fields = re.findall(field_pattern, line)
        
        condition = ''
        value = ''
        
        if '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                value = parts[1].strip()
                condition = '='
        elif '!=' in line:
            parts = line.split('!=', 1)
            if len(parts) == 2:
                value = parts[1].strip()
                condition = '!='
        elif '<>' in line:
            parts = line.split('<>', 1)
            if len(parts) == 2:
                value = parts[1].strip()
                condition = '<>'
        
        if tables or fields:
            return FilterCondition(
                序号=seq,
                表别名=aliases[0] if aliases else '',
                表名称=tables[0] if tables else '',
                字段名=fields[0] if fields else '',
                字段中文名='',
                条件=condition,
                值=value
            )
        
        return None
    
    def get_group_by_id(self, group_id: str) -> Optional[GroupInfo]:
        groups = self.extract_all_groups()
        return groups.get(group_id)
    
    def get_group_ids(self) -> list:
        groups = self.extract_all_groups()
        return list(groups.keys())
    
    def to_dict(self) -> dict:
        groups = self.extract_all_groups()
        result = {}
        for group_id, group_info in groups.items():
            result[group_id] = {
                '组别编号': group_info.组别编号,
                '组别名称': group_info.组别名称,
                '数据源表': [
                    {
                        '序号': t.序号,
                        '所属系统': t.所属系统,
                        '数据表名_英文': t.数据表名_英文,
                        '数据表别名': t.数据表别名,
                        '数据表名_中文': t.数据表名_中文,
                        '说明': t.说明
                    }
                    for t in group_info.数据源表
                ],
                '表间关联': [
                    {
                        '序号': j.序号,
                        '左表别名': j.左表别名,
                        '左表名称': j.左表名称,
                        '左字段名': j.左字段名,
                        '关联类型': j.关联类型,
                        '右表别名': j.右表别名,
                        '右表名称': j.右表名称,
                        '右字段名': j.右字段名
                    }
                    for j in group_info.表间关联
                ],
                '筛选条件': [
                    {
                        '序号': f.序号,
                        '表别名': f.表别名,
                        '表名称': f.表名称,
                        '字段名': f.字段名,
                        '条件': f.条件,
                        '值': f.值
                    }
                    for f in group_info.筛选条件
                ],
                '原始关联文本': group_info.原始关联文本
            }
        return result
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self._use_cache or not self._cache:
            return {
                'enabled': False,
                'message': '缓存未启用'
            }
        return self._cache.get_statistics()
    
    def get_cache_size(self) -> Dict[str, int]:
        """获取缓存大小"""
        if not self._use_cache or not self._cache:
            return {
                'table_cache_size': 0,
                'join_cache_size': 0,
                'filter_cache_size': 0,
                'total_size': 0
            }
        return self._cache.get_cache_size()
    
    def get_hot_tables(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """获取热点表（命中次数最多的表）"""
        if not self._use_cache or not self._cache:
            return []
        return self._cache.get_hot_tables(top_n)
    
    def get_hot_joins(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """获取热点JOIN条件"""
        if not self._use_cache or not self._cache:
            return []
        return self._cache.get_hot_joins(top_n)
    
    def clear_cache(self):
        """清空缓存"""
        if self._use_cache and self._cache:
            self._cache.clear_all()
            self._parsed_tables.clear()
            self._parsed_joins.clear()
            self._parsed_filters.clear()
    
    def enable_cache(self):
        """启用缓存"""
        self._use_cache = True
        if not self._cache:
            self._cache = get_cache_instance()
    
    def disable_cache(self):
        """禁用缓存"""
        self._use_cache = False
    
    def get_local_cache_info(self) -> Dict[str, int]:
        """获取本地解析缓存信息"""
        return {
            'parsed_tables_count': len(self._parsed_tables),
            'parsed_joins_count': len(self._parsed_joins),
            'parsed_filters_count': len(self._parsed_filters)
        }


class DataMapExtractor:
    """数据映射提取器
    
    从ITMapping Excel文件的"数据映射（DataMap）"sheet中提取字段映射信息，
    按"组别编号"分组，为每个分组建立独立的字段映射字典。
    """
    
    SHEET_KEYWORDS = ['数据映射', 'DataMap']
    HEADER_ROW = 3
    DATA_START_ROW = 4
    
    COLUMN_MAPPING = {
        '组别编号': 0,
        '字段序号': 1,
        '字段中文名称': 2,
        '字段英文名': 3,
        '数据类型': 4,
        '值域参考': 5,
        '数据项说明': 6,
        '备注_说明_左': 7,
        '组别编号_右': 8,
        '取数方式': 9,
        '源系统编码': 10,
        '数据表': 11,
        '源字段名_英文': 12,
        '源字段名_中文': 13,
        '默认值': 14,
        '字段加工逻辑': 15,
        '码值映射': 16,
        '备注_说明_右': 17,
    }
    
    def __init__(self, workbook: openpyxl.Workbook):
        self.workbook = workbook
        self._sheet = None
        self._headers = None
        self._field_mappings_cache = None
        self._grouped_mappings_cache = None
    
    def _fuzzy_match_sheet(self) -> Optional[openpyxl.worksheet.worksheet.Worksheet]:
        if self._sheet is not None:
            return self._sheet
        
        for name in self.workbook.sheetnames:
            for keyword in self.SHEET_KEYWORDS:
                if keyword in name:
                    self._sheet = self.workbook[name]
                    return self._sheet
        return None
    
    def _get_headers(self, sheet) -> list:
        if self._headers is not None:
            return self._headers
        
        header_row = list(sheet.iter_rows(
            min_row=self.HEADER_ROW, 
            max_row=self.HEADER_ROW, 
            values_only=True
        ))[0]
        self._headers = list(header_row)
        return self._headers
    
    def _is_valid_field_row(self, row: tuple) -> bool:
        if not row or len(row) < 4:
            return False
        
        group_id = row[0]
        field_seq = row[1]
        field_cn = row[2]
        field_en = row[3]
        
        if group_id is None or str(group_id).startswith('='):
            return False
        
        if not isinstance(field_seq, int):
            return False
        
        if field_cn is None and field_en is None:
            return False
        
        return True
    
    def _parse_row_to_field_mapping(self, row: tuple, row_idx: int) -> Optional[FieldMapping]:
        if not self._is_valid_field_row(row):
            return None
        
        def safe_get(index: int, default=None):
            if index < len(row):
                val = row[index]
                if val is not None and not str(val).startswith('='):
                    return val
            return default
        
        return FieldMapping(
            组别编号=str(safe_get(0, '')),
            字段序号=safe_get(1, 0),
            字段中文名称=str(safe_get(2, '')),
            字段英文名=str(safe_get(3, '')),
            数据类型=safe_get(4),
            值域参考=safe_get(5),
            数据项说明=safe_get(6),
            取数方式=safe_get(9),
            源系统编码=safe_get(10),
            数据表=safe_get(11),
            源字段名_英文=safe_get(12),
            源字段名_中文=safe_get(13),
            默认值=safe_get(14),
            字段加工逻辑=safe_get(15),
            码值映射=safe_get(16),
            备注_说明=safe_get(17),
            _excel_row=row_idx
        )
    
    def extract_all_field_mappings(self) -> list:
        if self._field_mappings_cache is not None:
            return self._field_mappings_cache
        
        sheet = self._fuzzy_match_sheet()
        if sheet is None:
            raise ValueError("未找到数据映射sheet")
        
        self._get_headers(sheet)
        
        field_mappings = []
        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=self.DATA_START_ROW, values_only=True),
            self.DATA_START_ROW
        ):
            field_mapping = self._parse_row_to_field_mapping(row, row_idx)
            if field_mapping:
                field_mappings.append(field_mapping)
        
        self._field_mappings_cache = field_mappings
        return field_mappings
    
    def extract_grouped_mappings(self) -> dict:
        if self._grouped_mappings_cache is not None:
            return self._grouped_mappings_cache
        
        field_mappings = self.extract_all_field_mappings()
        
        grouped = {}
        current_group_id = None
        current_group_name = None
        
        for field in field_mappings:
            group_id = field.组别编号
            
            if group_id not in grouped:
                group_name = self._get_group_name(group_id)
                grouped[group_id] = GroupFieldMapping(
                    组别编号=group_id,
                    组别名称=group_name,
                    字段列表=[]
                )
            
            grouped[group_id].字段列表.append(field)
        
        self._grouped_mappings_cache = grouped
        return grouped
    
    def _get_group_name(self, group_id: str) -> str:
        group_names = {
            'MP1': '联系地址',
            'MP2': '营业地址',
            'MP3': '其他地址',
        }
        return group_names.get(group_id, group_id)
    
    def get_group_mapping(self, group_id: str) -> Optional[GroupFieldMapping]:
        grouped = self.extract_grouped_mappings()
        return grouped.get(group_id)
    
    def get_group_ids(self) -> list:
        grouped = self.extract_grouped_mappings()
        return list(grouped.keys())
    
    def get_field_by_name(self, group_id: str, field_name: str) -> Optional[FieldMapping]:
        group_mapping = self.get_group_mapping(group_id)
        if group_mapping is None:
            return None
        
        for field in group_mapping.字段列表:
            if field.字段英文名 == field_name or field.字段中文名称 == field_name:
                return field
        return None
    
    def get_field_by_seq(self, group_id: str, field_seq: int) -> Optional[FieldMapping]:
        group_mapping = self.get_group_mapping(group_id)
        if group_mapping is None:
            return None
        
        for field in group_mapping.字段列表:
            if field.字段序号 == field_seq:
                return field
        return None
    
    def to_dict(self) -> dict:
        grouped = self.extract_grouped_mappings()
        result = {}
        
        for group_id, group_mapping in grouped.items():
            result[group_id] = {
                '组别编号': group_mapping.组别编号,
                '组别名称': group_mapping.组别名称,
                '字段数量': len(group_mapping.字段列表),
                '字段列表': [
                    {
                        '字段序号': f.字段序号,
                        '字段中文名称': f.字段中文名称,
                        '字段英文名': f.字段英文名,
                        '数据类型': f.数据类型,
                        '值域参考': f.值域参考,
                        '数据项说明': f.数据项说明,
                        '取数方式': f.取数方式,
                        '源系统编码': f.源系统编码,
                        '数据表': f.数据表,
                        '源字段名_英文': f.源字段名_英文,
                        '源字段名_中文': f.源字段名_中文,
                        '默认值': f.默认值,
                        '字段加工逻辑': f.字段加工逻辑,
                        '码值映射': f.码值映射,
                        '备注_说明': f.备注_说明,
                    }
                    for f in group_mapping.字段列表
                ]
            }
        
        return result
    
    def to_field_dict(self, group_id: str) -> dict:
        group_mapping = self.get_group_mapping(group_id)
        if group_mapping is None:
            return {}
        
        return {
            f.字段英文名: {
                '字段序号': f.字段序号,
                '字段中文名称': f.字段中文名称,
                '数据类型': f.数据类型,
                '值域参考': f.值域参考,
                '数据项说明': f.数据项说明,
                '取数方式': f.取数方式,
                '源系统编码': f.源系统编码,
                '数据表': f.数据表,
                '源字段名_英文': f.源字段名_英文,
                '源字段名_中文': f.源字段名_中文,
                '默认值': f.默认值,
                '字段加工逻辑': f.字段加工逻辑,
                '码值映射': f.码值映射,
            }
            for f in group_mapping.字段列表
        }


def load_excel(file_path: str) -> openpyxl.Workbook:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    if not file_path.lower().endswith('.xlsx'):
        raise ValueError("只支持.xlsx格式的Excel文件")
    
    return openpyxl.load_workbook(file_path, read_only=True, data_only=True)


def extract_groups_from_excel(file_path: str) -> dict:
    workbook = load_excel(file_path)
    extractor = GroupExtractor(workbook)
    groups = extractor.to_dict()
    workbook.close()
    return groups


def extract_data_map_from_excel(file_path: str) -> dict:
    """从Excel文件提取数据映射信息
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        按组别编号分组的字段映射字典
    """
    workbook = load_excel(file_path)
    extractor = DataMapExtractor(workbook)
    data_map = extractor.to_dict()
    workbook.close()
    return data_map


def extract_field_mappings_from_excel(file_path: str) -> list:
    """从Excel文件提取字段映射列表（用于Harness架构）

    Args:
        file_path: Excel文件路径

    Returns:
        字段映射信息列表，每个元素是一个字典，包含:
        - group_id: 组别编号
        - field_seq: 字段序号
        - target_field_cn: 目标字段中文名
        - target_field: 目标字段英文名
        - data_type: 数据类型
        - extract_method: 取数方式
        - source_table_alias: 源表别名
        - source_field: 源字段名
        - source_field_cn: 源字段中文名
        - default_value: 默认值
        - transformation_logic: 转换逻辑
    """
    workbook = load_excel(file_path)
    extractor = DataMapExtractor(workbook)
    field_mappings = extractor.extract_all_field_mappings()
    workbook.close()

    result = []
    for fm in field_mappings:
        result.append({
            'group_id': fm.组别编号,
            'field_seq': fm.字段序号,
            'target_field_cn': fm.字段中文名称,
            'target_field': fm.字段英文名,
            'data_type': fm.数据类型 or '',
            'extract_method': fm.取数方式 or '',
            'source_table_alias': fm.数据表 or '',
            'source_field': fm.源字段名_英文 or '',
            'source_field_cn': fm.源字段名_中文 or '',
            'default_value': fm.默认值 or '',
            'transformation_logic': fm.字段加工逻辑 or '',
            'value_domain': fm.值域参考 or '',
            'code_mapping': fm.码值映射 or '',
            'excel_row': fm._excel_row
        })

    # 打印分组统计信息
    group_ids = set(fm['group_id'] for fm in result if fm['group_id'])
    print(f'[extract_field_mappings_from_excel] 提取了 {len(result)} 个字段映射，分组: {group_ids}')

    return result


if __name__ == '__main__':
    import json
    
    test_file = r'c:\Users\14093\Desktop\SQL智能纠错系统\【客户物理地址信息】ITMappingv0.8.xlsx'
    
    print("=" * 60)
    print("测试1: 提取分组信息 (GroupExtractor)")
    print("=" * 60)
    groups = extract_groups_from_excel(test_file)
    
    print(f"\n共发现 {len(groups)} 个分组:")
    for group_id, group_info in groups.items():
        print(f"\n=== {group_id}: {group_info['组别名称']} ===")
        print(f"数据源表数量: {len(group_info['数据源表'])}")
        for table in group_info['数据源表']:
            print(f"  - {table['数据表别名']}: {table['数据表名_中文']} ({table['数据表名_英文']})")
        print(f"表间关联数量: {len(group_info['表间关联'])}")
        print(f"筛选条件数量: {len(group_info['筛选条件'])}")
    
    print("\n" + "=" * 60)
    print("测试2: 提取数据映射 (DataMapExtractor)")
    print("=" * 60)
    data_map = extract_data_map_from_excel(test_file)
    
    print(f"\n共发现 {len(data_map)} 个分组字段映射:")
    for group_id, group_info in data_map.items():
        print(f"\n=== {group_id}: {group_info['组别名称']} ===")
        print(f"字段数量: {group_info['字段数量']}")
        print("字段列表:")
        for field in group_info['字段列表']:
            print(f"  {field['字段序号']:2d}. {field['字段中文名称']} ({field['字段英文名']}) - {field['取数方式'] or '未指定'}")
    
    print("\n" + "=" * 60)
    print("测试3: 获取特定分组的字段映射字典")
    print("=" * 60)
    workbook = load_excel(test_file)
    extractor = DataMapExtractor(workbook)
    
    mp1_dict = extractor.to_field_dict('MP1')
    print(f"\nMP1分组字段映射字典 (共{len(mp1_dict)}个字段):")
    for field_name, field_info in list(mp1_dict.items())[:5]:
        print(f"  {field_name}: {field_info['字段中文名称']}")
    
    workbook.close()
    
    print("\n" + "=" * 60)
    print("测试4: 数据源表缓存机制测试")
    print("=" * 60)
    
    cache = get_cache_instance()
    cache.clear_all()
    
    print("\n第一次解析 (缓存未命中):")
    workbook = load_excel(test_file)
    group_extractor = GroupExtractor(workbook, use_cache=True)
    groups1 = group_extractor.extract_all_groups()
    stats1 = group_extractor.get_cache_statistics()
    print(f"  表缓存命中率: {stats1['table_cache']['hit_rate']}%")
    print(f"  JOIN缓存命中率: {stats1['join_cache']['hit_rate']}%")
    print(f"  总请求数: {stats1['overall']['total_requests']}")
    workbook.close()
    
    print("\n第二次解析相同文件 (应命中缓存):")
    workbook = load_excel(test_file)
    group_extractor2 = GroupExtractor(workbook, use_cache=True)
    groups2 = group_extractor2.extract_all_groups()
    stats2 = group_extractor2.get_cache_statistics()
    print(f"  表缓存命中率: {stats2['table_cache']['hit_rate']}%")
    print(f"  JOIN缓存命中率: {stats2['join_cache']['hit_rate']}%")
    print(f"  总请求数: {stats2['overall']['total_requests']}")
    workbook.close()
    
    print("\n缓存统计详情:")
    cache_stats = cache.get_statistics()
    print(f"  表缓存大小: {cache_stats['table_cache']['size']}")
    print(f"  表缓存命中次数: {cache_stats['table_cache']['hits']}")
    print(f"  表缓存未命中次数: {cache_stats['table_cache']['misses']}")
    print(f"  JOIN缓存大小: {cache_stats['join_cache']['size']}")
    print(f"  JOIN缓存命中次数: {cache_stats['join_cache']['hits']}")
    print(f"  JOIN缓存未命中次数: {cache_stats['join_cache']['misses']}")
    print(f"  筛选条件缓存大小: {cache_stats['filter_cache']['size']}")
    print(f"  总体命中率: {cache_stats['overall']['hit_rate']}%")
    
    print("\n热点表统计:")
    hot_tables = group_extractor2.get_hot_tables(5)
    for table_key, hit_count in hot_tables:
        print(f"  {table_key}: {hit_count}次命中")
    
    print("\n本地解析缓存信息:")
    local_info = group_extractor2.get_local_cache_info()
    print(f"  已解析表数量: {local_info['parsed_tables_count']}")
    print(f"  已解析JOIN数量: {local_info['parsed_joins_count']}")
    print(f"  已解析筛选条件数量: {local_info['parsed_filters_count']}")
    
    print("\n测试禁用缓存:")
    workbook = load_excel(test_file)
    group_extractor3 = GroupExtractor(workbook, use_cache=False)
    groups3 = group_extractor3.extract_all_groups()
    stats3 = group_extractor3.get_cache_statistics()
    print(f"  缓存状态: {stats3.get('message', '已启用')}")
    workbook.close()
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)

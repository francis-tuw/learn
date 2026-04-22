# -*- coding: utf-8 -*-
"""
分组对比结果展示模块

实现功能：
1. 分组结果汇总统计
2. 分组详情展示
3. 问题快速定位功能
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import json


class DisplayFormat(Enum):
    TEXT = 'text'
    TABLE = 'table'
    HTML = 'html'
    MARKDOWN = 'markdown'


class SeverityLevel(Enum):
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


SEVERITY_ICONS = {
    SeverityLevel.CRITICAL: '🔴',
    SeverityLevel.HIGH: '🟠',
    SeverityLevel.MEDIUM: '🟡',
    SeverityLevel.LOW: '🟢'
}

STATUS_ICONS = {
    'passed': '✅',
    'warning': '⚠️',
    'failed': '❌',
    'error': '💥'
}


@dataclass
class GroupSummary:
    group_id: str
    group_name: str
    status: str
    field_count: int
    consistent_fields: int
    inconsistent_fields: int
    consistency_rate: float


@dataclass
class OverallSummary:
    total_groups: int = 0
    passed_groups: int = 0
    failed_groups: int = 0
    warning_groups: int = 0
    total_fields: int = 0
    consistent_fields: int = 0
    inconsistent_fields: int = 0
    overall_consistency_rate: float = 0.0
    severity_counts: Dict[str, int] = field(default_factory=dict)
    issue_type_counts: Dict[str, int] = field(default_factory=dict)


class ComparisonResultDisplay:
    """分组对比结果展示器
    
    支持多种输出格式：
    - 文本格式（控制台输出）
    - 表格格式（ASCII表格）
    - HTML格式（网页展示）
    - Markdown格式（文档输出）
    """
    
    def __init__(self, format_type: DisplayFormat = DisplayFormat.TEXT):
        self.format_type = format_type
        self.terminal_width = 120
    
    def display_overall_result(
        self, 
        result: Any,
        format_type: DisplayFormat = None
    ) -> str:
        """展示总体对比结果
        
        Args:
            result: OverallComparisonResult对象或字典
            format_type: 输出格式，默认使用实例设置
            
        Returns:
            格式化的输出字符串
        """
        format_type = format_type or self.format_type
        
        if hasattr(result, '__dataclass_fields__'):
            summary = self._extract_summary_from_dataclass(result)
            groups = self._extract_groups_from_dataclass(result)
        else:
            summary = result.get('summary', {})
            groups = result.get('groups', [])
        
        overall_summary = self._build_overall_summary(summary, groups)
        
        if format_type == DisplayFormat.TEXT:
            return self._format_overall_text(overall_summary)
        elif format_type == DisplayFormat.TABLE:
            return self._format_overall_table(overall_summary)
        elif format_type == DisplayFormat.HTML:
            return self._format_overall_html(overall_summary)
        elif format_type == DisplayFormat.MARKDOWN:
            return self._format_overall_markdown(overall_summary)
        
        return self._format_overall_text(overall_summary)
    
    def display_group_details(
        self,
        group_result: Any,
        format_type: DisplayFormat = None
    ) -> str:
        """展示单个分组的详细结果
        
        Args:
            group_result: GroupComparisonResult对象或字典
            format_type: 输出格式
            
        Returns:
            格式化的输出字符串
        """
        format_type = format_type or self.format_type
        
        if hasattr(group_result, '__dataclass_fields__'):
            group_data = self._extract_group_data_from_dataclass(group_result)
        else:
            group_data = group_result
        
        if format_type == DisplayFormat.TEXT:
            return self._format_group_detail_text(group_data)
        elif format_type == DisplayFormat.TABLE:
            return self._format_group_detail_table(group_data)
        elif format_type == DisplayFormat.HTML:
            return self._format_group_detail_html(group_data)
        elif format_type == DisplayFormat.MARKDOWN:
            return self._format_group_detail_markdown(group_data)
        
        return self._format_group_detail_text(group_data)
    
    def display_all_groups(
        self,
        result: Any,
        format_type: DisplayFormat = None,
        sort_by: str = 'group_id'
    ) -> str:
        """展示所有分组的详细结果
        
        Args:
            result: OverallComparisonResult对象或字典
            format_type: 输出格式
            sort_by: 排序字段（group_id, status, consistency_rate）
            
        Returns:
            格式化的输出字符串
        """
        format_type = format_type or self.format_type
        
        if hasattr(result, '__dataclass_fields__'):
            groups = self._extract_groups_from_dataclass(result)
        else:
            groups = result.get('groups', [])
        
        sorted_groups = self._sort_groups(groups, sort_by)
        
        output_parts = []
        for group in sorted_groups:
            output_parts.append(self.display_group_details(group, format_type))
        
        return '\n\n'.join(output_parts)
    
    def locate_issues(
        self,
        result: Any,
        severity_filter: List[str] = None,
        group_id_filter: str = None
    ) -> Dict[str, Any]:
        """问题快速定位功能
        
        Args:
            result: OverallComparisonResult对象或字典
            severity_filter: 严重级别过滤 ['critical', 'high', 'medium', 'low']
            group_id_filter: 分组ID过滤
            
        Returns:
            问题定位结果字典
        """
        if hasattr(result, '__dataclass_fields__'):
            groups = self._extract_groups_from_dataclass(result)
        else:
            groups = result.get('groups', [])
        
        severity_filter = severity_filter or ['critical', 'high']
        
        issues = []
        problem_groups = []
        
        for group in groups:
            group_data = group if isinstance(group, dict) else self._extract_group_data_from_dataclass(group)
            
            if group_id_filter and group_data.get('group_id', '').upper() != group_id_filter.upper():
                continue
            
            group_issues = self._extract_issues_from_group(group_data, severity_filter)
            
            if group_issues:
                problem_groups.append({
                    'group_id': group_data.get('group_id', ''),
                    'group_name': group_data.get('group_name', ''),
                    'status': group_data.get('status', ''),
                    'issue_count': len(group_issues),
                    'issues': group_issues,
                    'context': self._build_group_context(group_data)
                })
                issues.extend(group_issues)
        
        return {
            'total_issues': len(issues),
            'problem_group_count': len(problem_groups),
            'severity_breakdown': self._count_severity(issues),
            'problem_groups': problem_groups,
            'quick_fix_suggestions': self._generate_quick_fix_suggestions(issues)
        }
    
    def display_issue_location(
        self,
        result: Any,
        severity_filter: List[str] = None,
        group_id_filter: str = None,
        format_type: DisplayFormat = None
    ) -> str:
        """展示问题定位结果
        
        Args:
            result: 对比结果
            severity_filter: 严重级别过滤
            group_id_filter: 分组ID过滤
            format_type: 输出格式
            
        Returns:
            格式化的问题定位输出
        """
        format_type = format_type or self.format_type
        location_result = self.locate_issues(result, severity_filter, group_id_filter)
        
        if format_type == DisplayFormat.TEXT:
            return self._format_issue_location_text(location_result)
        elif format_type == DisplayFormat.HTML:
            return self._format_issue_location_html(location_result)
        elif format_type == DisplayFormat.MARKDOWN:
            return self._format_issue_location_markdown(location_result)
        
        return self._format_issue_location_text(location_result)
    
    def _extract_summary_from_dataclass(self, result: Any) -> Dict:
        """从dataclass对象提取摘要"""
        if hasattr(result, 'summary'):
            return result.summary if isinstance(result.summary, dict) else {}
        return {}
    
    def _extract_groups_from_dataclass(self, result: Any) -> List:
        """从dataclass对象提取分组列表"""
        if hasattr(result, 'groups'):
            return result.groups
        return []
    
    def _extract_group_data_from_dataclass(self, group: Any) -> Dict:
        """从dataclass对象提取分组数据"""
        return {
            'group_id': getattr(group, 'group_id', ''),
            'group_name': getattr(group, 'group_name', ''),
            'status': getattr(group, 'status', ''),
            'field_count': getattr(group, 'field_count', 0),
            'consistent_fields': getattr(group, 'consistent_fields', 0),
            'inconsistent_fields': getattr(group, 'inconsistent_fields', 0),
            'details': getattr(group, 'details', []),
            'field_comparison': getattr(group, 'field_comparison', {}),
            'source_table_comparison': getattr(group, 'source_table_comparison', {}),
            'join_comparison': getattr(group, 'join_comparison', {}),
            'filter_comparison': getattr(group, 'filter_comparison', {})
        }
    
    def _build_overall_summary(self, summary: Dict, groups: List) -> OverallSummary:
        """构建总体摘要"""
        overall = OverallSummary()
        
        overall.total_groups = summary.get('total_groups', len(groups))
        overall.passed_groups = summary.get('passed_groups', 0)
        overall.failed_groups = summary.get('failed_groups', 0)
        overall.warning_groups = summary.get('warning_groups', 0)
        overall.total_fields = summary.get('total_fields', 0)
        overall.consistent_fields = summary.get('consistent_fields', 0)
        overall.inconsistent_fields = summary.get('inconsistent_fields', 0)
        overall.overall_consistency_rate = summary.get('consistency_rate', 0.0)
        overall.severity_counts = summary.get('severity_counts', {})
        overall.issue_type_counts = summary.get('issue_type_counts', {})
        
        return overall
    
    def _sort_groups(self, groups: List, sort_by: str) -> List:
        """对分组进行排序"""
        def sort_key(group):
            if isinstance(group, dict):
                if sort_by == 'group_id':
                    return (0, group.get('group_id', ''))
                elif sort_by == 'status':
                    status_order = {'failed': 0, 'error': 1, 'warning': 2, 'passed': 3}
                    return (status_order.get(group.get('status', ''), 4), group.get('group_id', ''))
                elif sort_by == 'consistency_rate':
                    field_count = group.get('field_count', 0)
                    consistent = group.get('consistent_fields', 0)
                    rate = consistent / field_count if field_count > 0 else 0
                    return (rate, group.get('group_id', ''))
            return (0, '')
        
        return sorted(groups, key=sort_key)
    
    def _extract_issues_from_group(self, group_data: Dict, severity_filter: List[str]) -> List[Dict]:
        """从分组中提取问题"""
        issues = []
        details = group_data.get('details', [])
        
        for detail in details:
            severity = detail.get('severity', 'low')
            if severity in severity_filter:
                issues.append({
                    'group_id': group_data.get('group_id', ''),
                    'group_name': group_data.get('group_name', ''),
                    'severity': severity,
                    'type': detail.get('type', 'unknown'),
                    'message': detail.get('message', ''),
                    'field_name': detail.get('field_name', ''),
                    'detail': detail
                })
        
        return issues
    
    def _build_group_context(self, group_data: Dict) -> Dict:
        """构建分组上下文信息"""
        return {
            'field_comparison': group_data.get('field_comparison', {}),
            'source_table_comparison': group_data.get('source_table_comparison', {}),
            'join_comparison': group_data.get('join_comparison', {}),
            'filter_comparison': group_data.get('filter_comparison', {})
        }
    
    def _count_severity(self, issues: List[Dict]) -> Dict[str, int]:
        """统计问题严重级别"""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for issue in issues:
            severity = issue.get('severity', 'low')
            if severity in counts:
                counts[severity] += 1
        return counts
    
    def _generate_quick_fix_suggestions(self, issues: List[Dict]) -> List[str]:
        """生成快速修复建议"""
        suggestions = []
        
        issue_types = set(issue.get('type', '') for issue in issues)
        
        if 'missing_sql_block' in issue_types:
            suggestions.append('检查SQL文件中是否缺少对应的INSERT语句块')
        
        if 'field_mapping' in issue_types:
            suggestions.append('检查字段映射是否与IT-Mapping定义一致')
        
        if 'extra_field' in issue_types:
            suggestions.append('确认新增字段是否已在IT-Mapping中更新')
        
        if 'source_table' in issue_types:
            suggestions.append('检查数据源表是否正确配置')
        
        if 'join_condition' in issue_types:
            suggestions.append('检查JOIN条件是否与IT-Mapping定义一致')
        
        if 'filter_condition' in issue_types:
            suggestions.append('检查WHERE条件是否与IT-Mapping定义一致')
        
        return suggestions
    
    def _format_overall_text(self, summary: OverallSummary) -> str:
        """格式化总体摘要为文本"""
        lines = []
        lines.append('=' * self.terminal_width)
        lines.append('📊 分组对比结果汇总统计')
        lines.append('=' * self.terminal_width)
        lines.append('')
        
        lines.append('📋 分组统计:')
        lines.append(f'   总分组数: {summary.total_groups}')
        lines.append(f'   ✅ 通过分组数: {summary.passed_groups}')
        lines.append(f'   ❌ 失败分组数: {summary.failed_groups}')
        lines.append(f'   ⚠️  警告分组数: {summary.warning_groups}')
        lines.append('')
        
        lines.append('📈 字段统计:')
        lines.append(f'   总字段数: {summary.total_fields}')
        lines.append(f'   一致字段数: {summary.consistent_fields}')
        lines.append(f'   不一致字段数: {summary.inconsistent_fields}')
        lines.append(f'   总体一致率: {summary.overall_consistency_rate:.2f}%')
        lines.append('')
        
        if summary.severity_counts:
            lines.append('🔍 问题严重级别分布:')
            for severity, count in summary.severity_counts.items():
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                lines.append(f'   {icon} {severity.upper()}: {count}')
            lines.append('')
        
        if summary.issue_type_counts:
            lines.append('📝 问题类型分布:')
            for issue_type, count in summary.issue_type_counts.items():
                lines.append(f'   • {issue_type}: {count}')
        
        lines.append('')
        lines.append('=' * self.terminal_width)
        
        return '\n'.join(lines)
    
    def _format_overall_table(self, summary: OverallSummary) -> str:
        """格式化总体摘要为表格"""
        lines = []
        lines.append('┌' + '─' * 50 + '┬' + '─' * 20 + '┐')
        lines.append('│ 指标' + ' ' * 46 + '│ 值' + ' ' * 17 + '│')
        lines.append('├' + '─' * 50 + '┼' + '─' * 20 + '┤')
        
        metrics = [
            ('总分组数', str(summary.total_groups)),
            ('通过分组数', f'✅ {summary.passed_groups}'),
            ('失败分组数', f'❌ {summary.failed_groups}'),
            ('警告分组数', f'⚠️ {summary.warning_groups}'),
            ('总字段数', str(summary.total_fields)),
            ('一致字段数', str(summary.consistent_fields)),
            ('不一致字段数', str(summary.inconsistent_fields)),
            ('总体一致率', f'{summary.overall_consistency_rate:.2f}%')
        ]
        
        for label, value in metrics:
            lines.append(f'│ {label}' + ' ' * (49 - len(label)) + f'│ {value}' + ' ' * (19 - len(value)) + '│')
        
        lines.append('└' + '─' * 50 + '┴' + '─' * 20 + '┘')
        
        return '\n'.join(lines)
    
    def _format_overall_html(self, summary: OverallSummary) -> str:
        """格式化总体摘要为HTML"""
        html = '''
<div class="comparison-summary">
    <h2>📊 分组对比结果汇总统计</h2>
    
    <div class="summary-section">
        <h3>📋 分组统计</h3>
        <table class="summary-table">
            <tr><td>总分组数</td><td>{total_groups}</td></tr>
            <tr><td>通过分组数</td><td class="passed">{passed_groups}</td></tr>
            <tr><td>失败分组数</td><td class="failed">{failed_groups}</td></tr>
            <tr><td>警告分组数</td><td class="warning">{warning_groups}</td></tr>
        </table>
    </div>
    
    <div class="summary-section">
        <h3>📈 字段统计</h3>
        <table class="summary-table">
            <tr><td>总字段数</td><td>{total_fields}</td></tr>
            <tr><td>一致字段数</td><td>{consistent_fields}</td></tr>
            <tr><td>不一致字段数</td><td>{inconsistent_fields}</td></tr>
            <tr><td>总体一致率</td><td>{consistency_rate:.2f}%</td></tr>
        </table>
    </div>
    
    <div class="summary-section">
        <h3>🔍 问题严重级别分布</h3>
        <div class="severity-chart">
            {severity_bars}
        </div>
    </div>
</div>
'''.format(
            total_groups=summary.total_groups,
            passed_groups=summary.passed_groups,
            failed_groups=summary.failed_groups,
            warning_groups=summary.warning_groups,
            total_fields=summary.total_fields,
            consistent_fields=summary.consistent_fields,
            inconsistent_fields=summary.inconsistent_fields,
            consistency_rate=summary.overall_consistency_rate,
            severity_bars=self._generate_severity_bars_html(summary.severity_counts)
        )
        return html
    
    def _generate_severity_bars_html(self, severity_counts: Dict[str, int]) -> str:
        """生成严重级别条形图HTML"""
        if not severity_counts:
            return '<p>无问题记录</p>'
        
        bars = []
        colors = {
            'critical': '#dc3545',
            'high': '#fd7e14',
            'medium': '#ffc107',
            'low': '#28a745'
        }
        
        for severity, count in severity_counts.items():
            color = colors.get(severity, '#6c757d')
            bars.append(f'''
            <div class="severity-bar">
                <span class="severity-label">{severity.upper()}</span>
                <div class="bar-container">
                    <div class="bar" style="width: {count * 10}px; background-color: {color};"></div>
                </div>
                <span class="severity-count">{count}</span>
            </div>
            ''')
        
        return ''.join(bars)
    
    def _format_overall_markdown(self, summary: OverallSummary) -> str:
        """格式化总体摘要为Markdown"""
        md = '''# 📊 分组对比结果汇总统计

## 📋 分组统计

| 指标 | 值 |
|------|-----|
| 总分组数 | {total_groups} |
| 通过分组数 | ✅ {passed_groups} |
| 失败分组数 | ❌ {failed_groups} |
| 警告分组数 | ⚠️ {warning_groups} |

## 📈 字段统计

| 指标 | 值 |
|------|-----|
| 总字段数 | {total_fields} |
| 一致字段数 | {consistent_fields} |
| 不一致字段数 | {inconsistent_fields} |
| 总体一致率 | {consistency_rate:.2f}% |

## 🔍 问题严重级别分布

{severity_table}
'''.format(
            total_groups=summary.total_groups,
            passed_groups=summary.passed_groups,
            failed_groups=summary.failed_groups,
            warning_groups=summary.warning_groups,
            total_fields=summary.total_fields,
            consistent_fields=summary.consistent_fields,
            inconsistent_fields=summary.inconsistent_fields,
            consistency_rate=summary.overall_consistency_rate,
            severity_table=self._generate_severity_table_md(summary.severity_counts)
        )
        return md
    
    def _generate_severity_table_md(self, severity_counts: Dict[str, int]) -> str:
        """生成严重级别表格Markdown"""
        if not severity_counts:
            return '无问题记录'
        
        lines = ['| 级别 | 数量 |', '|------|------|']
        icons = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
        
        for severity, count in severity_counts.items():
            icon = icons.get(severity, '⚪')
            lines.append(f'| {icon} {severity.upper()} | {count} |')
        
        return '\n'.join(lines)
    
    def _format_group_detail_text(self, group_data: Dict) -> str:
        """格式化分组详情为文本"""
        lines = []
        
        status_icon = STATUS_ICONS.get(group_data.get('status', ''), '❓')
        
        lines.append('─' * self.terminal_width)
        lines.append(f'{status_icon} 分组: {group_data.get("group_id", "")} - {group_data.get("group_name", "")}')
        lines.append('─' * self.terminal_width)
        lines.append('')
        
        field_count = group_data.get('field_count', 0)
        consistent = group_data.get('consistent_fields', 0)
        inconsistent = group_data.get('inconsistent_fields', 0)
        rate = (consistent / field_count * 100) if field_count > 0 else 0
        
        lines.append('📊 字段映射统计:')
        lines.append(f'   总字段数: {field_count}')
        lines.append(f'   一致字段数: {consistent}')
        lines.append(f'   不一致字段数: {inconsistent}')
        lines.append(f'   一致率: {rate:.2f}%')
        lines.append('')
        
        source_table_comp = group_data.get('source_table_comparison', {})
        if source_table_comp:
            lines.append('📋 数据源表清单:')
            mapping_tables = source_table_comp.get('mapping_tables', [])
            sql_tables = source_table_comp.get('sql_tables', [])
            
            if mapping_tables:
                lines.append('   IT-Mapping定义的表:')
                for table in mapping_tables:
                    lines.append(f'      • {table}')
            
            if sql_tables:
                lines.append('   SQL中使用的表:')
                for table in sql_tables:
                    lines.append(f'      • {table}')
            lines.append('')
        
        field_comp = group_data.get('field_comparison', {})
        if field_comp and field_comp.get('details'):
            lines.append('📝 字段映射对比详情:')
            for detail in field_comp.get('details', []):
                field_name = detail.get('field_name', '')
                consistent_flag = detail.get('consistent', True)
                severity = detail.get('severity', 'low')
                message = detail.get('message', '')
                
                icon = '✅' if consistent_flag else SEVERITY_ICONS.get(SeverityLevel(severity), '❓')
                lines.append(f'   {icon} {field_name}')
                if not consistent_flag and message:
                    lines.append(f'      └─ {message}')
            lines.append('')
        
        details = group_data.get('details', [])
        if details:
            lines.append('⚠️ 差异详情:')
            for detail in details:
                severity = detail.get('severity', 'low')
                detail_type = detail.get('type', 'unknown')
                message = detail.get('message', '')
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                lines.append(f'   {icon} [{severity.upper()}] {detail_type}: {message}')
        
        lines.append('')
        
        return '\n'.join(lines)
    
    def _format_group_detail_table(self, group_data: Dict) -> str:
        """格式化分组详情为表格"""
        lines = []
        
        status_icon = STATUS_ICONS.get(group_data.get('status', ''), '❓')
        
        lines.append('┌' + '─' * 80 + '┐')
        lines.append(f'│ {status_icon} {group_data.get("group_id", "")} - {group_data.get("group_name", "")}' + ' ' * (79 - len(f'{status_icon} {group_data.get("group_id", "")} - {group_data.get("group_name", "")}')) + '│')
        lines.append('├' + '─' * 80 + '┤')
        
        field_count = group_data.get('field_count', 0)
        consistent = group_data.get('consistent_fields', 0)
        rate = (consistent / field_count * 100) if field_count > 0 else 0
        
        lines.append(f'│ 状态: {group_data.get("status", "")}' + ' ' * (73 - len(f'状态: {group_data.get("status", "")}')) + '│')
        lines.append(f'│ 字段数: {field_count} | 一致: {consistent} | 一致率: {rate:.2f}%' + ' ' * (80 - len(f'│ 字段数: {field_count} | 一致: {consistent} | 一致率: {rate:.2f}%')) + '│')
        
        details = group_data.get('details', [])
        if details:
            lines.append('├' + '─' * 80 + '┤')
            lines.append('│ 差异详情:' + ' ' * 71 + '│')
            for detail in details[:5]:
                severity = detail.get('severity', 'low')
                message = detail.get('message', '')[:60]
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                line = f'│   {icon} {message}'
                lines.append(line + ' ' * (80 - len(line)) + '│')
        
        lines.append('└' + '─' * 80 + '┘')
        
        return '\n'.join(lines)
    
    def _format_group_detail_html(self, group_data: Dict) -> str:
        """格式化分组详情为HTML"""
        status = group_data.get('status', '')
        status_class = f'group-{status}'
        status_icon = STATUS_ICONS.get(status, '❓')
        
        field_count = group_data.get('field_count', 0)
        consistent = group_data.get('consistent_fields', 0)
        rate = (consistent / field_count * 100) if field_count > 0 else 0
        
        html = f'''
<div class="group-detail {status_class}">
    <div class="group-header">
        <span class="status-icon">{status_icon}</span>
        <h3>{group_data.get("group_id", "")} - {group_data.get("group_name", "")}</h3>
    </div>
    
    <div class="group-stats">
        <div class="stat">
            <span class="stat-label">总字段数</span>
            <span class="stat-value">{field_count}</span>
        </div>
        <div class="stat">
            <span class="stat-label">一致字段数</span>
            <span class="stat-value">{consistent}</span>
        </div>
        <div class="stat">
            <span class="stat-label">一致率</span>
            <span class="stat-value">{rate:.2f}%</span>
        </div>
    </div>
    
    {self._format_source_tables_html(group_data.get('source_table_comparison', {}))}
    
    {self._format_field_comparison_html(group_data.get('field_comparison', {}))}
    
    {self._format_details_html(group_data.get('details', []))}
</div>
'''
        return html
    
    def _format_source_tables_html(self, source_table_comp: Dict) -> str:
        """格式化数据源表HTML"""
        if not source_table_comp:
            return ''
        
        mapping_tables = source_table_comp.get('mapping_tables', [])
        sql_tables = source_table_comp.get('sql_tables', [])
        
        html = '''
<div class="source-tables">
    <h4>📋 数据源表清单</h4>
    <div class="tables-comparison">
        <div class="mapping-tables">
            <h5>IT-Mapping定义</h5>
            <ul>
                {}
            </ul>
        </div>
        <div class="sql-tables">
            <h5>SQL使用</h5>
            <ul>
                {}
            </ul>
        </div>
    </div>
</div>
'''.format(
            ''.join(f'<li>{table}</li>' for table in mapping_tables) or '<li>无</li>',
            ''.join(f'<li>{table}</li>' for table in sql_tables) or '<li>无</li>'
        )
        return html
    
    def _format_field_comparison_html(self, field_comp: Dict) -> str:
        """格式化字段对比HTML"""
        if not field_comp or not field_comp.get('details'):
            return ''
        
        rows = []
        for detail in field_comp.get('details', []):
            field_name = detail.get('field_name', '')
            consistent = detail.get('consistent', True)
            severity = detail.get('severity', 'low')
            message = detail.get('message', '')
            
            row_class = 'consistent' if consistent else f'inconsistent {severity}'
            icon = '✅' if consistent else SEVERITY_ICONS.get(SeverityLevel(severity), '❓')
            
            rows.append(f'''
            <tr class="{row_class}">
                <td>{icon}</td>
                <td>{field_name}</td>
                <td>{detail.get("mapping_source", "")}</td>
                <td>{detail.get("sql_expression", "")[:50]}</td>
                <td>{message}</td>
            </tr>
            ''')
        
        html = f'''
<div class="field-comparison">
    <h4>📝 字段映射对比</h4>
    <table class="field-table">
        <thead>
            <tr>
                <th>状态</th>
                <th>字段名</th>
                <th>Mapping源字段</th>
                <th>SQL表达式</th>
                <th>说明</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
</div>
'''
        return html
    
    def _format_details_html(self, details: List[Dict]) -> str:
        """格式化差异详情HTML"""
        if not details:
            return ''
        
        items = []
        for detail in details:
            severity = detail.get('severity', 'low')
            detail_type = detail.get('type', 'unknown')
            message = detail.get('message', '')
            icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
            
            items.append(f'''
            <div class="detail-item severity-{severity}">
                <span class="detail-icon">{icon}</span>
                <span class="detail-type">[{detail_type}]</span>
                <span class="detail-message">{message}</span>
            </div>
            ''')
        
        html = f'''
<div class="issue-details">
    <h4>⚠️ 差异详情</h4>
    <div class="details-list">
        {''.join(items)}
    </div>
</div>
'''
        return html
    
    def _format_group_detail_markdown(self, group_data: Dict) -> str:
        """格式化分组详情为Markdown"""
        status_icon = STATUS_ICONS.get(group_data.get('status', ''), '❓')
        
        field_count = group_data.get('field_count', 0)
        consistent = group_data.get('consistent_fields', 0)
        rate = (consistent / field_count * 100) if field_count > 0 else 0
        
        md = f'''## {status_icon} {group_data.get("group_id", "")} - {group_data.get("group_name", "")}

### 📊 字段映射统计

| 指标 | 值 |
|------|-----|
| 总字段数 | {field_count} |
| 一致字段数 | {consistent} |
| 不一致字段数 | {group_data.get("inconsistent_fields", 0)} |
| 一致率 | {rate:.2f}% |

{self._format_source_tables_md(group_data.get('source_table_comparison', {}))}

{self._format_field_comparison_md(group_data.get('field_comparison', {}))}

{self._format_details_md(group_data.get('details', []))}
'''
        return md
    
    def _format_source_tables_md(self, source_table_comp: Dict) -> str:
        """格式化数据源表Markdown"""
        if not source_table_comp:
            return ''
        
        mapping_tables = source_table_comp.get('mapping_tables', [])
        sql_tables = source_table_comp.get('sql_tables', [])
        
        md = '''### 📋 数据源表清单

**IT-Mapping定义的表:**
{}
**SQL中使用的表:**
{}
'''.format(
            '\n'.join(f'- {table}' for table in mapping_tables) or '- 无',
            '\n'.join(f'- {table}' for table in sql_tables) or '- 无'
        )
        return md
    
    def _format_field_comparison_md(self, field_comp: Dict) -> str:
        """格式化字段对比Markdown"""
        if not field_comp or not field_comp.get('details'):
            return ''
        
        lines = ['### 📝 字段映射对比详情', '', '| 状态 | 字段名 | Mapping源字段 | SQL表达式 | 说明 |', '|------|--------|---------------|-----------|------|']
        
        for detail in field_comp.get('details', []):
            field_name = detail.get('field_name', '')
            consistent = detail.get('consistent', True)
            severity = detail.get('severity', 'low')
            message = detail.get('message', '')
            
            icon = '✅' if consistent else SEVERITY_ICONS.get(SeverityLevel(severity), '❓')
            mapping_source = detail.get('mapping_source', '')
            sql_expr = detail.get('sql_expression', '')[:30]
            
            lines.append(f'| {icon} | {field_name} | {mapping_source} | {sql_expr} | {message} |')
        
        return '\n'.join(lines)
    
    def _format_details_md(self, details: List[Dict]) -> str:
        """格式化差异详情Markdown"""
        if not details:
            return ''
        
        lines = ['### ⚠️ 差异详情', '']
        
        for detail in details:
            severity = detail.get('severity', 'low')
            detail_type = detail.get('type', 'unknown')
            message = detail.get('message', '')
            icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
            
            lines.append(f'{icon} **[{severity.upper()}]** {detail_type}: {message}')
        
        return '\n'.join(lines)
    
    def _format_issue_location_text(self, location_result: Dict) -> str:
        """格式化问题定位结果为文本"""
        lines = []
        
        lines.append('=' * self.terminal_width)
        lines.append('🔍 问题快速定位结果')
        lines.append('=' * self.terminal_width)
        lines.append('')
        
        lines.append(f'📊 问题总数: {location_result.get("total_issues", 0)}')
        lines.append(f'📋 问题分组数: {location_result.get("problem_group_count", 0)}')
        lines.append('')
        
        severity_breakdown = location_result.get('severity_breakdown', {})
        if severity_breakdown:
            lines.append('📈 严重级别分布:')
            for severity, count in severity_breakdown.items():
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                lines.append(f'   {icon} {severity.upper()}: {count}')
            lines.append('')
        
        problem_groups = location_result.get('problem_groups', [])
        if problem_groups:
            lines.append('⚠️ 问题分组详情:')
            lines.append('')
            
            for pg in problem_groups:
                status_icon = STATUS_ICONS.get(pg.get('status', ''), '❓')
                lines.append(f'─' * 60)
                lines.append(f'{status_icon} 分组: {pg.get("group_id", "")} - {pg.get("group_name", "")}')
                lines.append(f'   问题数量: {pg.get("issue_count", 0)}')
                lines.append('')
                
                issues = pg.get('issues', [])
                for issue in issues:
                    severity = issue.get('severity', 'low')
                    issue_type = issue.get('type', 'unknown')
                    message = issue.get('message', '')
                    field_name = issue.get('field_name', '')
                    icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                    
                    lines.append(f'   {icon} [{severity.upper()}] {issue_type}')
                    if field_name:
                        lines.append(f'      字段: {field_name}')
                    if message:
                        lines.append(f'      说明: {message}')
                
                lines.append('')
        
        suggestions = location_result.get('quick_fix_suggestions', [])
        if suggestions:
            lines.append('💡 快速修复建议:')
            for suggestion in suggestions:
                lines.append(f'   • {suggestion}')
        
        lines.append('')
        lines.append('=' * self.terminal_width)
        
        return '\n'.join(lines)
    
    def _format_issue_location_html(self, location_result: Dict) -> str:
        """格式化问题定位结果为HTML"""
        html = '''
<div class="issue-location">
    <h2>🔍 问题快速定位结果</h2>
    
    <div class="location-summary">
        <div class="summary-stat">
            <span class="stat-value">{total_issues}</span>
            <span class="stat-label">问题总数</span>
        </div>
        <div class="summary-stat">
            <span class="stat-value">{problem_group_count}</span>
            <span class="stat-label">问题分组数</span>
        </div>
    </div>
    
    {severity_section}
    
    {problem_groups_section}
    
    {suggestions_section}
</div>
'''.format(
            total_issues=location_result.get('total_issues', 0),
            problem_group_count=location_result.get('problem_group_count', 0),
            severity_section=self._format_severity_breakdown_html(location_result.get('severity_breakdown', {})),
            problem_groups_section=self._format_problem_groups_html(location_result.get('problem_groups', [])),
            suggestions_section=self._format_suggestions_html(location_result.get('quick_fix_suggestions', []))
        )
        return html
    
    def _format_severity_breakdown_html(self, severity_breakdown: Dict) -> str:
        """格式化严重级别分布HTML"""
        if not severity_breakdown:
            return ''
        
        items = []
        colors = {'critical': '#dc3545', 'high': '#fd7e14', 'medium': '#ffc107', 'low': '#28a745'}
        
        for severity, count in severity_breakdown.items():
            color = colors.get(severity, '#6c757d')
            items.append(f'''
            <div class="severity-item" style="border-left: 4px solid {color};">
                <span class="severity-name">{severity.upper()}</span>
                <span class="severity-count">{count}</span>
            </div>
            ''')
        
        return f'''
<div class="severity-breakdown">
    <h3>📈 严重级别分布</h3>
    <div class="severity-list">
        {''.join(items)}
    </div>
</div>
'''
    
    def _format_problem_groups_html(self, problem_groups: List[Dict]) -> str:
        """格式化问题分组HTML"""
        if not problem_groups:
            return '<p>无问题分组</p>'
        
        groups_html = []
        for pg in problem_groups:
            status_icon = STATUS_ICONS.get(pg.get('status', ''), '❓')
            
            issues_html = []
            for issue in pg.get('issues', []):
                severity = issue.get('severity', 'low')
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                issues_html.append(f'''
                <div class="issue-item severity-{severity}">
                    <span class="issue-icon">{icon}</span>
                    <div class="issue-content">
                        <span class="issue-type">{issue.get("type", "")}</span>
                        <span class="issue-field">{issue.get("field_name", "")}</span>
                        <p class="issue-message">{issue.get("message", "")}</p>
                    </div>
                </div>
                ''')
            
            groups_html.append(f'''
            <div class="problem-group">
                <div class="group-header">
                    <span class="status-icon">{status_icon}</span>
                    <h4>{pg.get("group_id", "")} - {pg.get("group_name", "")}</h4>
                    <span class="issue-count">{pg.get("issue_count", 0)} 个问题</span>
                </div>
                <div class="group-issues">
                    {''.join(issues_html)}
                </div>
            </div>
            ''')
        
        return f'''
<div class="problem-groups">
    <h3>⚠️ 问题分组详情</h3>
    {''.join(groups_html)}
</div>
'''
    
    def _format_suggestions_html(self, suggestions: List[str]) -> str:
        """格式化修复建议HTML"""
        if not suggestions:
            return ''
        
        items = ''.join(f'<li>{s}</li>' for s in suggestions)
        
        return f'''
<div class="suggestions">
    <h3>💡 快速修复建议</h3>
    <ul class="suggestion-list">
        {items}
    </ul>
</div>
'''
    
    def _format_issue_location_markdown(self, location_result: Dict) -> str:
        """格式化问题定位结果为Markdown"""
        md = '''# 🔍 问题快速定位结果

## 📊 问题统计

| 指标 | 值 |
|------|-----|
| 问题总数 | {total_issues} |
| 问题分组数 | {problem_group_count} |

{severity_section}

{problem_groups_section}

{suggestions_section}
'''.format(
            total_issues=location_result.get('total_issues', 0),
            problem_group_count=location_result.get('problem_group_count', 0),
            severity_section=self._format_severity_breakdown_md(location_result.get('severity_breakdown', {})),
            problem_groups_section=self._format_problem_groups_md(location_result.get('problem_groups', [])),
            suggestions_section=self._format_suggestions_md(location_result.get('quick_fix_suggestions', []))
        )
        return md
    
    def _format_severity_breakdown_md(self, severity_breakdown: Dict) -> str:
        """格式化严重级别分布Markdown"""
        if not severity_breakdown:
            return ''
        
        lines = ['## 📈 严重级别分布', '', '| 级别 | 数量 |', '|------|------|']
        
        for severity, count in severity_breakdown.items():
            icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
            lines.append(f'| {icon} {severity.upper()} | {count} |')
        
        return '\n'.join(lines)
    
    def _format_problem_groups_md(self, problem_groups: List[Dict]) -> str:
        """格式化问题分组Markdown"""
        if not problem_groups:
            return '## ⚠️ 问题分组详情\n\n无问题分组'
        
        sections = ['## ⚠️ 问题分组详情', '']
        
        for pg in problem_groups:
            status_icon = STATUS_ICONS.get(pg.get('status', ''), '❓')
            
            sections.append(f'### {status_icon} {pg.get("group_id", "")} - {pg.get("group_name", "")}')
            sections.append(f'问题数量: {pg.get("issue_count", 0)}')
            sections.append('')
            
            for issue in pg.get('issues', []):
                severity = issue.get('severity', 'low')
                icon = SEVERITY_ICONS.get(SeverityLevel(severity), '⚪')
                issue_type = issue.get('type', '')
                field_name = issue.get('field_name', '')
                message = issue.get('message', '')
                
                sections.append(f'{icon} **[{severity.upper()}]** {issue_type}')
                if field_name:
                    sections.append(f'  - 字段: `{field_name}`')
                if message:
                    sections.append(f'  - 说明: {message}')
                sections.append('')
        
        return '\n'.join(sections)
    
    def _format_suggestions_md(self, suggestions: List[str]) -> str:
        """格式化修复建议Markdown"""
        if not suggestions:
            return ''
        
        lines = ['## 💡 快速修复建议', '']
        for s in suggestions:
            lines.append(f'- {s}')
        
        return '\n'.join(lines)


def create_display(format_type: str = 'text') -> ComparisonResultDisplay:
    """创建结果展示器
    
    Args:
        format_type: 输出格式类型 ('text', 'table', 'html', 'markdown')
        
    Returns:
        ComparisonResultDisplay实例
    """
    format_map = {
        'text': DisplayFormat.TEXT,
        'table': DisplayFormat.TABLE,
        'html': DisplayFormat.HTML,
        'markdown': DisplayFormat.MARKDOWN
    }
    
    return ComparisonResultDisplay(format_map.get(format_type, DisplayFormat.TEXT))


def display_comparison_result(
    result: Any,
    format_type: str = 'text',
    include_details: bool = True
) -> str:
    """便捷函数：展示对比结果
    
    Args:
        result: 对比结果对象或字典
        format_type: 输出格式
        include_details: 是否包含详细分组信息
        
    Returns:
        格式化的输出字符串
    """
    display = create_display(format_type)
    
    output_parts = []
    output_parts.append(display.display_overall_result(result))
    
    if include_details:
        output_parts.append('\n')
        output_parts.append(display.display_all_groups(result))
    
    return '\n'.join(output_parts)


def locate_and_display_issues(
    result: Any,
    severity_filter: List[str] = None,
    format_type: str = 'text'
) -> str:
    """便捷函数：定位并展示问题
    
    Args:
        result: 对比结果
        severity_filter: 严重级别过滤
        format_type: 输出格式
        
    Returns:
        格式化的问题定位输出
    """
    display = create_display(format_type)
    return display.display_issue_location(result, severity_filter)


if __name__ == '__main__':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    from sql_correction_engine import GroupComparisonResult, OverallComparisonResult
    
    test_groups = [
        GroupComparisonResult(
            group_id='MP001',
            group_name='客户基本信息',
            status='passed',
            field_count=10,
            consistent_fields=10,
            inconsistent_fields=0,
            details=[]
        ),
        GroupComparisonResult(
            group_id='MP002',
            group_name='客户地址信息',
            status='failed',
            field_count=15,
            consistent_fields=10,
            inconsistent_fields=5,
            details=[
                {
                    'type': 'field_mapping',
                    'severity': 'critical',
                    'field_name': 'ADDR_TYPE',
                    'message': '字段 ADDR_TYPE 在SQL中未找到',
                    'consistent': False
                },
                {
                    'type': 'source_table',
                    'severity': 'high',
                    'message': 'SQL中缺少数据源表 DWD_CUSTOMER',
                    'consistent': False
                }
            ],
            field_comparison={
                'total_fields': 15,
                'consistent_count': 10,
                'inconsistent_count': 5,
                'details': [
                    {
                        'field_name': 'ADDR_TYPE',
                        'consistent': False,
                        'severity': 'critical',
                        'message': '字段在SQL中未找到',
                        'mapping_source': 'ADDR_TYPE_CD',
                        'sql_expression': ''
                    }
                ]
            },
            source_table_comparison={
                'mapping_tables': ['DWD_CUSTOMER', 'DIM_ADDRESS'],
                'sql_tables': ['DIM_ADDRESS'],
                'consistent': False
            }
        ),
        GroupComparisonResult(
            group_id='MP003',
            group_name='客户联系方式',
            status='warning',
            field_count=8,
            consistent_fields=6,
            inconsistent_fields=2,
            details=[
                {
                    'type': 'field_mapping',
                    'severity': 'medium',
                    'field_name': 'PHONE_NUM',
                    'message': '字段映射逻辑存在差异',
                    'consistent': False
                }
            ]
        )
    ]
    
    overall = OverallComparisonResult(
        total_groups=3,
        passed_groups=1,
        failed_groups=1,
        overall_consistency_rate=78.6
    )
    overall.groups = test_groups
    overall.summary = {
        'total_groups': 3,
        'passed_groups': 1,
        'failed_groups': 1,
        'warning_groups': 1,
        'total_fields': 33,
        'consistent_fields': 26,
        'inconsistent_fields': 7,
        'consistency_rate': 78.79,
        'severity_counts': {'critical': 1, 'high': 1, 'medium': 1, 'low': 0},
        'issue_type_counts': {'field_mapping': 2, 'source_table': 1}
    }
    
    print('=' * 80)
    print('测试1: 文本格式输出')
    print('=' * 80)
    display = ComparisonResultDisplay(DisplayFormat.TEXT)
    print(display.display_overall_result(overall))
    
    print('\n' + '=' * 80)
    print('测试2: 表格格式输出')
    print('=' * 80)
    print(display.display_overall_result(overall, DisplayFormat.TABLE))
    
    print('\n' + '=' * 80)
    print('测试3: 分组详情展示')
    print('=' * 80)
    print(display.display_all_groups(overall))
    
    print('\n' + '=' * 80)
    print('测试4: 问题快速定位')
    print('=' * 80)
    print(display.display_issue_location(overall, ['critical', 'high']))
    
    print('\n' + '=' * 80)
    print('测试5: Markdown格式输出')
    print('=' * 80)
    print(display.display_overall_result(overall, DisplayFormat.MARKDOWN))

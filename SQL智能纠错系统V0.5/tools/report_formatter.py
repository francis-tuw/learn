from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


class ReportFormatter:
    DATASET_HEADERS = ['组别编号', '源表数量', '比较模块', 'IT-Mappin文件', 'SQL存储过程', '是否一致', '备注']
    DATAMAP_HEADERS = [
        '组别编号', '字段序号', '目标表字段中文名', '目标表字段英文名', '取数方式',
        '源数据表表名', '源表字段名（英文）', '源表字段名（中文）', '默认值',
        '字段加工逻辑', '存储过程SQL', '是否一致', '备注'
    ]
    
    @staticmethod
    def generate_excel_report(dataset_results: list, datamap_results: list) -> BytesIO:
        """
        生成Excel格式的纠错报告
        
        Args:
            dataset_results: 数据源对比结果列表，包含:
                - groups: 分组信息列表（包含表间关联和筛选条件）
            datamap_results: 数据映射对比结果列表
        
        Returns:
            BytesIO: Excel文件的字节流
        """
        wb = Workbook()
        
        ws_dataset = wb.active
        ws_dataset.title = '数据源（DataSet）'
        
        ws_datamap = wb.create_sheet(title='数据映射（DataMap）')
        
        ReportFormatter._write_dataset_sheet(ws_dataset, dataset_results)
        ReportFormatter._write_datamap_sheet(ws_datamap, datamap_results)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output
    
    @staticmethod
    def _write_dataset_sheet(ws, results: list):
        """写入数据源工作表，按照参考格式输出
        
        输出格式：
        | 组别编号 | 源表数量 | 比较模块 | IT-Mappin文件 | SQL存储过程 | 是否一致 | 备注 |
        """
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for col_idx, header in enumerate(ReportFormatter.DATASET_HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        groups = results.get('groups', []) if isinstance(results, dict) else []
        row_idx = 2
        
        for group in groups:
            group_id = group.get('group_id', '')
            source_tables = group.get('source_tables', '')
            
            relations = group.get('relations', [])
            if relations:
                for relation in relations:
                    compare_module = relation.get('compare_module', '')
                    content = relation.get('content', '')
                    sql_content = relation.get('sql_content', '')
                    is_consistent = relation.get('is_consistent', '是')
                    remark = relation.get('remark', '')
                    
                    row_data = [
                        group_id,
                        source_tables,
                        compare_module,
                        content,
                        sql_content,
                        is_consistent,
                        remark
                    ]
                    
                    for col_idx, value in enumerate(row_data, 1):
                        cell = ws.cell(row=row_idx, column=col_idx, value=value)
                        cell.alignment = cell_alignment
                        cell.border = thin_border
                        
                        if col_idx == 6:
                            if value == '否':
                                cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
                            else:
                                cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
                    
                    row_idx += 1
            
            filters = group.get('filters', [])
            if filters:
                for filter_item in filters:
                    compare_module = filter_item.get('compare_module', '')
                    content = filter_item.get('content', '')
                    sql_content = filter_item.get('sql_content', '')
                    is_consistent = filter_item.get('is_consistent', '是')
                    remark = filter_item.get('remark', '')
                    
                    row_data = [
                        group_id,
                        source_tables,
                        compare_module,
                        content,
                        sql_content,
                        is_consistent,
                        remark
                    ]
                    
                    for col_idx, value in enumerate(row_data, 1):
                        cell = ws.cell(row=row_idx, column=col_idx, value=value)
                        cell.alignment = cell_alignment
                        cell.border = thin_border
                        
                        if col_idx == 6:
                            if value == '否':
                                cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
                            else:
                                cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
                    
                    row_idx += 1
        
        column_widths = [12, 20, 12, 40, 50, 10, 30]
        for col_idx, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width
    
    @staticmethod
    def _write_datamap_sheet(ws, results: list):
        """写入数据映射工作表"""
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell_alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        for col_idx, header in enumerate(ReportFormatter.DATAMAP_HEADERS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        for row_idx, result in enumerate(results, 2):
            row_data = [
                result.get('group_id', ''),
                result.get('field_seq', 0),
                result.get('target_field_cn', ''),
                result.get('target_field_en', ''),
                result.get('extract_method', ''),
                result.get('source_table', ''),
                result.get('source_field_en', ''),
                result.get('source_field_cn', ''),
                result.get('default_value', ''),
                result.get('transform_logic', ''),
                result.get('sql_expression', ''),
                result.get('is_consistent', '是'),
                result.get('remark', '')
            ]
            
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = cell_alignment
                cell.border = thin_border
                
                if col_idx == 12:
                    if value == '否':
                        cell.fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
                    else:
                        cell.fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        
        column_widths = [12, 10, 18, 18, 12, 25, 18, 18, 12, 25, 30, 10, 25]
        for col_idx, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    @staticmethod
    def generate_markdown_report(result_data: dict) -> str:
        """
        生成Markdown格式的纠错报告

        Args:
            result_data: 包含task_id, total_checks, consistent_count,
                        inconsistent_count, duration, findings的字典

        Returns:
            Markdown格式的报告文本
        """
        task_id = result_data.get('task_id', 'N/A')
        total_checks = result_data.get('total_checks', 0)
        consistent_count = result_data.get('consistent_count', 0)
        inconsistent_count = result_data.get('inconsistent_count', 0)
        duration = result_data.get('duration', 0)
        findings = result_data.get('findings', [])
        mapping_file = result_data.get('mapping_file', 'N/A')
        sql_filename = result_data.get('sql_filename', 'N/A')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pass_rate = (consistent_count / max(total_checks, 1)) * 100

        report_lines = []

        report_lines.append('# SQL智能纠错报告')
        report_lines.append('')
        report_lines.append('## 元信息')
        report_lines.append('')
        report_lines.append('| 项目 | 值 |')
        report_lines.append('|------|-----|')
        report_lines.append(f'| 任务ID | `{task_id}` |')
        report_lines.append(f'| 生成时间 | {now} |')
        report_lines.append(f'| 耗时 | {duration}秒 |')
        report_lines.append(f'| 通过率 | {pass_rate:.1f}% |')
        report_lines.append(f'| Mapping文件 | {mapping_file} |')
        report_lines.append(f'| SQL文件 | {sql_filename} |')
        report_lines.append('')
        report_lines.append('## 统计摘要')
        report_lines.append('')
        report_lines.append(f'- **总检查项数**: {total_checks}')
        report_lines.append(f'- **一致项数**: ✅ {consistent_count}')
        report_lines.append(f'- **不一致项数**: ❌ {inconsistent_count}')

        inconsistent_findings = [f for f in findings if f.get('status') == 'inconsistent']

        if inconsistent_findings:
            report_lines.append('')
            report_lines.append('## 详细问题列表')
            report_lines.append('')

            for idx, finding in enumerate(inconsistent_findings, 1):
                severity = finding.get('severity', 'medium').upper()
                issue_type = finding.get('typeLabel', finding.get('type', '未知'))

                severity_emoji = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🔵'
                }.get(severity, '⚪')

                report_lines.append(f'### 问题 {idx}: {finding.get("issue", "未指定问题")}')
                report_lines.append('')
                report_lines.append(f'- **位置**: {finding.get("location", "未知")}')
                report_lines.append(f'- **类型**: {issue_type}')
                report_lines.append(f'- **严重程度**: {severity_emoji} {severity}')
                report_lines.append('')
                report_lines.append('**问题描述**:')
                report_lines.append('')
                report_lines.append(finding.get('explanation', '无详细说明'))
                report_lines.append('')

                mapping_ref = finding.get('mapping_ref', {})
                if mapping_ref and isinstance(mapping_ref, dict):
                    report_lines.append('**IT-Mapping 参考**:')
                    report_lines.append('')
                    report_lines.append(f"- 目标字段: `{mapping_ref.get('target', 'N/A')}`")
                    if mapping_ref.get('logic'):
                        report_lines.append(f"- 要求逻辑: {mapping_ref['logic']}")
                    report_lines.append('')

                original_sql = finding.get('original_sql', '')
                if original_sql:
                    report_lines.append('**原始SQL片段**:')
                    report_lines.append('')
                    report_lines.append('```sql')
                    report_lines.append(original_sql)
                    report_lines.append('```')
                    report_lines.append('')

                suggestion = finding.get('suggestion', '')
                if suggestion:
                    report_lines.append('**建议修改**:')
                    report_lines.append('')
                    report_lines.append(suggestion)
                    report_lines.append('')

                report_lines.append('---')
                report_lines.append('')
        else:
            report_lines.append('')
            report_lines.append('> 🎉 恭喜！未发现不一致项，代码符合IT-Mapping规范。')
            report_lines.append('')

        report_lines.append('---')
        report_lines.append('')
        report_lines.append(f'*报告生成时间: {now}*')
        report_lines.append(f'*由 SQL智能纠错系统 自动生成*')

        return '\n'.join(report_lines)

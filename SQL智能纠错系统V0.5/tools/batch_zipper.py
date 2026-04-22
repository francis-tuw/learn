import zipfile
import io
import os
import re
from datetime import datetime
from tools.sql_annotator import SQLAnnotator
from tools.report_formatter import ReportFormatter


class BatchZipper:
    """批量打包多个纠错结果为ZIP压缩包"""

    def __init__(self, sql_engine):
        self.sql_engine = sql_engine

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除或替换特殊字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名
        """
        if not filename:
            return 'unknown'
        name = re.sub(r'[<>:"/\\|?*\[\]]', '_', filename)
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        return name if name else 'unknown'

    def _format_datetime(self, dt_str: str) -> str:
        """
        格式化日期时间字符串

        Args:
            dt_str: 原始日期时间字符串

        Returns:
            格式化后的日期时间字符串 (YYYYMMDD_HHMMSS)
        """
        if not dt_str:
            return datetime.now().strftime('%Y%m%d_%H%M%S')

        try:
            if 'T' in dt_str:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y%m%d_%H%M%S')
        except (ValueError, TypeError):
            return datetime.now().strftime('%Y%m%d_%H%M%S')

    def create_batch_zip(self, task_ids):
        """
        为多个任务生成ZIP压缩包

        每条记录创建独立文件夹，文件夹命名格式为：
        {序号}_{Mapping文件名(去除扩展名)}_{日期时间}

        文件夹内包含：
        - 测试报告.md
        - 批注SQL.sql (如有SQL内容)

        Args:
            task_ids: 任务ID列表

        Returns:
            (zip_bytes, filename) 元组，如果失败返回 (None, None)
        """
        from services.history_service import HistoryService
        zip_buffer = io.BytesIO()
        total_files = 0
        success_count = 0

        hs = HistoryService()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, task_id in enumerate(task_ids, 1):
                try:
                    result = self.sql_engine.get_task_result(task_id)

                    if not result.get('success'):
                        print(f'[BatchZipper] 跳过无效任务: {task_id}')
                        continue

                    data = result['data']

                    record = hs.get_record(task_id)
                    created_at = record.get('created_at', '') if record else ''
                    mapping_file = data.get('mapping_file', '')
                    if mapping_file:
                        base_name = os.path.splitext(os.path.basename(mapping_file))[0]
                    else:
                        base_name = f'记录{idx}'

                    safe_name = self._sanitize_filename(base_name)
                    dt_str = self._format_datetime(created_at)
                    folder_name = f'{idx:02d}_{safe_name}_{dt_str}'

                    md_content = ReportFormatter.generate_markdown_report(data)
                    zf.writestr(
                        f'{folder_name}/测试报告.md',
                        md_content.encode('utf-8')
                    )
                    total_files += 1

                    sql_content = data.get('sql_content', '')
                    findings = data.get('findings', [])
                    if sql_content:
                        if findings:
                            annotated_sql = SQLAnnotator.annotate(sql_content, findings)
                        else:
                            annotated_sql = sql_content
                        zf.writestr(
                            f'{folder_name}/批注SQL.sql',
                            annotated_sql.encode('utf-8')
                        )
                        total_files += 1

                    success_count += 1
                    print(f'[BatchZipper] 已处理: {folder_name}')

                except Exception as e:
                    print(f'[BatchZipper] 处理任务 {task_id} 时出错: {e}')
                    import traceback
                    traceback.print_exc()
                    continue

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'SQL纠错结果_批量下载_{timestamp}_{success_count}条.zip'

        zip_data = zip_buffer.getvalue()

        if len(zip_data) == 0 or total_files == 0:
            return None, None

        return zip_data, filename

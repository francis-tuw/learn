import re
from datetime import datetime


class SQLAnnotator:
    """将纠错结果标注到原始SQL文件中"""

    ANNOTATION_TEMPLATE = """-- ============================================================
-- 【{status}】第 {location} 行：{issue}
-- 原因：{explanation}
-- IT-Mapping 参考：{mapping_ref}
-- 建议修改：{suggestion}
-- ============================================================"""

    ANNOTATION_TEMPLATE_ENHANCED = """-- ⚠️ 【{status}】第 {location} 行
-- ❌ 问题: {issue}
-- 📝 原因: {explanation}
-- 📋 IT-Mapping参考: {mapping_ref}
-- ✅ 建议: {suggestion}
-- ↓↓↓↓↓↓ 下方为问题代码行 ↓↓↓↓↓↓"""

    PROBLEM_LINE_MARKER = "-- ↑↑↑↑↑↑ 问题代码行(见上方说明) ↑↑↑↑↑↑"

    @staticmethod
    def annotate(sql_text: str, findings: list) -> str:
        """
        在原始SQL上标注所有不一致项（仅标注，不修改源代码）

        Args:
            sql_text: 原始SQL存储过程文本
            findings: 纠错结果列表（每个finding包含location, issue, explanation等）

        Returns:
            标注后的SQL文本（原始代码保持不变）
        """
        lines = sql_text.split('\n')

        inconsistent_findings = [f for f in findings if f.get('status') == 'inconsistent']

        annotated_lines = list(lines)
        unannotated_findings = []

        for finding in sorted(inconsistent_findings, key=lambda x: SQLAnnotator._extract_line_number_enhanced(
            x.get('location', ''), annotated_lines, x.get('original_sql', '')
        ), reverse=True):
            location = finding.get('location', '')
            original_sql = finding.get('original_sql', '')

            line_num = SQLAnnotator._extract_line_number_enhanced(location, annotated_lines, original_sql)

            if 0 < line_num <= len(annotated_lines):
                mapping_ref = finding.get('mapping_ref', {})
                if isinstance(mapping_ref, dict):
                    mapping_ref_str = f"目标字段: {mapping_ref.get('target', 'N/A')}, 逻辑: {mapping_ref.get('logic', 'N/A')}"
                else:
                    mapping_ref_str = str(mapping_ref) if mapping_ref else 'N/A'

                annotation_block = SQLAnnotator.ANNOTATION_TEMPLATE_ENHANCED.format(
                    status=finding.get('status', 'inconsistent').upper(),
                    location=line_num,
                    issue=finding.get('issue', '未指定问题'),
                    explanation=finding.get('explanation', '无'),
                    mapping_ref=mapping_ref_str,
                    suggestion=finding.get('suggestion', '无建议')
                )

                insert_index = line_num - 1
                annotation_lines = [line + '\n' for line in annotation_block.split('\n')]
                annotated_lines[insert_index:insert_index] = annotation_lines

                problem_marker_line = SQLAnnotator.PROBLEM_LINE_MARKER + '\n'
                annotated_lines.insert(insert_index + len(annotation_lines), problem_marker_line)
            else:
                unannotated_findings.append(finding)

        header_comment = SQLAnnotator._generate_header(len(inconsistent_findings), len(findings), len(unannotated_findings))
        unannotated_report = SQLAnnotator._generate_unannotated_report(unannotated_findings)
        annotated_text = header_comment + '\n' + unannotated_report + '\n'.join(annotated_lines)

        return annotated_text

    @staticmethod
    def _generate_header(inconsistent_count: int, total_count: int, unannotated_count: int = 0) -> str:
        """生成文件头部统计信息注释"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        consistent_count = total_count - inconsistent_count
        annotated_count = inconsistent_count - unannotated_count

        header = f"""-- ============================================================
-- SQL智能纠错系统 - 标注结果
-- 生成时间：{now}
-- 统计信息：
--   总检查项数：{total_count}
--   一致项数：{consistent_count}
--   不一致项数（已标注）：{annotated_count}
--   未成功标注项数：{unannotated_count}
--   通过率：{(consistent_count / max(total_count, 1)) * 100:.1f}%
-- ============================================================"""
        return header

    @staticmethod
    def _extract_line_number(location: str) -> int:
        """从location字符串中提取SQL行号（排除Excel行号）"""
        excel_pattern = r'Excel行号[:\s]*(\d+)'
        if re.search(excel_pattern, location, re.IGNORECASE):
            return 0

        patterns = [
            r'第\s*(\d+)\s*行',
            r'Line\s+(\d+)',
            r'SQL第?\s*(\d+)\s*行',
            r'SQL行[:\s]*(\d+)',
            r'L(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, location, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return 0

    @staticmethod
    def _extract_line_number_enhanced(location, sql_lines, original_sql):
        """增强版行号提取:优先通过original_sql内容匹配，再尝试location正则"""
        if original_sql and original_sql.strip():
            line_num = SQLAnnotator._find_line_by_content(sql_lines, original_sql)
            if line_num > 0:
                return line_num

        return SQLAnnotator._extract_line_number(location)

    @staticmethod
    def _find_line_by_content(sql_lines, content):
        """通过内容匹配查找行号"""
        content_clean = re.sub(r'\s+', ' ', content).strip()
        content_keywords = content_clean[:50] if len(content_clean) > 50 else content_clean
        
        best_match_idx = 0
        best_match_score = 0
        
        for idx, line in enumerate(sql_lines, 1):
            line_clean = re.sub(r'\s+', ' ', line).strip()
            
            if content_clean == line_clean:
                return idx
            
            if content_keywords.lower() in line_clean.lower():
                score = len(content_keywords)
                if score > best_match_score:
                    best_match_score = score
                    best_match_idx = idx
        
        return best_match_idx

    @staticmethod
    def _generate_unannotated_report(unannotated_list):
        """生成未成功标注项的报告文本"""
        if not unannotated_list:
            return "-- ✅ 所有不一致项均已成功标注到对应行"

        lines = ["", f"-- ⚠️ 未成功标注项（共{len(unannotated_list)}项）："]
        for item in unannotated_list:
            issue = item.get('issue', '未指定')[:50]
            original_sql = item.get('original_sql', '无')[:50]
            location = item.get('location', '未知')[:30]
            fid = item.get('id', '?')
            lines.append(f"--   [ID:{fid}] 问题: {issue}")
            lines.append(f"--         原始SQL: {original_sql}")
            lines.append(f"--         声明位置: {location}")
            lines.append("")

        return '\n'.join(lines)

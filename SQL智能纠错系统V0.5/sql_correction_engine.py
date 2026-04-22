# -*- coding: utf-8 -*-
import os
import json
import uuid
import time
import threading
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from openpyxl import load_workbook
import pandas as pd
import requests
from extract_datamap_to_md import (
    generate_markdown,
    extract_data_source_sheet,
    extract_data_map_sheet,
    load_excel
)
from sql_group_parser import FieldLocator, FieldPosition


class MappingParser:
    """IT-Mapping Excel文件解析器"""

    def __init__(self, filepath):
        self.filepath = filepath
        self.wb = None
        self.tables = []
        self.field_mappings = []
        self.relationships = []
        self.business_rules = []

    def parse(self):
        """解析Excel文件，提取映射规则"""
        try:
            self.wb = load_workbook(self.filepath, data_only=True)
            
            for sheet_name in self.wb.sheetnames:
                sheet = self.wb[sheet_name]
                self._parse_sheet(sheet, sheet_name)
            
            return {
                'success': True,
                'tables': self.tables,
                'field_mappings': self.field_mappings,
                'relationships': self.relationships,
                'business_rules': self.business_rules,
                'sheet_count': len(self.wb.sheetnames)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_sheet(self, sheet, sheet_name):
        """解析单个工作表"""
        try:
            df = pd.DataFrame(sheet.values)
            
            if df.empty or len(df) < 3:
                return
            
            header_row = None
            for idx in range(min(5, len(df))):
                row_values = [str(v).strip() if v else '' for v in df.iloc[idx]]
                if '字段英文名' in row_values or '目标字段' in row_values:
                    header_row = idx
                    break
            
            if header_row is None:
                return
            
            df.columns = [str(col).strip() if col else f'col_{i}' for i, col in enumerate(df.iloc[header_row])]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            
            column_mapping = {
                '组别编号': ['组别编号'],
                '字段序号': ['字段序号'],
                '目标字段中文名': ['字段中文名称', '目标字段中文名'],
                '目标字段': ['字段英文名', '目标字段', 'target_field'],
                '数据类型': ['数据类型', 'data_type'],
                '源表': ['数据表', '源表', 'source_table'],
                '源字段': ['字段名（英文）', '源字段', 'source_field', '字段名(英文)'],
                '源字段中文名': ['字段名（中文）', '源字段中文名'],
                '默认值': ['默认值', 'default_value'],
                '转换逻辑': ['字段加工逻辑', '转换逻辑', 'transformation_logic', '加工逻辑'],
                '业务规则': ['数据项说明', '业务规则', '备注/说明', 'business_rule', '值域参考'],
                '取数方式': ['取数方式', 'extract_method']
            }
            
            def find_column(target_aliases):
                for alias in target_aliases:
                    if alias in df.columns:
                        return alias
                    for col in df.columns:
                        if alias.lower() in col.lower():
                            return col
                return None

            group_id_col = find_column(column_mapping['组别编号'])
            field_seq_col = find_column(column_mapping['字段序号'])
            target_cn_col = find_column(column_mapping['目标字段中文名'])
            target_col = find_column(column_mapping['目标字段'])
            data_type_col = find_column(column_mapping['数据类型'])
            source_table_col = find_column(column_mapping['源表'])
            source_field_col = find_column(column_mapping['源字段'])
            source_field_cn_col = find_column(column_mapping['源字段中文名'])
            default_value_col = find_column(column_mapping['默认值'])
            logic_col = find_column(column_mapping['转换逻辑'])
            rule_col = find_column(column_mapping['业务规则'])
            method_col = find_column(column_mapping['取数方式'])
            
            if not target_col or not source_field_col:
                print(f'工作表 {sheet_name}: 未找到必要的列（目标字段或源字段）')
                return
            
            table_name = ''
            for idx in range(min(header_row, len(df) + header_row + 1)):
                cell_val = sheet.cell(row=idx+1, column=1).value
                if cell_val and isinstance(cell_val, str) and ('【' in cell_val or 'DWD' in cell_val.upper() or 'DM_' in cell_val.upper()):
                    table_name = cell_val.strip().replace('【', '').replace('】', '').split('】')[0] if '】' in cell_val else cell_val.strip()
                    break
            
            if not table_name:
                table_name = sheet_name
            
            table_info = {
                'sheet_name': sheet_name,
                'alias': 'T',
                'name': table_name
            }
            
            if table_info not in self.tables:
                self.tables.append(table_info)
            
            for _, row in df.iterrows():
                target_field = str(row.get(target_col, '')).strip()
                source_field = str(row.get(source_field_col, '')).strip()
                
                if not target_field or target_field.lower() == 'none' or target_field == 'nan':
                    continue
                
                def safe_get_value(row, col_name, default=''):
                    if not col_name:
                        return default
                    val = row.get(col_name, default)
                    if isinstance(val, pd.Series):
                        val = val.iloc[0] if len(val) > 0 else default
                    return str(val).strip() if val is not None else default
                
                group_id = safe_get_value(row, group_id_col, '')
                field_seq_val = row.get(field_seq_col, 0) if field_seq_col else 0
                if isinstance(field_seq_val, pd.Series):
                    field_seq_val = field_seq_val.iloc[0] if len(field_seq_val) > 0 else 0
                try:
                    field_seq = int(field_seq_val) if field_seq_val and not str(field_seq_val).startswith('=') else 0
                except (ValueError, TypeError):
                    field_seq = 0
                target_field_cn = safe_get_value(row, target_cn_col, '')
                data_type = safe_get_value(row, data_type_col, '')
                source_table = safe_get_value(row, source_table_col, '')
                source_field_cn = safe_get_value(row, source_field_cn_col, '')
                default_value = safe_get_value(row, default_value_col, '')
                transformation_logic = safe_get_value(row, logic_col, '')
                business_rule = safe_get_value(row, rule_col, '')
                extract_method = safe_get_value(row, method_col, '')
                
                if source_table and source_table != 'nan':
                    table_alias = source_table.split('】')[-1].strip() if '】' in source_table else source_table[:3]
                    
                    found = False
                    for rel in self.relationships:
                        if rel['table'] == source_table:
                            found = True
                            break
                    
                    if not found and source_table != 'nan':
                        self.relationships.append({
                            'type': 'JOIN',
                            'table': source_table,
                            'alias': table_alias,
                            'condition': ''
                        })
                
                mapping = {
                    'group_id': group_id if group_id and group_id != 'nan' else '',
                    'field_seq': field_seq if field_seq and not str(field_seq).startswith('=') else 0,
                    'target_field': target_field,
                    'target_field_cn': target_field_cn if target_field_cn and target_field_cn != 'nan' else '',
                    'source_table_alias': source_table if source_table and source_table != 'nan' else '',
                    'source_field': source_field if source_field != 'nan' else '',
                    'source_field_cn': source_field_cn if source_field_cn and source_field_cn != 'nan' else '',
                    'default_value': default_value if default_value and default_value != 'nan' else '',
                    'transformation_logic': transformation_logic if transformation_logic != 'nan' else '',
                    'business_rule': business_rule if business_rule != 'nan' else '',
                    'data_type': data_type if data_type and data_type != 'nan' else '',
                    'extract_method': extract_method if extract_method != 'nan' else '',
                    'sheet': sheet_name
                }
                
                self.field_mappings.append(mapping)
                
                if business_rule and business_rule != 'nan' and business_rule not in [r['rule'] for r in self.business_rules]:
                    self.business_rules.append({
                        'field': target_field,
                        'rule': business_rule
                    })

            # 打印工作表解析统计
            group_ids_in_sheet = set(m['group_id'] for m in self.field_mappings if m.get('sheet') == sheet_name and m.get('group_id'))
            fields_in_sheet = [m for m in self.field_mappings if m.get('sheet') == sheet_name]
            print(f'[MappingParser] 工作表 {sheet_name}: 解析了 {len(fields_in_sheet)} 个字段，分组: {group_ids_in_sheet}')

        except Exception as e:
            print(f'解析工作表 {sheet_name} 时出错: {e}')
            import traceback
            traceback.print_exc()

    def get_mapping_summary(self):
        """获取映射摘要信息"""
        return {
            'total_tables': len(self.tables),
            'total_fields': len(self.field_mappings),
            'total_relationships': len(self.relationships),
            'total_rules': len(self.business_rules),
            'tables': [{'alias': t['alias'], 'name': t['name']} for t in self.tables]
        }

    def generate_md_file(self):
        """
        生成MD文件，调用extract_datamap_to_md.py的功能
        
        Returns:
            dict: 包含success和md_file_path或error的字典
        """
        try:
            workbook = load_excel(self.filepath)
            
            data_source = extract_data_source_sheet(workbook)
            field_mappings = extract_data_map_sheet(workbook)
            
            workbook.close()
            
            base_name = os.path.splitext(os.path.basename(self.filepath))[0]
            output_dir = os.path.dirname(self.filepath)
            md_file_path = os.path.join(output_dir, f"{base_name}.md")
            
            generate_markdown(self.filepath, data_source, field_mappings, md_file_path)
            
            print(f'[MappingParser] MD文件生成成功: {md_file_path}')
            
            return {
                'success': True,
                'md_file_path': md_file_path
            }
        except Exception as e:
            print(f'[MappingParser] MD文件生成失败: {e}')
            return {
                'success': False,
                'error': str(e)
            }


class RelationshipCheckerAgent:
    """表间关联检查Agent - 专注于JOIN条件、表间关系、关联字段一致性检查"""

    def __init__(self, config):
        self.host = config.get('host', 'http://localhost:11434')
        self.model = config.get('model', 'qwen2.5:7b')
        agent_timeouts = config.get('agent_timeouts', {})
        self.timeout = int(agent_timeouts.get('relationship_checker', config.get('timeout', 180)))
        self.output_timeout = int(config.get('output_timeout', 120))

    def analyze(self, mapping_data, sql_content):
        """执行表间关联关系检查"""

        system_prompt = """【强制要求 - 必须严格遵守】

【语言约束（最高优先级）】：
- 所有输出内容必须使用中文
- 【绝对禁止】在输出中使用英文说明文字

【输出格式强制规范】：
- 只返回JSON，不要包含任何其他文字
- 根对象只能包含 "findings" 和 "summary" 两个字段

【location字段格式标准】：
- 格式：必须使用"第X行 + 具体位置描述"
- 示例："第15行 LEFT JOIN T1子句"、"第23行 ON条件"

【finding完整性规则】：
- original_sql字段：必填且长度≥20字符
- issue字段：必填，简洁描述问题（≤100字符）
- explanation字段：必填，详细说明原因和影响
- suggestion字段：必填，提供具体的修改建议

【severity分级标准】：
- critical：数据丢失风险/逻辑错误导致结果完全错误（如LEFT JOIN被隐式转为INNER JOIN）
- high：严重不一致但不会完全错误（如JOIN类型错误、ON条件错误）
- medium：一般性问题（如关联顺序不合理但功能正确）
- low：建议性优化（如性能优化建议）

你是"表间关联检查专家"，专门负责检查SQL中的表间关联关系。

【你的唯一任务】对比SQL与IT-Mapping的表间关联定义是否一致。
【否定清单】你不检查字段映射、不检查数据转换、不检查业务规则。

【检查维度（共5项）】：

1. **JOIN类型一致性** — 对比SQL JOIN类型 vs IT-Mapping数据源Sheet定义
   检查：LEFT JOIN/INNER JOIN/FULL OUTER JOIN是否符合Mapping定义；是否存在应该用LEFT JOIN但用了INNER JOIN的情况

2. **ON条件正确性** — 对比JOIN ON条件的关联字段 vs Mapping定义
   检查：ON条件中的关联字段是否正确；是否遗漏了必要的关联条件；关联字段的数据类型是否匹配

3. **隐式JOIN转换** — 检查WHERE过滤是否破坏了JOIN语义
   检查：WHERE中对右表的过滤条件是否会导致LEFT JOIN匹配不到的行被过滤掉（隐式转为INNER JOIN）；RIGHT JOIN是否有类似问题

4. **多表关联顺序** — 对比FROM/JOIN的表顺序 vs Mapping的数据源依赖关系
   检查：主表和从表的顺序是否符合Mapping定义；多表JOIN时依赖关系是否正确

5. **关联字段NULL处理** — 对比关联字段的NVL/COALESCE处理 vs Mapping加工逻辑
   检查：作为关联条件的字段是否需要NULL处理；NULL处理方式是否与Mapping一致

【正确示例】：
```json
{
  "findings": [
    {
      "id": 1,
      "status": "inconsistent",
      "agent": "relationship_checker",
      "location": "第15行 LEFT JOIN T1子句",
      "issue": "WHERE对右表T1过滤导致LEFT JOIN语义被破坏",
      "explanation": "WHERE中T1.ACCOUNT_TYPE IN ('1','2')会将LEFT JOIN匹配不到的行过滤掉，实际变成了INNER JOIN语义",
      "original_sql": "LEFT JOIN T1 ON T.ID = T1.ID WHERE T1.ACCOUNT_TYPE IN ('1','2')",
      "mapping_ref": {"target": "T与T1关联", "logic": "Mapping定义为LEFT JOIN保留T1所有记录"},
      "suggestion": "将T1.ACCOUNT_TYPE过滤移至ON条件：AND T1.ACCOUNT_TYPE IN ('1','2')",
      "severity": "critical",
      "type": "join_logic"
    }
  ],
  "summary": {
    "total_checks": 5,
    "consistent_count": 4,
    "inconsistent_count": 1
  }
}
```

请务必返回有效的JSON格式，使用 "findings" 作为发现列表的字段名。"""

        mapping_text = self._format_relationship_mapping(mapping_data)

        user_prompt = f"""请审查以下SQL代码的**表间关联关系**是否符合IT-Mapping规范：

## IT-Mapping 表间关联定义：
{mapping_text}

## SQL 代码：
```sql
{sql_content}
```

请专注检查JOIN类型、ON条件、隐式转换、关联顺序、NULL处理这5个维度。
只返回JSON格式的结果。"""

        try:
            import time
            url = f'{self.host}/api/generate'
            payload = {
                'model': self.model,
                'prompt': user_prompt,
                'system': system_prompt,
                'stream': True,
                'options': {
                    'temperature': 0,
                    'top_p': 0.9,
                    'num_predict': 4096
                }
            }

            print(f'[RelationshipChecker] 开始分析表间关联关系...')
            print(f'[RelationshipChecker] 超时设置: {self.timeout}秒 (实时检测模式: {self.output_timeout}秒无输出即结束)')
            start_time = time.time()

            response = requests.post(url, json=payload, timeout=self.timeout, stream=True)
            response.raise_for_status()

            full_response = ''
            last_output_time = time.time()
            output_timeout = self.output_timeout

            for line in response.iter_lines():
                if line:
                    current_time = time.time()
                    last_output_time = current_time

                    try:
                        line_data = json.loads(line.decode('utf-8'))
                        chunk = line_data.get('response', '')
                        if chunk:
                            full_response += chunk
                    except json.JSONDecodeError:
                        continue

                else:
                    current_time = time.time()
                    if current_time - last_output_time > output_timeout:
                        print(f'[RelationshipChecker] 检测到{output_timeout}秒无输出，提前结束')
                        break

            elapsed_time = time.time() - start_time

            print(f'[RelationshipChecker] 分析完成, 耗时: {elapsed_time:.2f}秒, 响应长度: {len(full_response)} 字符')

            if full_response:
                return self._parse_response(full_response, mapping_data, group_context)
            else:
                raise Exception('AI未返回任何内容')

        except requests.exceptions.Timeout:
            raise Exception(f'表间关联检查超时 ({self.timeout}秒)')
        except requests.exceptions.ConnectionError:
            raise Exception('无法连接到Ollama服务')
        except Exception as e:
            raise Exception(f'表间关联检查失败: {str(e)}')

    def _format_relationship_mapping(self, mapping_data):
        """将映射数据中的关联关系格式化为文本"""
        lines = []

        lines.append("### 表信息：")
        for table in mapping_data.get('tables', []):
            lines.append(f"- 表名: {table.get('name', 'N/A')}, 别名: {table.get('alias', 'N/A')}")

        if mapping_data.get('relationships'):
            lines.append("\n### 表间关联关系定义：")
            for i, rel in enumerate(mapping_data['relationships'], 1):
                lines.append(f"{i}. 关联类型: {rel.get('type', 'N/A')}")
                lines.append(f"   - 目标表: {rel.get('table', 'N/A')}")
                lines.append(f"   - 别名: {rel.get('alias', 'N/A')}")
                if rel.get('condition'):
                    lines.append(f"   - 关联条件: {rel.get('condition')}")

        return '\n'.join(lines)

    def _parse_response(self, response_text, mapping_data):
        """解析AI响应"""
        from sql_correction_engine import OllamaClient
        client = OllamaClient({'host': self.host, 'model': self.model, 'timeout': self.timeout})
        raw_response = response_text[:500] if response_text else ''

        try:
            result = client._extract_json_multi_level(response_text)
            if result is None:
                raise Exception('JSON解析失败')

            normalized = client._normalize_ai_response_format(result, mapping_data)
            findings = normalized.get('findings', [])
            summary = normalized.get('summary', {})

            for finding in findings:
                finding['agent'] = 'relationship_checker'
                if 'typeLabel' not in finding:
                    finding['typeLabel'] = finding.get('type', '表间关联检查')

            return {
                'success': True,
                'agent_name': 'relationship_checker',
                'findings': findings,
                'summary': summary,
                'raw_response': raw_response
            }
        except Exception as e:
            print(f'[RelationshipChecker] 解析失败: {e}')
            return {
                'success': False,
                'error': str(e),
                'raw_response': raw_response,
                'findings': [],
                'summary': {'total_checks': 0, 'consistent_count': 0, 'inconsistent_count': 0}
            }


class CodeValueValidator:
    """码值转换校验器 - 使用正则表达式进行确定性比对"""
    
    def __init__(self):
        pass
    
    def validate_code_mapping(self, transformation_logic: str, sql_content: str, field_name: str = '') -> dict:
        """验证码值转换逻辑与SQL是否一致
        
        Args:
            transformation_logic: 字段加工逻辑（如 "M => 01 -主管分行\nB => 02-业务分行"）
            sql_content: SQL代码内容
            field_name: 字段名称（用于错误报告）
            
        Returns:
            dict: 包含验证结果和发现的问题
        """
        result = {
            'is_valid': True,
            'issues': [],
            'mapping_rules': [],
            'sql_rules': []
        }
        
        mapping_rules = self._extract_mapping_rules(transformation_logic)
        sql_rules = self._extract_sql_case_rules(sql_content, field_name)
        
        result['mapping_rules'] = mapping_rules
        result['sql_rules'] = sql_rules
        
        if not mapping_rules or not sql_rules:
            return result
        
        issues = self._compare_rules(mapping_rules, sql_rules, field_name)
        
        if issues:
            result['is_valid'] = False
            result['issues'] = issues
        
        return result
    
    def _extract_mapping_rules(self, transformation_logic: str) -> List[dict]:
        """从字段加工逻辑中提取码值映射规则
        
        支持格式：
        - M => 01 -主管分行
        - M=>01
        - M -> 01
        - M: 01
        """
        if not transformation_logic:
            return []
        
        rules = []
        
        patterns = [
            r"['\"]?([A-Za-z0-9]+)['\"]?\s*=>\s*['\"]?(\d+)['\"]?\s*[-–—]?\s*(.*?)(?=\n|$)",
            r"['\"]?([A-Za-z0-9]+)['\"]?\s*->\s*['\"]?(\d+)['\"]?\s*[-–—]?\s*(.*?)(?=\n|$)",
            r"['\"]?([A-Za-z0-9]+)['\"]?\s*:\s*['\"]?(\d+)['\"]?\s*[-–—]?\s*(.*?)(?=\n|$)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, transformation_logic, re.IGNORECASE)
            for match in matches:
                source_value = match[0].strip().upper()
                target_value = match[1].strip()
                description = match[2].strip() if len(match) > 2 else ''
                
                if source_value and target_value:
                    rules.append({
                        'source_value': source_value,
                        'target_value': target_value,
                        'description': description,
                        'original_source': match[0].strip()
                    })
        
        return rules
    
    def _extract_sql_case_rules(self, sql_content: str, field_name: str = '') -> List[dict]:
        """从SQL CASE WHEN语句中提取码值映射规则"""
        if not sql_content:
            return []
        
        rules = []
        
        case_pattern = r"CASE\s+(.*?)\s+END"
        case_matches = re.findall(case_pattern, sql_content, re.IGNORECASE | re.DOTALL)
        
        for case_block in case_matches:
            when_pattern = r"WHEN\s+[\w.]+\s*=\s*['\"]([^'\"]+)['\"]\s+THEN\s+['\"]?([^'\"\s]+)['\"]?"
            when_matches = re.findall(when_pattern, case_block, re.IGNORECASE)
            
            for match in when_matches:
                source_value = match[0].strip().upper()
                target_value = match[1].strip()
                
                if source_value and target_value:
                    rules.append({
                        'source_value': source_value,
                        'target_value': target_value,
                        'original_source': match[0].strip()
                    })
        
        return rules
    
    def _compare_rules(self, mapping_rules: List[dict], sql_rules: List[dict], field_name: str = '') -> List[dict]:
        """比对映射规则和SQL规则，找出不一致"""
        issues = []
        
        mapping_dict = {r['source_value']: r for r in mapping_rules}
        sql_dict = {r['source_value']: r for r in sql_rules}
        
        for source_val, mapping_rule in mapping_dict.items():
            if source_val not in sql_dict:
                sql_values = list(sql_dict.keys())
                issues.append({
                    'type': 'missing_in_sql',
                    'severity': 'high',
                    'field_name': field_name,
                    'source_value': mapping_rule['original_source'],
                    'expected_target': mapping_rule['target_value'],
                    'description': mapping_rule.get('description', ''),
                    'message': f"字段加工逻辑中定义的码值 '{mapping_rule['original_source']}' => '{mapping_rule['target_value']}' 在SQL中未找到对应映射",
                    'sql_available_values': sql_values
                })
            else:
                sql_rule = sql_dict[source_val]
                if mapping_rule['target_value'] != sql_rule['target_value']:
                    issues.append({
                        'type': 'target_mismatch',
                        'severity': 'high',
                        'field_name': field_name,
                        'source_value': mapping_rule['original_source'],
                        'expected_target': mapping_rule['target_value'],
                        'actual_target': sql_rule['target_value'],
                        'description': mapping_rule.get('description', ''),
                        'message': f"码值 '{mapping_rule['original_source']}' 的目标值不一致：映射定义为 '{mapping_rule['target_value']}'，SQL中为 '{sql_rule['target_value']}'"
                    })
        
        for source_val, sql_rule in sql_dict.items():
            if source_val not in mapping_dict:
                mapping_values = list(mapping_dict.keys())
                issues.append({
                    'type': 'extra_in_sql',
                    'severity': 'medium',
                    'field_name': field_name,
                    'source_value': sql_rule['original_source'],
                    'actual_target': sql_rule['target_value'],
                    'message': f"SQL中存在额外的码值映射 '{sql_rule['original_source']}' => '{sql_rule['target_value']}'，但在字段加工逻辑中未定义",
                    'mapping_available_values': mapping_values
                })
        
        return issues
    
    def check_field(self, field_info: dict, sql_content: str) -> dict:
        """检查单个字段的码值转换
        
        Args:
            field_info: 字段信息字典，包含 transformation_logic, target_field 等
            sql_content: SQL代码内容
            
        Returns:
            dict: 检查结果
        """
        transformation_logic = field_info.get('transformation_logic', '')
        target_field = field_info.get('target_field', '')
        extract_method = field_info.get('extract_method', '')
        
        if extract_method != '码值转换' or not transformation_logic:
            return {
                'needs_check': False,
                'is_valid': True,
                'issues': []
            }
        
        return self.validate_code_mapping(transformation_logic, sql_content, target_field)


class FieldMappingCheckerAgent:
    """字段信息检查Agent - 专注于SELECT字段映射、源字段、转换逻辑、数据类型的对比检查"""

    def __init__(self, config):
        self.host = config.get('host', 'http://localhost:11434')
        self.model = config.get('model', 'qwen2.5:7b')
        agent_timeouts = config.get('agent_timeouts', {})
        self.timeout = int(agent_timeouts.get('field_mapping_checker', config.get('timeout', 180)))
        self.output_timeout = int(config.get('output_timeout', 120))

    def analyze(self, mapping_data, sql_content, business_context='', group_context=None):
        """执行字段信息检查
        
        Args:
            mapping_data: 字段映射数据
            sql_content: SQL代码内容
            business_context: 业务上下文说明
            group_context: 分组上下文信息，包含:
                - group_id: 分组ID
                - group_name: 分组名称
                - data_source_tables: 数据源表列表
                - join_conditions: JOIN条件
                - filter_conditions: 筛选条件
        """

        system_prompt = """【强制要求 - 必须严格遵守】

【语言约束（最高优先级）】：
- 所有输出内容必须使用中文
- 【绝对禁止】在输出中使用英文说明文字

【输出格式强制规范】：
- 只返回JSON，不要包含任何其他文字
- 根对象只能包含 "findings" 和 "summary" 两个字段

【location字段格式标准】：
- 格式：必须使用"第X行 + 具体位置描述"
- 示例："第8行 SELECT字段列表"、"第25行 CASE WHEN子句"

【finding完整性规则】：
- original_sql字段：必填且长度≥20字符
- issue字段：必填，简洁描述问题（≤100字符）
- explanation字段：必填，详细说明原因和影响
- suggestion字段：必填，提供具体的修改建议

【severity分级标准】：
- critical：数据丢失风险/逻辑错误导致结果完全错误
- high：严重不一致（如字段映射错误、关键转换函数错误）
- medium：一般性问题（如源字段名称差异、数据类型不匹配）
- low：建议性优化（如代码风格、最佳实践提醒）

你是"字段映射检查专家"，专门负责检查SQL中的字段级别细节。

【你的唯一任务】对比SQL的字段定义与IT-Mapping的字段映射规则是否一致。
【否定清单】你不检查JOIN关系、不检查表间关联、不分析业务合理性、只关注字段级别的对比。

【检查原则】：
- 只问"是否一致"，不问"是否合理"
- 只对比"定义 vs 实现"，不分析"为什么"
- 输出简洁明确：一致/不一致 + 差异点

【分组上下文约束】：
- 当前检查的是特定分组的字段映射
- 只检查当前分组涉及的字段和表
- 注意分组的数据源表、JOIN条件、筛选条件对字段的影响
- 若字段属于不同分组，需在finding中标注分组信息

【默认值映射规则】
以下映射是正确的默认值，不应标记为不一致：
- DATA_DATE 字段：默认取值为 V_SHORT_DATE（跑批日期变量）
- UUID 字段：默认值为 uuid() 或 UUID()
- LOAD_TIME 字段：默认值为 CURRENT_TIMESTAMP()

【检查维度（共5项）】：

1. **字段映射完整性** — 对比SELECT字段 vs IT-Mapping目标字段
   检查：SELECT字段是否与Mapping目标字段一一对应；是否存在多余或缺失的字段；字段别名是否一致

2. **源字段一致性** — 对比SQL源字段 vs IT-Mapping源字段定义
   检查：SQL中引用的源表字段是否与Mapping定义的源字段一致；字段名称是否匹配

3. **转换逻辑一致性** — 对比SQL转换函数 vs IT-Mapping转换逻辑
   检查：SUBSTR/||/CAST等函数的参数是否与Mapping定义一致；截取位置、长度、拼接顺序是否匹配

4. **码值转换一致性** — 【重点检查】对比SQL CASE WHEN vs IT-Mapping码值映射规则
   检查：当取数方式为"码值转换"时，必须逐字符比对：
   - 提取字段加工逻辑中的码值映射（如 "M => 01" 表示源值M映射为目标值01）
   - 提取SQL中CASE WHEN语句的码值映射（如 WHEN field = 'M' THEN '01'）
   - 逐个比对源值和目标值是否完全一致
   - 注意：字母O和数字0、字母I和数字1、字母M和字母N等容易混淆的字符必须仔细区分
   - 示例错误：Mapping定义 "M => 01"，但SQL中写 "WHEN field = 'O' THEN '01'"（M和O不同！）

5. **数据类型一致性** — 对比SQL数据类型 vs IT-Mapping数据类型
   检查：CAST/类型声明是否与Mapping定义的数据类型一致；类型转换目标类型是否匹配

【正确示例】：
```json
{
  "findings": [
    {
      "id": 1,
      "status": "inconsistent",
      "agent": "field_mapping_checker",
      "group_id": "group_001",
      "group_name": "基础信息分组",
      "location": "第12行 SELECT字段列表",
      "issue": "SUBSTR截取位置与Mapping定义不一致",
      "explanation": "SQL中使用SUBSTR(T.FIELD, 1, 10)，Mapping定义为从第2位开始截取8位",
      "original_sql": "SELECT SUBSTR(T.ACCOUNT_NO, 1, 10) AS account_no",
      "mapping_ref": {"target": "ACCOUNT_NO", "logic": "截取第2-9位共8位"},
      "suggestion": "修改为: SUBSTR(T.ACCOUNT_NO, 2, 8) AS account_no",
      "severity": "high",
      "type": "transformation_logic"
    }
  ],
  "summary": {
    "group_id": "group_001",
    "group_name": "基础信息分组",
    "total_checks": 4,
    "consistent_count": 3,
    "inconsistent_count": 1
  }
}
```

请务必返回有效的JSON格式，使用 "findings" 作为发现列表的字段名。"""

        mapping_text = self._format_field_mapping(mapping_data, group_context)
        group_info_text = self._format_group_context(group_context)

        user_prompt = f"""请审查以下SQL代码的**字段级别细节**是否符合IT-Mapping规范：

{group_info_text}

## IT-Mapping 字段映射规则：
{mapping_text}

## SQL 代码：
```sql
{sql_content}
```

## 补充业务说明：
{business_context or '无'}

请专注检查以下5个对比维度：
1. 字段映射完整性 — 对比SELECT字段 vs IT-Mapping目标字段
2. 源字段一致性 — 对比SQL源字段 vs IT-Mapping源字段定义
3. 转换逻辑一致性 — 对比SQL转换函数 vs IT-Mapping转换逻辑
4. 码值转换一致性 — 【重点】逐字符比对CASE WHEN中的码值与Mapping定义是否一致
5. 数据类型一致性 — 对比SQL数据类型 vs IT-Mapping数据类型

【特别提醒】对于"码值转换"类型的字段，必须逐字符比对源值和目标值，注意区分相似字符（如M与O、0与O、1与I等）。

注意：当前检查的是特定分组的字段映射，请在finding中标注group_id和group_name。
只返回JSON格式的结果。"""

        try:
            import time
            url = f'{self.host}/api/generate'
            payload = {
                'model': self.model,
                'prompt': user_prompt,
                'system': system_prompt,
                'stream': True,
                'options': {
                    'temperature': 0,
                    'top_p': 0.9,
                    'num_predict': 4096
                }
            }

            print(f'[FieldMappingChecker] 开始分析字段映射信息...')
            if group_context:
                print(f'[FieldMappingChecker] 分组: {group_context.get("group_name", "N/A")} (ID: {group_context.get("group_id", "N/A")})')
            print(f'[FieldMappingChecker] 超时设置: {self.timeout}秒 (实时检测模式: {self.output_timeout}秒无输出即结束)')
            start_time = time.time()

            response = requests.post(url, json=payload, timeout=self.timeout, stream=True)
            response.raise_for_status()

            full_response = ''
            last_output_time = time.time()
            output_timeout = self.output_timeout

            for line in response.iter_lines():
                if line:
                    current_time = time.time()
                    last_output_time = current_time

                    try:
                        line_data = json.loads(line.decode('utf-8'))
                        chunk = line_data.get('response', '')
                        if chunk:
                            full_response += chunk
                    except json.JSONDecodeError:
                        continue

                else:
                    current_time = time.time()
                    if current_time - last_output_time > output_timeout:
                        print(f'[FieldMappingChecker] 检测到{output_timeout}秒无输出，提前结束')
                        break

            elapsed_time = time.time() - start_time

            print(f'[FieldMappingChecker] 分析完成, 耗时: {elapsed_time:.2f}秒, 响应长度: {len(full_response)} 字符')

            if full_response:
                return self._parse_response(full_response, mapping_data)
            else:
                raise Exception('AI未返回任何内容')

        except requests.exceptions.Timeout:
            raise Exception(f'字段映射检查超时 ({self.timeout}秒)')
        except requests.exceptions.ConnectionError:
            raise Exception('无法连接到Ollama服务')
        except Exception as e:
            raise Exception(f'字段映射检查失败: {str(e)}')

    def _format_group_context(self, group_context):
        """将分组上下文格式化为文本"""
        if not group_context:
            return "## 当前检查范围：全局（无分组限制）"
        
        lines = []
        lines.append("## 当前检查范围：分组上下文")
        lines.append(f"- **分组ID**: {group_context.get('group_id', 'N/A')}")
        lines.append(f"- **分组名称**: {group_context.get('group_name', 'N/A')}")
        
        data_source_tables = group_context.get('data_source_tables', [])
        if data_source_tables:
            lines.append(f"- **数据源表**: {', '.join(data_source_tables)}")
        
        join_conditions = group_context.get('join_conditions', '')
        if join_conditions:
            lines.append(f"- **JOIN条件**: {join_conditions}")
        
        filter_conditions = group_context.get('filter_conditions', '')
        if filter_conditions:
            lines.append(f"- **筛选条件**: {filter_conditions}")
        
        return '\n'.join(lines)

    def _format_field_mapping(self, mapping_data, group_context=None):
        """将字段映射数据格式化为文本
        
        Args:
            mapping_data: 字段映射数据
            group_context: 分组上下文信息（可选）
        """
        lines = []

        lines.append("### 目标表信息：")
        for table in mapping_data.get('tables', []):
            lines.append(f"- 表名: {table.get('name', 'N/A')}, 别名: {table.get('alias', 'N/A')}")

        if group_context:
            lines.append(f"\n### 当前分组: {group_context.get('group_name', 'N/A')} (ID: {group_context.get('group_id', 'N/A')})")

        lines.append("\n### 字段映射规则：")
        for i, field in enumerate(mapping_data.get('field_mappings', []), 1):
            lines.append(f"{i}. **{field.get('target_field', 'N/A')}**")
            lines.append(f"   - 源表: {field.get('source_table_alias', 'N/A')}")
            lines.append(f"   - 源字段: {field.get('source_field', 'N/A')}")
            if field.get('transformation_logic'):
                lines.append(f"   - 转换逻辑: {field['transformation_logic']}")
            if field.get('data_type'):
                lines.append(f"   - 数据类型: {field['data_type']}")
            lines.append("")

        return '\n'.join(lines)

    def _parse_response(self, response_text, mapping_data, group_context=None):
        """解析AI响应
        
        Args:
            response_text: AI返回的响应文本
            mapping_data: 字段映射数据
            group_context: 分组上下文信息（可选）
        """
        from sql_correction_engine import OllamaClient
        client = OllamaClient({'host': self.host, 'model': self.model, 'timeout': self.timeout})
        raw_response = response_text[:500] if response_text else ''

        try:
            result = client._extract_json_multi_level(response_text)
            if result is None:
                raise Exception('JSON解析失败')

            normalized = client._normalize_ai_response_format(result, mapping_data)
            findings = normalized.get('findings', [])
            summary = normalized.get('summary', {})

            group_id = group_context.get('group_id', '') if group_context else ''
            group_name = group_context.get('group_name', '') if group_context else ''

            for finding in findings:
                finding['agent'] = 'field_mapping_checker'
                if 'typeLabel' not in finding:
                    finding['typeLabel'] = finding.get('type', '字段映射检查')
                if group_id and 'group_id' not in finding:
                    finding['group_id'] = group_id
                if group_name and 'group_name' not in finding:
                    finding['group_name'] = group_name

            if group_id:
                summary['group_id'] = group_id
            if group_name:
                summary['group_name'] = group_name

            return {
                'success': True,
                'agent_name': 'field_mapping_checker',
                'findings': findings,
                'summary': summary,
                'raw_response': raw_response,
                'group_context': group_context
            }
        except Exception as e:
            print(f'[FieldMappingChecker] 解析失败: {e}')
            error_summary = {'total_checks': 0, 'consistent_count': 0, 'inconsistent_count': 0}
            if group_context:
                error_summary['group_id'] = group_context.get('group_id', '')
                error_summary['group_name'] = group_context.get('group_name', '')
            return {
                'success': False,
                'error': str(e),
                'raw_response': raw_response,
                'findings': [],
                'summary': error_summary,
                'group_context': group_context
            }


class FieldCheckAgent:
    """单字段一致性检查Agent - 专注于单个字段与IT-Mapping的一致性检查"""

    def __init__(self, config, agent_id=1):
        self.host = config.get('host', 'http://localhost:11434')
        self.model = config.get('model', 'qwen2.5:7b')
        agent_timeouts = config.get('agent_timeouts', {})
        self.timeout = int(agent_timeouts.get('field_check', config.get('timeout', 120)))
        self.output_timeout = int(config.get('output_timeout', 120))
        self.agent_id = agent_id

    def _build_mapping_ref(self, field_info):
        """构建mapping_ref字典，包含target/logic/source字段"""
        source_table = field_info.get('source_table_alias', '')
        source_field = field_info.get('source_field', '')
        source = ''
        if source_table and source_table != 'nan' and source_field and source_field != 'nan':
            source = f"{source_table}.{source_field}"
        elif source_field and source_field != 'nan':
            source = source_field
        
        return {
            'target': field_info.get('target_field', ''),
            'logic': field_info.get('transformation_logic', ''),
            'source': source
        }

    def _format_data_source_info(self, data_source_info):
        """格式化数据源表信息为文本
        
        Args:
            data_source_info (dict): 数据源表信息，包含tables/joins/filters
            
        Returns:
            str: 格式化后的文本
        """
        if not data_source_info:
            return '无数据源表信息'
        
        lines = []
        
        tables = data_source_info.get('tables', [])
        if tables:
            lines.append('### 数据源表:')
            for t in tables:
                alias = t.get('alias', '')
                name_cn = t.get('name_cn', '')
                name_en = t.get('name_en', '')
                lines.append(f'- {alias}: {name_cn} ({name_en})')
        
        joins = data_source_info.get('joins', [])
        if joins:
            lines.append('### 表间关联:')
            for j in joins:
                left = j.get('left_table', '')
                left_field = j.get('left_field', '')
                join_type = j.get('join_type', '')
                right = j.get('right_table', '')
                right_field = j.get('right_field', '')
                lines.append(f'- {left}.{left_field} {join_type} {right}.{right_field}')
        
        filters = data_source_info.get('filters', [])
        if filters:
            lines.append('### 筛选条件:')
            for f in filters:
                table = f.get('table', '')
                field = f.get('field', '')
                condition = f.get('condition', '')
                value = f.get('value', '')
                lines.append(f'- {table}.{field} {condition} {value}')
        
        return '\n'.join(lines) if lines else '无数据源表信息'

    def _format_field_info(self, field_info):
        """格式化字段信息为文本
        
        Args:
            field_info (dict): 字段映射信息
            
        Returns:
            str: 格式化后的文本
        """
        lines = []
        lines.append(f"- 目标字段: {field_info.get('target_field', 'N/A')}")
        lines.append(f"- 目标字段中文名: {field_info.get('target_field_cn', 'N/A')}")
        lines.append(f"- 源表: {field_info.get('source_table_alias', 'N/A')}")
        lines.append(f"- 源字段: {field_info.get('source_field', 'N/A')}")
        lines.append(f"- 转换逻辑: {field_info.get('transformation_logic', 'N/A')}")
        lines.append(f"- 数据类型: {field_info.get('data_type', 'N/A')}")
        lines.append(f"- 取数方式: {field_info.get('extract_method', 'N/A')}")
        lines.append(f"- 默认值: {field_info.get('default_value', 'N/A')}")
        return '\n'.join(lines)

    def analyze(self, field_info, sql_content, md_content='', sql_snippet=None, sql_structure=None, data_source_info=None):
        """执行单字段一致性检查

        Args:
            field_info (dict): 字段映射信息字典，包含:
                - target_field: 目标字段名
                - source_field: 源字段名
                - source_table_alias: 源表别名
                - transformation_logic: 转换逻辑
                - data_type: 数据类型
                - extract_method: 取数方式
                - sheet: 来源Sheet
            sql_content (str): 完整SQL代码
            md_content (str): MD文档内容（可选，用于提供上下文）
            sql_snippet (str): 预提取的SQL片段（可选，若提供则优先使用）
            sql_structure (dict): SQL结构化解析结果（可选，包含字段-取值映射）
            data_source_info (dict): 数据源表信息（可选，包含tables/joins/filters）

        Returns:
            dict: 包含 success, status, issue, explanation, suggestion, mapping_ref 的字典
        """
        system_prompt = """【输出格式】
只返回JSON: {"status": "consistent/inconsistent/warning", "issue": "问题描述(如有)", "explanation": "详细说明", "suggestion": "修改建议(如有)", "confidence": 0.0-1.0}

【检查维度】
对比IT-Mapping定义与SQL实现是否一致，检查以下4个维度：
1. 字段名映射：对比SQL字段名 vs IT-Mapping目标字段
2. 源字段：对比SQL源字段 vs IT-Mapping源字段定义
3. 转换逻辑：对比SQL转换函数 vs IT-Mapping转换逻辑
4. 数据类型：对比SQL数据类型 vs IT-Mapping数据类型

【检查原则】
- 只问"是否一致"，不问"是否合理"
- 只对比"定义 vs 实现"，不分析"为什么"

【默认值映射规则】
以下映射是正确的默认值，不应标记为不一致：
- DATA_DATE 字段：默认取值为 V_SHORT_DATE（跑批日期变量）
- UUID 字段：默认值为 uuid() 或 UUID()
- LOAD_TIME 字段：默认值为 CURRENT_TIMESTAMP()

【status取值】
- consistent: 完全一致
- inconsistent: 存在差异
- warning: 潜在问题

禁止输出任何额外文字。"""

        field_text = self._format_field_info(field_info)
        data_source_text = self._format_data_source_info(data_source_info)
        
        if sql_snippet is None:
            sql_snippet, position_info = self._locate_field_in_sql(field_info, sql_content)
        else:
            # 如果提供了sql_snippet，尝试定位位置信息
            locator = FieldLocator(sql_content)
            target_field = field_info.get('target_field', '')
            source_field = field_info.get('source_field', '')
            field_position = None
            
            if target_field and target_field != 'nan':
                field_position = locator.get_position(target_field, "INSERT")
            
            if not field_position and source_field and source_field != 'nan':
                field_position = locator.get_position(source_field)
            
            position_info = {}
            if field_position:
                position_info = {
                    'line': field_position.line,
                    'column': field_position.column,
                    'start_index': field_position.start_index,
                    'end_index': field_position.end_index
                }

        if sql_structure and sql_structure.get('field_mapping'):
            field_name = field_info.get('target_field', '')
            select_expr = sql_structure.get('field_mapping', {}).get(field_name, '未找到')
            from_clause = sql_structure.get('from_clause', '')
            where_clause = sql_structure.get('where_clause', '')
            
            if select_expr == '未找到' or '未在SQL中找到' in str(select_expr):
                return {
                    'success': True,
                    'status': 'warning',
                    'issue': '字段在SQL中未找到对应取值',
                    'explanation': f'字段 {field_name} 在INSERT字段列表中没有对应的SELECT取值表达式，可能是新增字段或Mapping定义有误',
                    'suggestion': '请确认该字段是否需要在SQL中实现，或检查Mapping定义是否正确',
                    'mapping_ref': {'target': field_name, 'logic': field_info.get('transformation_logic', '')},
                    'field_info': field_info,
                    'position_info': position_info,
                    'confidence': 0.8,
                    'agent_id': self.agent_id
                }
            
            user_prompt = f"""检查字段 {field_name}:

## Mapping定义:
{field_text}

## 数据源表信息:
{data_source_text}

## SQL取值表达式:
{select_expr}

## 关联表:
{from_clause[:300]}

## 筛选条件:
{where_clause[:300]}

只输出JSON: {{"status": "consistent/inconsistent", "issue": "问题", "suggestion": "建议"}}
"""
        else:
            user_prompt = f"""请审查以下SQL代码中**单个字段**的实现是否符合IT-Mapping定义：

## IT-Mapping 字段定义：
{field_text}

## 数据源表信息：
{data_source_text}

## 相关SQL片段：
{sql_snippet}

## MD文档上下文（如有）：
{md_content[:2000] if md_content else '无'}

请专注检查以下4个维度的对比：
1. 字段名映射：对比SQL字段名 vs IT-Mapping目标字段
2. 源字段：对比SQL源字段 vs IT-Mapping源字段定义
3. 转换逻辑：对比SQL转换函数 vs IT-Mapping转换逻辑
4. 数据类型：对比SQL数据类型 vs IT-Mapping数据类型

只返回JSON格式的结果。"""

        try:
            import time
            url = f'{self.host}/api/generate'
            payload = {
                'model': self.model,
                'prompt': user_prompt,
                'system': system_prompt,
                'stream': True,
                'options': {
                    'temperature': 0,
                    'top_p': 0.9,
                    'num_predict': 2048
                }
            }

            print(f'[FieldCheckAgent-{self.agent_id}] 开始分析字段: {field_info.get("target_field", "未知")}')
            print(f'[FieldCheckAgent-{self.agent_id}] 超时设置: {self.timeout}秒')
            start_time = time.time()

            response = requests.post(url, json=payload, timeout=self.timeout, stream=True)
            response.raise_for_status()

            full_response = ''
            last_output_time = time.time()
            output_timeout = self.output_timeout

            for line in response.iter_lines():
                if line:
                    current_time = time.time()
                    last_output_time = current_time

                    try:
                        line_data = json.loads(line.decode('utf-8'))
                        chunk = line_data.get('response', '')
                        if chunk:
                            full_response += chunk
                    except json.JSONDecodeError:
                        continue

                else:
                    current_time = time.time()
                    if current_time - last_output_time > output_timeout:
                        print(f'[FieldCheckAgent-{self.agent_id}] 检测到{output_timeout}秒无输出，提前结束')
                        break

            elapsed_time = time.time() - start_time

            print(f'[FieldCheckAgent-{self.agent_id}] 分析完成, 耗时: {elapsed_time:.2f}秒, 响应长度: {len(full_response)} 字符')

            if full_response:
                return self._parse_response(full_response, field_info, position_info)
            else:
                return {
                    'success': False,
                    'status': 'error',
                    'issue': 'AI未返回任何内容',
                    'explanation': 'AI服务返回空响应',
                    'suggestion': '请检查AI服务状态或重试',
                    'mapping_ref': self._build_mapping_ref(field_info),
                    'field_info': field_info,
                    'position_info': position_info,
                    'confidence': 0.0
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'status': 'timeout',
                'issue': f'字段检查超时 ({self.timeout}秒)',
                'explanation': 'AI服务响应超时，可能是模型负载过高或网络问题',
                'suggestion': '建议增加超时时间或检查AI服务状态',
                'mapping_ref': self._build_mapping_ref(field_info),
                'field_info': field_info,
                'position_info': position_info,
                'confidence': 0.0
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'status': 'error',
                'issue': '无法连接到Ollama服务',
                'explanation': '请确认Ollama服务是否正在运行',
                'suggestion': '启动Ollama服务: ollama serve',
                'mapping_ref': self._build_mapping_ref(field_info),
                'field_info': field_info,
                'position_info': position_info,
                'confidence': 0.0
            }
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'issue': f'字段检查失败: {str(e)}',
                'explanation': f'检查过程中发生异常: {str(e)}',
                'suggestion': '请检查输入参数或联系技术支持',
                'mapping_ref': self._build_mapping_ref(field_info),
                'field_info': field_info,
                'position_info': position_info,
                'confidence': 0.0
            }

    def _format_field_info(self, field_info):
        """格式化字段信息为文本

        Args:
            field_info (dict): 字段映射信息字典

        Returns:
            str: 格式化后的字段信息文本
        """
        lines = []

        target_field = field_info.get('target_field', 'N/A')
        lines.append(f"### 目标字段: **{target_field}**")
        lines.append("")

        source_table = field_info.get('source_table_alias', '')
        if source_table and source_table != 'nan':
            lines.append(f"- 源表别名: {source_table}")

        source_field = field_info.get('source_field', '')
        if source_field and source_field != 'nan':
            lines.append(f"- 源字段: {source_field}")

        transformation_logic = field_info.get('transformation_logic', '')
        if transformation_logic and transformation_logic != 'nan':
            lines.append(f"- 转换逻辑: {transformation_logic}")

        data_type = field_info.get('data_type', '')
        if data_type and data_type != 'nan':
            lines.append(f"- 数据类型: {data_type}")

        extract_method = field_info.get('extract_method', '')
        if extract_method and extract_method != 'nan':
            lines.append(f"- 取数方式: {extract_method}")

        sheet = field_info.get('sheet', '')
        if sheet and sheet != 'nan':
            lines.append(f"- 来源Sheet: {sheet}")

        return '\n'.join(lines)

    def _locate_field_in_sql(self, field_info, sql_content):
        """在SQL中定位并提取字段相关代码片段

        Args:
            field_info (dict): 字段映射信息字典
            sql_content (str): 完整SQL代码

        Returns:
            tuple: (str, dict) - (相关SQL片段, 位置信息字典)
        """
        if not sql_content:
            return "无法定位：SQL内容为空", {}

        target_field = field_info.get('target_field', '')
        source_field = field_info.get('source_field', '')

        # 使用FieldLocator进行精确定位
        locator = FieldLocator(sql_content)
        field_position = None

        # 尝试定位目标字段
        if target_field and target_field != 'nan':
            field_position = locator.get_position(target_field, "INSERT")
        
        # 如果目标字段未找到，尝试定位源字段
        if not field_position and source_field and source_field != 'nan':
            field_position = locator.get_position(source_field)

        lines = sql_content.split('\n')
        found_line_nums = set()

        if field_position:
            # 使用精确位置信息
            line_num = field_position.line
            found_line_nums.add(line_num - 1)  # 转换为0-based索引
            for j in range(max(0, line_num - 3), min(len(lines), line_num + 2)):
                found_line_nums.add(j)
        else:
            # 回退到传统搜索方法
            search_terms = [target_field, source_field]
            search_terms = [t for t in search_terms if t and t != 'nan']

            for i, line in enumerate(lines):
                line_upper = line.upper()
                for term in search_terms:
                    if term and term.upper() in line_upper:
                        found_line_nums.add(i)
                        for j in range(max(0, i - 2), min(len(lines), i + 3)):
                            found_line_nums.add(j)
                        break

        if not found_line_nums:
            return f"未在SQL中找到字段 '{target_field}' 的相关代码", {}

        sorted_nums = sorted(found_line_nums)
        start = max(0, sorted_nums[0] - 1)
        end = min(len(lines), sorted_nums[-1] + 2)
        
        relevant_lines = lines[start:end]
        snippet = '\n'.join(relevant_lines)
        
        # 构建位置信息字典
        position_info = {}
        if field_position:
            position_info = {
                'line': field_position.line,
                'column': field_position.column,
                'start_index': field_position.start_index,
                'end_index': field_position.end_index
            }
            return f"相关SQL片段（第{field_position.line}行，第{field_position.column}列）：\n{snippet}", position_info
        else:
            position_info = {
                'lines': f"{start+1}-{end}"
            }
            return f"相关SQL片段（第{start+1}-{end}行）：\n{snippet}", position_info

    def _parse_response(self, response_text, field_info, position_info=None):
        """解析AI响应

        Args:
            response_text (str): AI返回的原始文本
            field_info (dict): 字段映射信息字典
            position_info (dict): 字段位置信息字典（可选）

        Returns:
            dict: 解析后的结果字典
        """
        raw_response = response_text[:500] if response_text else ''

        try:
            client = OllamaClient({'host': self.host, 'model': self.model, 'timeout': self.timeout})
            result = client._extract_json_multi_level(response_text)
            if result is None:
                raise Exception('JSON解析失败')

            if not isinstance(result, dict):
                raise Exception('JSON解析结果不是字典类型')

            status = result.get('status', 'unknown')
            if status not in ['consistent', 'inconsistent', 'warning', 'error']:
                status = 'inconsistent'

            confidence = result.get('confidence', 0.5)
            try:
                confidence = float(confidence)
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5

            source_table = field_info.get('source_table_alias', '')
            source_field = field_info.get('source_field', '')
            source = ''
            if source_table and source_table != 'nan' and source_field and source_field != 'nan':
                source = f"{source_table}.{source_field}"
            elif source_field and source_field != 'nan':
                source = source_field
            
            # 如果没有提供位置信息，尝试获取字段位置信息
            if position_info is None:
                position_info = {}
                if 'sql_content' in field_info:
                    locator = FieldLocator(field_info['sql_content'])
                    target_field = field_info.get('target_field', '')
                    if target_field and target_field != 'nan':
                        field_position = locator.get_position(target_field, "INSERT")
                    
                    if not field_position and source and source != 'nan':
                        field_position = locator.get_position(source)
                    
                    if field_position:
                        position_info = {
                            'line': field_position.line,
                            'column': field_position.column,
                            'start_index': field_position.start_index,
                            'end_index': field_position.end_index
                        }
            
            return {
                'success': True,
                'status': status,
                'issue': result.get('issue', ''),
                'explanation': result.get('explanation', ''),
                'suggestion': result.get('suggestion', ''),
                'mapping_ref': {
                    'target': field_info.get('target_field', ''),
                    'logic': field_info.get('transformation_logic', ''),
                    'source': source,
                    'sheet': field_info.get('sheet', '')
                },
                'field_info': field_info,
                'position_info': position_info,
                'confidence': confidence,
                'raw_response': raw_response
            }

        except json.JSONDecodeError as e:
            print(f'[FieldCheckAgent-{self.agent_id}] JSON解析失败: {e}')
            return {
                'success': False,
                'status': 'parse_error',
                'issue': 'AI响应解析失败',
                'explanation': f'无法解析AI返回的JSON格式: {str(e)}',
                'suggestion': '请检查AI服务输出格式',
                'mapping_ref': self._build_mapping_ref(field_info),
                'field_info': field_info,
                'confidence': 0.0,
                'raw_response': raw_response
            }
        except Exception as e:
            print(f'[FieldCheckAgent-{self.agent_id}] 解析失败: {e}')
            return {
                'success': False,
                'status': 'parse_error',
                'issue': 'AI响应解析失败',
                'explanation': f'解析过程发生异常: {str(e)}',
                'suggestion': '请重试或检查输入参数',
                'mapping_ref': self._build_mapping_ref(field_info),
                'field_info': field_info,
                'confidence': 0.0,
                'raw_response': raw_response
            }


class TripleAgentVoter:
    """三Agent投票器 - 通过多Agent并行检查并投票决定字段一致性"""

    def __init__(self, config):
        self.config = config
        self.agent_count = config.get('agent_count', 3)
        self.consensus_threshold = config.get('consensus_threshold', 2)
        agent_timeouts = config.get('agent_timeouts', {})
        self.timeout_per_agent = int(agent_timeouts.get('field_check', config.get('timeout', 120)))
        self.max_retries = config.get('max_retries', 3)

    def vote_on_field(self, field_info, sql_content, md_content='', fast_mode=False, field_sql_mapping=None, sql_structure=None, data_source_info=None):
        """对单个字段进行多Agent投票检查，支持自动重试

        Args:
            field_info (dict): 字段映射信息字典
            sql_content (str): SQL代码
            md_content (str): MD文档内容
            fast_mode (bool): 快速模式，仅使用1个Agent
            field_sql_mapping (dict): 字段名到SQL片段的映射表
            sql_structure (dict): SQL结构化解析结果
            data_source_info (dict): 数据源表信息（按分组ID组织）

        Returns:
            dict: 投票结果字典，包含:
                - field: 字段名
                - final_status: 最终状态 (consistent/inconsistent/needs_review/all_failed)
                - vote_details: 投票详情
                - agent_results: 各Agent的检查结果
                - confidence: 置信度
                - merged_findings: 合并后的findings列表
                - retry_count: 重试次数
        """
        field_name = field_info.get('target_field', '')
        sql_snippet = None
        if field_sql_mapping and field_name:
            sql_snippet = field_sql_mapping.get(field_name)
        
        group_id = field_info.get('group_id', '')
        group_data_source = data_source_info.get(group_id, {}) if data_source_info else {}
        
        code_value_result = self._check_code_value_mapping(field_info, sql_content, sql_snippet)
        if code_value_result:
            return code_value_result
        
        empty_field_result = self._check_empty_field_mapping(field_info, sql_content, sql_snippet)
        if empty_field_result:
            return empty_field_result
        
        if fast_mode:
            retry_count = 0
            while retry_count <= self.max_retries:
                agent = FieldCheckAgent(self.config, agent_id=1)
                result = agent.analyze(field_info, sql_content, md_content, sql_snippet=sql_snippet, sql_structure=sql_structure, data_source_info=group_data_source)
                result['agent_id'] = 1
                results = [result]
                
                if self._should_retry_fast_mode(result, retry_count):
                    retry_count += 1
                    print(f'[TripleAgentVoter] Fast模式检测到失败(超时/解析错误)，第{retry_count}次重试字段: {field_name}')
                    continue
                
                status = result.get('status', 'error') if result.get('success') else 'error'
                final_status = 'consistent' if status == 'consistent' else ('inconsistent' if status == 'inconsistent' else 'needs_review')
                confidence = result.get('confidence', 0.5)
                
                return {
                    'field': field_info.get('target_field'),
                    'final_status': final_status,
                    'vote_details': {
                        'consistent': 1 if final_status == 'consistent' else 0,
                        'inconsistent': 1 if final_status == 'inconsistent' else 0,
                        'warning': 1 if final_status == 'needs_review' else 0,
                        'error': 0
                    },
                    'agent_results': results,
                    'confidence': confidence,
                    'merged_findings': [{
                        'agent_id': 1,
                        'status': status,
                        'issue': result.get('issue', ''),
                        'explanation': result.get('explanation', ''),
                        'suggestion': result.get('suggestion', ''),
                        'confidence': confidence,
                        'mapping_ref': result.get('mapping_ref', {}),
                        'field_info': field_info
                    }],
                    'mode': 'fast',
                    'retry_count': retry_count
                }
            
            status = result.get('status', 'error') if result.get('success') else 'error'
            final_status = 'consistent' if status == 'consistent' else ('inconsistent' if status == 'inconsistent' else 'needs_review')
            confidence = result.get('confidence', 0.5)
            
            return {
                'field': field_info.get('target_field'),
                'final_status': final_status,
                'vote_details': {
                    'consistent': 1 if final_status == 'consistent' else 0,
                    'inconsistent': 1 if final_status == 'inconsistent' else 0,
                    'warning': 1 if final_status == 'needs_review' else 0,
                    'error': 0
                },
                'agent_results': results,
                'confidence': confidence,
                'merged_findings': [{
                    'agent_id': 1,
                    'status': status,
                    'issue': result.get('issue', ''),
                    'explanation': result.get('explanation', ''),
                    'suggestion': result.get('suggestion', ''),
                    'confidence': confidence,
                    'mapping_ref': result.get('mapping_ref', {}),
                    'field_info': field_info
                }],
                'mode': 'fast',
                'retry_count': retry_count
            }

        retry_count = 0
        last_results = None
        
        while retry_count <= self.max_retries:
            results = self._execute_vote_once(
                field_info, sql_content, md_content, sql_snippet, sql_structure, group_data_source
            )
            last_results = results
            
            if not self._should_retry(results, retry_count):
                break
            
            retry_count += 1
            failed_count = sum(1 for r in results if not r.get('success') or r.get('status') in ['timeout', 'parse_error', 'error'])
            print(f'[TripleAgentVoter] 检测到{failed_count}个Agent失败(超时/解析错误)，第{retry_count}次重试字段: {field_name}')

        status_counts = Counter()
        for r in results:
            if r.get('success'):
                status_counts[r.get('status', 'error')] += 1
            else:
                status_counts['error'] += 1

        successful_results = [r for r in results if r.get('success')]
        if not successful_results:
            final_status = 'all_failed'
        elif status_counts.get('consistent', 0) >= self.consensus_threshold:
            final_status = 'consistent'
        elif status_counts.get('inconsistent', 0) >= self.consensus_threshold:
            final_status = 'inconsistent'
        else:
            final_status = 'needs_review'

        confidence = self._calculate_confidence(status_counts)
        merged_findings = self._merge_findings(results, final_status)

        return {
            'field': field_info.get('target_field'),
            'final_status': final_status,
            'vote_details': {
                'consistent': status_counts.get('consistent', 0),
                'inconsistent': status_counts.get('inconsistent', 0),
                'warning': status_counts.get('warning', 0),
                'error': status_counts.get('error', 0)
            },
            'agent_results': results,
            'confidence': confidence,
            'merged_findings': merged_findings,
            'retry_count': retry_count
        }

    def _check_code_value_mapping(self, field_info, sql_content, sql_snippet=None):
        """检查码值转换是否一致
        
        Args:
            field_info (dict): 字段映射信息字典
            sql_content (str): SQL代码
            sql_snippet (str): SQL片段（可选）
            
        Returns:
            dict: 如果检测到问题，返回不一致结果；否则返回None
        """
        extract_method = field_info.get('extract_method', '')
        if extract_method != '码值转换':
            return None
        
        transformation_logic = field_info.get('transformation_logic', '')
        if not transformation_logic:
            return None
        
        target_field = field_info.get('target_field', '')
        
        sql_to_check = sql_snippet if sql_snippet else sql_content
        
        validator = CodeValueValidator()
        validation_result = validator.validate_code_mapping(transformation_logic, sql_to_check, target_field)
        
        if validation_result.get('is_valid', True):
            return None
        
        issues = validation_result.get('issues', [])
        if not issues:
            return None
        
        issue_messages = []
        for issue in issues:
            issue_messages.append(issue.get('message', '码值转换不一致'))
        
        primary_issue = issues[0]
        
        return {
            'field': target_field,
            'final_status': 'inconsistent',
            'vote_details': {
                'consistent': 0,
                'inconsistent': 1,
                'warning': 0,
                'error': 0
            },
            'agent_results': [{
                'success': True,
                'agent_id': 'code_value_validator',
                'status': 'inconsistent',
                'issue': primary_issue.get('message', '码值转换不一致'),
                'explanation': f"字段加工逻辑定义: {transformation_logic}",
                'suggestion': f"请检查码值 '{primary_issue.get('source_value', '')}' 的映射是否正确",
                'confidence': 1.0,
                'mapping_ref': {
                    'target': target_field,
                    'logic': transformation_logic
                },
                'field_info': field_info
            }],
            'confidence': 1.0,
            'merged_findings': [{
                'agent_id': 'code_value_validator',
                'status': 'inconsistent',
                'issue': primary_issue.get('message', '码值转换不一致'),
                'explanation': f"字段加工逻辑定义: {transformation_logic}\n所有问题: {'; '.join(issue_messages)}",
                'suggestion': f"请检查码值映射是否正确",
                'confidence': 1.0,
                'mapping_ref': {
                    'target': target_field,
                    'logic': transformation_logic
                },
                'field_info': field_info
            }],
            'mode': 'code_value_validator',
            'retry_count': 0
        }

    def _check_empty_field_mapping(self, field_info, sql_content, sql_snippet=None):
        """检查留空字段是否正确
        
        Args:
            field_info (dict): 字段映射信息字典
            sql_content (str): SQL代码
            sql_snippet (str): SQL片段（可选）
            
        Returns:
            dict: 如果检测到问题，返回不一致结果；否则返回None
        """
        extract_method = field_info.get('extract_method', '')
        if extract_method != '留空':
            return None
        
        target_field = field_info.get('target_field', '')
        default_value = field_info.get('default_value', '')
        
        sql_to_check = sql_snippet if sql_snippet else sql_content
        
        if not sql_to_check:
            return None
        
        import re
        field_pattern = rf"(?:AS\s+{re.escape(target_field)}|{re.escape(target_field)}\s*,)"
        if not re.search(field_pattern, sql_to_check, re.IGNORECASE):
            return None
        
        null_patterns = [
            rf"NULL\s+AS\s+{re.escape(target_field)}",
            rf"''\s+AS\s+{re.escape(target_field)}",
            rf"null\s+AS\s+{re.escape(target_field)}",
        ]
        
        is_null = False
        for pattern in null_patterns:
            if re.search(pattern, sql_to_check, re.IGNORECASE):
                is_null = True
                break
        
        if is_null:
            return None
        
        value_pattern = rf"['\"]?([^'\"\s]+)['\"]?\s+AS\s+{re.escape(target_field)}"
        match = re.search(value_pattern, sql_to_check, re.IGNORECASE)
        
        if match:
            actual_value = match.group(1)
            return {
                'field': target_field,
                'final_status': 'inconsistent',
                'vote_details': {
                    'consistent': 0,
                    'inconsistent': 1,
                    'warning': 0,
                    'error': 0
                },
                'agent_results': [{
                    'success': True,
                    'agent_id': 'empty_field_validator',
                    'status': 'inconsistent',
                    'issue': f"字段取数方式为'留空'，但SQL中赋值为 '{actual_value}'",
                    'explanation': f"字段加工逻辑定义: 取数方式为'留空'，应使用NULL或空字符串，但SQL中使用了 '{actual_value}'",
                    'suggestion': f"修改为: NULL AS {target_field}",
                    'confidence': 1.0,
                    'mapping_ref': {
                        'target': target_field,
                        'extract_method': '留空'
                    },
                    'field_info': field_info
                }],
                'confidence': 1.0,
                'merged_findings': [{
                    'agent_id': 'empty_field_validator',
                    'status': 'inconsistent',
                    'issue': f"字段取数方式为'留空'，但SQL中赋值为 '{actual_value}'",
                    'explanation': f"字段加工逻辑定义: 取数方式为'留空'，应使用NULL或空字符串，但SQL中使用了 '{actual_value}'",
                    'suggestion': f"修改为: NULL AS {target_field}",
                    'confidence': 1.0,
                    'mapping_ref': {
                        'target': target_field,
                        'extract_method': '留空'
                    },
                    'field_info': field_info
                }],
                'mode': 'empty_field_validator',
                'retry_count': 0
            }
        
        return None

    def _should_retry_fast_mode(self, result, retry_count):
        """判断Fast模式是否需要重试
        
        Args:
            result (dict): Agent结果
            retry_count (int): 当前重试次数
            
        Returns:
            bool: 是否需要重试
        """
        if retry_count >= self.max_retries:
            return False
        
        if not result.get('success'):
            return True
        
        status = result.get('status', '')
        if status in ['timeout', 'parse_error', 'error']:
            return True
        
        return False

    def _should_retry(self, results, retry_count):
        """判断是否需要重试
        
        Args:
            results (list): Agent结果列表
            retry_count (int): 当前重试次数
            
        Returns:
            bool: 是否需要重试
        """
        if retry_count >= self.max_retries:
            return False
        
        failed_count = 0
        for r in results:
            if not r.get('success'):
                failed_count += 1
            else:
                status = r.get('status', '')
                if status in ['timeout', 'parse_error', 'error']:
                    failed_count += 1
        
        return failed_count > 0

    def _execute_vote_once(self, field_info, sql_content, md_content, sql_snippet, sql_structure, group_data_source):
        """执行一次投票检查
        
        Args:
            field_info (dict): 字段映射信息字典
            sql_content (str): SQL代码
            md_content (str): MD文档内容
            sql_snippet (str): SQL片段
            sql_structure (dict): SQL结构化解析结果
            group_data_source (dict): 数据源信息
            
        Returns:
            list: Agent结果列表
        """
        agents = [FieldCheckAgent(self.config, agent_id=i+1) for i in range(self.agent_count)]

        results = []
        completed_agent_ids = set()
        
        with ThreadPoolExecutor(max_workers=self.agent_count) as executor:
            futures = {
                executor.submit(agent.analyze, field_info, sql_content, md_content, sql_snippet, sql_structure, group_data_source): agent.agent_id
                for agent in agents
            }
            total_timeout = self.timeout_per_agent * self.agent_count
            
            try:
                for future in as_completed(futures, timeout=total_timeout):
                    agent_id = futures[future]
                    completed_agent_ids.add(agent_id)
                    try:
                        result = future.result(timeout=self.timeout_per_agent)
                        result['agent_id'] = agent_id
                        results.append(result)
                    except Exception as e:
                        print(f'[TripleAgentVoter] Agent-{agent_id} 执行异常: {e}')
                        source_table = field_info.get('source_table_alias', '')
                        source_field = field_info.get('source_field', '')
                        source = f"{source_table}.{source_field}" if source_table and source_table != 'nan' and source_field and source_field != 'nan' else (source_field if source_field and source_field != 'nan' else '')
                        results.append({
                            'success': False,
                            'status': 'error',
                            'error': str(e),
                            'agent_id': agent_id,
                            'issue': f'Agent-{agent_id}执行异常',
                            'explanation': str(e),
                            'suggestion': '请检查Agent配置或重试',
                            'mapping_ref': {'target': field_info.get('target_field', ''), 'logic': '', 'source': source},
                            'field_info': field_info,
                            'confidence': 0.0
                        })
            except TimeoutError:
                print(f'[TripleAgentVoter] 检测到超时，部分Agent未完成')
                for future, agent_id in futures.items():
                    if agent_id not in completed_agent_ids:
                        print(f'[TripleAgentVoter] Agent-{agent_id} 超时未完成，标记为错误')
                        source_table = field_info.get('source_table_alias', '')
                        source_field = field_info.get('source_field', '')
                        source = f"{source_table}.{source_field}" if source_table and source_table != 'nan' and source_field and source_field != 'nan' else (source_field if source_field and source_field != 'nan' else '')
                        results.append({
                            'success': False,
                            'status': 'timeout',
                            'error': f'Agent-{agent_id}执行超时',
                            'agent_id': agent_id,
                            'issue': f'Agent-{agent_id}执行超时',
                            'explanation': f'Agent在{self.timeout_per_agent}秒内未完成检查',
                            'suggestion': '建议增加超时时间或检查AI服务状态',
                            'mapping_ref': {'target': field_info.get('target_field', ''), 'logic': '', 'source': source},
                            'field_info': field_info,
                            'confidence': 0.0
                        })
                        completed_agent_ids.add(agent_id)
            except Exception as e:
                print(f'[TripleAgentVoter] 投票过程发生未知异常: {e}')
                for future, agent_id in futures.items():
                    if agent_id not in completed_agent_ids:
                        source_table = field_info.get('source_table_alias', '')
                        source_field = field_info.get('source_field', '')
                        source = f"{source_table}.{source_field}" if source_table and source_table != 'nan' and source_field and source_field != 'nan' else (source_field if source_field and source_field != 'nan' else '')
                        results.append({
                            'success': False,
                            'status': 'error',
                            'error': str(e),
                            'agent_id': agent_id,
                            'issue': f'Agent-{agent_id}执行异常',
                            'explanation': str(e),
                            'suggestion': '请检查Agent配置或重试',
                            'mapping_ref': {'target': field_info.get('target_field', ''), 'logic': '', 'source': source},
                            'field_info': field_info,
                            'confidence': 0.0
                        })
                        completed_agent_ids.add(agent_id)
        
        return results

    def _calculate_confidence(self, status_counts):
        """计算投票结果的置信度

        置信度计算规则：
        - 3:0 = 1.0 (完全一致)
        - 2:1 = 0.67 (多数一致)
        - 1:1:1 = 0.33 (分歧严重)
        - 全部失败 = 0.0

        Args:
            status_counts (Counter): 状态计数字典

        Returns:
            float: 置信度值 (0.0-1.0)
        """
        total = sum(status_counts.values())
        if total == 0:
            return 0.0

        error_count = status_counts.get('error', 0)
        valid_total = total - error_count
        if valid_total == 0:
            return 0.0

        consistent_count = status_counts.get('consistent', 0)
        inconsistent_count = status_counts.get('inconsistent', 0)
        warning_count = status_counts.get('warning', 0)

        max_count = max(consistent_count, inconsistent_count, warning_count)

        if max_count == valid_total:
            return 1.0
        elif max_count >= self.consensus_threshold:
            return round(max_count / valid_total, 2)
        else:
            return round(max_count / valid_total, 2)

    def _merge_findings(self, agent_results, final_status):
        """合并多个Agent的findings

        Args:
            agent_results (list): 各Agent的检查结果列表
            final_status (str): 最终判定状态

        Returns:
            list: 合并后的findings列表
        """
        merged = []
        seen_issues = set()

        for result in agent_results:
            if not result.get('success'):
                merged.append({
                    'agent_id': result.get('agent_id'),
                    'status': result.get('status', 'error'),
                    'issue': result.get('issue', '检查失败'),
                    'explanation': result.get('explanation', ''),
                    'suggestion': result.get('suggestion', ''),
                    'confidence': result.get('confidence', 0.0),
                    'field_info': result.get('field_info', {})
                })
                continue

            issue_key = result.get('issue', '')
            if issue_key and issue_key in seen_issues:
                continue
            if issue_key:
                seen_issues.add(issue_key)

            merged.append({
                'agent_id': result.get('agent_id'),
                'status': result.get('status', 'unknown'),
                'issue': result.get('issue', ''),
                'explanation': result.get('explanation', ''),
                'suggestion': result.get('suggestion', ''),
                'confidence': result.get('confidence', 0.5),
                'mapping_ref': result.get('mapping_ref', {}),
                'field_info': result.get('field_info', {})
            })

        return merged


class ResultMerger:
    """结果合并器 - 合并多个Agent的检查结果"""

    @staticmethod
    def merge(agent_results, mapping_data=None):
        """
        合并多个Agent的结果

        Args:
            agent_results (list): Agent结果列表，每个元素为dict格式
            mapping_data (dict): 映射数据（用于生成fallback）

        Returns:
            dict: 合并后的统一结果
        """
        all_findings = []
        total_consistent = 0
        total_inconsistent = 0
        total_checks = 0
        successful_agents = []
        failed_agents = []

        for result in agent_results:
            if result.get('success'):
                findings = result.get('findings', [])
                all_findings.extend(findings)
                summary = result.get('summary', {})
                total_consistent += summary.get('consistent_count', 0)
                total_inconsistent += summary.get('inconsistent_count', 0)
                total_checks += summary.get('total_checks', 0)
                successful_agents.append(result.get('agent_name', 'unknown'))
            else:
                failed_agents.append({
                    'agent_name': result.get('agent_name', 'unknown'),
                    'error': result.get('error', '未知错误'),
                    'raw_response': result.get('raw_response', '')
                })

        if failed_agents:
            for failed in failed_agents:
                warning_finding = {
                    'id': len(all_findings) + 1,
                    'status': 'warning',
                    'agent': 'system',
                    'location': '系统提示',
                    'issue': f'Agent [{failed["agent_name"]}] 执行失败',
                    'explanation': f'错误原因: {failed["error"]}\n原始响应: {failed["raw_response"][:200]}',
                    'original_sql': '',
                    'mapping_ref': {'target': 'Agent异常', 'logic': '该Agent未能完成检查'},
                    'suggestion': '建议手动复核此Agent负责的检查项，或检查AI服务状态',
                    'severity': 'low',
                    'type': 'agent_error',
                    'typeLabel': 'Agent异常'
                }
                all_findings.append(warning_finding)

        global_id = 1
        for finding in all_findings:
            finding['id'] = global_id
            global_id += 1

        merged_result = {
            'success': True,
            'findings': all_findings,
            'summary': {
                'total_checks': total_checks,
                'consistent_count': total_consistent,
                'inconsistent_count': total_inconsistent,
                'pass_rate': round((total_consistent / max(total_checks, 1)) * 100, 1) if total_checks > 0 else 0,
                'agents_executed': len(successful_agents) + len(failed_agents),
                'successful_agents': successful_agents,
                'failed_agents': [f['agent_name'] for f in failed_agents],
                'duration': 0
            },
            'agent_details': {
                'successful': successful_agents,
                'failed': failed_agents
            }
        }

        print(f'[ResultMerger] 合并完成:')
        print(f'  - 成功Agent数: {len(successful_agents)} ({successful_agents})')
        print(f'  - 失败Agent数: {len(failed_agents)}')
        print(f'  - 总findings数: {len(all_findings)}')
        print(f'  - 一致性统计: {total_consistent}/{total_checks} (通过率: {merged_result["summary"]["pass_rate"]}%)')

        return merged_result


class OllamaClient:
    """Ollama AI客户端 - 支持多Agent架构"""

    def __init__(self, config):
        self.host = config.get('host', 'http://localhost:11434')
        self.model = config.get('model', 'qwen2.5:7b')
        self.timeout = int(config.get('timeout', 60))
        self.agent_timeouts = config.get('agent_timeouts', {})

        if self.agent_timeouts:
            print(f'[OllamaClient] 检测到Agent专属超时配置: {self.agent_timeouts}')
        else:
            print(f'[OllamaClient] 使用全局超时设置: {self.timeout}秒（所有Agent共用）')

    def analyze_sql_mapping(self, mapping_data, sql_content, business_context=''):
        """使用多Agent架构分析SQL与Mapping的一致性"""

        import time
        overall_start_time = time.time()

        print('=' * 60)
        print('[Multi-Agent] 开始执行SQL审查（多Agent协作模式）')
        print(f'[Multi-Agent] 模型: {self.model}, 全局超时: {self.timeout}秒')
        print('=' * 60)

        config = {
            'host': self.host,
            'model': self.model,
            'timeout': self.timeout,
            'agent_timeouts': getattr(self, 'agent_timeouts', {})
        }

        agent_results = []

        try:
            relationship_checker = RelationshipCheckerAgent(config)
            print('\n[Multi-Agent] >>> 启动 Agent 1: 表间关联检查器 (RelationshipChecker)')
            result1 = relationship_checker.analyze(mapping_data, sql_content)
            agent_results.append(result1)

            if result1.get('success'):
                print(f'[Multi-Agent] Agent 1 完成，发现 {len(result1.get("findings", []))} 条问题')
            else:
                print(f'[Multi-Agent] Agent 1 失败: {result1.get("error", "未知错误")}')

        except Exception as e:
            print(f'[Multi-Agent] Agent 1 异常: {e}')
            agent_results.append({
                'success': False,
                'agent_name': 'relationship_checker',
                'error': str(e),
                'findings': [],
                'summary': {'total_checks': 0, 'consistent_count': 0, 'inconsistent_count': 0}
            })

        try:
            field_mapping_checker = FieldMappingCheckerAgent(config)
            print('\n[Multi-Agent] >>> 启动 Agent 2: 字段信息检查器 (FieldMappingChecker)')
            result2 = field_mapping_checker.analyze(mapping_data, sql_content, business_context)
            agent_results.append(result2)

            if result2.get('success'):
                print(f'[Multi-Agent] Agent 2 完成，发现 {len(result2.get("findings", []))} 条问题')
            else:
                print(f'[Multi-Agent] Agent 2 失败: {result2.get("error", "未知错误")}')

        except Exception as e:
            print(f'[Multi-Agent] Agent 2 异常: {e}')
            agent_results.append({
                'success': False,
                'agent_name': 'field_mapping_checker',
                'error': str(e),
                'findings': [],
                'summary': {'total_checks': 0, 'consistent_count': 0, 'inconsistent_count': 0}
            })

        try:
            print('\n[Multi-Agent] >>> 启动 Agent 3: 码值转换校验器 (CodeValueValidator)')
            code_value_validator = CodeValueValidator()
            code_value_findings = []
            
            field_mappings = mapping_data.get('field_mappings', [])
            for field_info in field_mappings:
                if field_info.get('extract_method') == '码值转换':
                    validation_result = code_value_validator.check_field(field_info, sql_content)
                    if not validation_result.get('is_valid', True):
                        for issue in validation_result.get('issues', []):
                            finding = {
                                'id': len(code_value_findings) + 1,
                                'status': 'inconsistent',
                                'agent': 'code_value_validator',
                                'group_id': field_info.get('group_id', ''),
                                'group_name': '',
                                'location': f"字段 {field_info.get('target_field', '')} 的CASE WHEN语句",
                                'issue': issue.get('message', '码值转换不一致'),
                                'explanation': f"字段加工逻辑定义: {field_info.get('transformation_logic', '')}",
                                'original_sql': sql_content[:500] if sql_content else '',
                                'mapping_ref': {
                                    'target': field_info.get('target_field', ''),
                                    'logic': field_info.get('transformation_logic', '')
                                },
                                'suggestion': f"请检查码值 '{issue.get('source_value', '')}' 的映射是否正确",
                                'severity': issue.get('severity', 'high'),
                                'type': 'code_value_mismatch',
                                'typeLabel': '码值转换检查'
                            }
                            code_value_findings.append(finding)
            
            result3 = {
                'success': True,
                'agent_name': 'code_value_validator',
                'findings': code_value_findings,
                'summary': {
                    'total_checks': len([f for f in field_mappings if f.get('extract_method') == '码值转换']),
                    'consistent_count': len([f for f in field_mappings if f.get('extract_method') == '码值转换']) - len(code_value_findings),
                    'inconsistent_count': len(code_value_findings)
                }
            }
            agent_results.append(result3)
            
            if result3.get('success'):
                print(f'[Multi-Agent] Agent 3 完成，发现 {len(code_value_findings)} 条码值转换问题')
            else:
                print(f'[Multi-Agent] Agent 3 失败: {result3.get("error", "未知错误")}')

        except Exception as e:
            print(f'[Multi-Agent] Agent 3 异常: {e}')
            agent_results.append({
                'success': False,
                'agent_name': 'code_value_validator',
                'error': str(e),
                'findings': [],
                'summary': {'total_checks': 0, 'consistent_count': 0, 'inconsistent_count': 0}
            })

        print('\n[Multi-Agent] 所有Agent执行完毕，开始合并结果...')
        merged_result = ResultMerger.merge(agent_results, mapping_data=mapping_data)

        total_elapsed = time.time() - overall_start_time
        merged_result['summary']['duration'] = int(total_elapsed)

        print(f'\n[Multi-Agent] 总耗时: {total_elapsed:.2f}秒')
        print(f'[Multi-Agent] 最终结果: {len(merged_result["findings"])} 条findings')
        print('=' * 60)

        return merged_result

    def _format_mapping_for_ai(self, mapping_data):
        """将映射数据格式化为AI可读的文本"""
        lines = []
        
        lines.append("### 目标表信息：")
        for table in mapping_data.get('tables', []):
            lines.append(f"- 表名: {table.get('name', 'N/A')}, 别名: {table.get('alias', 'N/A')}")
        
        lines.append("\n### 字段映射规则：")
        for i, field in enumerate(mapping_data.get('field_mappings', []), 1):
            lines.append(f"{i}. **{field.get('target_field', 'N/A')}**")
            lines.append(f"   - 源表: {field.get('source_table_alias', 'N/A')}")
            lines.append(f"   - 源字段: {field.get('source_field', 'N/A')}")
            if field.get('transformation_logic'):
                lines.append(f"   - 转换逻辑: {field['transformation_logic']}")
            lines.append("")
        
        return '\n'.join(lines)

    def _parse_ai_response(self, response_text, mapping_data=None):
        """解析AI返回的结果 - 增强版：支持多种格式自动转换"""
        raw_response = response_text[:500] if response_text else ''
        try:
            result = self._extract_json_multi_level(response_text)
            if result is None:
                raise Exception('所有JSON解析策略均失败')

            normalized_result = self._normalize_ai_response_format(result, mapping_data)

            findings = normalized_result.get('findings', [])
            summary = normalized_result.get('summary', {})

            for i, finding in enumerate(findings):
                finding['id'] = i + 1
                if 'typeLabel' not in finding:
                    finding['typeLabel'] = finding.get('type', '未知')

            findings = self._ensure_chinese_output(findings)

            result_to_score = {'findings': findings, 'summary': summary}
            quality_score, score_details = self._score_result_quality(result_to_score)

            if quality_score < 60:
                warning_finding = {
                    'id': 0,
                    'status': 'warning',
                    'agent': 'quality_checker',
                    'location': '系统提示',
                    'issue': f'AI分析结果质量评分较低（{quality_score}/100分），请谨慎参考',
                    'explanation': f'质量评估详情:\n' + '\n'.join(
                        [f'- {dim}: {data["score"]}/{data["max"]}分 {data["status"]}'
                         for dim, data in score_details.items()
                         if isinstance(data, dict)]
                    ),
                    'original_sql': '',
                    'mapping_ref': {'target': '质量检查', 'logic': '自动质量评估'},
                    'suggestion': '建议人工复核以下方面：\n1. 检查location字段是否包含行号\n2. 确认original_sql是否完整\n3. 核实字段值是否为中文\n4. 验证必要字段是否齐全',
                    'severity': 'low',
                    'type': 'quality_warning',
                    'typeLabel': '质量警告'
                }
                findings.insert(0, warning_finding)
                print(f'[质量评分] 已插入质量警告finding（分数: {quality_score}）')

            return {
                'success': True,
                'findings': findings,
                'summary': {
                    'total_checks': summary.get('total_checks', len(findings)),
                    'consistent_count': summary.get('consistent_count', 0),
                    'inconsistent_count': summary.get('inconsistent_count', len([f for f in findings if f.get('status') == 'inconsistent'])),
                    'pass_rate': round((summary.get('consistent_count', 0) / max(summary.get('total_checks', 1), 1)) * 100, 1),
                    'duration': 0,
                    'raw_response': raw_response,
                    'quality_score': quality_score,
                    'quality_details': score_details
                }
            }
        except Exception as e:
            print(f'[AI响应解析] 解析失败: {e}')
            fallback_result = self._generate_smart_fallback(response_text, mapping_data)
            fallback_result['raw_response'] = raw_response
            return fallback_result

    def _is_english_dominant(self, text):
        """检测文本中英文字符占比，判断是否以英文为主

        Args:
            text (str): 待检测的文本字符串

        Returns:
            bool: 英文字符占比>70%返回True，否则返回False
        """
        if not text or not isinstance(text, str):
            return False

        english_chars = len([c for c in text if c.isascii() and c.isalpha()])
        total_chars = len(text.replace(' ', '').replace('\n', '').replace('\t', ''))

        if total_chars == 0:
            return False

        ratio = (english_chars / total_chars) * 100
        is_english = ratio > 70

        if is_english:
            print(f'[中文检测] 检测到英文主导文本（英文占比: {ratio:.1f}%），需要翻译')

        return is_english

    def _translate_to_chinese(self, text):
        """基于关键词词典的简单英译中翻译方法

        使用预定义的SQL术语词典进行关键词替换，将常见英文SQL术语转换为中文。
        支持短语级别的模式匹配和替换。

        Args:
            text (str): 可能包含英文术语的文本字符串

        Returns:
            str: 翻译后的中文文本
        """
        if not text or not isinstance(text, str):
            return text

        translation_dict = {
            'LEFT JOIN': '左连接',
            'RIGHT JOIN': '右连接',
            'INNER JOIN': '内连接',
            'FULL OUTER JOIN': '全外连接',
            'CROSS JOIN': '交叉连接',
            'JOIN': '连接',

            'WHERE clause': 'WHERE子句',
            'WHERE condition': 'WHERE条件',
            'WHERE': 'WHERE子句',
            'FROM clause': 'FROM子句',
            'FROM': 'FROM子句',
            'SELECT statement': 'SELECT语句',
            'SELECT': 'SELECT字段列表',
            'GROUP BY clause': 'GROUP BY子句',
            'GROUP BY': '分组依据',
            'ORDER BY clause': 'ORDER BY子句',
            'ORDER BY': '排序依据',
            'HAVING clause': 'HAVING子句',
            'HAVING': 'HAVING过滤',

            'NULL handling': 'NULL处理',
            'NULL value': '空值',
            'NULL check': '空值检查',
            'NULL': '空值',
            'NOT NULL': '非空约束',
            'IS NULL': '为空值',
            'IS NOT NULL': '不为空值',

            'NVL function': 'NVL函数',
            'COALESCE function': 'COALESCE函数',
            'NVL': 'NVL函数',
            'COALESCE': 'COALESCE函数',

            'Missing': '缺少',
            'missing': '缺少',
            'Not found': '未找到',
            'not found': '未找到',
            'Incorrect': '不正确',
            'incorrect': '不正确',
            'Error': '错误',
            'error': '错误',
            'Issue': '问题',
            'issue': '问题',
            'Problem': '问题',
            'problem': '问题',
            'Warning': '警告',
            'warning': '警告',
            'Critical': '严重',
            'critical': '严重',
            'High': '高',
            'high': '高',
            'Medium': '中等',
            'medium': '中等',
            'Low': '低',
            'low': '低',

            'should be': '应该是',
            'should': '应该',
            'must be': '必须是',
            'must': '必须',
            'need to': '需要',
            'needs to': '需要',
            'please': '请',
            'Please': '请',

            'field mapping': '字段映射',
            'field name': '字段名',
            'column': '列',
            'table': '表',
            'alias': '别名',
            'condition': '条件',
            'filter': '过滤',
            'constraint': '约束',
            'index': '索引',
            'primary key': '主键',
            'foreign key': '外键',
            'unique constraint': '唯一性约束',

            'substring': '子串截取',
            'concatenation': '拼接',
            'concat': '拼接',
            'cast': '类型转换',
            'type conversion': '类型转换',
            'date format': '日期格式化',
            'timestamp': '时间戳',

            'aggregate function': '聚合函数',
            'aggregation': '聚合',
            'count': '计数',
            'sum': '求和',
            'average': '平均值',
            'max': '最大值',
            'min': '最小值',
            'window function': '窗口函数',
            'partition by': '分区依据',

            'inconsistent with': '与...不一致',
            'does not match': '不匹配',
            'mismatch': '不匹配',
            'difference': '差异',
            'discrepancy': '不一致',

            'line': '行',
            'code snippet': '代码片段',
            'statement': '语句',
            'query': '查询',
            'subquery': '子查询',
            'expression': '表达式',
            'syntax error': '语法错误',
            'logic error': '逻辑错误',
            'performance issue': '性能问题',

            'suggestion': '建议',
            'recommendation': '建议',
            'solution': '解决方案',
            'fix': '修复',
            'change to': '修改为',
            'replace with': '替换为',
            'move to': '移动到',
            'add': '添加',
            'remove': '移除',
            'delete': '删除',
            'update': '更新',
            'modify': '修改'
        }

        translated_text = text

        for eng_term, cn_term in sorted(translation_dict.items(), key=lambda x: -len(x[0])):
            pattern = re.compile(re.escape(eng_term), re.IGNORECASE)
            matches = pattern.findall(translated_text)
            if matches:
                translated_text = pattern.sub(cn_term, translated_text)

        if translated_text != text:
            print(f'[中文翻译] 已翻译: "{text[:50]}..." → "{translated_text[:50]}..."')

        return translated_text

    def _ensure_chinese_output(self, findings):
        """确保所有finding的字段值都是中文，对英文内容进行自动翻译

        遍历findings数组中的每个finding对象，检查issue、explanation、suggestion等
        关键字段的文本语言。如果检测到英文占主导地位（>70%），则调用翻译方法
        将其转换为中文。

        Args:
            findings (list): finding字典的列表，每个finding应包含issue/explanation/suggestion等字段

        Returns:
            list: 处理后的findings列表（已确保关键中文化）
        """
        if not findings or not isinstance(findings, list):
            return findings

        chinese_fields = ['issue', 'explanation', 'suggestion', 'location']

        for finding in findings:
            if not isinstance(finding, dict):
                continue

            for field in chinese_fields:
                field_value = finding.get(field, '')
                if field_value and isinstance(field_value, str):
                    if self._is_english_dominant(field_value):
                        translated_value = self._translate_to_chinese(field_value)
                        finding[field] = translated_value

        print(f'[中文后处理] 已完成{len(findings)}条finding的中文化检查')
        return findings

    def _score_result_quality(self, result):
        """基于多维度评分机制对AI分析结果进行质量评估（0-100分）

        评分维度：
        - location格式正确性：包含"第X行"格式得10分，否则扣5分
        - original_sql完整性：长度≥20字符得10分，缺失或过短扣10分
        - 语言正确性：全中文输出得15分，检测到英文扣15分
        - 字段齐全度：issue/explanation/suggestion都存在且非空得15分，每缺一个扣5分

        Args:
            result (dict): AI分析的完整结果字典，应包含findings和summary字段

        Returns:
            tuple: (quality_score (int), score_details (dict))
                   quality_score: 0-100的质量分数
                   score_details: 各维度得分明细，用于调试和分析
        """
        if not isinstance(result, dict):
            return (0, {'error': '无效的结果格式'})

        findings = result.get('findings', [])
        if not findings or not isinstance(findings, list):
            return (50, {'warning': 'findings为空或格式错误'})

        score = 0
        details = {
            'location_format': {'max': 10, 'score': 0, 'issues': []},
            'original_sql_completeness': {'max': 10, 'score': 0, 'issues': []},
            'language_correctness': {'max': 15, 'score': 0, 'issues': []},
            'field_completeness': {'max': 15, 'score': 0, 'issues': []}
        }

        total_findings = len(findings)

        for finding in findings:
            if not isinstance(finding, dict):
                continue

            location = finding.get('location', '')
            if location:
                if re.search(r'第\d+行', location):
                    details['location_format']['score'] += 10 / total_findings
                else:
                    details['location_format']['issues'].append(f"location缺少行号: {location[:30]}")

            original_sql = finding.get('original_sql', '')
            if original_sql and len(original_sql) >= 20:
                details['original_sql_completeness']['score'] += 10 / total_findings
            else:
                details['original_sql_completeness']['issues'].append(
                    f"original_sql不完整(长度:{len(original_sql) if original_sql else 0})"
                )

            text_fields_to_check = ['issue', 'explanation', 'suggestion']
            english_count = 0
            for field_name in text_fields_to_check:
                field_value = finding.get(field_name, '')
                if field_value and isinstance(field_value, str):
                    if self._is_english_dominant(field_value):
                        english_count += 1

            if english_count == 0:
                details['language_correctness']['score'] += 15 / total_findings
            else:
                details['language_correctness']['issues'].append(
                    f"发现{english_count}个字段为英文"
                )

            required_fields = ['issue', 'explanation', 'suggestion']
            missing_fields = [f for f in required_fields if not finding.get(f)]
            empty_fields = [f for f in required_fields if finding.get(f) == '' or finding.get(f) is None]
            all_missing_or_empty = len(set(missing_fields + empty_fields))

            if all_missing_or_empty == 0:
                details['field_completeness']['score'] += 15 / total_findings
            else:
                details['field_completeness']['issues'].append(
                    f"缺少{all_missing_or_empty}个必要字段"
                )

        for dimension, data in details.items():
            actual_score = min(data['score'], data['max'])
            score += actual_score
            data['score'] = round(actual_score, 1)

            if not data['issues']:
                data['status'] = '✓'
            else:
                data['status'] = '✗'
                penalty = len(data['issues']) * 2
                score = max(0, score - penalty)

        score = max(0, min(100, int(score)))

        print(f'[质量评分] 总分: {score}/100')
        for dim, data in details.items():
            print(f'  - {dim}: {data["score"]}/{data["max"]} {data["status"]}')
            if data.get('issues'):
                for issue in data['issues']:
                    print(f'    ⚠ {issue}')

        return (score, details)

    def _extract_json_multi_level(self, text):
        """多级JSON提取策略 - 四级提取策略：L1直接解析→L2 Markdown→L3正则→L4格式修复（支持True/False/None/中文引号）"""
        if not text or not isinstance(text, str):
            return None

        strategies = [
            ('直接JSON解析', self._try_direct_parse),
            ('Markdown代码块提取', self._try_markdown_block_extract),
            ('正则最外层对象提取', self._try_regex_object_extract),
            ('格式修复后重试', self._try_format_fix_and_parse),
        ]

        for strategy_name, strategy_func in strategies:
            try:
                result = strategy_func(text)
                if result is not None and isinstance(result, dict):
                    print(f'[AI响应解析] 策略成功: {strategy_name}, 检测到字段: {list(result.keys())}')
                    return result
            except Exception as e:
                print(f'[AI响应解析] 策略失败 [{strategy_name}]: {e}')
                continue

        return None

    def _try_direct_parse(self, text):
        """第一级：尝试直接 json.loads()"""
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        return None

    def _try_markdown_block_extract(self, text):
        """第二级：使用正则提取 markdown 代码块内容"""
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                match = match.strip()
                if match.startswith('{'):
                    try:
                        result = json.loads(match)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        continue
        return None

    def _try_regex_object_extract(self, text):
        """第三级：使用正则提取最外层JSON对象"""
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            json_str = match.group(0)
            try:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
        return None

    def _try_format_fix_and_parse(self, text):
        """第四级：修复常见格式问题后再次解析 - 增强版：支持不完整JSON修复"""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return None
        json_str = json_match.group(0)

        fixes = [
            (lambda s: re.sub(r',\s*([}\]])', r'\1', s), '移除尾逗号'),
            (lambda s: s.replace("'", '"'), '单引号转双引号'),
            (lambda s: re.sub(r'//.*$', '', s, flags=re.MULTILINE).strip(), '移除单行注释'),
            (lambda s: re.sub(r'/\*[\s\S]*?\*/', '', s), '移除多行注释'),
            (lambda s: re.sub(r'(?<!\\)\n', ' ', s), '替换换行符为空格'),
            (lambda s: re.sub(r'\s+', ' ', s).strip(), '压缩空白字符'),
            (lambda s: re.sub(r'\bTrue\b', 'true', s), 'Python布尔值True转JSON'),
            (lambda s: re.sub(r'\bFalse\b', 'false', s), 'Python布尔值False转JSON'),
            (lambda s: re.sub(r'\bNone\b', 'null', s), 'Python空值None转JSON null'),
            (lambda s: s.replace('\u2018', '"').replace('\u2019', '"').replace('\u201c', '"').replace('\u201d', '"'), '中文引号统一转英文双引号'),
            (lambda s: re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s), '移除控制字符'),
        ]

        for fix_func, fix_desc in fixes:
            try:
                fixed_str = fix_func(json_str)
                result = json.loads(fixed_str)
                if isinstance(result, dict):
                    print(f'[AI响应解析] 格式修复成功: {fix_desc}')
                    return result
            except (json.JSONDecodeError, ValueError):
                json_str = fix_func(json_str)
                continue

        print('[AI响应解析] 尝试修复不完整的JSON...')

        try:
            repaired_json = self._repair_incomplete_json(json_str)
            if repaired_json:
                result = json.loads(repaired_json)
                if isinstance(result, dict):
                    print('[AI响应解析] 不完整JSON修复成功')
                    return result
        except Exception as e:
            print(f'[AI响应解析] 不完整JSON修复失败: {e}')

        return None

    def _repair_incomplete_json(self, json_str):
        """尝试修复不完整的JSON字符串

        处理以下情况：
        - 未闭合的括号或方括号
        - 未闭合的引号
        - 缺少字段值的截断

        Args:
            json_str (str): 可能不完整的JSON字符串

        Returns:
            str: 修复后的完整JSON字符串，如果无法修复则返回None
        """
        if not json_str or not json_str.strip():
            return None

        try:
            stack = []
            in_string = False
            escape_next = False
            i = 0

            while i < len(json_str):
                char = json_str[i]

                if escape_next:
                    escape_next = False
                    i += 1
                    continue

                if char == '\\' and in_string:
                    escape_next = True
                    i += 1
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    i += 1
                    continue

                if not in_string:
                    if char in '{[':
                        stack.append(char)
                    elif char in '}]':
                        if stack:
                            expected_open = '{' if char == '}' else '['
                            if stack[-1] == expected_open:
                                stack.pop()
                            else:
                                break
                        else:
                            break

                i += 1

            if not in_string and stack:
                print(f'[JSON修复] 检测到未闭合的括号: {stack}')

                repaired = json_str.rstrip()

                if in_string:
                    repaired += '"'

                while stack:
                    open_char = stack.pop()
                    if open_char == '{':
                        if not repaired.endswith('}'):
                            if repaired.rstrip().endswith(','):
                                repaired = repaired.rstrip()[:-1]
                            repaired += '}'
                        else:
                            stack.pop()
                    elif open_char == '[':
                        if not repaired.endswith(']'):
                            if repaired.rstrip().endswith(','):
                                repaired = repaired.rstrip()[:-1]
                            repaired += ']'
                        else:
                            stack.pop()

                print(f'[JSON修复] 已自动补全括号，修复后长度: {len(repaired)}')
                return repaired

            elif in_string:
                print('[JSON修复] 检测到未闭合的字符串，尝试截断到最后一个完整字段')

                last_complete = json_str.rfind('",')
                if last_complete > 0:
                    truncated = json_str[:last_complete + 1]
                    bracket_stack = []
                    for c in truncated:
                        if c in '{[':
                            bracket_stack.append(c)
                        elif c in '}]':
                            if bracket_stack:
                                bracket_stack.pop()

                    while bracket_stack:
                        open_bracket = bracket_stack.pop()
                        truncated += '}' if open_bracket == '{' else ']'

                    return truncated

            return None

        except Exception as e:
            print(f'[JSON修复] 修复过程出错: {e}')
            return None

    def _normalize_ai_response_format(self, raw_result, mapping_data=None):
        """将各种AI返回格式统一转换为标准格式

        支持的输入格式（共14种字段名变体）：
        - 标准格式: { findings: [...], summary: {...} }
        - differences格式: { differences: [{description, line, expected_comment}] }
        - issues格式: { issues: [...] }
        - errors格式: { errors: [...] }
        - problems格式: { problems: [...] }
        - error_list格式: { error_list: [...] }
        - warnings格式: { warnings: [...] }
        - violations格式: { violations: [...] }
        - anomalies格式: { anomalies: [...] }
        - results格式: { results: [...] }
        - items格式: { items: [...] }
        - data格式: { data: [...] }
        - inconsistencies格式: { inconsistencies: [...] }
        - mismatches格式: { mismatches: [...] }
        """
        if not isinstance(raw_result, dict):
            return self._create_empty_normalized_result()

        format_handlers = {
            'differences': self._convert_differences_to_findings,
            'issues': self._convert_generic_list_to_findings,
            'errors': self._convert_generic_list_to_findings,
            'problems': self._convert_generic_list_to_findings,
            'error_list': self._convert_generic_list_to_findings,
            'warnings': self._convert_generic_list_to_findings,
            'violations': self._convert_generic_list_to_findings,
            'anomalies': self._convert_generic_list_to_findings,
            'results': self._convert_generic_list_to_findings,
            'items': self._convert_generic_list_to_findings,
            'data': self._convert_generic_list_to_findings,
            'inconsistencies': self._convert_generic_list_to_findings,
            'mismatches': self._convert_generic_list_to_findings,
            'findings': self._convert_generic_list_to_findings
        }

        for field_name, handler in format_handlers.items():
            if field_name in raw_result:
                print(f'[AI响应解析] 检测到格式: {field_name}, 开始转换...')
                normalized = handler(raw_result, mapping_data)
                if normalized:
                    return normalized

        print(f'[AI响应解析] 未知格式，字段列表: {list(raw_result.keys())}，尝试智能解析')
        return self._try_intelligent_parsing(raw_result, mapping_data)

    def _convert_differences_to_findings(self, data, mapping_data=None):
        """转换 differences 格式为标准 findings 格式"""
        differences = data.get('differences', [])
        if not differences:
            return None

        findings = []
        for idx, diff in enumerate(differences, 1):
            description = diff.get('description', '')
            line_content = diff.get('line', '')
            expected_comment = diff.get('expected_comment', '')

            finding = {
                'id': idx,
                'status': 'inconsistent',
                'agent': 'mapping_check',
                'location': f'SQL行: {line_content[:50]}...' if len(line_content) > 50 else f'SQL行: {line_content}',
                'issue': f'缺少注释或与Mapping不一致' if 'not present' in description.lower() else description[:100],
                'explanation': f'{description}\n期望注释: {expected_comment}' if expected_comment else description,
                'original_sql': line_content,
                'mapping_ref': self._build_mapping_ref_from_data(expected_comment.replace('-- ', '') if expected_comment else '', '注释规范', mapping_data),
                'suggestion': f"在 '{line_content}' 前添加注释: {expected_comment}" if expected_comment else '请检查此行是否符合Mapping规范',
                'severity': 'medium',
                'type': 'comment',
                'typeLabel': '注释缺失'
            }
            findings.append(finding)

        inconsistent_count = len(findings)
        return {
            'findings': findings,
            'summary': {
                'total_checks': inconsistent_count + 1,
                'consistent_count': 0,
                'inconsistent_count': inconsistent_count
            }
        }

    def _convert_generic_list_to_findings(self, data, mapping_data=None, list_field=None):
        """通用的列表转findings转换器（支持 issues/errors/problems 等14种变体）"""
        if not list_field:
            known_fields = [
                'issues', 'errors', 'problems', 'error_list',
                'warnings', 'violations', 'anomalies', 'results',
                'items', 'data', 'inconsistencies', 'mismatches'
            ]
            for field in known_fields:
                if field in data:
                    list_field = field
                    break

        if not list_field or list_field not in data:
            return None

        items = data.get(list_field, [])
        if not items:
            return None

        findings = []
        for idx, item in enumerate(items, 1):
            if not isinstance(item, dict):
                item = {'description': str(item)}

            finding = {
                'id': idx,
                'status': item.get('status', 'inconsistent'),
                'agent': item.get('agent', 'mapping_check'),
                'location': item.get('location', item.get('line', item.get('position', '未知位置'))),
                'issue': item.get('issue', item.get('message', item.get('title', item.get('description', '发现问题')))),
                'explanation': item.get('explanation', item.get('detail', item.get('description', ''))),
                'original_sql': item.get('original_sql', item.get('code_snippet', '')),
                'mapping_ref': item.get('mapping_ref', {}),
                'suggestion': item.get('suggestion', item.get('recommendation', '')),
                'severity': item.get('severity', 'medium'),
                'type': item.get('type', 'mapping_check'),
                'typeLabel': item.get('typeLabel', item.get('category', '映射检查'))
            }
            findings.append(finding)

        inconsistent_count = len([f for f in findings if f.get('status') == 'inconsistent'])
        return {
            'findings': findings,
            'summary': {
                'total_checks': len(findings),
                'consistent_count': len(findings) - inconsistent_count,
                'inconsistent_count': inconsistent_count
            }
        }

    def _try_intelligent_parsing(self, data, mapping_data=None):
        """智能解析：尝试从非标准结构中提取有效信息"""
        findings = []

        for key, value in data.items():
            if key == 'summary':
                continue

            if isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict):
                    converted = self._convert_generic_list_to_findings(
                        {key: value}, mapping_data, list_field=key
                    )
                    if converted:
                        findings.extend(converted['findings'])
                else:
                    for idx, item in enumerate(value, len(findings) + 1):
                        findings.append({
                            'id': idx,
                            'status': 'warning',
                            'agent': 'intelligent_parser',
                            'location': f'字段: {key}',
                            'issue': str(item)[:200] if item else '空值',
                            'explanation': f'AI返回了未预期的数据结构，原始字段: {key}',
                            'original_sql': '',
                            'mapping_ref': self._build_mapping_ref_from_data('', '非标准格式解析', mapping_data),
                            'suggestion': '请手动检查此项',
                            'severity': 'low',
                            'type': 'business_rule',
                            'typeLabel': '非标准格式'
                        })

        if findings:
            inconsistent_count = len([f for f in findings if f.get('status') == 'inconsistent'])
            return {
                'findings': findings,
                'summary': {
                    'total_checks': len(findings),
                    'consistent_count': len(findings) - inconsistent_count,
                    'inconsistent_count': inconsistent_count
                }
            }

        return self._create_empty_normalized_result()

    def _build_mapping_ref_from_data(self, target, logic, mapping_data=None, field_info=None):
        """构建标准化的mapping_ref对象 - 新增功能：自动从mapping_data提取sheet等扩展字段，从field_info提取source信息

        Args:
            target (str): IT-Mapping目标字段名或规则描述
            logic (str): 转换逻辑或业务规则文本
            mapping_data (dict): 完整的映射数据，用于自动补充sheet等信息
            field_info (dict): 单个字段信息，用于提取source信息

        Returns:
            dict: 标准化的mapping_ref字典，包含target/logic/source/sheet等字段
               - target: 目标字段名
               - logic: 转换逻辑说明
               - source: 源表字段信息（格式：源表.源字段）
               - sheet: 来源Sheet名称（如有多个则逗号分隔）
        """
        ref = {'target': target or '', 'logic': logic or ''}
        
        if field_info and isinstance(field_info, dict):
            source_table = field_info.get('source_table_alias', '')
            source_field = field_info.get('source_field', '')
            if source_table and source_table != 'nan' and source_field and source_field != 'nan':
                ref['source'] = f"{source_table}.{source_field}"
            elif source_field and source_field != 'nan':
                ref['source'] = source_field
        
        if mapping_data and isinstance(mapping_data, dict):
            field_mappings = mapping_data.get('field_mappings', [])
            if field_mappings and isinstance(field_mappings, list) and len(field_mappings) > 0:
                sheets = set()
                for fm in field_mappings:
                    s = fm.get('sheet', '')
                    if s and s != 'nan':
                        sheets.add(s)
                if sheets:
                    ref['sheet'] = ', '.join(sorted(sheets))
        return ref

    def _create_empty_normalized_result(self):
        """创建空的标准化结果"""
        return {
            'findings': [],
            'summary': {
                'total_checks': 0,
                'consistent_count': 0,
                'inconsistent_count': 0
            }
        }

    def _generate_smart_fallback(self, response_text, mapping_data):
        """智能兜底机制：先尝试解析，失败再生成fallback"""
        if not response_text or not response_text.strip():
            return self._generate_fallback_result(response_text, mapping_data)

        try:
            import json
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    result = json.loads(json_match.group(0))
                    if isinstance(result, dict):
                        normalized = self._normalize_ai_response_format(result, mapping_data)
                        if normalized and normalized.get('findings'):
                            print('[AI响应解析] 智能Fallback成功：从原始文本提取并转换了JSON')
                            return {
                                'success': True,
                                **normalized,
                                'raw_response': response_text[:500]
                            }
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
        except Exception as e:
            print(f'[AI响应解析] 智能Fallback解析失败: {e}')

        return self._generate_fallback_result(response_text, mapping_data)

    def _generate_fallback_result(self, response_text, mapping_data):
        """兜底结果生成：确保返回的 findings 数组永远不为空"""
        findings = []

        raw_finding = {
            'id': 1,
            'status': 'warning',
            'agent': 'mapping_check',
            'location': 'AI响应解析',
            'issue': '无法从AI响应中提取结构化结果，以下为原始文本内容',
            'explanation': f'AI原始响应（前500字符）:\n{response_text[:500] if response_text else "(空)"}',
            'original_sql': '',
            'mapping_ref': self._build_mapping_ref_from_data('AI解析兜底', '无法从AI响应中提取结构化结果', mapping_data),
            'suggestion': '请检查AI服务是否正常工作，或手动审查SQL代码',
            'severity': 'medium',
            'type': 'business_rule',
            'typeLabel': '解析异常'
        }
        findings.append(raw_finding)

        field_mappings = []
        if mapping_data and isinstance(mapping_data, dict):
            field_mappings = mapping_data.get('field_mappings', [])

        if field_mappings:
            for idx, fm in enumerate(field_mappings, start=2):
                target_field = fm.get('target_field', '未知字段')
                source_field = fm.get('source_field', '')
                source_table = fm.get('source_table_alias', '')
                logic = fm.get('transformation_logic', '')
                sheet = fm.get('sheet', '')

                fallback_finding = {
                    'id': idx,
                    'status': 'consistent',
                    'agent': 'mapping_check',
                    'location': f'字段映射: {target_field}',
                    'issue': '',
                    'explanation': f'目标字段: {target_field}, 源表: {source_table or "N/A"}, 源字段: {source_field or "N/A"}{f", 转换逻辑: {logic}" if logic else ""}',
                    'original_sql': '',
                    'mapping_ref': {'target': target_field, 'logic': logic, **({'sheet': sheet} if sheet else {})},
                    'suggestion': '',
                    'severity': 'low',
                    'type': 'mapping_check',
                    'typeLabel': '映射一致性'
                }
                findings.append(fallback_finding)

        total = len(findings)
        consistent_count = len([f for f in findings if f.get('status') == 'consistent'])
        inconsistent_count = len([f for f in findings if f.get('status') == 'inconsistent'])

        return {
            'success': True,
            'findings': findings,
            'summary': {
                'total_checks': total,
                'consistent_count': consistent_count,
                'inconsistent_count': inconsistent_count,
                'pass_rate': round((consistent_count / max(total, 1)) * 100, 1),
                'duration': 0
            }
        }


class SQLEngine:
    """SQL纠错引擎主类"""

    def __init__(self, upload_folder, config_file):
        self.upload_folder = upload_folder
        self.config_file = config_file
        self.tasks = {}
        self.lock = threading.Lock()

    def load_config(self):
        """加载Ollama配置，包含投票策略配置"""
        default_config = {
            'host': 'http://localhost:11434',
            'model': 'qwen2.5:7b',
            'timeout': 500,
            'use_voting_strategy': True,
            'voting_config': {
                'agent_count': 3,
                'consensus_threshold': 2,
                'parallel_fields': 3,
                'fast_mode': False,
                'agent_timeouts': {
                    'field_check': 500,
                    'relationship_checker': 500,
                    'field_mapping_checker': 500
                }
            }
        }
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'use_voting_strategy' not in config:
                    config['use_voting_strategy'] = True
                if 'voting_config' not in config:
                    config['voting_config'] = default_config['voting_config']
                else:
                    merged_voting = {**default_config['voting_config'], **config.get('voting_config', {})}
                    config['voting_config'] = merged_voting
                return config
        except:
            return default_config

    def preprocess_sql_content(self, sql_content):
        """预处理SQL内容，提取INSERT到最后一个COMMIT之间的有效部分
        
        Args:
            sql_content (str): 原始SQL内容
        
        Returns:
            str: 预处理后的有效SQL部分
        """
        if not sql_content or not sql_content.strip():
            return sql_content
        
        insert_match = re.search(r'INSERT\s+INTO', sql_content, re.IGNORECASE)
        
        commit_matches = list(re.finditer(r'COMMIT\s*;', sql_content, re.IGNORECASE))
        
        if insert_match:
            start_pos = insert_match.start()
            if commit_matches:
                end_pos = commit_matches[-1].end()
                effective_sql = sql_content[start_pos:end_pos]
                print(f'[SQL预处理] 提取INSERT到最后COMMIT: 第{start_pos}字符到第{end_pos}字符')
            else:
                effective_sql = sql_content[start_pos:]
                print(f'[SQL预处理] 未找到COMMIT，保留INSERT到末尾')
        else:
            effective_sql = sql_content
            print(f'[SQL预处理] 未找到INSERT，保留完整SQL')
        
        effective_sql = re.sub(r'--.*$', '', effective_sql, flags=re.MULTILINE)
        effective_sql = re.sub(r'/\*[\s\S]*?\*/', '', effective_sql)
        
        effective_sql = re.sub(r'\n\s*\n', '\n', effective_sql)
        
        print(f'[SQL预处理] 原始SQL: {len(sql_content)}字符, 预处理后: {len(effective_sql)}字符')
        
        return effective_sql.strip()

    def parse_insert_select_structure(self, sql_content):
        """解析INSERT SELECT结构，建立字段-取值映射
        
        SQL结构: INSERT INTO 表名 (字段列表) SELECT 取值列表 FROM ... WHERE ...
        
        Args:
            sql_content (str): SQL内容
        
        Returns:
            dict: {
                'insert_fields': ['UUID', 'LOAD_TIME', ...],
                'select_values': ['uuid()', 'CURRENT_TIMESTAMP()', ...],
                'field_mapping': {'UUID': 'uuid()', 'LOAD_TIME': 'CURRENT_TIMESTAMP()', ...},
                'from_clause': 'FROM ...',
                'where_clause': 'WHERE ...',
                'insert_mappings': [{...}, {...}, ...]  # 多分组支持，按INSERT顺序排列
            }
        """
        result = {
            'insert_fields': [],
            'select_values': [],
            'field_mapping': {},
            'from_clause': '',
            'where_clause': '',
            'insert_mappings': []  # 按顺序排列的INSERT映射列表
        }
        
        if not sql_content:
            return result
        
        insert_mappings = self._parse_multi_group_inserts(sql_content)
        if insert_mappings:
            result['insert_mappings'] = insert_mappings
            result['field_mapping'] = insert_mappings[0] if insert_mappings else {}
            print(f'[SQL结构解析] 检测到 {len(insert_mappings)} 个INSERT语句块（按顺序匹配IT-Mapping分组）')
            return result
        
        insert_pattern = r'INSERT\s+INTO\s+\w+(?:\s+PARTITION\s*\([^)]*\))?\s*\(([\s\S]*?)\)\s*SELECT'
        insert_match = re.search(insert_pattern, sql_content, re.IGNORECASE)
        
        if insert_match:
            fields_str = insert_match.group(1)
            fields = []
            for line in fields_str.split('\n'):
                line = re.sub(r'--.*$', '', line).strip()
                if line and not line.startswith('--'):
                    field = line.rstrip(',').strip()
                    if field:
                        fields.append(field)
            result['insert_fields'] = fields
            print(f'[SQL结构解析] INSERT字段列表: {len(fields)}个字段')
        
        select_pattern = r'SELECT\s+([\s\S]*?)\s+FROM\s+'
        select_match = re.search(select_pattern, sql_content, re.IGNORECASE)
        
        if select_match:
            select_str = select_match.group(1)
            values = self._parse_select_values(select_str)
            result['select_values'] = values
            print(f'[SQL结构解析] SELECT取值列表: {len(values)}个表达式')
        
        if result['insert_fields'] and result['select_values']:
            for i, field in enumerate(result['insert_fields']):
                if i < len(result['select_values']):
                    result['field_mapping'][field] = result['select_values'][i]
            print(f'[SQL结构解析] 字段-取值映射: {len(result["field_mapping"])}对')
        
        from_pattern = r'FROM\s+([\s\S]*?)(?:WHERE|$)'
        from_match = re.search(from_pattern, sql_content, re.IGNORECASE)
        if from_match:
            result['from_clause'] = 'FROM ' + from_match.group(1).strip()[:500]
        
        where_pattern = r'WHERE\s+([\s\S]*?)(?:COMMIT|;|$)'
        where_match = re.search(where_pattern, sql_content, re.IGNORECASE)
        if where_match:
            result['where_clause'] = 'WHERE ' + where_match.group(1).strip()[:500]
        
        return result

    def _parse_multi_group_inserts(self, sql_content):
        """解析多分组的INSERT语句
        
        识别SQL中的多个INSERT语句，按顺序返回每个INSERT的字段映射
        IT-Mapping的分组顺序与SQL文件中的INSERT顺序一致
        
        Args:
            sql_content (str): SQL内容
            
        Returns:
            list: [{字段名: SQL表达式}, ...] 按INSERT顺序排列的映射列表
        """
        insert_mappings = []
        
        insert_blocks = list(re.finditer(
            r'INSERT\s+INTO\s+\w+(?:\s+PARTITION\s*\([^)]*\))?\s*\(([\s\S]*?)\)\s*SELECT\s+([\s\S]*?)\s+FROM\s+',
            sql_content, 
            re.IGNORECASE
        ))
        
        if len(insert_blocks) <= 1:
            return []
        
        print(f'[_parse_multi_group_inserts] 检测到 {len(insert_blocks)} 个INSERT语句块（按顺序匹配IT-Mapping分组）')
        
        for idx, match in enumerate(insert_blocks):
            fields_str = match.group(1)
            select_str = match.group(2)
            
            fields = []
            for line in fields_str.split('\n'):
                line = re.sub(r'--.*$', '', line).strip()
                if line and not line.startswith('--'):
                    field = line.rstrip(',').strip()
                    if field:
                        fields.append(field)
            
            values = self._parse_select_values(select_str)
            
            field_mapping = {}
            for i, field in enumerate(fields):
                if i < len(values):
                    field_mapping[field] = values[i]
            
            if field_mapping:
                insert_mappings.append(field_mapping)
                print(f'[_parse_multi_group_inserts] INSERT #{idx + 1}: {len(field_mapping)} 个字段映射')
        
        return insert_mappings

    def _parse_select_values(self, select_str):
        """解析SELECT取值列表，处理嵌套括号
        
        Args:
            select_str (str): SELECT和FROM之间的字符串
        
        Returns:
            list: 取值表达式列表
        """
        values = []
        current = ''
        paren_depth = 0
        
        for char in select_str:
            if char == '(':
                paren_depth += 1
                current += char
            elif char == ')':
                paren_depth -= 1
                current += char
            elif char == ',' and paren_depth == 0:
                if current.strip():
                    values.append(current.strip())
                current = ''
            else:
                current += char
        
        if current.strip():
            values.append(current.strip())
        
        return values

    def build_field_sql_mapping(self, effective_sql, field_names):
        """建立字段名到SQL片段的映射表
        
        Args:
            effective_sql (str): 预处理后的SQL
            field_names (list): 字段名列表
        
        Returns:
            dict: {字段名: SQL片段} 映射表
        """
        if not effective_sql or not field_names:
            return {}
        
        field_mapping = {}
        lines = effective_sql.split('\n')
        
        # 预处理：移除注释，只保留有效SQL
        clean_lines = []
        in_comment = False
        for line in lines:
            # 处理多行注释
            if '/*' in line:
                in_comment = True
            if not in_comment:
                # 移除单行注释
                line = line.split('--')[0].strip()
                if line:
                    clean_lines.append(line)
            if '*/' in line:
                in_comment = False
        
        # 查找SELECT子句区域
        select_start = -1
        select_end = -1
        for i, line in enumerate(clean_lines):
            if line.upper().startswith('SELECT'):
                select_start = i
            elif select_start != -1 and (line.upper().startswith('FROM') or line.upper().startswith('WHERE') or line.upper().startswith('GROUP BY') or line.upper().startswith('ORDER BY')):
                select_end = i
                break
        
        # 如果找到SELECT子句，只在其中搜索字段
        if select_start != -1:
            search_lines = clean_lines[select_start:select_end if select_end != -1 else len(clean_lines)]
        else:
            search_lines = clean_lines
        
        for field_name in field_names:
            if not field_name or field_name == 'nan':
                continue
            
            found = False
            # 首先在SELECT子句中精确匹配字段
            for i, line in enumerate(search_lines):
                # 构建精确匹配模式，确保字段名是一个完整的标识符
                # 考虑字段别名的情况，如 "field_name AS alias"
                pattern = r'(^|,|\s)' + re.escape(field_name) + r'(\s|$|,|AS|as|\))'
                if re.search(pattern, line, re.IGNORECASE):
                    # 找到匹配的行，提取完整的字段定义
                    # 查找原始SQL中对应的行
                    # 构建更准确的匹配模式，考虑大小写和空格差异
                    field_pattern = re.escape(field_name)
                    for j, original_line in enumerate(lines):
                        # 构建匹配模式，确保字段名是一个完整的标识符
                        pattern = r'(^|,|\s)' + field_pattern + r'(\s|$|,|AS|as|\))'
                        if re.search(pattern, original_line, re.IGNORECASE):
                            # 只提取匹配的单行，保持与网页显示格式一致
                            snippet = original_line.strip()
                            field_mapping[field_name] = snippet
                            found = True
                            break
                    break
            
            # 如果在SELECT子句中未找到，回退到原始的搜索方法
            if not found:
                for i, line in enumerate(lines):
                    # 构建更精确的匹配模式
                    pattern = r'(^|,|\s)' + re.escape(field_name) + r'(\s|$|,|\))'
                    if re.search(pattern, line, re.IGNORECASE):
                        # 只提取匹配的单行，保持与网页显示格式一致
                        snippet = line.strip()
                        field_mapping[field_name] = snippet
                        found = True
                        break
            
            if not found:
                field_mapping[field_name] = f"未在SQL中找到字段 '{field_name}' 的相关代码"
        
        print(f'[字段映射] 已建立 {len(field_mapping)} 个字段的SQL片段映射')
        return field_mapping

    def parse_mapping_file(self, filename):
        """解析上传的Mapping文件"""
        filepath = os.path.join(self.upload_folder, filename)
        
        if not os.path.exists(filepath):
            return {'success': False, 'error': f'文件不存在: {filename}'}
        
        parser = MappingParser(filepath)
        result = parser.parse()
        
        if result['success']:
            result['summary'] = parser.get_mapping_summary()
            
            md_result = parser.generate_md_file()
            if md_result['success']:
                result['md_file_path'] = md_result['md_file_path']
            else:
                result['md_file_path'] = None
                result['md_error'] = md_result.get('error', 'MD文件生成失败')
            
            # 将数据存入数据库
            self._save_mapping_to_db(filename, result)
        
        return result
    
    def _save_mapping_to_db(self, mapping_file, result):
        """将IT-Mapping数据存入数据库
        
        Args:
            mapping_file: 映射文件名
            result: 解析结果
        """
        try:
            # 清除旧数据
            from services.history_service import HistoryService
            history_service = HistoryService()
            history_service.clear_mapping_data(mapping_file)
            
            # 保存数据源信息
            tables = result.get('tables', [])
            relationships = result.get('relationships', [])
            
            for table in tables:
                sheet_name = table.get('sheet_name', 'Unknown')
                alias = table.get('alias', 'T')
                name = table.get('name', '')
                
                # 查找该表的关联关系
                table_relationships = [r for r in relationships if r.get('table') == name]
                
                history_service.save_data_source(
                    mapping_file=mapping_file,
                    sheet_name=sheet_name,
                    alias=alias,
                    name=name,
                    relationships=table_relationships
                )
            
            # 保存字段映射信息
            field_mappings = result.get('field_mappings', [])
            for mapping in field_mappings:
                history_service.save_field_mapping(
                    mapping_file=mapping_file,
                    group_id=mapping.get('group_id', ''),
                    field_seq=mapping.get('field_seq', 0),
                    target_field=mapping.get('target_field', ''),
                    target_field_cn=mapping.get('target_field_cn', ''),
                    source_table_alias=mapping.get('source_table_alias', ''),
                    source_field=mapping.get('source_field', ''),
                    source_field_cn=mapping.get('source_field_cn', ''),
                    default_value=mapping.get('default_value', ''),
                    transformation_logic=mapping.get('transformation_logic', ''),
                    business_rule=mapping.get('business_rule', ''),
                    data_type=mapping.get('data_type', ''),
                    extract_method=mapping.get('extract_method', ''),
                    sheet=mapping.get('sheet', '')
                )
            
            print(f'[SQLEngine] IT-Mapping数据已成功存入数据库: {mapping_file}')
        except Exception as e:
            print(f'[SQLEngine] 保存IT-Mapping数据到数据库失败: {e}')
    
    def _load_mapping_from_db(self, mapping_file):
        """从数据库加载IT-Mapping数据
        
        Args:
            mapping_file: 映射文件名
            
        Returns:
            dict: 加载结果
        """
        try:
            from services.history_service import HistoryService
            history_service = HistoryService()
            
            # 从数据库获取数据
            data_sources = history_service.get_data_sources(mapping_file)
            field_mappings = history_service.get_field_mappings(mapping_file)
            
            if not data_sources and not field_mappings:
                return None
            
            # 构建结果
            tables = []
            relationships = []
            
            for source in data_sources:
                tables.append({
                    'sheet_name': source.get('sheet_name', 'Unknown'),
                    'alias': source.get('alias', 'T'),
                    'name': source.get('name', '')
                })
                
                # 添加关联关系
                source_relationships = source.get('relationships', [])
                relationships.extend(source_relationships)
            
            # 构建摘要
            summary = {
                'total_tables': len(tables),
                'total_fields': len(field_mappings),
                'total_relationships': len(relationships),
                'total_rules': 0,  # 暂时不统计规则
                'tables': [{'alias': t['alias'], 'name': t['name']} for t in tables]
            }
            
            return {
                'success': True,
                'tables': tables,
                'field_mappings': field_mappings,
                'relationships': relationships,
                'business_rules': [],  # 暂时不返回规则
                'summary': summary
            }
        except Exception as e:
            print(f'[SQLEngine] 从数据库加载IT-Mapping数据失败: {e}')
            return None

    def start_review_task(self, mapping_filename, sql_content, business_context='', dialect='Hive'):
        """启动纠错任务"""
        task_id = str(uuid.uuid4())
        
        # 将SQL内容存入数据库
        self._save_sql_to_db(task_id, f'sql_{task_id}.sql', sql_content)
        
        with self.lock:
            self.tasks[task_id] = {
                'task_id': task_id,
                'status': 'pending',
                'progress': 0,
                'current_step': 'parsing',
                'created_at': datetime.now().isoformat(),
                'mapping_filename': mapping_filename,
                'sql_content': sql_content,
                'business_context': business_context,
                'dialect': dialect,
                'result': None,
                'error': None
            }
        
        thread = threading.Thread(
            target=self._execute_review_task,
            args=(task_id,)
        )
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'data': {'task_id': task_id}}
    
    def _save_sql_to_db(self, sql_id, filename, content):
        """将SQL内容存入数据库
        
        Args:
            sql_id: SQL文件ID
            filename: 文件名
            content: SQL内容
        """
        try:
            from services.history_service import HistoryService
            history_service = HistoryService()
            history_service.save_sql_file(sql_id, filename, content)
            print(f'[SQLEngine] SQL文件已成功存入数据库: {filename}')
        except Exception as e:
            print(f'[SQLEngine] 保存SQL文件到数据库失败: {e}')
    
    def _load_sql_from_db(self, sql_id):
        """从数据库加载SQL内容
        
        Args:
            sql_id: SQL文件ID
            
        Returns:
            str: SQL内容
        """
        try:
            from services.history_service import HistoryService
            history_service = HistoryService()
            sql_file = history_service.get_sql_file(sql_id)
            if sql_file:
                return sql_file.get('content', '')
            return ''
        except Exception as e:
            print(f'[SQLEngine] 从数据库加载SQL文件失败: {e}')
            return ''

    def _execute_review_task(self, task_id):
        """在后台线程中执行纠错任务，支持三Agent投票策略"""
        start_time = time.time()

        try:
            config = self.load_config()
            use_voting = config.get('use_voting_strategy', True)

            if use_voting:
                self._execute_voting_review_task(task_id, config, start_time)
            else:
                self._execute_legacy_review_task(task_id, config, start_time)

        except Exception as e:
            print(f'Task {task_id} error: {e}')
            with self.lock:
                if task_id in self.tasks:
                    self.tasks[task_id]['status'] = 'error'
                    self.tasks[task_id]['progress'] = 0
                    self.tasks[task_id]['current_step'] = 'error'
                    self.tasks[task_id]['error'] = str(e)

    def _execute_voting_review_task(self, task_id, config, start_time):
        """新工作流：解析Excel → 生成MD → 遍历字段 → 三Agent投票 → 逐字段存储到数据库 → 从数据库读取聚合结果"""
        try:
            self._update_task_status(task_id, 'running', 10, 'parsing')

            # 优先从数据库加载IT-Mapping数据
            mapping_file = self.tasks[task_id]['mapping_filename']
            mapping_result = self._load_mapping_from_db(mapping_file)
            
            # 如果数据库中没有数据，则解析文件
            if not mapping_result:
                mapping_result = self.parse_mapping_file(mapping_file)
                if not mapping_result['success']:
                    raise Exception(f'Mapping文件解析失败: {mapping_result.get("error")}')

            md_file_path = mapping_result.get('md_file_path')
            md_content = ''
            if md_file_path and os.path.exists(md_file_path):
                with open(md_file_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()

            field_mappings = mapping_result.get('field_mappings', [])
            sql_content = self.tasks[task_id]['sql_content']

            # 提取数据源表信息（从数据源sheet）
            data_source_info = self._extract_data_source_info(mapping_file)
            self.tasks[task_id]['data_source_info'] = data_source_info

            effective_sql = self.preprocess_sql_content(sql_content)

            field_names = [fm.get('target_field', '') for fm in field_mappings if fm.get('target_field')]
            field_sql_mapping = self.build_field_sql_mapping(effective_sql, field_names)

            sql_structure = self.parse_insert_select_structure(effective_sql)
            self.tasks[task_id]['sql_structure'] = sql_structure

            if sql_structure.get('field_mapping'):
                field_sql_mapping = sql_structure['field_mapping']
                print(f'[VotingTask] 使用结构化字段映射: {len(field_sql_mapping)}对')

            self.tasks[task_id]['field_sql_mapping'] = field_sql_mapping
            self.tasks[task_id]['effective_sql'] = effective_sql

            voting_config = config.get('voting_config', {})
            merged_config = {**config, **voting_config}
            voter = TripleAgentVoter(merged_config)

            from services.history_service import HistoryService
            hs = HistoryService()
            hs.clear_field_check_results(task_id)

            total_fields = len(field_mappings)
            print(f'[VotingTask] 开始对 {total_fields} 个字段进行三Agent投票检查（并行处理模式）...')

            self._update_task_status(task_id, 'running', 30, 'voting', total_fields=total_fields)

            parallel_fields = config.get('voting_config', {}).get('parallel_fields', 3)
            fast_mode = config.get('voting_config', {}).get('fast_mode', False)

            parallel_fields = min(parallel_fields, 10)

            completed_count = 0
            progress_lock = threading.Lock()
            task_start_time = time.time()

            def process_single_field(idx, field_info):
                nonlocal completed_count
                field_name = field_info.get('target_field', '未知字段')
                excel_row = idx + 1

                print(f'[ParallelFieldCheck] 开始检查字段 {idx + 1}/{total_fields}: {field_name}')

                vote_result = voter.vote_on_field(
                    field_info, sql_content, md_content, 
                    fast_mode=fast_mode, 
                    field_sql_mapping=field_sql_mapping,
                    sql_structure=sql_structure,
                    data_source_info=data_source_info
                )

                hs.save_field_check_result(
                    task_id=task_id,
                    excel_row=excel_row,
                    field_name=field_name,
                    final_status=vote_result.get('final_status', 'needs_review'),
                    confidence=vote_result.get('confidence', 0.0),
                    vote_details=vote_result.get('vote_details', {}),
                    agent_results=vote_result.get('agent_results', []),
                    merged_findings=vote_result.get('merged_findings', [])
                )

                with progress_lock:
                    completed_count += 1
                    progress = 30 + int((completed_count / max(total_fields, 1)) * 60)
                    
                    elapsed = time.time() - task_start_time
                    if completed_count > 0:
                        avg_time_per_field = elapsed / completed_count
                        remaining_fields = total_fields - completed_count
                        estimated_remaining = int(avg_time_per_field * remaining_fields)
                    else:
                        estimated_remaining = 0
                    
                    active_workers = min(parallel_fields, total_fields - completed_count + 1)
                    parallel_status = f'正在并行处理 {active_workers}/{total_fields} 个字段'
                    
                    self._update_task_status(
                        task_id, 'running', progress, 'voting',
                        current_field=field_name,
                        completed_fields=completed_count,
                        total_fields=total_fields,
                        estimated_remaining_time=estimated_remaining,
                        parallel_status=parallel_status
                    )

                print(f'[ParallelFieldCheck] 字段 {field_name} 检查完成 ({completed_count}/{total_fields})')
                return vote_result

            with ThreadPoolExecutor(max_workers=parallel_fields) as executor:
                futures = {
                    executor.submit(process_single_field, idx, field_info): (idx, field_info)
                    for idx, field_info in enumerate(field_mappings)
                }

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        idx, field_info = futures[future]
                        print(f'[ParallelFieldCheck] 字段 {field_info.get("target_field")} 检查失败: {e}')

            self._update_task_status(task_id, 'running', 95, 'merging')
            
            db_results = hs.get_field_check_results(task_id)
            sql_content = self.tasks[task_id].get('sql_content', '')
            final_result = self._aggregate_vote_results_from_db(db_results, mapping_result, sql_content)

            duration = int(time.time() - start_time)
            final_result['duration'] = duration

            with self.lock:
                if task_id in self.tasks:
                    self.tasks[task_id]['status'] = 'completed'
                    self.tasks[task_id]['progress'] = 100
                    self.tasks[task_id]['current_step'] = 'done'
                    self.tasks[task_id]['result'] = final_result

            # 保存所有字段的映射信息到数据库，确保Excel报告包含完整字段列表
            sql_structure = self.tasks[task_id].get('sql_structure')
            self._save_all_field_mappings(task_id, field_mappings, sql_content, final_result, sql_structure)

            self._save_to_history(task_id, final_result, duration)

            print(f'[VotingTask] 任务 {task_id} 完成，耗时 {duration} 秒')

        except Exception as e:
            print(f'[VotingTask] 任务 {task_id} 执行失败: {e}')
            raise

    def _execute_legacy_review_task(self, task_id, config, start_time):
        """原有双Agent模式工作流（向后兼容）"""
        try:
            self._update_task_status(task_id, 'running', 10, 'parsing')

            mapping_result = self.parse_mapping_file(self.tasks[task_id]['mapping_filename'])

            if not mapping_result['success']:
                raise Exception(f'Mapping文件解析失败: {mapping_result.get("error")}')

            self._update_task_status(task_id, 'running', 30, 'agents')

            ollama_client = OllamaClient(config)

            analysis_result = ollama_client.analyze_sql_mapping(
                mapping_data=mapping_result,
                sql_content=self.tasks[task_id]['sql_content'],
                business_context=self.tasks[task_id]['business_context']
            )

            if not analysis_result['success']:
                raise Exception(analysis_result.get('error', 'AI分析失败'))

            duration = int(time.time() - start_time)
            analysis_result['duration'] = duration

            with self.lock:
                if task_id in self.tasks:
                    self.tasks[task_id]['status'] = 'completed'
                    self.tasks[task_id]['progress'] = 100
                    self.tasks[task_id]['current_step'] = 'done'
                    self.tasks[task_id]['result'] = analysis_result

            self._save_to_history(task_id, analysis_result, duration)

        except Exception as e:
            print(f'[LegacyTask] 任务 {task_id} 执行失败: {e}')
            raise

    def _convert_vote_to_finding(self, vote_result, finding_id):
        """将投票结果转换为finding格式

        Args:
            vote_result (dict): TripleAgentVoter.vote_on_field() 返回的投票结果
            finding_id (int): finding的ID序号

        Returns:
            dict: 标准格式的finding字典
        """
        field_name = vote_result.get('field', '未知字段')
        final_status = vote_result.get('final_status', 'needs_review')
        vote_details = vote_result.get('vote_details', {})
        confidence = vote_result.get('confidence', 0.0)
        merged_findings = vote_result.get('merged_findings', [])

        status_mapping = {
            'consistent': 'consistent',
            'inconsistent': 'inconsistent',
            'needs_review': 'warning',
            'all_failed': 'error'
        }

        severity_mapping = {
            'consistent': 'low',
            'inconsistent': 'high',
            'needs_review': 'medium',
            'all_failed': 'critical'
        }

        status = status_mapping.get(final_status, 'warning')
        severity = severity_mapping.get(final_status, 'medium')

        primary_issue = ''
        primary_explanation = ''
        primary_suggestion = ''
        mapping_ref = {'target': field_name, 'logic': ''}

        if merged_findings:
            for mf in merged_findings:
                if mf.get('status') == 'inconsistent' and mf.get('issue'):
                    primary_issue = mf.get('issue', '')
                    primary_explanation = mf.get('explanation', '')
                    primary_suggestion = mf.get('suggestion', '')
                    mapping_ref = mf.get('mapping_ref', mapping_ref)
                    break

            if not primary_issue:
                for mf in merged_findings:
                    if mf.get('issue'):
                        primary_issue = mf.get('issue', '')
                        primary_explanation = mf.get('explanation', '')
                        primary_suggestion = mf.get('suggestion', '')
                        mapping_ref = mf.get('mapping_ref', mapping_ref)
                        break

        if final_status == 'consistent':
            primary_issue = '字段实现与Mapping一致'
            primary_explanation = f'三Agent投票结果：{vote_details.get("consistent", 0)}/3 认为一致'
            primary_suggestion = ''
        elif final_status == 'all_failed':
            primary_issue = '所有Agent检查均失败'
            primary_explanation = '三Agent投票过程中所有Agent均未能完成检查，请检查AI服务状态'
            primary_suggestion = '建议检查Ollama服务状态或增加超时时间'

        vote_summary = f"投票结果: 一致={vote_details.get('consistent', 0)}, 不一致={vote_details.get('inconsistent', 0)}, 警告={vote_details.get('warning', 0)}, 失败={vote_details.get('error', 0)}"

        finding = {
            'id': finding_id,
            'status': status,
            'agent': 'triple_agent_voter',
            'location': f'字段: {field_name}',
            'issue': primary_issue,
            'explanation': f'{primary_explanation}\n{vote_summary}',
            'original_sql': '',
            'mapping_ref': mapping_ref,
            'suggestion': primary_suggestion,
            'severity': severity,
            'type': 'field_consistency',
            'typeLabel': '字段一致性检查',
            'confidence': confidence,
            'vote_details': vote_details,
            'agent_results': vote_result.get('agent_results', [])
        }

        return finding

    def _aggregate_vote_results(self, all_findings, vote_results, mapping_result):
        """聚合所有投票结果

        Args:
            all_findings (list): 所有finding列表
            vote_results (list): 所有投票结果列表
            mapping_result (dict): 原始映射解析结果

        Returns:
            dict: 聚合后的最终结果
        """
        consistent_count = len([f for f in all_findings if f.get('status') == 'consistent'])
        inconsistent_count = len([f for f in all_findings if f.get('status') == 'inconsistent'])
        warning_count = len([f for f in all_findings if f.get('status') == 'warning'])
        error_count = len([f for f in all_findings if f.get('status') == 'error'])

        total_checks = len(all_findings)

        avg_confidence = 0.0
        if vote_results:
            confidences = [vr.get('confidence', 0.0) for vr in vote_results]
            avg_confidence = round(sum(confidences) / len(confidences), 2)

        status_distribution = {
            'consistent': consistent_count,
            'inconsistent': inconsistent_count,
            'warning': warning_count,
            'error': error_count
        }

        pass_rate = round((consistent_count / max(total_checks, 1)) * 100, 1)

        final_result = {
            'success': True,
            'findings': all_findings,
            'summary': {
                'total_checks': total_checks,
                'consistent_count': consistent_count,
                'inconsistent_count': inconsistent_count,
                'warning_count': warning_count,
                'error_count': error_count,
                'pass_rate': pass_rate,
                'avg_confidence': avg_confidence,
                'status_distribution': status_distribution,
                'strategy': 'triple_agent_voting',
                'agent_count': 3
            },
            'mapping_summary': mapping_result.get('summary', {}),
            'vote_statistics': {
                'total_fields': total_checks,
                'avg_confidence': avg_confidence,
                'status_distribution': status_distribution
            }
        }

        print(f'[ResultAggregator] 聚合完成:')
        print(f'  - 总字段数: {total_checks}')
        print(f'  - 一致: {consistent_count}, 不一致: {inconsistent_count}, 警告: {warning_count}, 错误: {error_count}')
        print(f'  - 通过率: {pass_rate}%')
        print(f'  - 平均置信度: {avg_confidence}')

        return final_result

    def _aggregate_vote_results_from_db(self, db_results, mapping_result, sql_content=''):
        """从数据库读取的字段检查结果聚合为最终结果

        Args:
            db_results (list): 从数据库获取的字段检查结果列表
            mapping_result (dict): 原始映射解析结果
            sql_content (str): 原始SQL内容，用于提取代码片段

        Returns:
            dict: 聚合后的最终结果
        """
        all_findings = []
        
        for db_record in db_results:
            excel_row = db_record.get('excel_row', 0)
            field_name = db_record.get('field_name', '未知字段')
            final_status = db_record.get('final_status', 'needs_review')
            confidence = db_record.get('confidence', 0.0)
            vote_details = db_record.get('vote_details', {})
            agent_results = db_record.get('agent_results', [])
            merged_findings = db_record.get('merged_findings', [])

            status_mapping = {
                'consistent': 'consistent',
                'inconsistent': 'inconsistent',
                'needs_review': 'warning',
                'all_failed': 'error'
            }

            severity_mapping = {
                'consistent': 'low',
                'inconsistent': 'high',
                'needs_review': 'medium',
                'all_failed': 'critical'
            }

            status = status_mapping.get(final_status, 'warning')
            severity = severity_mapping.get(final_status, 'medium')

            primary_issue = ''
            primary_explanation = ''
            primary_suggestion = ''
            mapping_ref = {'target': field_name, 'logic': ''}

            if merged_findings:
                for mf in merged_findings:
                    if mf.get('status') == 'inconsistent' and mf.get('issue'):
                        primary_issue = mf.get('issue', '')
                        primary_explanation = mf.get('explanation', '')
                        primary_suggestion = mf.get('suggestion', '')
                        mapping_ref = mf.get('mapping_ref', mapping_ref)
                        break

                if not primary_issue:
                    for mf in merged_findings:
                        if mf.get('issue'):
                            primary_issue = mf.get('issue', '')
                            primary_explanation = mf.get('explanation', '')
                            primary_suggestion = mf.get('suggestion', '')
                            mapping_ref = mf.get('mapping_ref', mapping_ref)
                            break

            if final_status == 'consistent':
                primary_issue = '字段实现与Mapping一致'
                primary_explanation = f'三Agent投票结果：{vote_details.get("consistent", 0)}/3 认为一致'
                primary_suggestion = ''
            elif final_status == 'all_failed':
                primary_issue = '所有Agent检查均失败'
                primary_explanation = '三Agent投票过程中所有Agent均未能完成检查，请检查AI服务状态'
                primary_suggestion = '建议检查Ollama服务状态或增加超时时间'

            vote_summary = f"投票结果: 一致={vote_details.get('consistent', 0)}, 不一致={vote_details.get('inconsistent', 0)}, 警告={vote_details.get('warning', 0)}, 失败={vote_details.get('error', 0)}"

            original_sql_snippet = self._extract_sql_snippet_for_field(sql_content, field_name)

            finding = {
                'id': excel_row,
                'status': status,
                'agent': 'triple_agent_voter',
                'location': f'字段: {field_name} (Excel行号: {excel_row})',
                'issue': primary_issue,
                'explanation': f'{primary_explanation}\n{vote_summary}',
                'original_sql': original_sql_snippet,
                'mapping_ref': mapping_ref,
                'suggestion': primary_suggestion,
                'severity': severity,
                'type': 'field_consistency',
                'typeLabel': '字段一致性检查',
                'confidence': confidence,
                'vote_details': vote_details,
                'agent_results': agent_results,
                'excel_row': excel_row
            }

            all_findings.append(finding)

        consistent_count = len([f for f in all_findings if f.get('status') == 'consistent'])
        inconsistent_count = len([f for f in all_findings if f.get('status') == 'inconsistent'])
        warning_count = len([f for f in all_findings if f.get('status') == 'warning'])
        error_count = len([f for f in all_findings if f.get('status') == 'error'])

        total_checks = len(all_findings)

        avg_confidence = 0.0
        if db_results:
            confidences = [r.get('confidence', 0.0) for r in db_results]
            avg_confidence = round(sum(confidences) / len(confidences), 2)

        status_distribution = {
            'consistent': consistent_count,
            'inconsistent': inconsistent_count,
            'warning': warning_count,
            'error': error_count
        }

        pass_rate = round((consistent_count / max(total_checks, 1)) * 100, 1)

        final_result = {
            'success': True,
            'findings': all_findings,
            'summary': {
                'total_checks': total_checks,
                'consistent_count': consistent_count,
                'inconsistent_count': inconsistent_count,
                'warning_count': warning_count,
                'error_count': error_count,
                'pass_rate': pass_rate,
                'avg_confidence': avg_confidence,
                'status_distribution': status_distribution,
                'strategy': 'triple_agent_voting_with_db_storage',
                'agent_count': 3,
                'storage_mode': 'database_incremental'
            },
            'mapping_summary': mapping_result.get('summary', {}),
            'vote_statistics': {
                'total_fields': total_checks,
                'avg_confidence': avg_confidence,
                'status_distribution': status_distribution
            }
        }

        print(f'[ResultAggregator-DB] 从数据库聚合完成:')
        print(f'  - 总字段数: {total_checks}')
        print(f'  - 一致: {consistent_count}, 不一致: {inconsistent_count}, 警告: {warning_count}, 错误: {error_count}')
        print(f'  - 通过率: {pass_rate}%')
        print(f'  - 平均置信度: {avg_confidence}')

        return final_result

    def _extract_sql_snippet_for_field(self, sql_content, field_name):
        """从SQL内容中提取包含指定字段名的代码行

        Args:
            sql_content (str): 原始SQL内容
            field_name (str): 字段名

        Returns:
            str: 包含该字段的SQL代码行
        """
        if not sql_content or not field_name:
            return ''
        
        lines = sql_content.split('\n')
        
        select_pattern = rf'.*\bAS\s+{re.escape(field_name)}\b.*'
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('--'):
                continue
            if re.match(select_pattern, line_stripped, re.IGNORECASE):
                return line_stripped
        
        assignment_pattern = rf'.*[\'"].*\bAS\s+{re.escape(field_name)}\b.*'
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('--'):
                continue
            if re.match(assignment_pattern, line_stripped, re.IGNORECASE):
                return line_stripped
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('--'):
                continue
            
            patterns = [
                rf'\bAS\s+{re.escape(field_name)}\b',
                rf'{re.escape(field_name)}\s*,',
                rf',\s*{re.escape(field_name)}\b',
                rf'\b{re.escape(field_name)}\s*=',
            ]
            
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    if 'SELECT' in line_stripped.upper() or 'AS' in line_stripped.upper():
                        return line_stripped
        
        return ''

    def _extract_data_source_info(self, mapping_file):
        """从Excel文件中提取数据源表信息
        
        Args:
            mapping_file (str): Mapping文件名
            
        Returns:
            dict: 按分组ID组织的数据源表信息
        """
        try:
            from excel_parser import extract_groups_from_excel, load_excel
            import os
            
            file_path = os.path.join(self.upload_folder, mapping_file)
            if not os.path.exists(file_path):
                print(f'[_extract_data_source_info] 文件不存在: {file_path}')
                return {}
            
            workbook = load_excel(file_path)
            from excel_parser import GroupExtractor
            extractor = GroupExtractor(workbook)
            groups = extractor.extract_all_groups()
            workbook.close()
            
            result = {}
            for group_id, group_info in groups.items():
                tables = []
                for table in group_info.数据源表:
                    tables.append({
                        'alias': table.数据表别名,
                        'name_cn': table.数据表名_中文,
                        'name_en': table.数据表名_英文
                    })
                
                joins = []
                for join in group_info.表间关联:
                    joins.append({
                        'left_table': join.左表别名,
                        'left_field': join.左字段名,
                        'join_type': join.关联类型,
                        'right_table': join.右表别名,
                        'right_field': join.右字段名
                    })
                
                filters = []
                for f in group_info.筛选条件:
                    filters.append({
                        'table': f.表别名,
                        'field': f.字段名,
                        'condition': f.条件,
                        'value': f.值
                    })
                
                result[group_id] = {
                    'group_name': group_info.组别名称,
                    'tables': tables,
                    'joins': joins,
                    'filters': filters
                }
            
            print(f'[_extract_data_source_info] 提取了 {len(result)} 个分组的数据源信息')
            return result
            
        except Exception as e:
            print(f'[_extract_data_source_info] 提取数据源信息失败: {e}')
            import traceback
            traceback.print_exc()
            return {}

    def _save_all_field_mappings(self, task_id, field_mappings, sql_content, final_result, sql_structure=None):
        """保存所有字段的映射信息到数据库，确保Excel报告包含完整字段列表

        Args:
            task_id (str): 任务ID
            field_mappings (list): 所有字段的映射信息
            sql_content (str): 原始SQL内容
            final_result (dict): 最终检查结果
            sql_structure (dict): SQL结构化解析结果（可选，用于确保SQL表达式一致性）
        """
        try:
            from services.history_service import HistoryService
            hs = HistoryService()

            # 打印分组统计信息
            group_ids_ordered = []
            for fm in field_mappings:
                gid = fm.get('group_id', '')
                if gid and gid not in group_ids_ordered:
                    group_ids_ordered.append(gid)
            print(f'[_save_all_field_mappings] 字段映射包含 {len(field_mappings)} 个字段，分组顺序: {group_ids_ordered}')

            inconsistent_fields = set()
            for f in final_result.get('findings', []):
                if f.get('status') == 'inconsistent':
                    field_name = f.get('location', '').split(': ')[-1].split(' (')[0]
                    if field_name:
                        inconsistent_fields.add(field_name)
                    field_name_alt = f.get('field_name', '')
                    if field_name_alt:
                        inconsistent_fields.add(field_name_alt)

            field_names = [fm.get('target_field', '') for fm in field_mappings if fm.get('target_field')]
            
            # 获取INSERT映射列表（按顺序）
            insert_mappings = []
            if sql_structure and sql_structure.get('insert_mappings'):
                insert_mappings = sql_structure['insert_mappings']
                print(f'[_save_all_field_mappings] 使用INSERT映射列表: {len(insert_mappings)}个INSERT块')
            elif sql_structure and sql_structure.get('field_mapping'):
                insert_mappings = [sql_structure['field_mapping']]
                print(f'[_save_all_field_mappings] 使用单一字段映射: {len(sql_structure["field_mapping"])}对')
            else:
                field_sql_mapping = self.build_field_sql_mapping(sql_content, field_names)
                insert_mappings = [field_sql_mapping]
                print(f'[_save_all_field_mappings] 使用build_field_sql_mapping: {len(field_sql_mapping)}对')

            # 构建分组ID到INSERT映射的对应关系（按顺序匹配）
            group_to_insert_idx = {}
            for idx, group_id in enumerate(group_ids_ordered):
                if idx < len(insert_mappings):
                    group_to_insert_idx[group_id] = idx

            # 保存所有字段的映射信息
            dataset_results = []
            datamap_results = []

            for fm in field_mappings:
                target_field = fm.get('target_field', '')
                if not target_field:
                    continue

                is_inconsistent = target_field in inconsistent_fields

                # 根据分组ID选择正确的SQL表达式（按顺序匹配）
                group_id = fm.get('group_id', '')
                field_sql_mapping = {}
                if group_id in group_to_insert_idx:
                    insert_idx = group_to_insert_idx[group_id]
                    field_sql_mapping = insert_mappings[insert_idx]
                elif insert_mappings:
                    field_sql_mapping = insert_mappings[0]

                # 构建数据映射结果
                datamap_result = {
                    'group_id': group_id,
                    'field_seq': fm.get('field_seq', 0),
                    'target_field_cn': fm.get('target_field_cn', ''),
                    'target_field_en': target_field,
                    'extract_method': fm.get('extract_method', ''),
                    'source_table': fm.get('source_table_alias', ''),
                    'source_field_en': fm.get('source_field', ''),
                    'source_field_cn': fm.get('source_field_cn', ''),
                    'default_value': fm.get('default_value', ''),
                    'transform_logic': fm.get('transformation_logic', ''),
                    'sql_expression': field_sql_mapping.get(target_field, ''),
                    'is_consistent': '否' if is_inconsistent else '是',
                    'remark': '字段未在SQL中找到' if not field_sql_mapping.get(target_field) else ''
                }

                datamap_results.append(datamap_result)

            # 批量保存数据映射结果（不清除其他分组数据）
            if datamap_results:
                hs.save_datamap_comparison_batch(task_id, datamap_results, clear_existing=False)
                print(f'[SQLEngine] 已保存 {len(datamap_results)} 个字段的完整映射信息到数据库')

        except Exception as e:
            print(f'[SQLEngine] 保存字段映射信息失败: {e}')

    def _save_to_history(self, task_id, result, duration):
        """保存任务结果到历史记录

        Args:
            task_id (str): 任务ID
            result (dict): 任务执行结果
            duration (int): 执行耗时（秒）
        """
        try:
            from services.history_service import HistoryService
            hs = HistoryService()

            task_data = self.tasks.get(task_id, {})
            history_data = {
                'task_id': task_id,
                'mapping_file': task_data.get('mapping_filename', ''),
                'sql_filename': task_data.get('sql_filename', ''),
                'status': 'completed',
                'total_checks': result.get('summary', {}).get('total_checks', 0),
                'consistent_count': result.get('summary', {}).get('consistent_count', 0),
                'inconsistent_count': result.get('summary', {}).get('inconsistent_count', 0),
                'duration': duration,
                'findings': result.get('findings', []),
                'summary_text': '',
                'strategy': result.get('summary', {}).get('strategy', 'unknown')
            }

            save_success = hs.save_review_result(task_id, history_data)
            if save_success:
                print(f'[SQLEngine] 任务 {task_id} 结果已自动保存到数据库')
            else:
                print(f'[SQLEngine] 任务 {task_id} 结果保存失败，将在前端请求时重试')
        except Exception as db_error:
            print(f'[SQLEngine] 自动保存到数据库失败: {db_error}，将在前端请求时重试')

    def _update_task_status(self, task_id, status, progress, step, **kwargs):
        """更新任务状态，支持详细的进度信息
        
        Args:
            task_id (str): 任务ID
            status (str): 任务状态
            progress (int): 进度百分比
            step (str): 当前步骤
            **kwargs: 额外的进度信息字段，支持:
                - current_field: 当前正在检查的字段名称
                - completed_fields: 已完成的字段数
                - total_fields: 总字段数
                - estimated_remaining_time: 预估剩余时间（秒）
                - parallel_status: 并行处理状态描述
        """
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = status
                self.tasks[task_id]['progress'] = progress
                self.tasks[task_id]['current_step'] = step
                
                if 'current_field' in kwargs:
                    self.tasks[task_id]['current_field'] = kwargs['current_field']
                if 'completed_fields' in kwargs:
                    self.tasks[task_id]['completed_fields'] = kwargs['completed_fields']
                if 'total_fields' in kwargs:
                    self.tasks[task_id]['total_fields'] = kwargs['total_fields']
                if 'estimated_remaining_time' in kwargs:
                    self.tasks[task_id]['estimated_remaining_time'] = kwargs['estimated_remaining_time']
                if 'parallel_status' in kwargs:
                    self.tasks[task_id]['parallel_status'] = kwargs['parallel_status']

    def get_task_progress(self, task_id):
        """获取任务进度，返回详细的进度信息"""
        with self.lock:
            if task_id not in self.tasks:
                return {'success': False, 'error': '任务不存在'}
            
            task = self.tasks[task_id]
            
            progress_info = {
                'success': True,
                'data': {
                    'task_id': task_id,
                    'status': task['status'],
                    'progress': task['progress'],
                    'current_step': task['current_step'],
                    'current_field': task.get('current_field', ''),
                    'completed_fields': task.get('completed_fields', 0),
                    'total_fields': task.get('total_fields', 0),
                    'estimated_remaining_time': task.get('estimated_remaining_time', 0),
                    'parallel_status': task.get('parallel_status', '')
                }
            }
            
            if task['status'] == 'completed' and task.get('result'):
                summary = task['result'].get('summary', {})
                progress_info['data']['summary'] = {
                    'total_checks': summary.get('total_checks', 0),
                    'consistent_count': summary.get('consistent_count', 0),
                    'inconsistent_count': summary.get('inconsistent_count', 0),
                    'pass_rate': summary.get('pass_rate', 0)
                }
            
            return progress_info

    def get_task_result(self, task_id):
        """获取任务结果（优先内存，回退数据库）"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]

                if task['status'] != 'completed':
                    return {'success': False, 'error': '任务尚未完成', 'status': task['status']}

                result = task['result']

                return {
                    'success': True,
                    'data': {
                        'task_id': task_id,
                        'status': 'completed',
                        'total_checks': result['summary']['total_checks'],
                        'consistent_count': result['summary']['consistent_count'],
                        'inconsistent_count': result['summary']['inconsistent_count'],
                        'duration': result['duration'],
                        'agents_count': 7,
                        'findings': result['findings'],
                        'sql_content': task.get('sql_content', ''),
                        'mapping_file': task.get('mapping_filename', ''),
                        'sql_filename': task.get('sql_filename', '')
                    }
                }

        try:
            from services.history_service import HistoryService
            hs = HistoryService()
            record = hs.get_record(task_id)

            if not record:
                return {'success': False, 'error': '任务不存在'}

            findings = record.get('findings', [])
            if isinstance(findings, str):
                import json
                try:
                    findings = json.loads(findings)
                except:
                    findings = []

            return {
                'success': True,
                'data': {
                    'task_id': task_id,
                    'status': record.get('status', 'completed'),
                    'total_checks': record.get('total_checks', 0),
                    'consistent_count': record.get('consistent_count', 0),
                    'inconsistent_count': record.get('inconsistent_count', 0),
                    'duration': record.get('duration', 0),
                    'agents_count': 7,
                    'findings': findings,
                    'sql_content': record.get('sql_content', ''),
                    'mapping_file': record.get('mapping_file', ''),
                    'sql_filename': record.get('sql_filename', '')
                }
            }

        except Exception as e:
            print(f'[SQLEngine] 从数据库加载任务结果失败: {e}')
            return {'success': False, 'error': f'任务不存在或加载失败: {str(e)}'}


@dataclass
class GroupComparisonResult:
    """分组对比结果"""
    group_id: str
    group_name: str
    status: str
    field_count: int
    consistent_fields: int
    inconsistent_fields: int
    details: List[Dict] = field(default_factory=list)
    field_comparison: Dict = field(default_factory=dict)
    source_table_comparison: Dict = field(default_factory=dict)
    join_comparison: Dict = field(default_factory=dict)
    filter_comparison: Dict = field(default_factory=dict)


@dataclass
class OverallComparisonResult:
    """总体对比结果"""
    summary: Dict = field(default_factory=dict)
    groups: List[GroupComparisonResult] = field(default_factory=list)
    total_groups: int = 0
    passed_groups: int = 0
    failed_groups: int = 0
    overall_consistency_rate: float = 0.0


class GroupComparisonAgent:
    """分组对比Agent - 按分组进行SQL与IT-Mapping的对比检查
    
    支持分组级别的对比：
    - 字段映射对比
    - 数据源表对比
    - JOIN条件对比
    - 筛选条件对比
    
    支持并行处理多个分组
    """
    
    def __init__(self, config: Dict = None):
        self.host = config.get('host', 'http://localhost:11434') if config else 'http://localhost:11434'
        self.model = config.get('model', 'qwen2.5:7b') if config else 'qwen2.5:7b'
        self.timeout = config.get('timeout', 180) if config else 180
        self.max_workers = config.get('max_workers', 4) if config else 4
        self.debug = config.get('debug', False) if config else False
    
    def compare_groups(
        self,
        mapping_groups: Dict[str, Any],
        sql_blocks: List[Any],
        parallel: bool = True
    ) -> OverallComparisonResult:
        """对比IT-Mapping分组与SQL分组
        
        Args:
            mapping_groups: IT-Mapping分组信息字典 {group_id: GroupInfo/GroupFieldMapping}
            sql_blocks: SQL分组信息列表 [InsertBlock]
            parallel: 是否并行处理
            
        Returns:
            OverallComparisonResult: 总体对比结果
        """
        overall_result = OverallComparisonResult()
        
        group_pairs = self._match_groups(mapping_groups, sql_blocks)
        
        if self.debug:
            print(f'[GroupComparisonAgent] 匹配到 {len(group_pairs)} 个分组对')
        
        if parallel and len(group_pairs) > 1:
            group_results = self._parallel_compare_groups(group_pairs)
        else:
            group_results = self._sequential_compare_groups(group_pairs)
        
        overall_result.groups = group_results
        overall_result.total_groups = len(group_results)
        overall_result.passed_groups = sum(1 for g in group_results if g.status == 'passed')
        overall_result.failed_groups = sum(1 for g in group_results if g.status == 'failed')
        
        overall_result.summary = self._aggregate_summary(group_results)
        
        total_fields = sum(g.field_count for g in group_results)
        total_consistent = sum(g.consistent_fields for g in group_results)
        overall_result.overall_consistency_rate = (
            total_consistent / total_fields * 100 if total_fields > 0 else 0.0
        )
        
        return overall_result
    
    def _match_groups(
        self,
        mapping_groups: Dict[str, Any],
        sql_blocks: List[Any]
    ) -> List[Tuple[Any, Any]]:
        """匹配IT-Mapping分组与SQL分组
        
        Args:
            mapping_groups: IT-Mapping分组信息
            sql_blocks: SQL分组信息
            
        Returns:
            匹配的分组对列表 [(mapping_group, sql_block), ...]
        """
        pairs = []
        
        sql_block_map = {}
        for block in sql_blocks:
            group_id = getattr(block, 'group_id', '') or block.get('group_id', '')
            if group_id:
                sql_block_map[group_id.upper()] = block
        
        for group_id, mapping_group in mapping_groups.items():
            mapping_id = str(group_id).upper()
            
            sql_block = sql_block_map.get(mapping_id)
            
            if sql_block is None:
                for sql_id, block in sql_block_map.items():
                    if mapping_id in sql_id or sql_id in mapping_id:
                        sql_block = block
                        break
            
            if sql_block:
                pairs.append((mapping_group, sql_block))
            else:
                pairs.append((mapping_group, None))
        
        return pairs
    
    def _parallel_compare_groups(
        self,
        group_pairs: List[Tuple[Any, Any]]
    ) -> List[GroupComparisonResult]:
        """并行对比多个分组
        
        Args:
            group_pairs: 分组对列表
            
        Returns:
            分组对比结果列表
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_pair = {
                executor.submit(self._compare_single_group, pair[0], pair[1]): pair
                for pair in group_pairs
            }
            
            for future in as_completed(future_to_pair):
                pair = future_to_pair[future]
                try:
                    result = future.result(timeout=self.timeout)
                    results.append(result)
                except Exception as e:
                    if self.debug:
                        print(f'[GroupComparisonAgent] 分组对比失败: {e}')
                    mapping_group = pair[0]
                    group_id = self._get_group_id(mapping_group)
                    group_name = self._get_group_name(mapping_group)
                    results.append(GroupComparisonResult(
                        group_id=group_id,
                        group_name=group_name,
                        status='error',
                        field_count=0,
                        consistent_fields=0,
                        inconsistent_fields=0,
                        details=[{'error': str(e)}]
                    ))
        
        return results
    
    def _sequential_compare_groups(
        self,
        group_pairs: List[Tuple[Any, Any]]
    ) -> List[GroupComparisonResult]:
        """顺序对比多个分组
        
        Args:
            group_pairs: 分组对列表
            
        Returns:
            分组对比结果列表
        """
        results = []
        
        for mapping_group, sql_block in group_pairs:
            try:
                result = self._compare_single_group(mapping_group, sql_block)
                results.append(result)
            except Exception as e:
                if self.debug:
                    print(f'[GroupComparisonAgent] 分组对比失败: {e}')
                group_id = self._get_group_id(mapping_group)
                group_name = self._get_group_name(mapping_group)
                results.append(GroupComparisonResult(
                    group_id=group_id,
                    group_name=group_name,
                    status='error',
                    field_count=0,
                    consistent_fields=0,
                    inconsistent_fields=0,
                    details=[{'error': str(e)}]
                ))
        
        return results
    
    def _compare_single_group(
        self,
        mapping_group: Any,
        sql_block: Any
    ) -> GroupComparisonResult:
        """对比单个分组
        
        Args:
            mapping_group: IT-Mapping分组信息
            sql_block: SQL分组信息
            
        Returns:
            GroupComparisonResult: 分组对比结果
        """
        group_id = self._get_group_id(mapping_group)
        group_name = self._get_group_name(mapping_group)
        
        result = GroupComparisonResult(
            group_id=group_id,
            group_name=group_name,
            status='passed',
            field_count=0,
            consistent_fields=0,
            inconsistent_fields=0,
            details=[]
        )
        
        if sql_block is None:
            result.status = 'failed'
            result.details.append({
                'type': 'missing_sql_block',
                'message': f'分组 {group_id} 在SQL中未找到对应的INSERT块',
                'severity': 'critical'
            })
            return result
        
        field_result = self._compare_field_mapping(mapping_group, sql_block)
        result.field_comparison = field_result
        result.field_count = field_result.get('total_fields', 0)
        result.consistent_fields = field_result.get('consistent_count', 0)
        result.inconsistent_fields = field_result.get('inconsistent_count', 0)
        if field_result.get('details'):
            result.details.extend(field_result['details'])
        
        source_table_result = self._compare_source_tables(mapping_group, sql_block)
        result.source_table_comparison = source_table_result
        if source_table_result.get('inconsistent'):
            result.details.extend(source_table_result.get('details', []))
        
        join_result = self._compare_join_conditions(mapping_group, sql_block)
        result.join_comparison = join_result
        if join_result.get('inconsistent'):
            result.details.extend(join_result.get('details', []))
        
        filter_result = self._compare_filter_conditions(mapping_group, sql_block)
        result.filter_comparison = filter_result
        if filter_result.get('inconsistent'):
            result.details.extend(filter_result.get('details', []))
        
        critical_issues = sum(1 for d in result.details if d.get('severity') == 'critical')
        high_issues = sum(1 for d in result.details if d.get('severity') == 'high')
        
        if critical_issues > 0 or high_issues > 2:
            result.status = 'failed'
        elif high_issues > 0 or len(result.details) > 3:
            result.status = 'warning'
        else:
            result.status = 'passed'
        
        return result
    
    def _compare_field_mapping(
        self,
        mapping_group: Any,
        sql_block: Any
    ) -> Dict:
        """对比字段映射
        
        Args:
            mapping_group: IT-Mapping分组信息
            sql_block: SQL分组信息
            
        Returns:
            字段映射对比结果
        """
        result = {
            'total_fields': 0,
            'consistent_count': 0,
            'inconsistent_count': 0,
            'details': [],
            'inconsistent': False
        }
        
        mapping_fields = self._get_mapping_fields(mapping_group)
        sql_fields = self._get_sql_fields(sql_block)
        sql_field_mapping = self._get_sql_field_mapping(sql_block)
        
        result['total_fields'] = len(mapping_fields)
        
        for field_name, field_info in mapping_fields.items():
            detail = {
                'type': 'field_mapping',
                'field_name': field_name,
                'mapping_source': field_info.get('source_field', ''),
                'mapping_table': field_info.get('source_table', ''),
                'mapping_logic': field_info.get('transformation_logic', ''),
                'sql_expression': '',
                'consistent': True,
                'severity': 'low',
                'message': ''
            }
            
            if field_name in sql_fields:
                sql_expr = sql_field_mapping.get(field_name, '')
                detail['sql_expression'] = sql_expr
                
                is_consistent, message = self._check_field_consistency(
                    field_info, sql_expr
                )
                detail['consistent'] = is_consistent
                detail['message'] = message
                
                if is_consistent:
                    result['consistent_count'] += 1
                else:
                    result['inconsistent_count'] += 1
                    detail['severity'] = 'high'
                    result['inconsistent'] = True
            else:
                detail['consistent'] = False
                detail['message'] = f'字段 {field_name} 在SQL中未找到'
                detail['severity'] = 'critical'
                result['inconsistent_count'] += 1
                result['inconsistent'] = True
            
            if not detail['consistent']:
                result['details'].append(detail)
        
        extra_fields = set(sql_fields) - set(mapping_fields.keys())
        for extra_field in extra_fields:
            result['details'].append({
                'type': 'extra_field',
                'field_name': extra_field,
                'sql_expression': sql_field_mapping.get(extra_field, ''),
                'consistent': False,
                'severity': 'medium',
                'message': f'字段 {extra_field} 在Mapping中未定义，可能是新增字段'
            })
        
        return result
    
    def _compare_source_tables(
        self,
        mapping_group: Any,
        sql_block: Any
    ) -> Dict:
        """对比数据源表
        
        Args:
            mapping_group: IT-Mapping分组信息
            sql_block: SQL分组信息
            
        Returns:
            数据源表对比结果
        """
        result = {
            'mapping_tables': [],
            'sql_tables': [],
            'consistent': True,
            'inconsistent': False,
            'details': []
        }
        
        mapping_tables = self._get_mapping_source_tables(mapping_group)
        sql_tables = self._get_sql_source_tables(sql_block)
        
        result['mapping_tables'] = mapping_tables
        result['sql_tables'] = sql_tables
        
        mapping_table_names = set(t.lower() for t in mapping_tables)
        sql_table_names = set(t.lower() for t in sql_tables)
        
        missing_tables = mapping_table_names - sql_table_names
        extra_tables = sql_table_names - mapping_table_names
        
        if missing_tables:
            result['inconsistent'] = True
            result['consistent'] = False
            for table in missing_tables:
                result['details'].append({
                    'type': 'missing_table',
                    'table_name': table,
                    'severity': 'critical',
                    'message': f'数据源表 {table} 在SQL中未找到'
                })
        
        if extra_tables:
            result['inconsistent'] = True
            for table in extra_tables:
                result['details'].append({
                    'type': 'extra_table',
                    'table_name': table,
                    'severity': 'medium',
                    'message': f'数据源表 {table} 在Mapping中未定义'
                })
        
        return result
    
    def _compare_join_conditions(
        self,
        mapping_group: Any,
        sql_block: Any
    ) -> Dict:
        """对比JOIN条件
        
        Args:
            mapping_group: IT-Mapping分组信息
            sql_block: SQL分组信息
            
        Returns:
            JOIN条件对比结果
        """
        result = {
            'mapping_joins': [],
            'sql_joins': [],
            'consistent': True,
            'inconsistent': False,
            'details': []
        }
        
        mapping_joins = self._get_mapping_joins(mapping_group)
        sql_joins = self._get_sql_joins(sql_block)
        
        result['mapping_joins'] = mapping_joins
        result['sql_joins'] = sql_joins
        
        for mapping_join in mapping_joins:
            matched = False
            for sql_join in sql_joins:
                if self._joins_match(mapping_join, sql_join):
                    matched = True
                    break
            
            if not matched:
                result['inconsistent'] = True
                result['consistent'] = False
                result['details'].append({
                    'type': 'join_mismatch',
                    'mapping_join': str(mapping_join),
                    'severity': 'high',
                    'message': f'JOIN条件 {mapping_join.get("右表别名", "")} 在SQL中未找到匹配的关联'
                })
        
        for sql_join in sql_joins:
            matched = False
            for mapping_join in mapping_joins:
                if self._joins_match(mapping_join, sql_join):
                    matched = True
                    break
            
            if not matched:
                result['details'].append({
                    'type': 'extra_join',
                    'sql_join': str(sql_join),
                    'severity': 'medium',
                    'message': f'JOIN条件 {sql_join.get("table", "")} 在Mapping中未定义'
                })
        
        return result
    
    def _compare_filter_conditions(
        self,
        mapping_group: Any,
        sql_block: Any
    ) -> Dict:
        """对比筛选条件
        
        Args:
            mapping_group: IT-Mapping分组信息
            sql_block: SQL分组信息
            
        Returns:
            筛选条件对比结果
        """
        result = {
            'mapping_filters': [],
            'sql_where': '',
            'consistent': True,
            'inconsistent': False,
            'details': []
        }
        
        mapping_filters = self._get_mapping_filters(mapping_group)
        sql_where = self._get_sql_where(sql_block)
        
        result['mapping_filters'] = mapping_filters
        result['sql_where'] = sql_where
        
        for mapping_filter in mapping_filters:
            field_name = mapping_filter.get('字段名', '')
            condition = mapping_filter.get('条件', '')
            value = mapping_filter.get('值', '')
            
            if field_name and condition:
                found_in_sql = False
                
                if field_name.lower() in sql_where.lower():
                    found_in_sql = True
                
                if not found_in_sql:
                    result['details'].append({
                        'type': 'filter_mismatch',
                        'field_name': field_name,
                        'mapping_condition': f'{condition} {value}',
                        'severity': 'medium',
                        'message': f'筛选条件 {field_name} {condition} {value} 在SQL WHERE子句中未找到'
                    })
        
        if result['details']:
            result['inconsistent'] = True
        
        return result
    
    def _check_field_consistency(
        self,
        field_info: Dict,
        sql_expr: str
    ) -> Tuple[bool, str]:
        """检查字段一致性
        
        Args:
            field_info: Mapping字段信息
            sql_expr: SQL表达式
            
        Returns:
            (是否一致, 消息)
        """
        source_field = field_info.get('source_field', '')
        source_table = field_info.get('source_table', '')
        transformation_logic = field_info.get('transformation_logic', '')
        
        if not sql_expr:
            return False, 'SQL表达式为空'
        
        sql_expr_upper = sql_expr.upper()
        
        default_values = {
            'UUID': ['UUID()', 'UUID'],
            'LOAD_TIME': ['CURRENT_TIMESTAMP()', 'NOW()', 'SYSDATE'],
            'DATA_DATE': ['V_SHORT_DATE', 'CURRENT_DATE()', 'SYSDATE']
        }
        
        field_name_upper = field_info.get('field_name', '').upper()
        if field_name_upper in default_values:
            for default_val in default_values[field_name_upper]:
                if default_val.upper() in sql_expr_upper:
                    return True, '默认值匹配'
        
        if source_field:
            source_fields = [f.strip() for f in source_field.replace('\r\n', '\n').replace('\r', '\n').split('\n') if f.strip()]
            source_fields = list(set(source_fields))
            
            sql_expr_clean = sql_expr.replace('.', '').replace('_', '').upper()
            
            matched_fields = []
            for sf in source_fields:
                sf_clean = sf.replace('.', '').replace('_', '').upper()
                if sf_clean and sf_clean in sql_expr_clean:
                    matched_fields.append(sf)
            
            if matched_fields:
                return True, f'源字段匹配 ({len(matched_fields)}/{len(source_fields)}个字段)'
            
            for sf in source_fields:
                sf_upper = sf.upper()
                if sf_upper in sql_expr_upper:
                    return True, f'源字段匹配 ({sf})'
        
        if source_table:
            source_tables = [t.strip() for t in source_table.replace('\r\n', '\n').replace('\r', '\n').split('\n') if t.strip()]
            
            for st in source_tables:
                st_clean = st.split(']')[-1].strip() if ']' in st else st
                if st_clean.lower() in sql_expr.lower():
                    if not source_field:
                        return True, '源表匹配'
                    for sf in source_fields if source_field else []:
                        if sf.lower() in sql_expr.lower():
                            return True, '源表和字段匹配'
        
        if transformation_logic:
            logic_keywords = self._extract_logic_keywords(transformation_logic)
            matched_keywords = sum(1 for kw in logic_keywords if kw.lower() in sql_expr.lower())
            
            if logic_keywords and matched_keywords >= len(logic_keywords) * 0.5:
                return True, f'转换逻辑部分匹配 ({matched_keywords}/{len(logic_keywords)})'
        
        if source_field:
            source_fields = [f.strip() for f in source_field.replace('\r\n', '\n').replace('\r', '\n').split('\n') if f.strip()]
            source_fields = list(set(source_fields))
            
            all_not_found = all(sf.lower() not in sql_expr.lower() for sf in source_fields)
            if all_not_found:
                return False, f'源字段 {source_field} 在SQL表达式中未找到'
        
        return True, '基本匹配'
    
    def _extract_logic_keywords(self, logic: str) -> List[str]:
        """从转换逻辑中提取关键词
        
        Args:
            logic: 转换逻辑描述
            
        Returns:
            关键词列表
        """
        keywords = []
        
        function_patterns = [
            r'SUBSTR\s*\(',
            r'SUBSTRING\s*\(',
            r'CONCAT\s*\(',
            r'\|\|',
            r'CAST\s*\(',
            r'TO_CHAR\s*\(',
            r'TO_DATE\s*\(',
            r'TRIM\s*\(',
            r'UPPER\s*\(',
            r'LOWER\s*\(',
            r'REPLACE\s*\(',
            r'NVL\s*\(',
            r'COALESCE\s*\(',
            r'CASE\s+WHEN',
        ]
        
        for pattern in function_patterns:
            if re.search(pattern, logic, re.IGNORECASE):
                keywords.append(pattern.replace(r'\s*\(', '').replace(r'\s+', ' '))
        
        number_matches = re.findall(r'\d+', logic)
        keywords.extend(number_matches)
        
        return keywords
    
    def _joins_match(self, mapping_join: Dict, sql_join: Dict) -> bool:
        """检查JOIN是否匹配
        
        Args:
            mapping_join: Mapping JOIN信息
            sql_join: SQL JOIN信息
            
        Returns:
            是否匹配
        """
        mapping_table = mapping_join.get('右表别名', '') or mapping_join.get('右表名称', '')
        sql_table = sql_join.get('table', '')
        
        if not mapping_table or not sql_table:
            return False
        
        mapping_table_clean = mapping_table.split(']')[-1].strip() if ']' in mapping_table else mapping_table
        
        return mapping_table_clean.lower() in sql_table.lower() or sql_table.lower() in mapping_table_clean.lower()
    
    def _get_group_id(self, mapping_group: Any) -> str:
        """获取分组ID"""
        if hasattr(mapping_group, '组别编号'):
            return mapping_group.组别编号
        elif isinstance(mapping_group, dict):
            return mapping_group.get('组别编号', '') or mapping_group.get('group_id', '')
        return ''
    
    def _get_group_name(self, mapping_group: Any) -> str:
        """获取分组名称"""
        if hasattr(mapping_group, '组别名称'):
            return mapping_group.组别名称
        elif isinstance(mapping_group, dict):
            return mapping_group.get('组别名称', '') or mapping_group.get('group_name', '')
        return ''
    
    def _get_mapping_fields(self, mapping_group: Any) -> Dict:
        """获取Mapping字段列表"""
        fields = {}
        
        if hasattr(mapping_group, '字段列表'):
            for field in mapping_group.字段列表:
                field_name = getattr(field, '字段英文名', '') if hasattr(field, '字段英文名') else ''
                if field_name:
                    fields[field_name] = {
                        'source_field': getattr(field, '源字段名_英文', ''),
                        'source_table': getattr(field, '数据表', ''),
                        'transformation_logic': getattr(field, '字段加工逻辑', ''),
                        'data_type': getattr(field, '数据类型', ''),
                        'field_name': field_name
                    }
        elif isinstance(mapping_group, dict):
            field_list = mapping_group.get('字段列表', [])
            for field in field_list:
                field_name = field.get('字段英文名', '') if isinstance(field, dict) else ''
                if field_name:
                    fields[field_name] = {
                        'source_field': field.get('源字段名_英文', ''),
                        'source_table': field.get('数据表', ''),
                        'transformation_logic': field.get('字段加工逻辑', ''),
                        'data_type': field.get('数据类型', ''),
                        'field_name': field_name
                    }
        
        return fields
    
    def _get_sql_fields(self, sql_block: Any) -> List[str]:
        """获取SQL字段列表"""
        if hasattr(sql_block, 'insert_fields'):
            return sql_block.insert_fields
        elif isinstance(sql_block, dict):
            return sql_block.get('insert_fields', [])
        return []
    
    def _get_sql_field_mapping(self, sql_block: Any) -> Dict:
        """获取SQL字段映射"""
        if hasattr(sql_block, 'field_mapping'):
            return sql_block.field_mapping
        elif isinstance(sql_block, dict):
            return sql_block.get('field_mapping', {})
        return {}
    
    def _get_mapping_source_tables(self, mapping_group: Any) -> List[str]:
        """获取Mapping数据源表列表"""
        tables = []
        
        if hasattr(mapping_group, '数据源表'):
            for table in mapping_group.数据源表:
                if hasattr(table, '数据表名_英文'):
                    tables.append(table.数据表名_英文)
                elif isinstance(table, dict):
                    tables.append(table.get('数据表名_英文', ''))
        elif hasattr(mapping_group, '字段列表'):
            for field in mapping_group.字段列表:
                data_table = getattr(field, '数据表', '') if hasattr(field, '数据表') else ''
                if data_table:
                    table_names = [t.strip() for t in data_table.replace('\r\n', '\n').replace('\r', '\n').split('\n') if t.strip()]
                    for tn in table_names:
                        if '【' in tn:
                            match = re.search(r'【([^】]+)】', tn)
                            if match:
                                tables.append(match.group(1))
                        elif tn:
                            tables.append(tn)
        elif isinstance(mapping_group, dict):
            source_tables = mapping_group.get('数据源表', [])
            for table in source_tables:
                if hasattr(table, '数据表名_英文'):
                    tables.append(table.数据表名_英文)
                elif isinstance(table, dict):
                    tables.append(table.get('数据表名_英文', ''))
            
            field_list = mapping_group.get('字段列表', [])
            for field in field_list:
                if isinstance(field, dict):
                    data_table = field.get('数据表', '')
                    if data_table:
                        table_names = [t.strip() for t in data_table.replace('\r\n', '\n').replace('\r', '\n').split('\n') if t.strip()]
                        for tn in table_names:
                            if '【' in tn:
                                match = re.search(r'【([^】]+)】', tn)
                                if match:
                                    tables.append(match.group(1))
                            elif tn:
                                tables.append(tn)
        
        return list(set([t for t in tables if t]))
    
    def _get_sql_source_tables(self, sql_block: Any) -> List[str]:
        """获取SQL数据源表列表"""
        tables = []
        
        if hasattr(sql_block, 'from_clause') and sql_block.from_clause:
            tables.append(sql_block.from_clause.split()[0] if sql_block.from_clause else '')
        
        if hasattr(sql_block, 'join_clauses'):
            for join in sql_block.join_clauses:
                if isinstance(join, dict):
                    table = join.get('table', '')
                    if table:
                        tables.append(table.split()[0])
        
        if isinstance(sql_block, dict):
            from_clause = sql_block.get('from_clause', '')
            if from_clause:
                tables.append(from_clause.split()[0])
            
            join_clauses = sql_block.get('join_clauses', [])
            for join in join_clauses:
                if isinstance(join, dict):
                    table = join.get('table', '')
                    if table:
                        tables.append(table.split()[0])
        
        return [t for t in tables if t]
    
    def _get_mapping_joins(self, mapping_group: Any) -> List[Dict]:
        """获取Mapping JOIN条件列表"""
        joins = []
        
        if hasattr(mapping_group, '表间关联'):
            for join in mapping_group.表间关联:
                if hasattr(join, '__dict__'):
                    joins.append({
                        '左表别名': getattr(join, '左表别名', ''),
                        '左字段名': getattr(join, '左字段名', ''),
                        '关联类型': getattr(join, '关联类型', ''),
                        '右表别名': getattr(join, '右表别名', ''),
                        '右字段名': getattr(join, '右字段名', '')
                    })
                elif isinstance(join, dict):
                    joins.append(join)
        elif isinstance(mapping_group, dict):
            joins = mapping_group.get('表间关联', [])
        
        return joins
    
    def _get_sql_joins(self, sql_block: Any) -> List[Dict]:
        """获取SQL JOIN条件列表"""
        joins = []
        
        if hasattr(sql_block, 'join_clauses'):
            for join in sql_block.join_clauses:
                if isinstance(join, dict):
                    joins.append({
                        'type': join.get('type', ''),
                        'table': join.get('table', ''),
                        'condition': join.get('condition', '')
                    })
        elif isinstance(sql_block, dict):
            joins = sql_block.get('join_clauses', [])
        
        return joins
    
    def _get_mapping_filters(self, mapping_group: Any) -> List[Dict]:
        """获取Mapping筛选条件列表"""
        filters = []
        
        if hasattr(mapping_group, '筛选条件'):
            for filter_cond in mapping_group.筛选条件:
                if hasattr(filter_cond, '__dict__'):
                    filters.append({
                        '字段名': getattr(filter_cond, '字段名', ''),
                        '条件': getattr(filter_cond, '条件', ''),
                        '值': getattr(filter_cond, '值', '')
                    })
                elif isinstance(filter_cond, dict):
                    filters.append(filter_cond)
        elif isinstance(mapping_group, dict):
            filters = mapping_group.get('筛选条件', [])
        
        return filters
    
    def _get_sql_where(self, sql_block: Any) -> str:
        """获取SQL WHERE子句"""
        if hasattr(sql_block, 'where_clause'):
            return sql_block.where_clause
        elif isinstance(sql_block, dict):
            return sql_block.get('where_clause', '')
        return ''
    
    def _aggregate_summary(self, group_results: List[GroupComparisonResult]) -> Dict:
        """聚合汇总统计
        
        Args:
            group_results: 分组对比结果列表
            
        Returns:
            汇总统计字典
        """
        total_fields = sum(g.field_count for g in group_results)
        consistent_fields = sum(g.consistent_fields for g in group_results)
        inconsistent_fields = sum(g.inconsistent_fields for g in group_results)
        
        total_details = []
        for g in group_results:
            total_details.extend(g.details)
        
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for detail in total_details:
            severity = detail.get('severity', 'low')
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        issue_type_counts = {}
        for detail in total_details:
            issue_type = detail.get('type', 'unknown')
            issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1
        
        return {
            'total_groups': len(group_results),
            'passed_groups': sum(1 for g in group_results if g.status == 'passed'),
            'failed_groups': sum(1 for g in group_results if g.status == 'failed'),
            'warning_groups': sum(1 for g in group_results if g.status == 'warning'),
            'total_fields': total_fields,
            'consistent_fields': consistent_fields,
            'inconsistent_fields': inconsistent_fields,
            'consistency_rate': round(consistent_fields / total_fields * 100, 2) if total_fields > 0 else 0,
            'severity_counts': severity_counts,
            'issue_type_counts': issue_type_counts,
            'total_issues': len(total_details)
        }
    
    def to_dict(self, result: OverallComparisonResult) -> Dict:
        """将结果转换为字典格式
        
        Args:
            result: 总体对比结果
            
        Returns:
            字典格式的结果
        """
        return {
            'summary': result.summary,
            'total_groups': result.total_groups,
            'passed_groups': result.passed_groups,
            'failed_groups': result.failed_groups,
            'overall_consistency_rate': result.overall_consistency_rate,
            'groups': [
                {
                    'group_id': g.group_id,
                    'group_name': g.group_name,
                    'status': g.status,
                    'field_count': g.field_count,
                    'consistent_fields': g.consistent_fields,
                    'inconsistent_fields': g.inconsistent_fields,
                    'details': g.details,
                    'field_comparison': g.field_comparison,
                    'source_table_comparison': g.source_table_comparison,
                    'join_comparison': g.join_comparison,
                    'filter_comparison': g.filter_comparison
                }
                for g in result.groups
            ]
        }


class SQLFieldExtractorAgent:
    """SQL字段提取Agent - 从SQL文件中根据目标字段名提取相关信息"""

    def __init__(self, config):
        self.host = config.get('host', 'http://localhost:11434')
        self.model = config.get('model', 'qwen2.5:7b')
        self.timeout = int(config.get('timeout', 120))

    def extract_field_info(self, target_field_name, sql_content, sql_structure=None):
        """从SQL中提取指定字段的相关信息

        Args:
            target_field_name (str): 目标字段名
            sql_content (str): 完整SQL代码
            sql_structure (dict): SQL结构化解析结果（可选）

        Returns:
            dict: 提取的字段信息，包含:
                - field_name: 字段名
                - sql_expression: SQL表达式
                - source_table: 源表
                - source_field: 源字段
                - transform_logic: 转换逻辑
                - data_type: 数据类型
                - line_number: 行号
                - raw_sql_line: 原始SQL行
        """
        lines = sql_content.split('\n')
        field_info = {
            'field_name': target_field_name,
            'sql_expression': '',
            'source_table': '',
            'source_field': '',
            'transform_logic': '',
            'data_type': '',
            'line_number': 0,
            'raw_sql_line': ''
        }

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith('--'):
                continue

            patterns = [
                rf'\bAS\s+{re.escape(target_field_name)}\b',
                rf'{re.escape(target_field_name)}\s*,',
                rf',\s*{re.escape(target_field_name)}\b',
            ]

            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    field_info['line_number'] = i
                    field_info['raw_sql_line'] = line_stripped
                    field_info['sql_expression'] = line_stripped

                    parsed = self._parse_sql_expression(line_stripped, target_field_name)
                    field_info.update(parsed)
                    break

            if field_info['line_number'] > 0:
                break

        if sql_structure and sql_structure.get('field_mapping'):
            field_mapping = sql_structure.get('field_mapping', {})
            if target_field_name in field_mapping:
                field_info['sql_expression'] = field_mapping.get(target_field_name, '')

        return field_info

    def _parse_sql_expression(self, sql_line, field_name):
        """解析SQL表达式，提取源表、源字段、转换逻辑等信息

        Args:
            sql_line (str): SQL行
            field_name (str): 字段名

        Returns:
            dict: 解析结果
        """
        result = {
            'source_table': '',
            'source_field': '',
            'transform_logic': '',
            'data_type': ''
        }

        as_match = re.search(rf'(.+?)\s+AS\s+{re.escape(field_name)}', sql_line, re.IGNORECASE)
        if as_match:
            expression = as_match.group(1).strip()

            table_field_match = re.search(r'(\w+)\.(\w+)', expression)
            if table_field_match:
                result['source_table'] = table_field_match.group(1)
                result['source_field'] = table_field_match.group(2)

            if '(' in expression:
                func_match = re.search(r'(\w+)\s*\(', expression)
                if func_match:
                    result['transform_logic'] = func_match.group(1).upper()

        return result

    def extract_all_fields(self, field_names, sql_content, sql_structure=None):
        """批量提取多个字段的信息

        Args:
            field_names (list): 字段名列表
            sql_content (str): 完整SQL代码
            sql_structure (dict): SQL结构化解析结果（可选）

        Returns:
            dict: {字段名: 字段信息} 映射表
        """
        results = {}
        for field_name in field_names:
            if field_name and field_name != 'nan':
                results[field_name] = self.extract_field_info(
                    field_name, sql_content, sql_structure
                )
        return results


class ComparisonHarness:
    """对比Harness - 协调SQL字段提取、存储和三Agent投票的完整流程"""

    def __init__(self, config):
        self.config = config
        self.extractor = SQLFieldExtractorAgent(config)
        self.voter = TripleAgentVoter(config)

    def execute_comparison(self, task_id, field_mappings, sql_content, 
                           md_content='', sql_structure=None, fast_mode=False):
        """执行完整的对比流程

        Args:
            task_id (str): 任务ID
            field_mappings (list): 字段映射信息列表（来自IT-Mapping）
            sql_content (str): 完整SQL代码
            md_content (str): MD文档内容（可选）
            sql_structure (dict): SQL结构化解析结果（可选）
            fast_mode (bool): 是否使用快速模式（单Agent）

        Returns:
            dict: 完整的对比结果，包含:
                - dataset_results: 数据源对比结果
                - datamap_results: 数据映射对比结果
                - vote_results: 投票结果
                - summary: 汇总统计
        """
        from services.history_service import HistoryService
        hs = HistoryService()

        field_names = [fm.get('target_field', '') for fm in field_mappings if fm.get('target_field')]

        # 打印分组统计信息（按顺序）
        group_ids_ordered = []
        for fm in field_mappings:
            gid = fm.get('group_id', '')
            if gid and gid not in group_ids_ordered:
                group_ids_ordered.append(gid)
        print(f'[ComparisonHarness] 开始执行对比流程，共 {len(field_names)} 个字段，分组顺序: {group_ids_ordered}')

        # 获取INSERT映射列表（按顺序）
        insert_mappings = []
        if sql_structure and sql_structure.get('insert_mappings'):
            insert_mappings = sql_structure['insert_mappings']
            print(f'[ComparisonHarness] 使用INSERT映射列表: {len(insert_mappings)}个INSERT块')

        # 构建分组ID到INSERT映射的对应关系（按顺序匹配）
        group_to_insert_idx = {}
        for idx, group_id in enumerate(group_ids_ordered):
            if idx < len(insert_mappings):
                group_to_insert_idx[group_id] = idx

        extracted_fields = self.extractor.extract_all_fields(
            field_names, sql_content, sql_structure
        )

        dataset_results = []
        datamap_results = []
        vote_results = []

        for idx, fm in enumerate(field_mappings):
            target_field = fm.get('target_field', '')
            if not target_field:
                continue

            extracted = extracted_fields.get(target_field, {})
            group_id = fm.get('group_id', '')

            # 根据分组ID选择正确的SQL表达式（按顺序匹配）
            sql_expression = extracted.get('sql_expression', '')
            if group_id in group_to_insert_idx:
                insert_idx = group_to_insert_idx[group_id]
                field_sql_mapping = insert_mappings[insert_idx]
                sql_expression = field_sql_mapping.get(target_field, sql_expression)

            datamap_result = {
                'group_id': group_id,
                'field_seq': fm.get('field_seq', idx + 1),
                'target_field_cn': fm.get('target_field_cn', ''),
                'target_field_en': target_field,
                'extract_method': fm.get('extract_method', ''),
                'source_table': extracted.get('source_table', fm.get('source_table_alias', '')),
                'source_field_en': extracted.get('source_field', fm.get('source_field', '')),
                'source_field_cn': fm.get('source_field_cn', ''),
                'default_value': fm.get('default_value', ''),
                'transform_logic': fm.get('transformation_logic', ''),
                'sql_expression': sql_expression,
                'is_consistent': '待检查',
                'remark': ''
            }

            field_info_for_vote = {
                'target_field': target_field,
                'target_field_cn': fm.get('target_field_cn', ''),
                'source_field': extracted.get('source_field', fm.get('source_field', '')),
                'source_table_alias': extracted.get('source_table', fm.get('source_table_alias', '')),
                'transformation_logic': fm.get('transformation_logic', ''),
                'data_type': fm.get('data_type', ''),
                'extract_method': fm.get('extract_method', ''),
                'default_value': fm.get('default_value', ''),
                'group_id': group_id,
                'field_seq': fm.get('field_seq', idx + 1)
            }

            vote_result = self.voter.vote_on_field(
                field_info_for_vote,
                sql_content,
                md_content,
                fast_mode=fast_mode,
                field_sql_mapping={target_field: sql_expression},
                sql_structure=sql_structure
            )

            vote_results.append(vote_result)

            final_status = vote_result.get('final_status', 'needs_review')
            is_consistent = '是' if final_status == 'consistent' else ('否' if final_status == 'inconsistent' else '待复核')
            datamap_result['is_consistent'] = is_consistent

            if final_status == 'inconsistent':
                merged_findings = vote_result.get('merged_findings', [])
                if merged_findings:
                    datamap_result['remark'] = merged_findings[0].get('issue', '')

            datamap_results.append(datamap_result)

            if idx % 10 == 0:
                print(f'[ComparisonHarness] 已处理 {idx + 1}/{len(field_mappings)} 个字段')

        if datamap_results:
            hs.save_datamap_comparison_batch(task_id, datamap_results, clear_existing=False)
            print(f'[ComparisonHarness] 已保存 {len(datamap_results)} 条数据映射结果（保留其他分组数据）')

        summary = self._aggregate_results(vote_results)

        return {
            'dataset_results': dataset_results,
            'datamap_results': datamap_results,
            'vote_results': vote_results,
            'summary': summary
        }

    def _aggregate_results(self, vote_results):
        """聚合投票结果

        Args:
            vote_results (list): 投票结果列表

        Returns:
            dict: 聚合统计
        """
        total = len(vote_results)
        consistent = sum(1 for v in vote_results if v.get('final_status') == 'consistent')
        inconsistent = sum(1 for v in vote_results if v.get('final_status') == 'inconsistent')
        needs_review = sum(1 for v in vote_results if v.get('final_status') == 'needs_review')
        all_failed = sum(1 for v in vote_results if v.get('final_status') == 'all_failed')

        confidences = [v.get('confidence', 0.0) for v in vote_results]
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

        return {
            'total_fields': total,
            'consistent_count': consistent,
            'inconsistent_count': inconsistent,
            'needs_review_count': needs_review,
            'all_failed_count': all_failed,
            'pass_rate': round(consistent / total * 100, 1) if total > 0 else 0,
            'avg_confidence': avg_confidence
        }

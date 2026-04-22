from flask import Flask, send_from_directory, render_template, jsonify, request, Response, current_app
from flask_cors import CORS
import os
import json
from urllib.parse import quote
from sql_correction_engine import SQLEngine
from services.history_service import HistoryService
from tools.sql_annotator import SQLAnnotator
from tools.report_formatter import ReportFormatter

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

@app.after_request
def add_no_cache_headers(response):
    if 'text/html' in response.content_type or 'javascript' in response.content_type or 'css' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'ollama_config.json')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

sql_engine = SQLEngine(UPLOAD_FOLDER, CONFIG_FILE)
history_service = HistoryService()

def load_ollama_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f'Error loading ollama config: {e}')
    return {
        'host': 'http://localhost:11434',
        'model': 'qwen2.5:7b',
        'timeout': 30,
        'auto_connect': True
    }

def save_ollama_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f'Error saving ollama config: {e}')
        return False

def _extract_data_source_info(mapping_file, sql_content=''):
    """从ITMapping Excel文件中提取数据源信息
    
    返回格式：
    {
        'groups': [  # 分组信息
            {
                'group_id': 'MP1',
                'source_tables': 'T:表1、\nT1:表2',
                'relations': [  # 表间关联和筛选条件，每条拆分为一行
                    {
                        'compare_module': '表间关联',
                        'content': 'A、【T】客户联系信息表.【CLIENT_NO】客户号 左关联 【T1】客户信息表.【CLIENT_NO】客户号',
                        'sql_content': 'LEFT JOIN ODM_STO_CIF_CLIENT_TFD T1 ON T.CLIENT_NO = T1.CLIENT_NO',
                        'is_consistent': '是',
                        'remark': ''
                    },
                    ...
                ]
            },
            ...
        ]
    }
    """
    from excel_parser import extract_groups_from_excel, GroupExtractor, load_excel
    from sql_group_parser import parse_grouped_sql
    import os
    import re
    
    dataset_results = {
        'groups': []
    }
    
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], mapping_file)
        
        workbook = load_excel(file_path)
        extractor = GroupExtractor(workbook)
        groups = extractor.extract_all_groups()
        
        sql_structure = None
        if sql_content:
            try:
                sql_structure = parse_grouped_sql(sql_content)
            except Exception as e:
                print(f"解析SQL结构失败: {e}")
        
        for group_id, group_info in groups.items():
            source_tables_dict = {}
            for table in group_info.数据源表:
                if table.数据表别名 and table.数据表名_中文:
                    source_tables_dict[table.数据表别名] = table.数据表名_中文
            source_tables_list = [f"{alias}:{name}" for alias, name in source_tables_dict.items()]
            source_tables = '、\n'.join(source_tables_list) if source_tables_list else ''
            
            group_data = {
                'group_id': group_id,
                'source_tables': source_tables,
                'relations': []
            }
            
            sql_block = None
            if sql_structure:
                for block in sql_structure.get('insert_blocks', []):
                    if block.get('group_id', '').upper() == group_id.upper():
                        sql_block = block
                        break
            
            for join in group_info.表间关联:
                left_table = join.左表别名
                left_table_name = join.左表名称
                left_field = join.左字段名
                left_field_cn = join.左字段中文名
                join_type = join.关联类型
                right_table = join.右表别名
                right_table_name = join.右表名称
                right_field = join.右字段名
                right_field_cn = join.右字段中文名
                
                content = f"{join_type}：【{left_table}】{left_table_name}.{left_field}【{left_field_cn}】 = 【{right_table}】{right_table_name}.{right_field}【{right_field_cn}】"
                
                sql_snippet = ''
                is_consistent = '是'
                remark = ''
                
                if sql_block:
                    join_clauses = sql_block.get('join_clauses', [])
                    for sql_join in join_clauses:
                        sql_join_type = sql_join.get('type', '').upper()
                        sql_table = sql_join.get('table', '')
                        sql_condition = sql_join.get('condition', '')
                        
                        table_match = False
                        if right_table and right_table in sql_table:
                            table_match = True
                        elif right_table_name and right_table_name in sql_table:
                            table_match = True
                        
                        if table_match:
                            join_type_match = False
                            if 'LEFT' in join_type and 'LEFT' in sql_join_type:
                                join_type_match = True
                            elif 'RIGHT' in join_type and 'RIGHT' in sql_join_type:
                                join_type_match = True
                            elif 'INNER' in join_type and 'INNER' in sql_join_type:
                                join_type_match = True
                            elif join_type == '关联' or join_type == '左关联':
                                join_type_match = True
                            
                            if join_type_match:
                                sql_snippet = f"{sql_join_type} {sql_table} ON {sql_condition}"
                                
                                if left_field and right_field:
                                    if left_field in sql_condition and right_field in sql_condition:
                                        is_consistent = '是'
                                    else:
                                        is_consistent = '否'
                                        remark = '关联字段不匹配'
                                break
                
                group_data['relations'].append({
                    'compare_module': '表间关联',
                    'content': content,
                    'sql_content': sql_snippet,
                    'is_consistent': is_consistent,
                    'remark': remark
                })
            
            for filter_cond in group_info.筛选条件:
                table_alias = filter_cond.表别名
                table_name = filter_cond.表名称
                field_name = filter_cond.字段名
                field_cn = filter_cond.字段中文名
                condition = filter_cond.条件
                value = filter_cond.值
                
                content = f"筛选条件：【{table_alias}】{table_name}.{field_name}【{field_cn}】 {condition} {value}"
                
                sql_snippet = ''
                is_consistent = '是'
                remark = ''
                
                if sql_block:
                    where_clause = sql_block.get('where_clause', '')
                    if where_clause:
                        if field_name and field_name in where_clause:
                            patterns = [
                                rf'{table_alias}\.{field_name}\s*=\s*{re.escape(value)}',
                                rf'{table_alias}\.{field_name}\s*=\s*[Vv]_[A-Z_]+',
                                rf'{field_name}\s*=\s*{re.escape(value)}',
                            ]
                            
                            found = False
                            for pattern in patterns:
                                if re.search(pattern, where_clause, re.IGNORECASE):
                                    found = True
                                    break
                            
                            if found:
                                where_lines = where_clause.split(' AND ')
                                for line in where_lines:
                                    if field_name in line:
                                        sql_snippet = line.strip()
                                        break
                                is_consistent = '是'
                            else:
                                is_consistent = '否'
                                remark = '筛选条件不匹配'
                                sql_snippet = where_clause[:200] if len(where_clause) > 200 else where_clause
                        else:
                            is_consistent = '否'
                            remark = '未找到筛选字段'
                
                group_data['relations'].append({
                    'compare_module': '筛选条件',
                    'content': content,
                    'sql_content': sql_snippet,
                    'is_consistent': is_consistent,
                    'remark': remark
                })
            
            dataset_results['groups'].append(group_data)
        
        workbook.close()
        
    except Exception as e:
        print(f"提取数据源信息失败: {e}")
        import traceback
        traceback.print_exc()
        dataset_results = {
            'tables': [],
            'groups': [{
                'group_id': 'ERROR',
                'group_name': '错误',
                'relations': [{
                    'content': '数据源提取失败',
                    'sql_content': '',
                    'is_consistent': '否',
                    'remark': str(e)
                }]
            }]
        }
    
    return dataset_results

def _extract_from_clause(sql_content):
    """从SQL内容中提取FROM子句"""
    if not sql_content:
        return ''
    
    # 标准化SQL内容
    sql_content = ' '.join(sql_content.split())
    sql_lower = sql_content.lower()
    
    # 查找FROM关键字
    from_pos = sql_lower.find(' from ')
    if from_pos == -1:
        from_pos = sql_lower.find('from ')
        if from_pos == -1:
            return ''
    
    # 调整位置，确保包含FROM关键字
    if from_pos > 0 and sql_lower[from_pos-1] != ' ':
        from_pos -= 1
    
    # 查找FROM子句的结束位置
    # 可能的结束关键字
    end_keywords = [' where ', ' group by ', ' order by ', ' having ', ' limit ']
    end_pos = len(sql_content)
    
    # 处理括号嵌套
    bracket_count = 0
    in_brackets = False
    
    for i in range(from_pos, len(sql_lower)):
        if sql_lower[i] == '(':
            bracket_count += 1
            in_brackets = True
        elif sql_lower[i] == ')':
            bracket_count -= 1
            if bracket_count == 0:
                in_brackets = False
        
        # 如果不在括号内，检查是否遇到结束关键字
        if not in_brackets:
            for keyword in end_keywords:
                if i + len(keyword) <= len(sql_lower) and sql_lower[i:i+len(keyword)] == keyword:
                    end_pos = i
                    break
            if end_pos != len(sql_content):
                break
    
    # 提取FROM子句
    from_clause = sql_content[from_pos:end_pos].strip()
    
    # 格式化输出
    # 为JOIN关键字添加换行
    from_clause = from_clause.replace(' LEFT JOIN ', '\nLEFT JOIN ')
    from_clause = from_clause.replace(' RIGHT JOIN ', '\nRIGHT JOIN ')
    from_clause = from_clause.replace(' INNER JOIN ', '\nINNER JOIN ')
    from_clause = from_clause.replace(' OUTER JOIN ', '\nOUTER JOIN ')
    from_clause = from_clause.replace(' CROSS JOIN ', '\nCROSS JOIN ')
    # 为ON关键字添加换行
    from_clause = from_clause.replace(' ON ', '\n  ON ')
    
    return from_clause

def _extract_select_clause(sql_content):
    """从SQL内容中提取SELECT子句"""
    if not sql_content:
        return ''
    
    # 标准化SQL内容
    sql_content = ' '.join(sql_content.split())
    sql_lower = sql_content.lower()
    
    # 查找SELECT关键字
    select_pos = sql_lower.find('select ')
    if select_pos == -1:
        return ''
    
    # 查找FROM关键字作为SELECT子句的结束
    from_pos = sql_lower.find(' from ', select_pos)
    if from_pos == -1:
        from_pos = sql_lower.find('from ', select_pos)
        if from_pos == -1:
            return ''
    
    # 处理括号嵌套
    bracket_count = 0
    in_brackets = False
    
    for i in range(select_pos, len(sql_lower)):
        if sql_lower[i] == '(':
            bracket_count += 1
            in_brackets = True
        elif sql_lower[i] == ')':
            bracket_count -= 1
            if bracket_count == 0:
                in_brackets = False
        
        # 如果不在括号内且找到了FROM关键字，停止搜索
        if not in_brackets and i >= from_pos:
            break
    
    # 提取SELECT子句
    select_clause = sql_content[select_pos:from_pos].strip()
    
    # 格式化输出
    select_clause = 'SELECT ' + select_clause[7:] if select_clause.startswith('SELECT ') else select_clause
    select_clause = select_clause.replace(', ', '\n, ')
    
    return select_clause

def _extract_sql_snippet(sql_content, table1, table2='', field=''):
    """从SQL内容中提取相关代码片段"""
    if not sql_content:
        return ''
    
    lines = sql_content.split('\n')
    relevant_lines = []
    
    # 查找包含表名或字段的行，优先匹配完整的表别名.字段名
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        line_lower = line_stripped.lower()
        # 跳过注释和空行
        if line_stripped.startswith('--') or line_stripped.startswith('/*') or line_stripped.endswith('*/'):
            continue
        
        # 检查是否包含完整的表别名.字段名
        if field:
            if table1 and f"{table1.lower()}.{field.lower()}" in line_lower:
                # 包含完整的表别名.字段名，添加这一行及其前后几行
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                relevant_lines.extend(lines[start:end])
                continue
        # 检查是否包含表名
        if (table1 and table1.lower() in line_lower) or \
           (table2 and table2.lower() in line_lower):
            # 包含表名，添加这一行及其前后几行
            start = max(0, i - 1)
            end = min(len(lines), i + 2)
            relevant_lines.extend(lines[start:end])
    
    # 去重并保持顺序
    seen = set()
    unique_lines = []
    for line in relevant_lines:
        if line.strip() and line not in seen:
            seen.add(line)
            unique_lines.append(line)
    
    # 如果没有找到相关内容，返回空字符串
    if not unique_lines:
        return ''
    
    return '\n'.join(unique_lines)






def _convert_findings_to_excel_format(findings, task_id, sql_structure=None):
    """将findings转换为Excel格式数据
    
    Args:
        findings: 检查结果列表
        task_id: 任务ID
        sql_structure: SQL结构化解析结果，包含field_mapping等字段
    
    Returns:
        tuple: (dataset_results, datamap_results)
            dataset_results: {'groups': [...]} 格式
            datamap_results: 列表格式
    """
    groups_dict = {}
    datamap_results = []
    
    field_seq_counter = {}
    
    for finding in findings:
        group_id = finding.get('group_id', 'MP1')
        if group_id not in field_seq_counter:
            field_seq_counter[group_id] = 0
        
        if group_id not in groups_dict:
            groups_dict[group_id] = {
                'group_id': group_id,
                'source_tables': '',
                'relations': []
            }
        
        finding_type = finding.get('type', '')
        is_consistent = '否' if finding.get('status') == 'inconsistent' else '是'
        
        if finding_type in ['join_logic', 'join_condition', 'join_mismatch', 'filter_condition']:
            compare_module = '表间关联' if 'join' in finding_type else '筛选条件'
            groups_dict[group_id]['relations'].append({
                'compare_module': compare_module,
                'content': finding.get('mapping_ref', {}).get('logic', '') if isinstance(finding.get('mapping_ref'), dict) else '',
                'sql_content': finding.get('original_sql', ''),
                'is_consistent': is_consistent,
                'remark': finding.get('issue', '')
            })
        else:
            field_seq_counter[group_id] += 1
            mapping_ref = finding.get('mapping_ref', {})
            if not isinstance(mapping_ref, dict):
                mapping_ref = {}
            
            field_info = finding.get('field_info', {})
            if not isinstance(field_info, dict):
                field_info = {}
            
            field_seq = field_info.get('field_seq', 0)
            if not field_seq or field_seq == 0:
                field_seq = field_seq_counter[group_id]
            
            target_field = field_info.get('target_field', mapping_ref.get('target', finding.get('field_name', '')))
            
            sql_expression = ''
            if sql_structure and isinstance(sql_structure, dict):
                field_mapping = sql_structure.get('field_mapping', {})
                if field_mapping and target_field in field_mapping:
                    sql_expression = field_mapping.get(target_field, '')
            
            if not sql_expression:
                original_sql = finding.get('original_sql', '')
                if original_sql:
                    sql_expression = original_sql
            
            datamap_results.append({
                'group_id': group_id,
                'field_seq': field_seq,
                'target_field_cn': field_info.get('target_field_cn', ''),
                'target_field_en': target_field,
                'extract_method': field_info.get('extract_method', ''),
                'source_table': field_info.get('source_table_alias', mapping_ref.get('source_table', '')),
                'source_field_en': field_info.get('source_field', mapping_ref.get('source', '')),
                'source_field_cn': field_info.get('source_field_cn', ''),
                'default_value': field_info.get('default_value', ''),
                'transform_logic': field_info.get('transformation_logic', mapping_ref.get('logic', '')),
                'sql_expression': sql_expression,
                'is_consistent': is_consistent,
                'remark': finding.get('issue', '')
            })
    
    dataset_results = {
        'groups': list(groups_dict.values())
    }
    
    return dataset_results, datamap_results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    import urllib.request
    import urllib.error

    config = load_ollama_config()
    
    ollama_connected = False
    status = 'offline'
    
    if config.get('auto_connect', True):
        try:
            host = config.get('host', 'http://localhost:11434')
            timeout = int(config.get('timeout', 30))
            url = f'{host}/api/tags'
            req = urllib.request.Request(url, method='GET')
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                ollama_connected = True
                status = 'online'
        except urllib.error.URLError:
            status = 'offline'
        except Exception as e:
            print(f'Status check error: {e}')
            status = 'error'
    
    return jsonify({
        'success': True,
        'data': {
            'ollama_connected': ollama_connected,
            'model_name': config.get('model'),
            'status': status,
            'config': config
        }
    })

@app.route('/api/ollama/config', methods=['GET'])
def get_ollama_config():
    config = load_ollama_config()
    return jsonify({
        'success': True,
        'data': config
    })

@app.route('/api/ollama/config', methods=['POST'])
def update_ollama_config():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效的配置数据'}), 400

    config = {
        'host': data.get('host', 'http://localhost:11434'),
        'model': data.get('model', 'qwen2.5:7b'),
        'timeout': int(data.get('timeout', 30)),
        'auto_connect': data.get('auto_connect', True)
    }

    if save_ollama_config(config):
        return jsonify({
            'success': True,
            'message': '配置已保存',
            'data': config
        })
    else:
        return jsonify({'success': False, 'message': '配置保存失败'}), 500

@app.route('/api/ollama/test-connection', methods=['POST'])
def test_ollama_connection():
    import urllib.request
    import urllib.error

    data = request.get_json()
    host = data.get('host', 'http://localhost:11434')
    timeout = int(data.get('timeout', 30))

    try:
        url = f'{host}/api/tags'
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
            models = [m.get('name', '') for m in result.get('models', [])]
            return jsonify({
                'success': True,
                'message': '连接成功',
                'data': {
                    'connected': True,
                    'models': models
                }
            })
    except urllib.error.URLError as e:
        return jsonify({
            'success': False,
            'message': f'连接失败：无法访问 {host}，请确认Ollama服务是否启动'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'连接失败：{str(e)}'
        }), 400

@app.route('/api/upload', methods=['POST'])
def upload_mapping():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未检测到文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400
    if not file.filename.endswith('.xlsx'):
        return jsonify({'success': False, 'message': '仅支持.xlsx格式'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    
    parse_result = sql_engine.parse_mapping_file(file.filename)
    
    if parse_result['success']:
        summary = parse_result.get('summary', {})
        return jsonify({
            'success': True,
            'data': {
                'filename': file.filename,
                'tables': summary.get('tables', []),
                'field_mappings': parse_result.get('field_mappings', []),
                'relationships': parse_result.get('relationships', []),
                'summary': summary
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': f'文件解析失败: {parse_result.get("error", "未知错误")}'
        }), 400

@app.route('/api/review', methods=['POST'])
def start_review():
    data = request.get_json()
    
    mapping_file = data.get('mapping_file')
    sql_content = data.get('sql_content', '')
    business_context = data.get('business_context', '')
    dialect = data.get('dialect', 'Hive')
    
    if not mapping_file:
        return jsonify({'success': False, 'message': '缺少Mapping文件信息'}), 400
    
    if not sql_content:
        return jsonify({'success': False, 'message': '缺少SQL内容'}), 400
    
    mapping_path = os.path.join(app.config['UPLOAD_FOLDER'], mapping_file)
    if not os.path.exists(mapping_path):
        return jsonify({'success': False, 'message': f'Mapping文件不存在: {mapping_file}'}), 400
    
    with open(mapping_path, 'rb') as f:
        mapping_file_content = f.read()
    
    sql_filename = 'uploaded.sql'
    
    manager = get_data_flow_manager()
    result = manager.start_data_flow(
        mapping_file_content=mapping_file_content,
        mapping_filename=mapping_file,
        sql_file_content=sql_content.encode('utf-8'),
        sql_filename=sql_filename
    )
    
    return jsonify(result)

@app.route('/api/harness/compare', methods=['POST'])
def harness_compare():
    """使用Harness架构执行SQL字段提取和三Agent投票对比
    
    流程:
    1. SQLFieldExtractorAgent从SQL中提取字段信息
    2. 存储到dataset/datamap
    3. TripleAgentVoter进行三Agent投票判断一致性
    """
    data = request.get_json()
    
    task_id = data.get('task_id')
    mapping_file = data.get('mapping_file')
    sql_content = data.get('sql_content', '')
    fast_mode = data.get('fast_mode', False)
    
    if not task_id:
        return jsonify({'success': False, 'message': '缺少任务ID'}), 400
    
    if not mapping_file:
        return jsonify({'success': False, 'message': '缺少Mapping文件信息'}), 400
    
    if not sql_content:
        return jsonify({'success': False, 'message': '缺少SQL内容'}), 400
    
    try:
        from sql_correction_engine import ComparisonHarness
        from excel_parser import extract_field_mappings_from_excel
        
        config = load_ollama_config()
        harness = ComparisonHarness(config)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], mapping_file)
        field_mappings = extract_field_mappings_from_excel(file_path)
        
        if not field_mappings:
            return jsonify({'success': False, 'message': '无法从Mapping文件中提取字段映射'}), 400
        
        effective_sql = sql_engine.preprocess_sql_content(sql_content)
        sql_structure = sql_engine.parse_insert_select_structure(effective_sql)
        
        result = harness.execute_comparison(
            task_id=task_id,
            field_mappings=field_mappings,
            sql_content=sql_content,
            sql_structure=sql_structure,
            fast_mode=fast_mode
        )
        
        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'summary': result['summary'],
                'datamap_count': len(result['datamap_results']),
                'vote_results_count': len(result['vote_results'])
            }
        })
        
    except Exception as e:
        print(f'[HarnessCompare] 执行失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    manager = get_data_flow_manager()
    progress = manager.get_task_progress(task_id)
    if not progress or progress.get('status') == 'not_found':
        return jsonify(sql_engine.get_task_progress(task_id))
    return jsonify(progress)

@app.route('/api/result/<task_id>', methods=['GET'])
def get_result(task_id):
    manager = get_data_flow_manager()
    df_result = manager.get_task_result(task_id)
    if df_result and df_result.get('success'):
        return jsonify(df_result)
    
    result = sql_engine.get_task_result(task_id)
    if result.get('success') and result.get('data', {}).get('status') == 'completed':
        data = result['data']
        history_data = {
            'task_id': task_id,
            'mapping_file': data.get('mapping_file'),
            'sql_filename': data.get('sql_filename'),
            'sql_content': data.get('sql_content', ''),
            'status': 'completed',
            'total_checks': data.get('total_checks', 0),
            'consistent_count': data.get('consistent_count', 0),
            'inconsistent_count': data.get('inconsistent_count', 0),
            'duration': data.get('duration', 0),
            'findings': data.get('findings', []),
            'summary_text': data.get('summary_text')
        }
        history_service.save_review_result(task_id, history_data)
    return jsonify(result)

@app.route('/api/download/report/<task_id>', methods=['GET'])
def download_report(task_id):
    result = sql_engine.get_task_result(task_id)
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('error', '任务不存在或未完成')}), 404

    dataset_results = history_service.get_dataset_comparison_results(task_id)
    datamap_results = history_service.get_datamap_comparison_results(task_id)
    
    data = result['data']
    sql_content = data.get('sql_content', '')
    
    sql_structure = None
    if sql_content:
        effective_sql = sql_engine.preprocess_sql_content(sql_content)
        sql_structure = sql_engine.parse_insert_select_structure(effective_sql)
    
    if not dataset_results.get('groups') and not datamap_results:
        findings = data.get('findings', [])
        dataset_results, datamap_results = _convert_findings_to_excel_format(findings, task_id, sql_structure)
    
    record = history_service.get_record(task_id)
    mapping_file = record.get('mapping_file', '') if record else ''
    if not sql_content and record:
        sql_content = record.get('sql_content', '')
    
    if dataset_results.get('groups'):
        data_source_results = dataset_results
    elif mapping_file:
        data_source_results = _extract_data_source_info(mapping_file, sql_content)
    else:
        data_source_results = {'groups': []}
    
    excel_buffer = ReportFormatter.generate_excel_report(data_source_results, datamap_results)
    
    if mapping_file:
        base_name = os.path.splitext(os.path.basename(mapping_file))[0]
    else:
        base_name = task_id[:8]
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'SQL纠错报告_{base_name}_{timestamp}.xlsx'
    encoded_filename = quote(filename)

    return Response(
        excel_buffer.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )

@app.route('/api/excel-data/<task_id>', methods=['GET'])
def get_excel_data(task_id):
    """获取Excel格式化的数据，用于前端展示"""
    result = sql_engine.get_task_result(task_id)
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('error', '任务不存在或未完成')}), 404

    dataset_results = history_service.get_dataset_comparison_results(task_id)
    datamap_results = history_service.get_datamap_comparison_results(task_id)
    
    data = result['data']
    sql_content = data.get('sql_content', '')
    
    sql_structure = None
    if sql_content:
        effective_sql = sql_engine.preprocess_sql_content(sql_content)
        sql_structure = sql_engine.parse_insert_select_structure(effective_sql)
    
    if not dataset_results.get('groups') and not datamap_results:
        findings = data.get('findings', [])
        dataset_results, datamap_results = _convert_findings_to_excel_format(findings, task_id, sql_structure)
    
    record = history_service.get_record(task_id)
    mapping_file = record.get('mapping_file', '') if record else ''
    if not sql_content and record:
        sql_content = record.get('sql_content', '')
    
    if dataset_results.get('groups'):
        data_source_results = dataset_results
    elif mapping_file:
        data_source_results = _extract_data_source_info(mapping_file, sql_content)
    else:
        data_source_results = {'groups': []}
    
    dataset_inconsistent = 0
    for group in data_source_results.get('groups', []):
        for relation in group.get('relations', []):
            if relation.get('is_consistent') == '否':
                dataset_inconsistent += 1
    
    datamap_inconsistent = sum(1 for row in datamap_results if row.get('is_consistent') == '否')
    
    total_inconsistent = dataset_inconsistent + datamap_inconsistent
    total_checks = sum(len(g.get('relations', [])) for g in data_source_results.get('groups', [])) + len(datamap_results)
    
    return jsonify({
        'success': True,
        'data': {
            'task_id': task_id,
            'mapping_file': mapping_file,
            'dataset': {
                'headers': ReportFormatter.DATASET_HEADERS,
                'groups': data_source_results.get('groups', [])
            },
            'datamap': {
                'headers': ReportFormatter.DATAMAP_HEADERS,
                'rows': datamap_results
            },
            'statistics': {
                'total_checks': total_checks,
                'dataset_inconsistent': dataset_inconsistent,
                'datamap_inconsistent': datamap_inconsistent,
                'total_inconsistent': total_inconsistent
            }
        }
    })

@app.route('/api/download/annotated-sql/<task_id>', methods=['GET'])
def download_annotated_sql(task_id):
    result = sql_engine.get_task_result(task_id)
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('error', '任务不存在或未完成')}), 404

    data = result['data']
    sql_content = data.get('sql_content', '')
    findings = data.get('findings', [])

    if not sql_content:
        return jsonify({'success': False, 'message': '原始SQL内容为空'}), 400

    annotated_sql = SQLAnnotator.annotate(sql_content, findings)

    return Response(
        annotated_sql,
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename=annotated_sql_{task_id[:8]}.sql'
        }
    )

@app.route('/api/export/<task_id>', methods=['GET'])
def export_report(task_id):
    format_type = request.args.get('format', 'md')

    if format_type == 'md':
        return download_report(task_id)
    else:
        return download_report(task_id)

@app.route('/api/batch-download', methods=['GET'])
def batch_download_history():
    """
    批量下载多条历史记录的结果物，生成合并的Excel文件

    Query参数:
    - ids: 逗号分隔的任务ID列表 (如: "id1,id2,id3")

    返回:
    - Excel文件下载，包含所有记录的数据源和数据映射对比结果
    """
    ids_str = request.args.get('ids', '')
    if not ids_str:
        return jsonify({'success': False, 'message': '未指定要下载的记录ID'}), 400

    task_ids = [tid.strip() for tid in ids_str.split(',') if tid.strip()]
    if len(task_ids) == 0:
        return jsonify({'success': False, 'message': '无效的记录ID'}), 400

    try:
        merged_dataset_results = {
            'groups': []
        }
        all_datamap_results = []
        processed_mapping_files = set()
        
        for task_id in task_ids:
            dataset_results = history_service.get_dataset_comparison_results(task_id)
            datamap_results = history_service.get_datamap_comparison_results(task_id)
            
            record = history_service.get_record(task_id)
            sql_content = record.get('sql_content', '') if record else ''
            
            sql_structure = None
            if sql_content:
                effective_sql = sql_engine.preprocess_sql_content(sql_content)
                sql_structure = sql_engine.parse_insert_select_structure(effective_sql)
            
            if not dataset_results.get('groups') and not datamap_results:
                result = sql_engine.get_task_result(task_id)
                if result.get('success'):
                    findings = result['data'].get('findings', [])
                    dataset_results, datamap_results = _convert_findings_to_excel_format(findings, task_id, sql_structure)
            
            mapping_file = record.get('mapping_file', '') if record else ''
            if dataset_results.get('groups'):
                for group in dataset_results.get('groups', []):
                    merged_dataset_results['groups'].append(group)
            elif mapping_file and mapping_file not in processed_mapping_files:
                data_source_results = _extract_data_source_info(mapping_file, sql_content)
                
                for group in data_source_results.get('groups', []):
                    merged_dataset_results['groups'].append(group)
                
                processed_mapping_files.add(mapping_file)
            
            all_datamap_results.extend(datamap_results)
        
        if not merged_dataset_results['groups'] and not all_datamap_results:
            return jsonify({'success': False, 'message': '无法生成Excel文件，所有任务都无数据'}), 500
        
        excel_buffer = ReportFormatter.generate_excel_report(merged_dataset_results, all_datamap_results)
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'SQL纠错报告_批量_{timestamp}_{len(task_ids)}条.xlsx'
        encoded_filename = quote(filename)

        response = current_app.response_class(
            excel_buffer.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            direct_passthrough=True
        )
        response.headers.set(
            'Content-Disposition',
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
        return response

    except Exception as e:
        print(f'[Batch Download] Error: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'批量下载失败: {str(e)}'
        }), 500

@app.route('/api/batch/upload', methods=['POST'])
def batch_upload():
    import uuid
    batch_id = str(uuid.uuid4())
    return jsonify({
        'success': True,
        'data': {'batch_id': batch_id}
    })

@app.route('/api/batch/start', methods=['POST'])
def batch_start():
    return jsonify({'success': True})

@app.route('/api/history', methods=['GET'])
def get_history():
    limit = request.args.get('limit', 20, type=int)
    records = history_service.get_history(limit=limit)
    
    for record in records:
        task_id = record.get('id')
        mapping_file = record.get('mapping_file', '')
        sql_content = record.get('sql_content', '')
        
        if task_id:
            dataset_results = history_service.get_dataset_comparison_results(task_id)
            datamap_results = history_service.get_datamap_comparison_results(task_id)
            
            if not dataset_results.get('groups') and mapping_file:
                dataset_results = _extract_data_source_info(mapping_file, sql_content)
            
            dataset_inconsistent = 0
            for group in dataset_results.get('groups', []):
                for relation in group.get('relations', []):
                    if relation.get('is_consistent') == '否':
                        dataset_inconsistent += 1
            
            datamap_inconsistent = sum(1 for row in datamap_results if row.get('is_consistent') == '否')
            
            total_inconsistent = dataset_inconsistent + datamap_inconsistent
            total_checks = sum(len(g.get('relations', [])) for g in dataset_results.get('groups', [])) + len(datamap_results)
            
            if total_checks > 0:
                record['total_checks'] = total_checks
                record['inconsistent_count'] = total_inconsistent
                record['consistent_count'] = total_checks - total_inconsistent
    
    return jsonify({
        'success': True,
        'data': records
    })

@app.route('/api/history/<task_id>', methods=['DELETE'])
def delete_history(task_id):
    success = history_service.delete_record(task_id)
    if success:
        return jsonify({'success': True, 'message': '记录已删除'})
    else:
        return jsonify({'success': False, 'message': '记录不存在或删除失败'}), 404

data_flow_manager = None

def get_data_flow_manager():
    global data_flow_manager
    if data_flow_manager is None:
        from services.data_flow_manager import DataFlowManager
        data_flow_manager = DataFlowManager(
            upload_dir=UPLOAD_FOLDER,
            db_service=history_service
        )
    return data_flow_manager

@app.route('/api/dataflow/start', methods=['POST'])
def start_data_flow():
    if 'mapping_file' not in request.files or 'sql_file' not in request.files:
        return jsonify({
            'success': False,
            'message': '需要同时上传IT-Mapping文件和SQL文件'
        }), 400
    
    mapping_file = request.files['mapping_file']
    sql_file = request.files['sql_file']
    
    if mapping_file.filename == '' or sql_file.filename == '':
        return jsonify({
            'success': False,
            'message': '请选择要上传的文件'
        }), 400
    
    try:
        manager = get_data_flow_manager()
        
        task_id, result = manager.start_data_flow(
            mapping_file_content=mapping_file.read(),
            mapping_filename=mapping_file.filename,
            sql_file_content=sql_file.read(),
            sql_filename=sql_file.filename
        )
        
        return jsonify({
            'success': True,
            'data': {
                'task_id': task_id,
                'status': result['status'],
                'message': result['message']
            }
        })
        
    except Exception as e:
        print(f'[DataFlow] 启动失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'启动数据流处理失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/status/<task_id>', methods=['GET'])
def get_data_flow_status(task_id):
    try:
        manager = get_data_flow_manager()
        status = manager.get_task_status(task_id)
        
        if status is None:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        print(f'[DataFlow] 获取状态失败: {e}')
        return jsonify({
            'success': False,
            'message': f'获取任务状态失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/log/<task_id>', methods=['GET'])
def get_data_flow_log(task_id):
    try:
        manager = get_data_flow_manager()
        log = manager.get_comparison_log(task_id)
        
        if log is None:
            return jsonify({
                'success': False,
                'message': '日志不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': log
        })
        
    except Exception as e:
        print(f'[DataFlow] 获取日志失败: {e}')
        return jsonify({
            'success': False,
            'message': f'获取对比日志失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/export/<task_id>', methods=['GET'])
def export_data_flow_report(task_id):
    try:
        manager = get_data_flow_manager()
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            f'comparison_report_{task_id[:8]}_{timestamp}.json'
        )
        
        success = manager.export_comparison_report(task_id, output_path)
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'report_path': output_path,
                    'message': '报告导出成功'
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': '报告导出失败'
            }), 500
            
    except Exception as e:
        print(f'[DataFlow] 导出报告失败: {e}')
        return jsonify({
            'success': False,
            'message': f'导出报告失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/upload-mapping', methods=['POST'])
def upload_mapping_only():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未检测到文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': '仅支持.xlsx和.xls格式'}), 400
    
    try:
        from services.data_flow_manager import DataUploadHandler, ITMappingProcessor
        
        upload_handler = DataUploadHandler(UPLOAD_FOLDER)
        success, file_path, error = upload_handler.save_uploaded_file(
            file.read(), file.filename, 'mapping'
        )
        
        if not success:
            return jsonify({
                'success': False,
                'message': error.error_message if error else '文件上传失败'
            }), 400
        
        processor = ITMappingProcessor()
        task_id = str(uuid.uuid4())
        success, data, error = processor.parse_mapping_file(file_path, task_id)
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'filename': file.filename,
                    'file_path': file_path,
                    'data_sources_count': len(data.get('data_sources', [])),
                    'field_mappings_count': len(data.get('field_mappings', [])),
                    'sheets': list(data.get('sheets', {}).keys())
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': error.error_message if error else '文件解析失败'
            }), 400
            
    except Exception as e:
        print(f'[DataFlow] 上传Mapping失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'上传处理失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/upload-sql', methods=['POST'])
def upload_sql_only():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未检测到文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'}), 400
    
    if not file.filename.endswith(('.sql', '.txt')):
        return jsonify({'success': False, 'message': '仅支持.sql和.txt格式'}), 400
    
    try:
        from services.data_flow_manager import DataUploadHandler, SQLProcessor
        
        upload_handler = DataUploadHandler(UPLOAD_FOLDER)
        success, file_path, error = upload_handler.save_uploaded_file(
            file.read(), file.filename, 'sql'
        )
        
        if not success:
            return jsonify({
                'success': False,
                'message': error.error_message if error else '文件上传失败'
            }), 400
        
        processor = SQLProcessor()
        task_id = str(uuid.uuid4())
        success, data, error = processor.parse_sql_file(file_path, task_id)
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'filename': file.filename,
                    'file_path': file_path,
                    'procedure_name': data.get('procedure_name', ''),
                    'insert_blocks_count': len(data.get('insert_blocks', [])),
                    'content_length': data.get('content_length', 0)
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': error.error_message if error else '文件解析失败'
            }), 400
            
    except Exception as e:
        print(f'[DataFlow] 上传SQL失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'上传处理失败: {str(e)}'
        }), 500

@app.route('/api/dataflow/compare', methods=['POST'])
def execute_comparison():
    data = request.get_json()
    
    task_id = data.get('task_id')
    mapping_file = data.get('mapping_file')
    sql_content = data.get('sql_content', '')
    
    if not task_id or not mapping_file or not sql_content:
        return jsonify({
            'success': False,
            'message': '缺少必要参数: task_id, mapping_file, sql_content'
        }), 400
    
    try:
        from services.data_flow_manager import ConsistencyComparator, ComparisonLogger
        
        comparator = ConsistencyComparator(
            db_service=history_service,
            logger_instance=ComparisonLogger()
        )
        
        sql_data = {
            'insert_blocks': data.get('insert_blocks', [])
        }
        
        success, metrics, error = comparator.compare_all_records(
            task_id, mapping_file, sql_data
        )
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'task_id': task_id,
                    'metrics': metrics.to_dict()
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': error.error_message if error else '对比失败'
            }), 500
            
    except Exception as e:
        print(f'[DataFlow] 对比失败: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'对比执行失败: {str(e)}'
        }), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'message': '文件大小超过50MB限制'}), 413

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

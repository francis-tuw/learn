import sqlite3
import os
import json
from datetime import datetime

class HistoryService:
    def __init__(self, db_path='data/review_history.db'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_history (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mapping_file TEXT,
                sql_filename TEXT,
                sql_content TEXT,
                status TEXT,
                total_checks INTEGER DEFAULT 0,
                consistent_count INTEGER DEFAULT 0,
                inconsistent_count INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 0,
                findings_json TEXT,
                summary_text TEXT
            )
        ''')
        
        try:
            cursor.execute('ALTER TABLE review_history ADD COLUMN sql_content TEXT')
        except sqlite3.OperationalError:
            pass
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS field_check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                excel_row INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                final_status TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                vote_details_json TEXT,
                agent_results_json TEXT,
                merged_findings_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(task_id, excel_row)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_field_check_task_id 
            ON field_check_results(task_id)
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dataset_comparison_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                source_tables TEXT,
                compare_module TEXT NOT NULL,
                mapping_item TEXT,
                sql_content TEXT,
                is_consistent TEXT DEFAULT '是',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_dataset_task_id 
            ON dataset_comparison_results(task_id)
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS datamap_comparison_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                field_seq INTEGER NOT NULL,
                target_field_cn TEXT,
                target_field_en TEXT,
                extract_method TEXT,
                source_table TEXT,
                source_field_en TEXT,
                source_field_cn TEXT,
                default_value TEXT,
                transform_logic TEXT,
                sql_expression TEXT,
                is_consistent TEXT DEFAULT '是',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_datamap_task_id 
            ON datamap_comparison_results(task_id)
        ''')
        
        # 新增表：IT-Mapping 数据源信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mapping_file TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                alias TEXT NOT NULL,
                name TEXT NOT NULL,
                relationships_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(mapping_file, sheet_name)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_data_sources_mapping_file 
            ON data_sources(mapping_file)
        ''')
        
        # 新增表：IT-Mapping 数据映射信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS field_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mapping_file TEXT NOT NULL,
                group_id TEXT NOT NULL,
                field_seq INTEGER NOT NULL,
                target_field TEXT NOT NULL,
                target_field_cn TEXT,
                source_table_alias TEXT,
                source_field TEXT,
                source_field_cn TEXT,
                default_value TEXT,
                transformation_logic TEXT,
                business_rule TEXT,
                data_type TEXT,
                extract_method TEXT,
                sheet TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(mapping_file, group_id, target_field)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_field_mappings_mapping_file 
            ON field_mappings(mapping_file)
        ''')
        
        # 新增表：SQL 文件信息
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sql_files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 新增表：数据源（DataSet）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_set (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                compare_module TEXT NOT NULL,
                it_mapping_file TEXT,
                sql_procedure TEXT,
                is_consistent TEXT DEFAULT '是',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_data_set_group_id 
            ON data_set(group_id)
        ''')
        
        # 新增表：数据映射（DataMap）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                field_seq INTEGER NOT NULL,
                target_field_cn TEXT NOT NULL,
                target_field_en TEXT NOT NULL,
                extract_method TEXT,
                source_table TEXT,
                source_field_en TEXT,
                source_field_cn TEXT,
                default_value TEXT,
                transform_logic TEXT,
                sql_expression TEXT,
                is_consistent TEXT DEFAULT '是',
                remark TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_data_map_group_id 
            ON data_map(group_id)
        ''')
        
        cursor.execute("PRAGMA table_info(dataset_comparison_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'source_tables' not in columns:
            cursor.execute('ALTER TABLE dataset_comparison_results ADD COLUMN source_tables TEXT')
            print('[HistoryService] 已为dataset_comparison_results表添加source_tables列')
        
        conn.commit()
        conn.close()
    
    def save_review_result(self, task_id, data):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            findings = data.get('findings', [])
            findings_json = json.dumps(findings, ensure_ascii=False) if findings else None

            cursor.execute('''
                INSERT OR REPLACE INTO review_history 
                (id, mapping_file, sql_filename, sql_content, status, total_checks, 
                 consistent_count, inconsistent_count, duration, findings_json, summary_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                data.get('mapping_file'),
                data.get('sql_filename'),
                data.get('sql_content', ''),
                data.get('status', 'completed'),
                data.get('total_checks', 0),
                data.get('consistent_count', 0),
                data.get('inconsistent_count', 0),
                data.get('duration', 0),
                findings_json,
                data.get('summary_text')
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存记录失败: {e}')
            return False
    
    def get_history(self, limit=20):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM review_history 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            result = []
            for row in rows:
                record = dict(row)
                if record.get('findings_json'):
                    try:
                        record['findings'] = json.loads(record['findings_json'])
                    except json.JSONDecodeError:
                        record['findings'] = []
                else:
                    record['findings'] = []
                del record['findings_json']
                result.append(record)

            conn.close()
            return result
        except Exception as e:
            print(f'[HistoryService] 获取历史记录失败: {e}')
            return []
    
    def get_record(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM review_history WHERE id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            if row:
                record = dict(row)
                if record.get('findings_json'):
                    try:
                        record['findings'] = json.loads(record['findings_json'])
                    except json.JSONDecodeError:
                        record['findings'] = []
                else:
                    record['findings'] = []
                del record['findings_json']
                conn.close()
                return record
            
            conn.close()
            return None
        except Exception as e:
            print(f'[HistoryService] 获取记录失败: {e}')
            return None
    
    def delete_record(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM review_history WHERE id = ?', (task_id,))
            deleted = cursor.rowcount > 0

            cursor.execute('DELETE FROM field_check_results WHERE task_id = ?', (task_id,))

            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            print(f'[HistoryService] 删除记录失败: {e}')
            return False
    
    def save_field_check_result(self, task_id, excel_row, field_name, final_status, 
                                  confidence=0.0, vote_details=None, agent_results=None, 
                                  merged_findings=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            vote_details_json = json.dumps(vote_details, ensure_ascii=False) if vote_details else None
            agent_results_json = json.dumps(agent_results, ensure_ascii=False) if agent_results else None
            merged_findings_json = json.dumps(merged_findings, ensure_ascii=False) if merged_findings else None

            cursor.execute('''
                INSERT OR REPLACE INTO field_check_results 
                (task_id, excel_row, field_name, final_status, confidence, 
                 vote_details_json, agent_results_json, merged_findings_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                excel_row,
                field_name,
                final_status,
                confidence,
                vote_details_json,
                agent_results_json,
                merged_findings_json
            ))

            conn.commit()
            conn.close()
            print(f'[HistoryService] 字段检查结果已保存: task_id={task_id}, row={excel_row}, field={field_name}')
            return True
        except Exception as e:
            print(f'[HistoryService] 保存字段检查结果失败: {e}')
            return False
    
    def get_field_check_results(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM field_check_results 
                WHERE task_id = ? 
                ORDER BY excel_row ASC
            ''', (task_id,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                record = dict(row)
                if record.get('vote_details_json'):
                    try:
                        record['vote_details'] = json.loads(record['vote_details_json'])
                    except json.JSONDecodeError:
                        record['vote_details'] = {}
                else:
                    record['vote_details'] = {}
                
                if record.get('agent_results_json'):
                    try:
                        record['agent_results'] = json.loads(record['agent_results_json'])
                    except json.JSONDecodeError:
                        record['agent_results'] = []
                else:
                    record['agent_results'] = []
                
                if record.get('merged_findings_json'):
                    try:
                        record['merged_findings'] = json.loads(record['merged_findings_json'])
                    except json.JSONDecodeError:
                        record['merged_findings'] = []
                else:
                    record['merged_findings'] = []
                
                del record['vote_details_json']
                del record['agent_results_json']
                del record['merged_findings_json']
                results.append(record)

            conn.close()
            print(f'[HistoryService] 获取字段检查结果: task_id={task_id}, 共{len(results)}条')
            return results
        except Exception as e:
            print(f'[HistoryService] 获取字段检查结果失败: {e}')
            return []
    
    def clear_field_check_results(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM field_check_results WHERE task_id = ?', (task_id,))
            deleted_count = cursor.rowcount

            conn.commit()
            conn.close()
            print(f'[HistoryService] 清除字段检查结果: task_id={task_id}, 删除{deleted_count}条')
            return True
        except Exception as e:
            print(f'[HistoryService] 清除字段检查结果失败: {e}')
            return False
    
    def save_dataset_comparison(self, task_id, group_id, compare_module, 
                                 source_tables='', mapping_item='', sql_content='', is_consistent='是', remark=''):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO dataset_comparison_results 
                (task_id, group_id, source_tables, compare_module, mapping_item, sql_content, is_consistent, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, group_id, source_tables, compare_module, mapping_item, sql_content, is_consistent, remark))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存数据源对比结果失败: {e}')
            return False
    
    def save_dataset_comparison_batch(self, task_id, results):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for r in results:
                cursor.execute('''
                    INSERT INTO dataset_comparison_results 
                    (task_id, group_id, source_tables, compare_module, mapping_item, sql_content, is_consistent, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id,
                    r.get('group_id', ''),
                    r.get('source_tables', ''),
                    r.get('compare_module', ''),
                    r.get('mapping_item', ''),
                    r.get('sql_content', ''),
                    r.get('is_consistent', '是'),
                    r.get('remark', '')
                ))

            conn.commit()
            conn.close()
            print(f'[HistoryService] 批量保存数据源对比结果: task_id={task_id}, 共{len(results)}条')
            return True
        except Exception as e:
            print(f'[HistoryService] 批量保存数据源对比结果失败: {e}')
            return False
    
    def get_dataset_comparison_results(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM dataset_comparison_results 
                WHERE task_id = ? 
                ORDER BY group_id, id ASC
            ''', (task_id,))

            rows = cursor.fetchall()
            
            groups_dict = {}
            for row in rows:
                row_dict = dict(row)
                group_id = row_dict.get('group_id', '')
                source_tables = row_dict.get('source_tables', '')
                
                if group_id not in groups_dict:
                    groups_dict[group_id] = {
                        'group_id': group_id,
                        'source_tables': source_tables,
                        'relations': []
                    }
                
                groups_dict[group_id]['relations'].append({
                    'compare_module': row_dict.get('compare_module', ''),
                    'content': row_dict.get('mapping_item', ''),
                    'sql_content': row_dict.get('sql_content', ''),
                    'is_consistent': row_dict.get('is_consistent', '是'),
                    'remark': row_dict.get('remark', '')
                })
            
            results = {
                'groups': list(groups_dict.values())
            }

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取数据源对比结果失败: {e}')
            return {'groups': []}
    
    def save_datamap_comparison(self, task_id, group_id, field_seq, 
                                 target_field_cn='', target_field_en='', extract_method='',
                                 source_table='', source_field_en='', source_field_cn='',
                                 default_value='', transform_logic='', sql_expression='',
                                 is_consistent='是', remark=''):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 先尝试更新现有记录
            cursor.execute('''
                UPDATE datamap_comparison_results 
                SET target_field_cn = ?, target_field_en = ?, extract_method = ?, 
                    source_table = ?, source_field_en = ?, source_field_cn = ?, 
                    default_value = ?, transform_logic = ?, sql_expression = ?, 
                    is_consistent = ?, remark = ?
                WHERE task_id = ? AND group_id = ? AND field_seq = ?
            ''', (
                target_field_cn, target_field_en, extract_method, 
                source_table, source_field_en, source_field_cn, 
                default_value, transform_logic, sql_expression, 
                is_consistent, remark, task_id, group_id, field_seq
            ))

            # 如果没有更新任何记录，则插入新记录
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO datamap_comparison_results 
                    (task_id, group_id, field_seq, target_field_cn, target_field_en, 
                     extract_method, source_table, source_field_en, source_field_cn,
                     default_value, transform_logic, sql_expression, is_consistent, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id, group_id, field_seq, target_field_cn, target_field_en,
                    extract_method, source_table, source_field_en, source_field_cn,
                    default_value, transform_logic, sql_expression, is_consistent, remark
                ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存数据映射对比结果失败: {e}')
            return False
    
    def save_datamap_comparison_batch(self, task_id, results, clear_existing=False):
        """批量保存数据映射对比结果

        Args:
            task_id (str): 任务ID
            results (list): 结果列表
            clear_existing (bool): 是否清除所有现有数据。默认False，只更新当前批次涉及的分组
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if clear_existing:
                cursor.execute('DELETE FROM datamap_comparison_results WHERE task_id = ?', (task_id,))
                print(f'[HistoryService] 已清除task_id={task_id}的所有数据映射结果')
            else:
                group_ids_in_batch = set(r.get('group_id', '') for r in results if r.get('group_id'))
                if group_ids_in_batch:
                    placeholders = ','.join(['?' for _ in group_ids_in_batch])
                    cursor.execute(
                        f'DELETE FROM datamap_comparison_results WHERE task_id = ? AND group_id IN ({placeholders})',
                        [task_id] + list(group_ids_in_batch)
                    )
                    print(f'[HistoryService] 已清除分组 {group_ids_in_batch} 的现有数据（保留其他分组）')

            for r in results:
                field_seq = r.get('field_seq', 0)
                try:
                    field_seq = int(field_seq) if field_seq else 0
                except (ValueError, TypeError):
                    field_seq = 0

                cursor.execute('''
                    INSERT INTO datamap_comparison_results 
                    (task_id, group_id, field_seq, target_field_cn, target_field_en, 
                     extract_method, source_table, source_field_en, source_field_cn,
                     default_value, transform_logic, sql_expression, is_consistent, remark)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id,
                    r.get('group_id', ''),
                    field_seq,
                    r.get('target_field_cn', ''),
                    r.get('target_field_en', ''),
                    r.get('extract_method', ''),
                    r.get('source_table', ''),
                    r.get('source_field_en', ''),
                    r.get('source_field_cn', ''),
                    r.get('default_value', ''),
                    r.get('transform_logic', ''),
                    r.get('sql_expression', ''),
                    r.get('is_consistent', '是'),
                    r.get('remark', '')
                ))

            conn.commit()
            
            cursor.execute('SELECT COUNT(*) FROM datamap_comparison_results WHERE task_id = ?', (task_id,))
            total_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT group_id, COUNT(*) FROM datamap_comparison_results WHERE task_id = ? GROUP BY group_id', (task_id,))
            group_counts = cursor.fetchall()
            
            conn.close()
            print(f'[HistoryService] 批量保存数据映射对比结果: task_id={task_id}, 本次保存{len(results)}条, 数据库共{total_count}条')
            for gid, cnt in group_counts:
                print(f'  - 分组 {gid}: {cnt}条')
            return True
        except Exception as e:
            print(f'[HistoryService] 批量保存数据映射对比结果失败: {e}')
            import traceback
            traceback.print_exc()
            return False
    
    def get_datamap_comparison_results(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM datamap_comparison_results 
                WHERE task_id = ? 
                ORDER BY group_id, field_seq ASC
            ''', (task_id,))

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取数据映射对比结果失败: {e}')
            return []
    
    def clear_comparison_results(self, task_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM dataset_comparison_results WHERE task_id = ?', (task_id,))
            cursor.execute('DELETE FROM datamap_comparison_results WHERE task_id = ?', (task_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 清除对比结果失败: {e}')
            return False
    
    def get_all_comparison_results_for_excel(self, task_ids):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            placeholders = ','.join(['?' for _ in task_ids])
            
            cursor.execute(f'''
                SELECT * FROM dataset_comparison_results 
                WHERE task_id IN ({placeholders})
                ORDER BY task_id, group_id, id ASC
            ''', task_ids)
            dataset_results = [dict(row) for row in cursor.fetchall()]

            cursor.execute(f'''
                SELECT * FROM datamap_comparison_results 
                WHERE task_id IN ({placeholders})
                ORDER BY task_id, group_id, field_seq ASC
            ''', task_ids)
            datamap_results = [dict(row) for row in cursor.fetchall()]

            conn.close()
            return {
                'dataset': dataset_results,
                'datamap': datamap_results
            }
        except Exception as e:
            print(f'[HistoryService] 获取Excel对比结果失败: {e}')
            return {'dataset': [], 'datamap': []}
    
    def save_data_source(self, mapping_file, sheet_name, alias, name, relationships=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            relationships_json = json.dumps(relationships, ensure_ascii=False) if relationships else None

            cursor.execute('''
                INSERT OR REPLACE INTO data_sources 
                (mapping_file, sheet_name, alias, name, relationships_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (mapping_file, sheet_name, alias, name, relationships_json))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存数据源信息失败: {e}')
            return False
    
    def save_field_mapping(self, mapping_file, group_id, field_seq, target_field, 
                          target_field_cn='', source_table_alias='', source_field='', 
                          source_field_cn='', default_value='', transformation_logic='', 
                          business_rule='', data_type='', extract_method='', sheet=''):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO field_mappings 
                (mapping_file, group_id, field_seq, target_field, target_field_cn, 
                 source_table_alias, source_field, source_field_cn, default_value, 
                 transformation_logic, business_rule, data_type, extract_method, sheet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                mapping_file, group_id, field_seq, target_field, target_field_cn,
                source_table_alias, source_field, source_field_cn, default_value,
                transformation_logic, business_rule, data_type, extract_method, sheet
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存字段映射信息失败: {e}')
            return False
    
    def save_sql_file(self, sql_id, filename, content):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO sql_files 
                (id, filename, content)
                VALUES (?, ?, ?)
            ''', (sql_id, filename, content))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存SQL文件失败: {e}')
            return False
    
    def get_data_sources(self, mapping_file):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM data_sources 
                WHERE mapping_file = ?
            ''', (mapping_file,))

            rows = cursor.fetchall()
            results = []
            for row in rows:
                record = dict(row)
                if record.get('relationships_json'):
                    try:
                        record['relationships'] = json.loads(record['relationships_json'])
                    except json.JSONDecodeError:
                        record['relationships'] = []
                else:
                    record['relationships'] = []
                del record['relationships_json']
                results.append(record)

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取数据源信息失败: {e}')
            return []
    
    def get_field_mappings(self, mapping_file):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM field_mappings 
                WHERE mapping_file = ?
                ORDER BY field_seq ASC
            ''', (mapping_file,))

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取字段映射信息失败: {e}')
            return []
    
    def get_sql_file(self, sql_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM sql_files 
                WHERE id = ?
            ''', (sql_id,))

            row = cursor.fetchone()
            if row:
                record = dict(row)
                conn.close()
                return record
            
            conn.close()
            return None
        except Exception as e:
            print(f'[HistoryService] 获取SQL文件失败: {e}')
            return None
    
    def clear_mapping_data(self, mapping_file):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM data_sources WHERE mapping_file = ?', (mapping_file,))
            cursor.execute('DELETE FROM field_mappings WHERE mapping_file = ?', (mapping_file,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 清除映射数据失败: {e}')
            return False
    
    def save_data_set(self, group_id, compare_module, it_mapping_file='', sql_procedure='', is_consistent='是', remark=''):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO data_set 
                (group_id, compare_module, it_mapping_file, sql_procedure, is_consistent, remark)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (group_id, compare_module, it_mapping_file, sql_procedure, is_consistent, remark))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存数据源记录失败: {e}')
            return False
    
    def get_data_set(self, group_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM data_set 
                WHERE group_id = ? 
                ORDER BY id ASC
            ''', (group_id,))

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取数据源记录失败: {e}')
            return []
    
    def clear_data_set(self, group_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM data_set WHERE group_id = ?', (group_id,))
            deleted_count = cursor.rowcount

            conn.commit()
            conn.close()
            print(f'[HistoryService] 清除数据源记录: group_id={group_id}, 删除{deleted_count}条')
            return True
        except Exception as e:
            print(f'[HistoryService] 清除数据源记录失败: {e}')
            return False
    
    def save_data_map(self, group_id, field_seq, target_field_cn, target_field_en, 
                     extract_method='', source_table='', source_field_en='', source_field_cn='',
                     default_value='', transform_logic='', sql_expression='',
                     is_consistent='是', remark=''):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO data_map 
                (group_id, field_seq, target_field_cn, target_field_en, 
                 extract_method, source_table, source_field_en, source_field_cn,
                 default_value, transform_logic, sql_expression, is_consistent, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                group_id, field_seq, target_field_cn, target_field_en,
                extract_method, source_table, source_field_en, source_field_cn,
                default_value, transform_logic, sql_expression, is_consistent, remark
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 保存数据映射记录失败: {e}')
            return False
    
    def get_data_map(self, group_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM data_map 
                WHERE group_id = ? 
                ORDER BY field_seq ASC
            ''', (group_id,))

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()
            return results
        except Exception as e:
            print(f'[HistoryService] 获取数据映射记录失败: {e}')
            return []
    
    def clear_data_map(self, group_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM data_map WHERE group_id = ?', (group_id,))
            deleted_count = cursor.rowcount

            conn.commit()
            conn.close()
            print(f'[HistoryService] 清除数据映射记录: group_id={group_id}, 删除{deleted_count}条')
            return True
        except Exception as e:
            print(f'[HistoryService] 清除数据映射记录失败: {e}')
            return False
    
    def update_dataset_comparison_sql(self, task_id, group_id, sql_content):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE dataset_comparison_results 
                SET sql_content = ?
                WHERE task_id = ? AND group_id = ?
            ''', (sql_content, task_id, group_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 更新数据源对比结果SQL信息失败: {e}')
            return False
    
    def update_datamap_comparison_sql(self, task_id, group_id, target_field, sql_expression):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE datamap_comparison_results 
                SET sql_expression = ?
                WHERE task_id = ? AND group_id = ? AND target_field_en = ?
            ''', (sql_expression, task_id, group_id, target_field))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f'[HistoryService] 更新数据映射对比结果SQL信息失败: {e}')
            return False

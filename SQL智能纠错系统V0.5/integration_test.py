#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统集成测试脚本
验证SQL智能纠错系统的完整功能流程
"""
import os
import time
import json
import requests
from datetime import datetime

BASE_URL = "http://localhost:5001"
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ITMAPPING_FILE = os.path.join(TEST_DIR, "【客户物理地址信息】ITMappingv0.8.xlsx")
SQL_FILE = os.path.join(TEST_DIR, "SP_DWD_DM_T02_CUST_ADDR_INFO.sql")

def test_system_status():
    """测试系统状态"""
    print("\n=== 测试系统状态 ===")
    response = requests.get(f"{BASE_URL}/api/status")
    data = response.json()
    print(f"状态: {data['data']['status']}")
    print(f"Ollama连接: {data['data']['ollama_connected']}")
    print(f"模型: {data['data']['model_name']}")
    return response.status_code == 200

def test_upload_mapping():
    """测试IT-Mapping文件上传"""
    print("\n=== 测试IT-Mapping文件上传 ===")
    with open(ITMAPPING_FILE, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/api/upload", files=files)
    
    data = response.json()
    if response.status_code == 200 and data['success']:
        print(f"上传成功: {data['data']['filename']}")
        print(f"总字段数: {data['data']['summary']['total_fields']}")
        print(f"总表数: {data['data']['summary']['total_tables']}")
        return True
    else:
        print(f"上传失败: {data.get('message', '未知错误')}")
        return False

def test_upload_sql():
    """测试SQL文件上传"""
    print("\n=== 测试SQL文件上传 ===")
    with open(SQL_FILE, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/api/dataflow/upload-sql", files=files)
    
    data = response.json()
    if response.status_code == 200 and data['success']:
        print(f"上传成功: {data['data']['filename']}")
        print(f"INSERT块数: {data['data']['insert_blocks_count']}")
        print(f"存储过程名: {data['data']['procedure_name']}")
        return True
    else:
        print(f"上传失败: {data.get('message', '未知错误')}")
        return False

def test_data_flow():
    """测试完整数据流处理"""
    print("\n=== 测试完整数据流处理 ===")
    with open(ITMAPPING_FILE, 'rb') as f1, open(SQL_FILE, 'rb') as f2:
        files = {
            'mapping_file': f1,
            'sql_file': f2
        }
        response = requests.post(f"{BASE_URL}/api/dataflow/start", files=files)
    
    data = response.json()
    if response.status_code == 200 and data['success']:
        task_id = data['data']['task_id']
        print(f"数据流启动成功，任务ID: {task_id}")
        
        # 等待任务完成
        print("等待任务完成...")
        for i in range(10):
            time.sleep(2)
            status_response = requests.get(f"{BASE_URL}/api/dataflow/status/{task_id}")
            status_data = status_response.json()
            if status_data['success']:
                status = status_data['data']['status']
                print(f"任务状态: {status}")
                if status == 'completed':
                    print("任务完成！")
                    metrics = status_data['data']['result']['metrics']
                    print(f"总记录数: {metrics['total_records']}")
                    print(f"一致记录: {metrics['consistent_records']}")
                    print(f"不一致记录: {metrics['inconsistent_records']}")
                    print(f"错误记录: {metrics['error_records']}")
                    return True
                elif status == 'failed':
                    print(f"任务失败: {status_data['data'].get('errors', [])}")
                    return False
        print("任务超时")
        return False
    else:
        print(f"数据流启动失败: {data.get('message', '未知错误')}")
        return False

def test_report_download(task_id):
    """测试报告下载"""
    print("\n=== 测试报告下载 ===")
    response = requests.get(f"{BASE_URL}/api/download/report/{task_id}")
    if response.status_code == 200:
        print("报告下载成功")
        print(f"文件大小: {len(response.content)} 字节")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"文件名: {response.headers.get('Content-Disposition')}")
        return True
    else:
        print(f"报告下载失败: {response.status_code}")
        return False

def test_history():
    """测试历史记录功能"""
    print("\n=== 测试历史记录功能 ===")
    response = requests.get(f"{BASE_URL}/api/history")
    data = response.json()
    if response.status_code == 200 and data['success']:
        records = data['data']
        print(f"历史记录数: {len(records)}")
        if records:
            print(f"最新记录: {records[0]['mapping_file']}")
        return True
    else:
        print(f"获取历史记录失败: {data.get('message', '未知错误')}")
        return False

def main():
    """主测试函数"""
    print("开始SQL智能纠错系统集成测试...")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试文件: {ITMAPPING_FILE}")
    print(f"测试SQL: {SQL_FILE}")
    
    tests = [
        test_system_status,
        test_upload_mapping,
        test_upload_sql,
        test_data_flow,
        test_history
    ]
    
    passed = 0
    failed = 0
    task_id = None
    
    for test in tests:
        try:
            if test():
                passed += 1
                # 保存任务ID用于后续测试
                if test.__name__ == 'test_data_flow':
                    # 重新获取任务ID
                    history_response = requests.get(f"{BASE_URL}/api/history")
                    if history_response.status_code == 200:
                        history_data = history_response.json()
                        if history_data['success'] and history_data['data']:
                            task_id = history_data['data'][0]['id']
            else:
                failed += 1
        except Exception as e:
            print(f"测试 {test.__name__} 失败: {e}")
            failed += 1
    
    # 测试报告下载
    if task_id:
        try:
            if test_report_download(task_id):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"测试报告下载失败: {e}")
            failed += 1
    
    print(f"\n=== 测试完成 ===")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"成功率: {passed / (passed + failed) * 100:.2f}%")
    
    if failed == 0:
        print("🎉 所有测试通过！系统运行正常。")
    else:
        print("❌ 部分测试失败，需要检查系统。")

if __name__ == "__main__":
    main()

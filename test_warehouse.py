#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WAREHOUSE_API_URL = "http://localhost:8000"
DATA_DIR = "warehouse/text_data"  # 更新数据目录路径

def test_store_data(content, uid=None, db_type="text"):
    """Test storing data in the warehouse"""
    url = f"{WAREHOUSE_API_URL}/store"
    payload = {"content": content}
    
    # 如果提供了 uid，则添加到 payload 中
    if uid:
        payload["uid"] = uid
        
    params = {"db_type": db_type}
    
    try:
        response = requests.post(url, json=payload, params=params)
        
        if response.status_code == 200:
            data = response.json()
            uid = data.get("data", {}).get("uid")
            print(f"Data stored successfully in {db_type} storage: UID {uid}")
            return uid
        else:
            print(f"Error storing data: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Exception storing data: {str(e)}")
        return None

def test_get_data(param, db_type="text", uids=None):
    """Test retrieving data from the warehouse"""
    url = f"{WAREHOUSE_API_URL}/data"
    params = {"p": param, "db_type": db_type}
    
    if param == "by_uids" and uids:
        params["uids"] = ",".join(uids)
    
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", {}).get("items", [])
            
            print(f"\nRetrieved {len(items)} items from {db_type} storage:")
            for i, item in enumerate(items):
                print(f"{i+1}. UID: {item.get('uid')}")
                content = item.get('content', '')
                if len(content) > 70:
                    content = content[:70] + "..."
                print(f"   Content: {content}")
            
            return items
        else:
            print(f"Error retrieving data: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception retrieving data: {str(e)}")
        return []

def generate_sample_data(count=5, db_type="text", use_custom_uid=False):
    """Generate and store sample data"""
    print(f"\n=== Generating {count} sample data items in {db_type} storage ===")
    
    stored_uids = []
    
    for i in range(count):
        content = f"这是测试内容 #{i+1}"
        
        if use_custom_uid:
            # 使用自定义 UID
            uid = f"test_{int(time.time())}_{i}"
            stored_uid = test_store_data(content, uid, db_type)
        else:
            # 使用自动生成的 UUID
            stored_uid = test_store_data(content, None, db_type)
            
        if stored_uid:
            stored_uids.append(stored_uid)
    
    print(f"Generated {len(stored_uids)} sample data items")
    return stored_uids

def test_uuid_generation():
    """测试 UUID 生成"""
    print("\n=== 测试 UUID 生成 ===")
    
    # 生成并打印一些 UUID 示例
    for i in range(3):
        u = uuid.uuid4()
        print(f"UUID 示例 #{i+1}: {u}")
        print(f"  - 类型: {type(u)}")
        print(f"  - 字符串形式: {str(u)}")
        print(f"  - 十六进制: {u.hex}")
        print(f"  - 整数形式: {u.int}")
        print(f"  - 字节形式: {u.bytes}")
        print()

def main():
    """Main test function"""
    print("=== DegenPy Warehouse API Test ===")
    
    # 测试 UUID 生成
    test_uuid_generation()
    
    # 测试使用自动生成的 UUID
    print("\n--- 测试使用自动生成的 UUID ---")
    auto_uids = generate_sample_data(2, "text", use_custom_uid=False)
    
    # 测试使用自定义 UID
    print("\n--- 测试使用自定义 UID ---")
    custom_uids = generate_sample_data(2, "text", use_custom_uid=True)
    
    # 测试获取最近数据
    print("\n--- 测试获取最近数据 ---")
    test_get_data("last30", "text")
    
    # 测试根据 UID 获取数据
    all_uids = auto_uids + custom_uids
    if all_uids:
        print("\n--- 测试根据 UID 获取数据 ---")
        test_get_data("by_uids", "text", all_uids[:2])
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()

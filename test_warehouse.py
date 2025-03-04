#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WAREHOUSE_API_URL = "http://localhost:8000"

def test_store_data(uid, content, db_type="text"):
    """Test storing data in the warehouse"""
    url = f"{WAREHOUSE_API_URL}/store"
    payload = {"uid": uid, "content": content}
    params = {"db_type": db_type}
    
    try:
        response = requests.post(url, json=payload, params=params)
        
        if response.status_code == 200:
            print(f"Data stored successfully in {db_type} storage: UID {uid}")
            return True
        else:
            print(f"Error storing data: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Exception storing data: {str(e)}")
        return False

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
                if len(content) > 50:
                    content = content[:50] + "..."
                print(f"   Content: {content}")
            
            return items
        else:
            print(f"Error retrieving data: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        print(f"Exception retrieving data: {str(e)}")
        return []

def generate_sample_data(count=5, db_type="text"):
    """Generate and store sample data"""
    print(f"\n=== Generating {count} sample data items in {db_type} storage ===")
    
    stored_uids = []
    
    for i in range(count):
        uid = f"test_{int(time.time())}_{i}"
        content = f"This is test content #{i+1} generated at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        if test_store_data(uid, content, db_type):
            stored_uids.append(uid)
    
    print(f"Generated {len(stored_uids)} sample data items")
    return stored_uids

def main():
    """Main test function"""
    print("=== DegenPy Warehouse API Test ===")
    
    # Test text storage
    print("\n--- Testing Text Storage ---")
    text_uids = generate_sample_data(3, "text")
    
    # Test retrieving last 5 items
    print("\n--- Testing Get Last Items ---")
    test_get_data("last30", "text")
    
    # Test retrieving by UIDs
    if text_uids:
        print("\n--- Testing Get By UIDs ---")
        test_get_data("by_uids", "text", text_uids[:2])
    
    # Test MySQL storage (if available)
    try:
        print("\n--- Testing MySQL Storage (if available) ---")
        mysql_uids = generate_sample_data(2, "mysql")
        
        if mysql_uids:
            print("\n--- Testing MySQL Retrieval ---")
            test_get_data("last30", "mysql")
    except Exception as e:
        print(f"\nMySQL storage not available: {str(e)}")
    
    print("\n=== Test Completed ===")

if __name__ == "__main__":
    main()

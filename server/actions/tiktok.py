#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import json
import time
from typing import Dict, Any, Optional, Tuple, List
from dotenv import load_dotenv, set_key
from pathlib import Path
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING

# Load environment variables
load_dotenv()

# MongoDB connection
def get_mongo_connection():
    """
    Get MongoDB connection for TikTok token storage
    
    Returns:
        MongoDB collection for tiktok_tokens
    """
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    if not connection_string:
        raise ValueError("MongoDB connection string not found in environment variables")
    
    client = MongoClient(connection_string)
    db_name = os.getenv('MONGODB_DATABASE', 'degenpy')
    db = client[db_name]
    collection = db['tiktok_tokens']
    
    # Create indexes for efficient querying
    try:
        # Check if indexes exist before creating them
        existing_indexes = collection.index_information()
        
        # Create index on created_at field if it doesn't exist
        if 'created_at_-1' not in existing_indexes:
            collection.create_index([('created_at', DESCENDING)], background=True)
            print("Created index on created_at field")
            
        # Create index on expires_at field if it doesn't exist
        if 'expires_at_1' not in existing_indexes:
            collection.create_index('expires_at', background=True)
            print("Created index on expires_at field")
            
        # Create index on access_token field if it doesn't exist
        if 'access_token_1' not in existing_indexes:
            collection.create_index('access_token', background=True)
            print("Created index on access_token field")
    except Exception as e:
        print(f"Warning: Failed to create indexes: {e}")
    
    return collection

def get_tiktok_token():
    """
    获取 TikTok 访问令牌使用授权码
    
    Returns:
        包含令牌数据和获取时间戳的字典，如果失败则返回 None
    """
    # 直接从 .env 文件读取凭证
    env_path = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        return None
        
    # 读取 .env 文件内容
    env_vars = {}
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')
    except Exception as e:
        print(f"Error reading .env file: {e}")
        return None
    
    # 获取 TikTok 凭证
    client_key = env_vars.get('TIKTOK_CLIENT_KEY')
    client_secret = env_vars.get('TIKTOK_CLIENT_SECRET')
    code = env_vars.get('TIKTOK_AUTH_CODE')
    redirect_uri = env_vars.get('TIKTOK_REDIRECT_URI')
    
    if not all([client_key, client_secret, code, redirect_uri]):
        print("Error: TikTok credentials not found in .env file")
        print(f"Available keys: {list(env_vars.keys())}")
        return None
    
    try:
        # Make the token request
        response = requests.post(
            'https://open.tiktokapis.com/v2/oauth/token/',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cache-Control': 'no-cache'
            },
            data={
                'client_key': client_key,
                'client_secret': client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
        )
        
        # Check if request was successful
        if response.status_code == 200:
            # Add acquisition timestamp
            token_data = response.json()
            token_data['acquired_at'] = datetime.now().timestamp()
            return token_data
        else:
            print(f"Error getting TikTok token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception getting TikTok token: {str(e)}")
        return None

def process_token_response(response_str):
    """
    Process token response string: extract token data, calculate expiration time,
    save to .env file and store in MongoDB
    
    Args:
        response_str: JSON response string from TikTok API
        
    Returns:
        Dict containing the token data or None if parsing failed
    """
    # Clean up the response string
    response_str = response_str.strip()
    if response_str.endswith('%'):
        response_str = response_str[:-1]
    
    try:
        # Parse the JSON response
        token_data = json.loads(response_str)
        
        # Calculate token expiration time
        acquired_at = token_data.get('acquired_at', datetime.now().timestamp())
        expires_in = int(token_data.get('expires_in', 86400))  # Default to 24 hours if not provided
        expires_at = acquired_at + expires_in
        
        # Get path to .env file
        env_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / '.env'
        
        # Save token data to .env file
        set_key(env_path, 'TIKTOK_ACCESS_TOKEN', token_data.get('access_token', ''))
        set_key(env_path, 'TIKTOK_REFRESH_TOKEN', token_data.get('refresh_token', ''))
        set_key(env_path, 'TIKTOK_TOKEN_EXPIRES_IN', str(expires_in))
        set_key(env_path, 'TIKTOK_OPEN_ID', token_data.get('open_id', ''))
        set_key(env_path, 'TIKTOK_TOKEN_TYPE', token_data.get('token_type', ''))
        set_key(env_path, 'TIKTOK_SCOPE', token_data.get('scope', ''))
        
        print(f"Token saved to {env_path}")
        
        # Store token in MongoDB
        try:
            collection = get_mongo_connection()
            
            # Create token document
            token_document = {
                'access_token': token_data.get('access_token', ''),
                'refresh_token': token_data.get('refresh_token', ''),
                'expires_at': expires_at,
                'created_at': datetime.now(),
            }
            
            # Insert token document
            collection.insert_one(token_document)
            print(f"Token stored in MongoDB, expires at: {datetime.fromtimestamp(expires_at)}")
            
        except Exception as e:
            print(f"Error storing token in MongoDB: {e}")
        
        # Add expiration time to returned token data
        token_data['expires_at'] = expires_at
        return token_data
        
    except json.JSONDecodeError as e:
        print(f"Error parsing response: {e}")
        return None

def get_valid_token() -> Optional[str]:
    """
    获取有效的 TikTok 访问令牌
    
    Returns:
        有效的访问令牌或者 None（如果无法获取）
    """
    try:
        # 从 MongoDB 获取最新的 token 记录
        collection = get_mongo_connection()
        token_doc = collection.find_one(
            {'access_token': {'$exists': True, '$ne': ''}},  # 确保 access_token 存在且不为空
            sort=[('created_at', DESCENDING)]
        )
        
        if token_doc:
            # 检查 token 是否仍然有效
            expires_at = token_doc.get('expires_at')
            current_time = datetime.now().timestamp()
            
            if expires_at and current_time < expires_at:
                # Token 仍然有效，直接返回
                access_token = token_doc.get('access_token')
                return access_token
            else:
                print("TikTok token 已过期，尝试获取新 token")
        else:
            print("数据库中没有找到有效的 TikTok token")
        
        # 获取新 token
        token_data = get_tiktok_token()
        if token_data and 'access_token' in token_data:
            # 处理并存储 token
            processed_token = process_token_response(json.dumps(token_data))
            if processed_token and 'access_token' in processed_token:
                print(f"成功获取并存储新 token")
                return processed_token.get('access_token')
        
        # 如果无法获取新 token，尝试使用环境变量中的 token
        env_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        if env_token:
            print("使用环境变量中的 token")
            return env_token
            
        print("没有可用的有效 token")
        return None
        
    except Exception as e:
        print(f"获取有效 token 时出错: {e}")
        # 尝试使用环境变量中的 token
        env_token = os.getenv("TIKTOK_ACCESS_TOKEN")
        if env_token:
            print("出错后使用环境变量中的 token")
            return env_token
        return None

def publish_to_tiktok(video_url: str, caption: str = "new_report", hashtags: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Publish a video to TikTok
    
    Args:
        video_url: URL to the video file
        caption: Caption for the video
        hashtags: List of hashtags to include
            
    Returns:
        Tuple of (success, publish_id)
            success: True if video was published successfully
            publish_id: ID of the published video or None if failed
    """
    # Get a valid access token
    access_token = get_valid_token()
    
    if not access_token:
        print("Error: Unable to get a valid TikTok access token")
        return False, None
    
    # Prepare the caption with hashtags
    if hashtags:
        # Add hashtags to caption if not already included
        for tag in hashtags:
            if tag not in caption:
                caption += f" {tag}"
    
    # Prepare request data
    data = {
        "post_info": {
            "title": caption,
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": True,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url
        }
    }
    
    try:
        # Make the request to publish the video
        response = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            data=json.dumps(data)
        )
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            publish_id = result.get("data", {}).get("publish_id")
            
            if publish_id:
                # Return success and publish ID
                return True, publish_id
            else:
                print(f"Error: No publish_id in response: {result}")
                return False, None
        else:
            print(f"Error publishing to TikTok: {response.status_code} - {response.text}")
            return False, None
            
    except Exception as e:
        print(f"Exception publishing to TikTok: {str(e)}")
        return False, None
        
def check_publish_status(publish_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check the status of a published video
    
    Args:
        publish_id: ID of the published video
        
    Returns:
        Tuple of (success, status)
            success: True if status check was successful
            status: Status of the published video or None if check failed
    """
    # Get access token from environment variables
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
    
    if not access_token:
        print("Error: TikTok access token not found in environment variables")
        return False, None
    
    # Prepare request data
    data = {
        "publish_id": publish_id
    }
    
    try:
        # Make the request to check the status
        response = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8"
            },
            data=json.dumps(data)
        )
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            status = result.get("data", {}).get("status")
            
            if status:
                # Return success and status
                return True, status
            else:
                print(f"Error: No status in response: {result}")
                return False, None
        else:
            print(f"Error checking publish status: {response.status_code} - {response.text}")
            return False, None
            
    except Exception as e:
        print(f"Exception checking publish status: {str(e)}")
        return False, None

if __name__ == "__main__":
    success, publish_id = publish_to_tiktok(
        video_url="https://tbt.kip.pro/google-oauth2%7C110776176785457408466/tlk_bMUL8IO9eRcjxAkRHKs3E/1741863859672.mp4?AWSAccessKeyId=AKIA5CUMPJBIK65W6FGA&Expires=1741950278&Signature=v8Kg%2FGYJfgoj0UeR6w7KbMz1LFs%3D",
        caption="Testing TikTok API integration with token management",
        hashtags=["#test", "#api", "#tiktok"]
    )
        
    # Check the publish status
    status_success, status = check_publish_status(publish_id)
    if status_success:
        print(f"Publish status: {status}")
        
        # If status is not complete, wait and check again
        if status != "PUBLISH_COMPLETE":
            print("Waiting for video to be processed...")
            time.sleep(5)  # Wait 5 seconds
            status_success, status = check_publish_status(publish_id)
            if status_success:
                print(f"Updated publish status: {status}")
    else:
        print("Failed to check publish status")
    # Test 4: Check status of a known publish ID
    example_publish_id = "v_pub_url~v2-1.7481612523855398967"
    print(f"\nTest 4: Checking status of example publish ID: {example_publish_id}")
    status_success, status = check_publish_status(example_publish_id)
    if status_success:
        print(f"Publish status: {status}")
    else:
        print("Failed to check publish status")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import logging
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('text2v')

# 直接从根目录下的 .env 文件读取配置
def load_env_from_file():
    env_path = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
    if not env_path.exists():
        logger.error(f"Error: .env file not found at {env_path}")
        return {}
        
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
        logger.info(f"Successfully loaded .env file from {env_path}")
        return env_vars
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
        return {}

# Load environment variables
env_vars = load_env_from_file()

# D-ID API configuration
API_CREATE_URL = env_vars.get("TEXT2VIDEO_API_CREATE_URL", "https://api.d-id.com/talks")
API_STATUS_URL = env_vars.get("TEXT2VIDEO_API_STATUS_URL", "https://api.d-id.com/talks/{id}")
API_KEY = env_vars.get("TEXT2VIDEO_API_KEY", "")

# Default avatar image URL
DEFAULT_AVATAR_URL = "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"

def check_api_configuration() -> Dict[str, Any]:
    """
    Check if D-ID API configuration is valid
    
    Returns:
        Dictionary containing configuration status
    """
    if not API_KEY:
        logger.warning("D-ID API key not found in .env file")
        return {
            "valid": False,
            "error": "D-ID API key not found in .env file. Please add TEXT2VIDEO_API_KEY to your .env file."
        }
    
    # Check if API URLs are valid
    if not API_CREATE_URL or not API_STATUS_URL:
        logger.warning("D-ID API URLs not properly configured")
        return {
            "valid": False,
            "error": "D-ID API URLs not properly configured. Please check your .env file."
        }
    
    logger.info("D-ID API configuration is valid")
    return {
        "valid": True,
        "error": None,
        "api_key": f"{API_KEY[:5]}...{API_KEY[-5:]}" if API_KEY else None,
        "create_url": API_CREATE_URL,
        "status_url": API_STATUS_URL
    }

def create_video(text: str, avatar_url: str = None) -> Dict[str, Any]:
    """
    Create a video task using D-ID API
    
    Args:
        text: Text content to be displayed in the video
        avatar_url: Avatar image URL, defaults to the sample avatar provided by D-ID
        
    Returns:
        Dictionary containing task information, including id, status, etc.
    """
    try:
        # Check if API configuration is valid
        config_status = check_api_configuration()
        if not config_status["valid"]:
            error_msg = config_status["error"]
            logger.error(error_msg)
            return {
                "success": False,
                "video_id": None,
                "status": "error",
                "created_at": None,
                "error": error_msg,
                "raw_response": None
            }
            
        # If avatar URL is not specified, use the default avatar
        if not avatar_url:
            avatar_url = DEFAULT_AVATAR_URL
            
        # Prepare request data
        payload = {
            "source_url": avatar_url,
            "script": {
                "type": "text",
                "subtitles": "false",
                "provider": {
                    "type": "microsoft",
                    "voice_id": "Sara" 
                },
                "input": text,
                "ssml": "false"
            },
            "config": { "fluent": "false" }
        }
        
        # Prepare request headers
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Basic eXVhbi53QGhpZ2hicm93dGVjaC51cw:SYKEflQYIKVjgi1C6Ja8W"
        }
        
        # Send request to create video
        logger.info(f"Starting video creation: {text[:30]}...")
        response = requests.post(API_CREATE_URL, json=payload, headers=headers)
        
        # Process response
        if response.status_code in [200, 201, 202]:
            result = response.json()
            logger.info(f"Video creation task successfully submitted: ID={result.get('id')}")
            return {
                "success": True,
                "video_id": result.get('id'),
                "status": result.get('status', 'created'),
                "created_at": result.get('created_at'),
                "error": None,
                "raw_response": result
            }
        else:
            error_msg = f"Failed to create video: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "video_id": None,
                "status": "error",
                "created_at": None,
                "error": error_msg,
                "raw_response": None
            }
            
    except Exception as e:
        error_msg = f"Video creation exception: {str(e)}"
        logger.exception(error_msg)
        return {
            "success": False,
            "video_id": None,
            "status": "error",
            "created_at": None,
            "error": error_msg,
            "raw_response": None
        }

def get_video_status(video_id: str) -> Dict[str, Any]:
    """
    Get the status of a D-ID video task
    
    Args:
        video_id: Video task ID
        
    Returns:
        Dictionary containing video task status information
    """
    try:
        # Check if API configuration is valid
        config_status = check_api_configuration()
        if not config_status["valid"]:
            error_msg = config_status["error"]
            logger.error(error_msg)
            return {
                "success": False,
                "video_id": video_id,
                "status": "error",
                "result_url": None,
                "error": error_msg,
                "raw_response": None
            }
            
        # Build status query URL
        status_url = API_STATUS_URL.format(id=video_id)
        
        # Prepare request headers
        headers = {
            "accept": "application/json",
            "authorization": f"Basic eXVhbi53QGhpZ2hicm93dGVjaC51cw:SYKEflQYIKVjgi1C6Ja8W"
        }
        
        # Send request to get status
        logger.info(f"Querying video status: ID={video_id}")
        response = requests.get(status_url, headers=headers)
        
        # Process response
        if response.status_code == 200:
            result = response.json()
            status = result.get('status')
            logger.info(f"Retrieved video status: ID={video_id}, Status={status}")
            
            # Build return data
            response_data = {
                "success": True,
                "video_id": video_id,
                "status": status,
                "result_url": result.get('result_url'),  # Video URL
                "error": None,
                "raw_response": result
            }
            
            # If video is completed, add video URL
            if status == "done":
                response_data["video_url"] = result.get('result_url')
                logger.info(f"Video generation completed: ID={video_id}, URL={result.get('result_url')}")
            # If video generation failed, add error information
            elif status == "error":
                response_data["error"] = result.get('error', 'Unknown error')
                logger.error(f"Video generation failed: ID={video_id}, Error={result.get('error', 'Unknown error')}")
                
            return response_data
        else:
            error_msg = f"Failed to get video status: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {
                "success": False,
                "video_id": video_id,
                "status": "error",
                "result_url": None,
                "error": error_msg,
                "raw_response": None
            }
            
    except Exception as e:
        error_msg = f"Exception getting video status: {str(e)}"
        logger.exception(error_msg)
        return {
            "success": False,
            "video_id": video_id,
            "status": "error",
            "result_url": None,
            "error": error_msg,
            "raw_response": None
        }

if __name__ == "__main__":
    # Validate configuration
    print("\n=== Checking D-ID API Configuration ===\n")
    config = check_api_configuration()
    print(f"Configuration status: {json.dumps(config, ensure_ascii=False, indent=2)}")
    
    if not config["valid"]:
        print(f"\nError: {config['error']}")
        print("Please add the correct TEXT2VIDEO_API_KEY to your .env file\n")
        exit(1)
    
    # Test example
    print("\n=== Testing Video Creation ===\n")
    test_text = "Bitcoin price breaks through $70,000, reaching an all-time high! The cryptocurrency market continues to strengthen, with Ethereum also breaking through the $4,000 mark."
    
    # Step 1: Create video
    create_result = create_video(test_text)
    print(f"Video creation result: {json.dumps(create_result, ensure_ascii=False, indent=2)}")
    
    if create_result["success"]:
        video_id = create_result["video_id"]
        
        # Step 2: Query video status (polling may be needed in actual applications)
        import time
        print("\nWaiting 5 seconds before querying video status...")
        time.sleep(5)
        
        status_result = get_video_status(video_id)
        print(f"Video status: {json.dumps(status_result, ensure_ascii=False, indent=2)}")
        
        if status_result["success"] and status_result["status"] == "done":
            print(f"\nVideo generation successful! View at: {status_result.get('result_url')}")
        elif status_result["success"] and status_result["status"] == "processing":
            print("\nVideo is processing, please check status later")
        else:
            print(f"\nVideo generation failed: {status_result.get('error')}")
    else:
        print(f"\nUnable to create video: {create_result.get('error')}")
    
    print("\n=== Test Completed ===\n")

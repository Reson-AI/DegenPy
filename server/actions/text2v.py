#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import logging
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('text2v')

# 加载环境变量
load_dotenv()

# D-ID API配置
API_CREATE_URL = os.getenv("TEXT2VIDEO_API_CREATE_URL", "https://api.d-id.com/talks")
API_STATUS_URL = os.getenv("TEXT2VIDEO_API_STATUS_URL", "https://api.d-id.com/talks/{id}")
API_KEY = os.getenv("TEXT2VIDEO_API_KEY", "")

# 默认头像图片URL
DEFAULT_AVATAR_URL = "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg"

def create_video(text: str, avatar_url: str = None) -> Dict[str, Any]:
    """
    使用D-ID API创建视频任务
    
    Args:
        text: 要在视频中展示的文本内容
        avatar_url: 头像图片URL，默认使用D-ID提供的示例头像
        
    Returns:
        包含任务信息的字典，包括id、状态等
    """
    try:
        # 如果未指定头像URL，使用默认头像
        if not avatar_url:
            avatar_url = DEFAULT_AVATAR_URL
            
        # 准备请求数据
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
        
        # 准备请求头
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {API_KEY}"
        }
        
        # 发送请求创建视频
        logger.info(f"开始创建视频: {text[:30]}...")
        response = requests.post(API_CREATE_URL, json=payload, headers=headers)
        
        # 处理响应
        if response.status_code in [200, 201, 202]:
            result = response.json()
            logger.info(f"视频创建任务成功提交: ID={result.get('id')}")
            return {
                "success": True,
                "video_id": result.get('id'),
                "status": result.get('status', 'created'),
                "created_at": result.get('created_at'),
                "error": None,
                "raw_response": result
            }
        else:
            error_msg = f"创建视频失败: HTTP {response.status_code} - {response.text}"
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
        error_msg = f"视频创建异常: {str(e)}"
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
    获取D-ID视频任务的状态
    
    Args:
        video_id: 视频任务ID
        
    Returns:
        包含视频任务状态信息的字典
    """
    try:
        # 构建状态查询URL
        status_url = API_STATUS_URL.format(id=video_id)
        
        # 准备请求头
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {API_KEY}"
        }
        
        # 发送请求获取状态
        logger.info(f"正在查询视频状态: ID={video_id}")
        response = requests.get(status_url, headers=headers)
        
        # 处理响应
        if response.status_code == 200:
            result = response.json()
            status = result.get('status')
            logger.info(f"获取到视频状态: ID={video_id}, 状态={status}")
            
            # 构建返回数据
            response_data = {
                "success": True,
                "video_id": video_id,
                "status": status,
                "result_url": result.get('result_url'),  # 视频URL
                "error": None,
                "raw_response": result
            }
            
            # 如果视频已完成，添加视频URL
            if status == "done":
                response_data["video_url"] = result.get('result_url')
                logger.info(f"视频生成完成: ID={video_id}, URL={result.get('result_url')}")
            # 如果视频生成失败，添加错误信息
            elif status == "error":
                response_data["error"] = result.get('error', '未知错误')
                logger.error(f"视频生成失败: ID={video_id}, 错误={result.get('error', '未知错误')}")
                
            return response_data
        else:
            error_msg = f"获取视频状态失败: HTTP {response.status_code} - {response.text}"
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
        error_msg = f"获取视频状态异常: {str(e)}"
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
    # 测试示例
    test_text = "比特币价格突破7万美元，创历史新高！加密货币市场持续走强，以太坊也突破4000美元关口。"
    
    # 步骤1: 创建视频
    create_result = create_video(test_text)
    print(f"创建视频结果: {json.dumps(create_result, ensure_ascii=False, indent=2)}")
    
    if create_result["success"]:
        video_id = create_result["video_id"]
        
        # 步骤2: 查询视频状态 (实际应用中可能需要轮询)
        import time
        print("等待5秒后查询视频状态...")
        time.sleep(5)
        
        status_result = get_video_status(video_id)
        print(f"视频状态: {json.dumps(status_result, ensure_ascii=False, indent=2)}")

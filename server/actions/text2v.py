#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Text2VideoGenerator:
    """
    Text to Video generation service
    
    负责与文生视频 API 交互，执行具体的视频生成操作
    """
    
    def __init__(self):
        self.api_url = os.getenv("TEXT2VIDEO_API_URL")
        if not self.api_url:
            print("Warning: TEXT2VIDEO_API_URL environment variable not set, using mock implementation")
            self.api_url = None
            
    def generate(self, text: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        从文本生成视频
        
        Args:
            text: 用于生成视频的文本内容
            config: 视频生成配置
                - style: 视频风格 (news_report, trend_analysis 等)
                - duration: 目标时长（秒）
                - resolution: 分辨率
                - format: 视频格式
                
        Returns:
            (成功标志, 视频URL或本地路径, 错误信息)
        """
        if not self.api_url:
            return self._mock_generate(text, config)
            
        try:
            # 准备请求数据
            payload = {
                "text": text,
                "style": config.get("style", "default"),
                "duration": config.get("duration", 30),
                "resolution": config.get("resolution", "1080p"),
                "format": config.get("format", "mp4")
            }
            
            # 发送 API 请求
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 202:
                # 异步处理 - 获取任务ID并轮询状态
                job_id = response.json().get("job_id")
                return self._poll_job_status(job_id)
            elif response.status_code == 200:
                # 同步响应
                video_url = response.json().get("video_url")
                return True, video_url, None
            else:
                error_msg = f"Error generating video: {response.status_code} - {response.text}"
                print(error_msg)
                return False, None, error_msg
                
        except Exception as e:
            error_msg = f"Exception in text2video generation: {str(e)}"
            print(error_msg)
            return False, None, error_msg
            
    def _poll_job_status(self, job_id: str, max_attempts: int = 30, delay: int = 10) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        轮询任务完成状态
        
        Args:
            job_id: 任务ID
            max_attempts: 最大轮询次数
            delay: 轮询间隔（秒）
            
        Returns:
            (成功标志, 视频URL, 错误信息)
        """
        status_url = f"{self.api_url}/status/{job_id}"
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(status_url)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    
                    if status == "completed":
                        return True, data.get("video_url"), None
                    elif status == "failed":
                        error_msg = f"Video generation failed: {data.get('error')}"
                        print(error_msg)
                        return False, None, error_msg
                    else:
                        # 仍在处理中
                        print(f"Video generation in progress ({attempt+1}/{max_attempts}): {status}")
                        time.sleep(delay)
                else:
                    print(f"Error checking job status: {response.status_code} - {response.text}")
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"Exception while polling job status: {str(e)}")
                time.sleep(delay)
                
        error_msg = f"Timed out waiting for video generation after {max_attempts} attempts"
        print(error_msg)
        return False, None, error_msg
        
    def _mock_generate(self, text: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        模拟视频生成（用于测试）
        
        Args:
            text: 文本内容
            config: 配置
            
        Returns:
            (成功标志, 模拟视频路径, 错误信息)
        """
        try:
            # 创建临时视频文件
            import tempfile
            import uuid
            
            # 创建一个唯一的文件名
            video_id = str(uuid.uuid4())
            video_dir = os.path.join(tempfile.gettempdir(), "degenpy_videos")
            os.makedirs(video_dir, exist_ok=True)
            
            video_path = os.path.join(video_dir, f"{video_id}.mp4")
            
            # 创建一个空的视频文件（模拟）
            with open(video_path, "wb") as f:
                f.write(b"MOCK_VIDEO_DATA")
                
            print(f"Mock video generated at: {video_path}")
            
            # 模拟处理延迟
            time.sleep(2)
            
            return True, video_path, None
            
        except Exception as e:
            error_msg = f"Error in mock video generation: {str(e)}"
            print(error_msg)
            return False, None, error_msg

# 单例实例
generator = Text2VideoGenerator()

def generate_video(text: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    从文本生成视频
    
    Args:
        text: 用于生成视频的文本内容
        config: 视频生成配置
            
    Returns:
        (成功标志, 视频URL或本地路径, 错误信息)
    """
    return generator.generate(text, config)

if __name__ == "__main__":
    # 示例用法
    config = {
        "style": "news_report",
        "duration": 30
    }
    
    sample_text = """
    Bitcoin has reached a new all-time high today, surpassing $70,000 for the first time.
    Analysts attribute this surge to increased institutional adoption and growing interest
    from traditional finance. This milestone comes after months of steady growth and
    represents a significant moment for cryptocurrency enthusiasts.
    """
    
    success, video_path, error = generate_video(sample_text, config)
    
    if success and video_path:
        print(f"Video generated successfully: {video_path}")
    else:
        print(f"Failed to generate video: {error}")

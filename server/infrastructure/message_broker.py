#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import redis
import threading
import logging
from typing import Dict, Any, List, Callable, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("message_broker")

# Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# 频道名称
VIDEO_TASK_CHANNEL = "degenpy:video_tasks"
ACTION_TASK_CHANNEL = "degenpy:action_tasks"

class MessageBroker:
    """
    消息代理类
    
    负责管理 Redis 发布/订阅通信
    """
    
    def __init__(self):
        """初始化消息代理"""
        try:
            self.redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True
            )
            self.pubsub = self.redis.pubsub()
            self.subscribers = {}
            self.running = False
            
            # 测试连接
            self.redis.ping()
            logger.info("Connected to Redis server")
            
        except redis.ConnectionError as e:
            logger.error(f"Error connecting to Redis: {str(e)}")
            logger.info("Using fallback in-memory message broker")
            self.redis = None
            self.pubsub = None
            self.messages = []
            self.callbacks = {}
            
    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        发布消息到指定频道
        
        Args:
            channel: 频道名称
            message: 消息内容
            
        Returns:
            发布是否成功
        """
        try:
            if self.redis:
                # 使用 Redis 发布
                message_str = json.dumps(message)
                return bool(self.redis.publish(channel, message_str))
            else:
                # 使用内存回退方案
                message_data = {
                    "channel": channel,
                    "message": message,
                    "timestamp": time.time()
                }
                self.messages.append(message_data)
                
                # 调用已注册的回调
                if channel in self.callbacks:
                    for callback in self.callbacks[channel]:
                        try:
                            callback(message)
                        except Exception as e:
                            logger.error(f"Error in callback: {str(e)}")
                            
                return True
                
        except Exception as e:
            logger.error(f"Error publishing message: {str(e)}")
            return False
            
    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """
        订阅指定频道
        
        Args:
            channel: 频道名称
            callback: 消息处理回调函数
            
        Returns:
            订阅是否成功
        """
        try:
            if self.redis:
                # 使用 Redis 订阅
                if channel not in self.subscribers:
                    self.subscribers[channel] = []
                self.subscribers[channel].append(callback)
                
                # 确保已订阅该频道
                self.pubsub.subscribe(channel)
                
                # 如果尚未运行，启动消息处理线程
                if not self.running:
                    self._start_message_thread()
                    
                return True
            else:
                # 使用内存回退方案
                if channel not in self.callbacks:
                    self.callbacks[channel] = []
                self.callbacks[channel].append(callback)
                return True
                
        except Exception as e:
            logger.error(f"Error subscribing to channel: {str(e)}")
            return False
            
    def _start_message_thread(self):
        """启动消息处理线程"""
        import threading
        
        def message_worker():
            self.running = True
            while self.running:
                try:
                    message = self.pubsub.get_message()
                    if message and message["type"] == "message":
                        channel = message["channel"]
                        data = json.loads(message["data"])
                        
                        if channel in self.subscribers:
                            for callback in self.subscribers[channel]:
                                try:
                                    callback(data)
                                except Exception as e:
                                    logger.error(f"Error in callback: {str(e)}")
                                    
                    time.sleep(0.01)  # 避免 CPU 占用过高
                except Exception as e:
                    logger.error(f"Error in message worker: {str(e)}")
                    time.sleep(1)  # 发生错误时等待一段时间
                    
        thread = threading.Thread(target=message_worker, daemon=True)
        thread.start()
        
    def stop(self):
        """停止消息代理"""
        self.running = False
        if self.pubsub:
            self.pubsub.unsubscribe()
        if self.redis:
            self.redis.close()

# 创建单例实例
broker = MessageBroker()

# 导出函数
def publish_video_task(task_id: str, status: str, data: Dict[str, Any]) -> bool:
    """
    发布视频任务状态更新
    
    Args:
        task_id: 任务ID
        status: 任务状态
        data: 任务数据
        
    Returns:
        发布是否成功
    """
    message = {
        "task_id": task_id,
        "status": status,
        "timestamp": time.time(),
        "data": data
    }
    return broker.publish(VIDEO_TASK_CHANNEL, message)

def publish_action_task(task_id: str, action: str, platform: str, 
                       status: str, data: Dict[str, Any]) -> bool:
    """
    发布动作任务状态更新
    
    Args:
        task_id: 任务ID
        action: 动作类型
        platform: 平台
        status: 任务状态
        data: 任务数据
        
    Returns:
        发布是否成功
    """
    message = {
        "task_id": task_id,
        "action": action,
        "platform": platform,
        "status": status,
        "timestamp": time.time(),
        "data": data
    }
    return broker.publish(ACTION_TASK_CHANNEL, message)

def subscribe_to_video_tasks(callback: Callable[[Dict[str, Any]], None]) -> bool:
    """
    订阅视频任务更新
    
    Args:
        callback: 消息处理回调函数
        
    Returns:
        订阅是否成功
    """
    return broker.subscribe(VIDEO_TASK_CHANNEL, callback)

def subscribe_to_action_tasks(callback: Callable[[Dict[str, Any]], None]) -> bool:
    """
    订阅动作任务更新
    
    Args:
        callback: 消息处理回调函数
        
    Returns:
        订阅是否成功
    """
    return broker.subscribe(ACTION_TASK_CHANNEL, callback)

if __name__ == "__main__":
    # 测试代码
    def handle_video_task(message):
        logger.info(f"Received video task: {message}")
        
    def handle_action_task(message):
        logger.info(f"Received action task: {message}")
        
    # 订阅频道
    subscribe_to_video_tasks(handle_video_task)
    subscribe_to_action_tasks(handle_action_task)
    
    # 发布测试消息
    publish_video_task(
        task_id="test-task-1",
        status="completed",
        data={
            "content": "比特币价格突破6万美元，创下历史新高！",
            "video_path": "/path/to/video.mp4"
        }
    )
    
    publish_action_task(
        task_id="test-task-1",
        action="publish",
        platform="tiktok",
        status="pending",
        data={
            "content": "比特币价格突破6万美元，创下历史新高！",
            "video_path": "/path/to/video.mp4"
        }
    )
    
    # 等待消息处理
    time.sleep(1)
    broker.stop()

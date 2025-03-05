#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import threading
import logging
from typing import Dict, Any, List, Optional, Callable
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入消息代理
from server.infrastructure.message_broker import subscribe_to_action_tasks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("action_dispatcher")

# 导入自定义模块
from server.infrastructure.video_pool import get_video_task, get_video_path
from server.infrastructure.actions.twitter import post_to_twitter
from server.infrastructure.actions.webhook import notify_content_published, notify_video_created

class ActionDispatcher:
    """
    动作调度器
    
    负责监听视频生成事件，并根据任务配置执行后续动作
    """
    
    def __init__(self):
        """初始化动作调度器"""
        self.running = False
        self.action_handlers = {
            "twitter": self._handle_twitter_action,
            "tiktok": self._handle_tiktok_action,
            "webhook": self._handle_webhook_action
        }
        
    def start(self):
        """启动动作调度器"""
        if self.running:
            return
            
        self.running = True
        
        # 订阅视频任务更新
        subscribe_to_action_tasks(self._handle_video_task)
        
        logger.info("Action dispatcher started")
        
    def stop(self):
        """停止动作调度器"""
        self.running = False
        logger.info("Action dispatcher stopped")
        
    def _handle_video_task(self, message: Dict[str, Any]):
        """
        处理视频任务消息
        
        Args:
            message: 视频任务消息
        """
        task_id = message.get("task_id")
        status = message.get("status")
        
        # 只处理已完成的视频任务
        if status != "completed":
            return
            
        # 获取任务详情
        task = get_video_task(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return
            
        # 获取视频路径
        video_path = get_video_path(task_id)
        if not video_path:
            logger.error(f"Video for task {task_id} not found")
            return
            
        # 获取动作序列
        action_sequence = task.get("action_sequence", [])
        if not action_sequence:
            logger.error(f"No actions defined for task {task_id}")
            return
            
        # 通知视频创建完成
        notify_video_created(
            agent_id=task.get("agent_id", "unknown"),
            content=task.get("content", ""),
            video_url=video_path,
            trigger_id=task.get("trigger_id", "unknown")
        )
        
        # 启动线程执行动作序列
        threading.Thread(
            target=self._execute_action_sequence,
            args=(task_id, task, video_path, action_sequence),
            daemon=True
        ).start()
        
    def _execute_action_sequence(self, task_id: str, task: Dict[str, Any], 
                                video_path: str, action_sequence: List[str]):
        """
        执行动作序列
        
        Args:
            task_id: 任务ID
            task: 任务详情
            video_path: 视频路径
            action_sequence: 动作序列
        """
        logger.info(f"Executing action sequence for task {task_id}: {action_sequence}")
        
        for action in action_sequence:
            # 发布动作开始消息
            # publish_action_task(
            #     task_id=task_id,
            #     action="publish",
            #     platform=action,
            #     status="processing",
            #     data={
            #         "content": task.get("content", ""),
            #         "video_path": video_path
            #     }
            # )
            
            # 执行动作
            handler = self.action_handlers.get(action)
            if handler:
                success, result = handler(task, video_path)
                
                # 发布动作结果消息
                # status = "completed" if success else "failed"
                # publish_action_task(
                #     task_id=task_id,
                #     action="publish",
                #     platform=action,
                #     status=status,
                #     data={
                #         "content": task.get("content", ""),
                #         "video_path": video_path,
                #         "result": result
                #     }
                # )
            else:
                logger.error(f"No handler for action: {action}")
                # publish_action_task(
                #     task_id=task_id,
                #     action="publish",
                #     platform=action,
                #     status="failed",
                #     data={
                #         "content": task.get("content", ""),
                #         "video_path": video_path,
                #         "error": f"No handler for action: {action}"
                #     }
                # )
                
            # 在动作之间添加短暂延迟
            time.sleep(1)
            
    def _handle_twitter_action(self, task: Dict[str, Any], 
                              video_path: str) -> tuple[bool, Dict[str, Any]]:
        """
        处理 Twitter 发布动作
        
        Args:
            task: 任务详情
            video_path: 视频路径
            
        Returns:
            (成功标志, 结果数据)
        """
        try:
            content = task.get("content", "")
            
            # 发布到 Twitter
            success, tweet_url = post_to_twitter(content, video_path)
            
            if success and tweet_url:
                # 通知内容已发布
                notify_content_published(
                    platform="twitter",
                    content_id=tweet_url.split("/")[-1],
                    url=tweet_url
                )
                
                return True, {"url": tweet_url}
            else:
                return False, {"error": "Failed to post to Twitter"}
                
        except Exception as e:
            logger.error(f"Error posting to Twitter: {str(e)}")
            return False, {"error": str(e)}
            
    def _handle_tiktok_action(self, task: Dict[str, Any], 
                             video_path: str) -> tuple[bool, Dict[str, Any]]:
        """
        处理 TikTok 发布动作
        
        Args:
            task: 任务详情
            video_path: 视频路径
            
        Returns:
            (成功标志, 结果数据)
        """
        # 注意：这是一个占位实现，实际应该集成 TikTok API
        try:
            content = task.get("content", "")
            
            # 模拟发布到 TikTok
            logger.info(f"Would post to TikTok: {content}")
            logger.info(f"With video: {video_path}")
            
            # 模拟成功
            tiktok_url = f"https://tiktok.com/@user/video/{int(time.time())}"
            
            # 通知内容已发布
            notify_content_published(
                platform="tiktok",
                content_id=tiktok_url.split("/")[-1],
                url=tiktok_url
            )
            
            return True, {"url": tiktok_url}
            
        except Exception as e:
            logger.error(f"Error posting to TikTok: {str(e)}")
            return False, {"error": str(e)}
            
    def _handle_webhook_action(self, task: Dict[str, Any], 
                              video_path: str) -> tuple[bool, Dict[str, Any]]:
        """
        处理 Webhook 通知动作
        
        Args:
            task: 任务详情
            video_path: 视频路径
            
        Returns:
            (成功标志, 结果数据)
        """
        try:
            # 通知视频已创建
            success = notify_video_created(
                agent_id=task.get("agent_id", "unknown"),
                content=task.get("content", ""),
                video_url=video_path,
                trigger_id=task.get("trigger_id", "unknown")
            )
            
            if success:
                return True, {"status": "notification_sent"}
            else:
                return False, {"error": "Failed to send webhook notification"}
                
        except Exception as e:
            logger.error(f"Error sending webhook: {str(e)}")
            return False, {"error": str(e)}

# 创建单例实例
dispatcher = ActionDispatcher()

# 导出函数
def start_action_dispatcher():
    """启动动作调度器"""
    dispatcher.start()

def stop_action_dispatcher():
    """停止动作调度器"""
    dispatcher.stop()

if __name__ == "__main__":
    # 测试代码
    start_action_dispatcher()
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_action_dispatcher()

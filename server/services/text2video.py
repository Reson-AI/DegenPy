#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import json
import uuid
import threading
import logging
from typing import Dict, List, Any, Optional, Tuple
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入视频生成API
from server.actions.text2v import generate_video as text2v_generate_video

# 导入视频池和消息代理
from server.services.video_pool import (
    create_video_task, 
    update_video_task, 
    get_video_task, 
    get_pending_video_tasks,
    get_processing_video_tasks,
    get_video_task_count
)
from server.infrastructure.message_broker import publish_video_task

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("text2video")

# 配置
VIDEO_GEN_TIMEOUT = int(os.getenv("VIDEO_GEN_TIMEOUT", "3600"))  # 默认超时1小时
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))  # 默认最大并发任务数2
TASK_CHECK_INTERVAL = int(os.getenv("TASK_CHECK_INTERVAL", "5"))  # 任务检查间隔（秒）

class Text2VideoGenerator:
    """
    文本到视频生成器
    
    负责管理文本到视频的生成任务
    """
    
    def __init__(self):
        """初始化生成器"""
        self.running = False
        self.active_tasks = {}  # 正在处理的任务 {task_id: thread}
        self.task_processor_thread = None
        self.task_monitor_thread = None
        
    def start(self):
        """启动生成器"""
        if self.running:
            logger.warning("Text2Video generator is already running")
            return
            
        logger.info("Starting Text2Video generator")
        self.running = True
        
        # 启动任务处理线程
        self.task_processor_thread = threading.Thread(
            target=self._task_processor,
            daemon=True
        )
        self.task_processor_thread.start()
        
        # 启动任务监控线程
        self.task_monitor_thread = threading.Thread(
            target=self._task_monitor,
            daemon=True
        )
        self.task_monitor_thread.start()
        
    def stop(self):
        """停止生成器"""
        if not self.running:
            logger.warning("Text2Video generator is not running")
            return
            
        logger.info("Stopping Text2Video generator")
        self.running = False
        
        # 等待线程结束
        if self.task_processor_thread:
            self.task_processor_thread.join(timeout=5)
            
        if self.task_monitor_thread:
            self.task_monitor_thread.join(timeout=5)
            
        # 终止所有正在运行的任务
        active_tasks = list(self.active_tasks.items())
        for task_id, thread in active_tasks:
            logger.info(f"Terminating active task: {task_id}")
            update_video_task(task_id, "failed", error="Service stopped")
            
        self.active_tasks = {}
        
    def generate_video(self, content: str, trigger_id: str, agent_id: str, 
                      action_sequence: List[str], priority: int = 0) -> str:
        """
        生成视频
        
        Args:
            content: 文本内容
            trigger_id: 触发器ID
            agent_id: 代理ID
            action_sequence: 后续动作序列
            priority: 任务优先级（数字越大优先级越高）
            
        Returns:
            任务ID
        """
        # 创建任务
        task_id = create_video_task(
            content=content,
            trigger_id=trigger_id,
            agent_id=agent_id,
            action_sequence=action_sequence,
            priority=priority,
            timeout=VIDEO_GEN_TIMEOUT
        )
        
        logger.info(f"Created video generation task: {task_id}")
        
        # 发布任务状态更新
        publish_video_task(task_id, "pending", {})
        
        return task_id
        
    def _task_processor(self):
        """任务处理线程"""
        logger.info("Task processor thread started")
        
        while self.running:
            try:
                # 检查是否可以处理更多任务
                if len(self.active_tasks) >= MAX_CONCURRENT_TASKS:
                    time.sleep(TASK_CHECK_INTERVAL)
                    continue
                    
                # 获取待处理任务
                pending_tasks = get_pending_video_tasks()
                if not pending_tasks:
                    time.sleep(TASK_CHECK_INTERVAL)
                    continue
                    
                # 按优先级和创建时间排序（优先级高的先处理，同优先级按创建时间先后顺序）
                task = sorted(pending_tasks, key=lambda t: (-t.get("priority", 0), t.get("created_at", 0)))[0]
                task_id = task["id"]
                
                # 更新任务状态为处理中
                update_video_task(task_id, "processing")
                
                # 发布任务状态更新
                publish_video_task(task_id, "processing", {})
                
                # 启动视频生成线程
                thread = threading.Thread(
                    target=self._video_generation_thread,
                    args=(task,),
                    daemon=True
                )
                thread.start()
                
                # 记录活动任务
                self.active_tasks[task_id] = {
                    "thread": thread,
                    "start_time": time.time(),
                    "task": task
                }
                
                logger.info(f"Started processing task: {task_id}")
                
            except Exception as e:
                logger.error(f"Error in task processor: {str(e)}")
                time.sleep(TASK_CHECK_INTERVAL)
                
    def _task_monitor(self):
        """任务监控线程"""
        logger.info("Task monitor thread started")
        
        while self.running:
            try:
                # 检查活动任务
                active_tasks = list(self.active_tasks.items())
                for task_id, task_info in active_tasks:
                    thread = task_info["thread"]
                    start_time = task_info["start_time"]
                    task = task_info["task"]
                    
                    # 检查线程是否还在运行
                    if not thread.is_alive():
                        logger.info(f"Task thread completed: {task_id}")
                        del self.active_tasks[task_id]
                        continue
                        
                    # 检查是否超时
                    current_time = time.time()
                    timeout = task.get("timeout", VIDEO_GEN_TIMEOUT)
                    
                    if current_time - start_time > timeout:
                        logger.warning(f"Task timed out: {task_id}")
                        
                        # 更新任务状态为失败
                        update_video_task(
                            task_id, 
                            "failed", 
                            error=f"Task timed out after {timeout} seconds"
                        )
                        
                        # 发布任务状态更新
                        publish_video_task(task_id, "failed", {})
                        
                        # 从活动任务中移除
                        del self.active_tasks[task_id]
                        
                # 检查队列状态并记录
                task_counts = get_video_task_count()
                pending_count = task_counts["pending"]
                processing_count = task_counts["processing"]
                
                if pending_count > 0 or processing_count > 0:
                    logger.info(f"Queue status: {pending_count} pending, {processing_count} processing")
                
                time.sleep(TASK_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in task monitor: {str(e)}")
                time.sleep(TASK_CHECK_INTERVAL)
                
    def _video_generation_thread(self, task: Dict[str, Any]):
        """
        视频生成线程
        
        Args:
            task: 任务信息
        """
        task_id = task["id"]
        content = task["content"]
        
        try:
            logger.info(f"Generating video for task: {task_id}")
            
            # 视频配置
            video_config = {
                "task_id": task_id,
                "trigger_id": task["trigger_id"],
                "agent_id": task["agent_id"]
            }
            
            # 调用视频生成API
            success, video_path, error = text2v_generate_video(content, video_config)
            
            if success and video_path:
                # 更新任务状态为已完成
                update_video_task(task_id, "completed", video_path=video_path)
                
                # 发布任务状态更新
                publish_video_task(task_id, "completed", {})
                
                logger.info(f"Video generation completed for task: {task_id}")
                
                # 获取完整的任务信息（包括视频路径）
                task = get_video_task(task_id)
                
                # 处理后续动作
                self._handle_action_sequence(task)
                
            else:
                # 更新任务状态为失败
                update_video_task(
                    task_id, 
                    "failed", 
                    error=error or "Unknown error during video generation"
                )
                
                # 发布任务状态更新
                publish_video_task(task_id, "failed", {})
                
                logger.error(f"Video generation failed for task: {task_id} - {error}")
                
        except Exception as e:
            # 更新任务状态为失败
            error_message = f"Exception during video generation: {str(e)}"
            update_video_task(task_id, "failed", error=error_message)
            
            # 发布任务状态更新
            publish_video_task(task_id, "failed", {})
            
            logger.exception(f"Exception in video generation thread for task: {task_id}")
            
    def _handle_action_sequence(self, task: Dict[str, Any]):
        """
        处理后续动作序列
        
        Args:
            task: 任务信息
        """
        try:
            task_id = task["id"]
            action_sequence = task.get("action_sequence", [])
            
            if not action_sequence:
                logger.info(f"No action sequence for task: {task_id}")
                return
                
            logger.info(f"Handling action sequence for task: {task_id}: {action_sequence}")
            
            # 发布动作序列事件
            from server.infrastructure.message_broker import publish_action_task_update
            
            publish_action_task_update(
                task_id=task_id,
                status="pending",
                action_sequence=action_sequence,
                video_path=task.get("video_path"),
                trigger_id=task.get("trigger_id"),
                agent_id=task.get("agent_id"),
                content=task.get("content")
            )
            
        except Exception as e:
            logger.exception(f"Error handling action sequence for task: {task['id']}")

# 创建全局生成器实例
generator = Text2VideoGenerator()

def start_text2video_service():
    """启动文本到视频生成服务"""
    generator.start()

def stop_text2video_service():
    """停止文本到视频生成服务"""
    generator.stop()

def generate_video_from_text(content: str, trigger_id: str, agent_id: str, 
                            action_sequence: List[str], priority: int = 0) -> str:
    """
    从文本生成视频
    
    Args:
        content: 文本内容
        trigger_id: 触发器ID
        agent_id: 代理ID
        action_sequence: 后续动作序列
        priority: 任务优先级（数字越大优先级越高）
        
    Returns:
        任务ID
    """
    # 检查队列长度
    pending_count = get_video_task_count("pending")
    max_queue_length = int(os.getenv("MAX_QUEUE_LENGTH", "100"))
    
    if pending_count >= max_queue_length:
        logger.error(f"Queue length exceeded maximum limit of {max_queue_length}")
        raise ValueError(f"Queue length exceeded maximum limit of {max_queue_length}")
    
    return generator.generate_video(content, trigger_id, agent_id, action_sequence, priority)

if __name__ == "__main__":
    # 测试代码
    start_text2video_service()
    
    # 生成测试视频
    task_id = generate_video_from_text(
        content="This is a test video content.",
        trigger_id="test_trigger",
        agent_id="test_agent",
        action_sequence=["webhook", "twitter"],
        priority=1  # 高优先级
    )
    
    print(f"Generated video task: {task_id}")
    
    # 保持程序运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_text2video_service()
        print("Service stopped")

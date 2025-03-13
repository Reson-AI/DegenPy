#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import traceback
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

# 导入MongoDB连接
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError

# 导入MongoDB连接器
from warehouse.storage.mongodb.connector import mongodb_connector

# 导入D-ID API函数
from server.actions.text2v import get_video_status

# 导入TikTok发布功能
from server.actions.tiktok import publish_to_tiktok

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('video_tasks')

class VideoTaskMonitor:
    """视频任务监控类
    
    负责定期监控视频生成任务的状态，并更新到数据库
    完成时自动调用TikTok接口发布视频
    """
    
    def __init__(self, task_config, agent_config):
        """初始化监控器"""
        self.task_config = task_config
        self.agent_config = agent_config
        self.task_id = task_config.get('id', 'unknown_task')
        self.max_check_attempts = 30  # 最大检查次数
        self.running = False
        self.poll_thread = None
    
    def start(self) -> Dict[str, Any]:
        """执行任务监控
        
        Returns:
            包含任务执行结果的字典
        """
        # 判断是否已经在运行
        if self.running:
            return {"success": True, "message": f"视频任务监控 {self.task_id} 已经在运行中"}
        
        self.running = True
        
        # 获取轮询配置
        poll_config = self.task_config.get('schedule', {})
        if isinstance(poll_config, str) or not poll_config:
            # 简化配置，默认每1分钟执行一次
            poll_config = {
                'type': 'interval',
                'minutes': 1
            }
        
        # 启动轮询线程
        self._start_polling(poll_config)
        logger.info(f"开始视频任务监控: {self.task_id}")
        
        return {"success": True, "message": f"视频任务监控 {self.task_id} 已启动"}
        
    def _start_polling(self, poll_config: Dict[str, Any]):
        """启动轮询线程
        
        Args:
            poll_config: 轮询配置，包含type和时间间隔
        """
        poll_type = poll_config.get('type', 'interval')
        
        if poll_type == 'interval':
            # 计算间隔秒数
            seconds = poll_config.get('seconds', 0)
            minutes = poll_config.get('minutes', 0)
            hours = poll_config.get('hours', 0)
            
            interval_seconds = seconds + minutes * 60 + hours * 3600
            if interval_seconds <= 0:
                interval_seconds = 60  # 默认1分钟
            
            logger.info(f"视频任务监控 {self.task_id} 启动轮询，间隔 {interval_seconds} 秒")
            
            # 启动轮询线程
            def poll_thread_func():
                logger.info(f"视频任务监控 {self.task_id} 轮询线程启动")
                
                # 立即执行一次
                self._execute_and_handle_exceptions()
                
                while self.running:
                    time.sleep(interval_seconds)
                    if not self.running:
                        break
                    
                    self._execute_and_handle_exceptions()
                
                logger.info(f"视频任务监控 {self.task_id} 轮询线程停止")
            
            self.poll_thread = threading.Thread(
                target=poll_thread_func,
                name=f"VideoTaskPoll-{self.task_id}",
                daemon=True
            )
            self.poll_thread.start()
        else:
            logger.error(f"不支持的轮询类型: {poll_type}")
        
    def _execute_and_handle_exceptions(self):
        """执行任务并处理异常"""
        try:
            # 获取需要更新状态的视频任务
            pending_tasks = self._get_pending_tasks()
            
            if not pending_tasks:
                logger.info("没有需要更新的视频任务")
                return
            
            # 更新任务状态
            updated_count = 0
            completed_count = 0
            for task in pending_tasks:
                result = self._update_task_status(task)
                if result["updated"]:
                    updated_count += 1
                    if result["completed"]:
                        completed_count += 1
            
            logger.info(f"视频任务监控完成: 更新了{updated_count}个视频任务状态，完成并发布了{completed_count}个视频")
            
        except Exception as e:
            error_msg = f"视频任务监控异常: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
    
    def _get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取需要更新状态的视频任务
        
        Returns:
            需要更新的任务列表
        """
        try:
            collection = mongodb_connector.db['video_tasks']
            
            # 查询条件：只获取 created 和 started 状态的任务
            query = {
                "status": {"$in": ["created", "started"]}
            }
            
            # 按创建时间排序，优先处理较早的任务
            tasks = list(collection.find(query).sort("created_at", DESCENDING))
            
            logger.info(f"找到{len(tasks)}个需要更新状态的视频任务")
            return tasks
            
        except PyMongoError as e:
            logger.error(f"获取待处理视频任务异常: {str(e)}")
            return []
    
    def _update_task_status(self, task: Dict[str, Any]) -> Dict[str, bool]:
        """更新单个任务的状态
        
        Args:
            task: 要更新的任务信息
            
        Returns:
            包含更新状态的字典，包括updated和completed标志
        """
        d_id_video_id = task.get("d_id_video_id")
        task_id = task.get("task_id", "unknown")
        
        result = {"updated": False, "completed": False}
        
        if not d_id_video_id:
            logger.warning(f"任务缺少必要的 d_id_video_id: {task}")
            return result
        
        try:
            # 调用D-ID API获取视频状态
            api_result = get_video_status(d_id_video_id)
            
            # 当前尝试次数
            current_attempt = task.get("attempt", 0) + 1
            
            # 映射D-ID API状态到我们简化的状态
            api_status = api_result.get("status", "unknown")
            
            # 简化状态映射
            if api_status in ["done", "ready", "completed"]:
                mapped_status = "done"
            elif api_status in ["created", "pending"]:
                mapped_status = "created"
            elif api_status in ["processing", "in_progress"]:
                mapped_status = "started"
            else:
                # 错误状态保持不变
                mapped_status = api_status
            
            # 更新数据
            update_data = {
                "status": mapped_status,# 保存原始状态用于调试
                "attempt": current_attempt
            }
            
            # 如果有结果URL，添加到更新数据中
            if "result_url" in api_result:
                update_data["result_url"] = api_result["result_url"]
            
            # 如果有错误信息，添加到更新数据中
            if "error" in api_result:
                update_data["error"] = api_result["error"]
            
            # 更新MongoDB中的任务状态，使用d_id_video_id作为主键
            collection = mongodb_connector.db['video_tasks']
            collection.update_one(
                {"d_id_video_id": d_id_video_id},
                {"$set": update_data}
            )
            
            result["updated"] = True
            
            # 检查是否已完成，如果完成则调用TikTok接口
            if mapped_status == "done" and "result_url" in update_data:
                result_url = update_data["result_url"]
                logger.info(f"视频生成完成，准备发布到TikTok: ID={task_id}, URL={result_url}")
                
                # 尝试发布到TikTok
                try:
                    # 获取任务内容作为标题
                    caption = task.get("title", f"视频 {task_id}")
                    
                    # 获取任何相关的标签
                    raw_tags = task.get("tags", ["AI生成", "新闻"])
                    hashtags = [f"#{tag}" if not tag.startswith('#') else tag for tag in raw_tags]
                    
                    # 调用TikTok发布接口
                    tiktok_result = publish_to_tiktok(
                        video_url=result_url,
                        caption=caption,
                        hashtags=hashtags
                    )
                    
                    # 更新发布结果
                    publish_update = {
                        "tiktok_published": True,
                        "tiktok_result": tiktok_result
                    }
                    
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
                        {"$set": publish_update}
                    )
                    
                    logger.info(f"视频成功发布到TikTok: ID={task_id}")
                    result["completed"] = True
                    
                except Exception as pub_err:
                    logger.error(f"发布视频到TikTok失败: ID={task_id}, 错误={str(pub_err)}")
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
                        {"$set": {
                            "tiktok_published": False,
                            "tiktok_error": str(pub_err)
                        }}
                    )
            elif mapped_status == "done" and "result_url" not in update_data:
                logger.warning(f"视频标记为已完成但没有URL: ID={task_id}")
            elif current_attempt >= self.max_check_attempts:
                # 超过最大尝试次数，标记为超时
                collection.update_one(
                    {"d_id_video_id": d_id_video_id},
                    {"$set": {"status": "timeout"}}
                )
                logger.warning(f"视频生成超时: ID={task_id}, 已达到最大尝试次数{self.max_check_attempts}")
            else:
                logger.info(f"视频状态更新: ID={task_id}, 状态={mapped_status}, 尝试={current_attempt}/{self.max_check_attempts}")
            
            return result
            
        except Exception as e:
            logger.error(f"更新视频任务状态异常: d_id_video_id={d_id_video_id}, error={str(e)}")
            return result


def stop(task_id=None):
    """停止视频任务监控"""
    # 这里只是一个接口占位符，在实际使用时需要实现
    logger.info(f"停止视频任务监控: {task_id if task_id else 'all'}")
    return {"success": True, "message": "视频任务监控已停止"}

def execute(task_config=None, agent_config=None):
    """执行视频任务监控
    
    Args:
        task_config: 任务配置，如果为None则使用默认配置
        agent_config: 代理配置，如果为None则使用默认配置
        
    Returns:
        包含任务执行结果的字典
    """
    # 如果没有提供配置，则使用默认配置
    if task_config is None:
        task_config = {
            'id': 'video_task_monitor',
            'name': '视频任务监控',
            'schedule': {
                'type': 'interval',
                'minutes': 1
            }
        }
    
    if agent_config is None:
        agent_config = {}
    
    monitor = VideoTaskMonitor(task_config, agent_config)
    return monitor.start()


if __name__ == "__main__":
    # 用于测试
    result = execute()
    print(result)
    
    # 保持主线程运行，让守护线程能够执行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("收到中断信号，程序退出")

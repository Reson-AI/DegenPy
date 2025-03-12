#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import traceback
from typing import Dict, List, Any, Optional
from datetime import datetime

# 导入MongoDB连接
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError

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
    
    def __init__(self):
        """初始化监控器"""
        self.task_id = f"video_monitor_{int(time.time())}"
        self.db = self._connect_db()
        self.max_check_attempts = 30  # 最大检查次数
        
    def _connect_db(self) -> Optional[Any]:
        """连接MongoDB数据库"""
        try:
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
            mongo_db = os.getenv("MONGO_DB", "degenpy")
            client = MongoClient(mongo_uri)
            db = client[mongo_db]
            logger.info(f"MongoDB连接成功: {mongo_uri}")
            return db
        except Exception as e:
            logger.error(f"MongoDB连接失败: {str(e)}")
            return None
    
    def start(self) -> Dict[str, Any]:
        """执行任务监控
        
        Returns:
            包含任务执行结果的字典
        """
        start_time = time.time()
        logger.info(f"开始视频任务监控: {self.task_id}")
        
        if not self.db:
            return {
                "success": False,
                "message": "数据库连接失败",
                "task_id": self.task_id,
                "elapsed_time": time.time() - start_time
            }
        
        try:
            # 获取需要更新状态的视频任务
            pending_tasks = self._get_pending_tasks()
            
            if not pending_tasks:
                logger.info("没有需要更新的视频任务")
                return {
                    "success": True,
                    "message": "没有需要更新的视频任务",
                    "task_id": self.task_id,
                    "elapsed_time": time.time() - start_time
                }
            
            # 更新任务状态
            updated_count = 0
            completed_count = 0
            for task in pending_tasks:
                result = self._update_task_status(task)
                if result["updated"]:
                    updated_count += 1
                    if result["completed"]:
                        completed_count += 1
            
            result = {
                "success": True,
                "message": f"更新了{updated_count}个视频任务状态，完成并发布了{completed_count}个视频",
                "task_id": self.task_id,
                "updated_count": updated_count,
                "completed_count": completed_count,
                "total_count": len(pending_tasks),
                "elapsed_time": time.time() - start_time
            }
            
            logger.info(f"视频任务监控完成: {result['message']}")
            return result
            
        except Exception as e:
            error_msg = f"视频任务监控异常: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "message": error_msg,
                "task_id": self.task_id,
                "elapsed_time": time.time() - start_time
            }
    
    def _get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取需要更新状态的视频任务
        
        Returns:
            需要更新的任务列表
        """
        try:
            collection = self.db['video_tasks']
            
            # 查询条件：只获取 created 和 started 状态的任务
            query = {
                "status": {"$in": ["created", "started"]},
                "attempt": {"$lt": self.max_check_attempts}
            }
            
            # 按创建时间排序，优先处理较早的任务
            tasks = list(collection.find(query).sort("created_at", DESCENDING).limit(20))
            
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
        task_id = task.get("task_id")
        d_id_video_id = task.get("d_id_video_id")
        
        result = {"updated": False, "completed": False}
        
        if not task_id or not d_id_video_id:
            logger.warning(f"任务缺少必要信息: {task}")
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
                "status": mapped_status,
                "raw_status": api_status,  # 保存原始状态用于调试
                "last_checked": datetime.now(),
                "attempt": current_attempt,
                "updated_at": int(time.time())
            }
            
            # 如果有结果URL，添加到更新数据中
            if "result_url" in api_result:
                update_data["result_url"] = api_result["result_url"]
            
            # 如果有错误信息，添加到更新数据中
            if "error" in api_result:
                update_data["error"] = api_result["error"]
            
            # 更新MongoDB中的任务状态
            collection = self.db['video_tasks']
            collection.update_one(
                {"task_id": task_id},
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
                        "tiktok_result": tiktok_result,
                        "published_at": int(time.time())
                    }
                    
                    collection.update_one(
                        {"task_id": task_id},
                        {"$set": publish_update}
                    )
                    
                    logger.info(f"视频成功发布到TikTok: ID={task_id}")
                    result["completed"] = True
                    
                except Exception as pub_err:
                    logger.error(f"发布视频到TikTok失败: ID={task_id}, 错误={str(pub_err)}")
                    collection.update_one(
                        {"task_id": task_id},
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
                    {"task_id": task_id},
                    {"$set": {"status": "timeout"}}
                )
                logger.warning(f"视频生成超时: ID={task_id}, 已达到最大尝试次数{self.max_check_attempts}")
            else:
                logger.info(f"视频状态更新: ID={task_id}, 状态={mapped_status}, 尝试={current_attempt}/{self.max_check_attempts}")
            
            return result
            
        except Exception as e:
            logger.error(f"更新视频任务状态异常: task_id={task_id}, error={str(e)}")
            return result


def execute():
    """执行视频任务监控"""
    monitor = VideoTaskMonitor()
    return monitor.start()


if __name__ == "__main__":
    # 用于测试
    result = execute()
    print(result)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("video_pool")

# 视频池配置
VIDEO_POOL_DIR = os.getenv("VIDEO_POOL_DIR", "video_pool")
VIDEO_POOL_MAX_AGE = int(os.getenv("VIDEO_POOL_MAX_AGE", "7"))  # 默认7天
MAX_QUEUE_LENGTH = int(os.getenv("MAX_QUEUE_LENGTH", "100"))  # 默认最大队列长度100
QUEUE_WARNING_THRESHOLD = int(os.getenv("QUEUE_WARNING_THRESHOLD", "50"))  # 队列警告阈值

# 确保视频池目录存在
os.makedirs(VIDEO_POOL_DIR, exist_ok=True)

class VideoPool:
    """
    视频池管理类
    
    负责管理视频生成任务和结果
    """
    
    def __init__(self):
        """初始化视频池"""
        self.metadata_file = os.path.join(VIDEO_POOL_DIR, "metadata.json")
        self.videos = self._load_metadata()
        
    def _load_metadata(self) -> Dict[str, Any]:
        """加载视频元数据"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading video metadata: {str(e)}")
                return {}
        else:
            return {}
            
    def _save_metadata(self) -> bool:
        """保存视频元数据"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.videos, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving video metadata: {str(e)}")
            return False
            
    def create_task(self, content: str, trigger_id: str, agent_id: str, 
                    action_sequence: List[str], priority: int = 0,
                    timeout: Optional[int] = None) -> str:
        """
        创建视频生成任务
        
        Args:
            content: 用于生成视频的文本内容
            trigger_id: 触发任务的规则ID
            agent_id: 生成内容的代理ID
            action_sequence: 后续动作序列
            priority: 任务优先级（数字越大优先级越高）
            timeout: 任务超时时间（秒），如果为None则使用默认值
            
        Returns:
            任务ID
        """
        # 检查队列长度
        pending_tasks = self.get_pending_tasks()
        if len(pending_tasks) >= MAX_QUEUE_LENGTH:
            raise ValueError(f"Queue length exceeded maximum limit of {MAX_QUEUE_LENGTH}")
            
        task_id = str(uuid.uuid4())
        
        task_data = {
            "id": task_id,
            "content": content,
            "trigger_id": trigger_id,
            "agent_id": agent_id,
            "action_sequence": action_sequence,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time(),
            "priority": priority,
            "timeout": timeout,
            "video_path": None,
            "error": None
        }
        
        self.videos[task_id] = task_data
        self._save_metadata()
        
        # 检查是否需要发出警告
        if len(pending_tasks) + 1 >= QUEUE_WARNING_THRESHOLD:
            logger.warning(f"Video task queue is backing up! Current length: {len(pending_tasks) + 1}")
        
        return task_id
        
    def update_task_status(self, task_id: str, status: str, 
                          video_path: Optional[str] = None, 
                          error: Optional[str] = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态 (pending, processing, completed, failed)
            video_path: 生成的视频路径
            error: 错误信息
            
        Returns:
            更新是否成功
        """
        if task_id not in self.videos:
            logger.error(f"Task {task_id} not found")
            return False
            
        self.videos[task_id]["status"] = status
        self.videos[task_id]["updated_at"] = time.time()
        
        if video_path:
            self.videos[task_id]["video_path"] = video_path
            
        if error:
            self.videos[task_id]["error"] = error
            
        return self._save_metadata()
        
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，如果任务不存在则返回None
        """
        return self.videos.get(task_id)
        
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有待处理的任务
        
        Returns:
            待处理任务列表
        """
        return [task for task_id, task in self.videos.items() 
                if task["status"] == "pending"]
                
    def get_processing_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有正在处理的任务
        
        Returns:
            正在处理的任务列表
        """
        return [task for task_id, task in self.videos.items() 
                if task["status"] == "processing"]
                
    def get_completed_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有已完成的任务
        
        Returns:
            已完成任务列表
        """
        return [task for task_id, task in self.videos.items() 
                if task["status"] == "completed"]
                
    def get_failed_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有失败的任务
        
        Returns:
            失败任务列表
        """
        return [task for task_id, task in self.videos.items() 
                if task["status"] == "failed"]
                
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务
        
        Returns:
            所有任务列表
        """
        return list(self.videos.values())
        
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        if task_id not in self.videos:
            return False
            
        # 如果有视频文件，也删除它
        task = self.videos[task_id]
        video_path = task.get("video_path")
        
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception as e:
                logger.error(f"Error deleting video file: {str(e)}")
                
        # 删除任务记录
        del self.videos[task_id]
        return self._save_metadata()
        
    def clean_old_tasks(self, days: int = 7) -> int:
        """
        清理旧任务
        
        Args:
            days: 超过多少天的任务将被删除
            
        Returns:
            删除的任务数量
        """
        now = time.time()
        max_age = days * 24 * 60 * 60  # 转换为秒
        
        tasks_to_delete = []
        
        for task_id, task in self.videos.items():
            if now - task["created_at"] > max_age:
                tasks_to_delete.append(task_id)
                
        for task_id in tasks_to_delete:
            self.delete_task(task_id)
            
        return len(tasks_to_delete)

# 创建单例实例
video_pool = VideoPool()

# 导出函数
def create_video_task(content: str, trigger_id: str, agent_id: str, 
                     action_sequence: List[str], priority: int = 0,
                     timeout: Optional[int] = None) -> str:
    """创建视频生成任务"""
    return video_pool.create_task(content, trigger_id, agent_id, action_sequence, priority, timeout)

def update_video_task(task_id: str, status: str, 
                     video_path: Optional[str] = None, 
                     error: Optional[str] = None) -> bool:
    """更新视频任务状态"""
    return video_pool.update_task_status(task_id, status, video_path, error)

def get_video_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取视频任务信息"""
    return video_pool.get_task(task_id)

def get_video_path(task_id: str) -> Optional[str]:
    """获取视频文件路径"""
    task = video_pool.get_task(task_id)
    if task and task.get("status") == "completed":
        return task.get("video_path")
    return None

def get_pending_video_tasks() -> List[Dict[str, Any]]:
    """获取待处理的视频任务"""
    return video_pool.get_pending_tasks()

def get_processing_video_tasks() -> List[Dict[str, Any]]:
    """获取正在处理的视频任务"""
    return video_pool.get_processing_tasks()

def get_completed_video_tasks() -> List[Dict[str, Any]]:
    """获取已完成的视频任务"""
    return video_pool.get_completed_tasks()

def get_video_task_count() -> Dict[str, int]:
    """获取各状态的视频任务数量
    
    Returns:
        包含各状态任务数量的字典
    """
    return {
        "pending": len(video_pool.get_pending_tasks()),
        "processing": len(video_pool.get_processing_tasks()),
        "completed": len(video_pool.get_completed_tasks()),
        "failed": len(video_pool.get_failed_tasks()),
        "total": len(video_pool.get_all_tasks())
    }

if __name__ == "__main__":
    # 测试代码
    task_id = create_video_task(
        content="比特币价格突破6万美元，创下历史新高！",
        trigger_id="price-alert",
        agent_id="crypto-news",
        action_sequence=["tiktok", "twitter"],
        priority=1
    )
    
    logger.info(f"Created task: {task_id}")
    logger.info(f"Task info: {get_video_task(task_id)}")
    
    # 模拟视频生成完成
    update_video_task(
        task_id=task_id,
        status="completed",
        video_path=f"{VIDEO_POOL_DIR}/video_{task_id}.mp4"
    )
    
    logger.info(f"Updated task: {get_video_task(task_id)}")
    logger.info(f"Video path: {get_video_path(task_id)}")

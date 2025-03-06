#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# 导入数据库连接器
from warehouse.storage.mongodb.connector import MongoDBConnector

# Load environment variables
load_dotenv()

# Create necessary directories
os.makedirs("warehouse/text_data", exist_ok=True)

app = FastAPI(title="DegenPy Warehouse API", description="Data warehouse API for DegenPy")

class WarehouseAPI:
    def __init__(self):
        self.connector = MongoDBConnector()

# In-memory storage for recent UIDs
recent_uids = {
    "followed": [],
    "trending": [],
    "other": []
}
MAX_RECENT_UIDS = 100  # 每种类型最多保存的最近UID数量

class StoreRequest(BaseModel):
    content: str
    author_id: Optional[str] = None
    source_type: Optional[str] = "other"  # 可以是 "followed", "trending" 或 "other"
    uid: Optional[str] = None  # 如果不提供将自动生成 UUID

class Response(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

class RecentUIDTracker:
    """跟踪最近添加的UUID，按来源类型分组"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RecentUIDTracker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.followed_uids = []
        self.trending_uids = []
        self.other_uids = []
        self.lock = threading.Lock()
        self.last_activity_time = datetime.now()
        self._initialized = True
    
    def add_uid(self, uid: str, source_type: str):
        """添加一个UUID到跟踪器"""
        with self.lock:
            if source_type == "followed":
                self.followed_uids.append((uid, datetime.now()))
            elif source_type == "trending":
                self.trending_uids.append((uid, datetime.now()))
            else:
                self.other_uids.append((uid, datetime.now()))
            
            self.last_activity_time = datetime.now()
    
    def get_uids(self, source_type: Optional[str] = None, clear: bool = False, 
                 min_items: int = 0, max_age_hours: Optional[int] = None) -> List[str]:
        """获取指定类型的UUID列表
        
        Args:
            source_type: 来源类型，可以是 "followed", "trending", "all" 或 None
            clear: 是否在返回后清除列表
            min_items: 最小项目数，如果不满足则返回空列表
            max_age_hours: 最大年龄（小时），只返回不超过此年龄的项目
            
        Returns:
            UUID列表
        """
        with self.lock:
            current_time = datetime.now()
            
            # 根据年龄筛选
            if max_age_hours is not None:
                cutoff_time = current_time - timedelta(hours=max_age_hours)
                
                if source_type == "followed":
                    filtered_items = [(uid, ts) for uid, ts in self.followed_uids if ts >= cutoff_time]
                    self.followed_uids = filtered_items
                elif source_type == "trending":
                    filtered_items = [(uid, ts) for uid, ts in self.trending_uids if ts >= cutoff_time]
                    self.trending_uids = filtered_items
                else:
                    filtered_followed = [(uid, ts) for uid, ts in self.followed_uids if ts >= cutoff_time]
                    filtered_trending = [(uid, ts) for uid, ts in self.trending_uids if ts >= cutoff_time]
                    filtered_other = [(uid, ts) for uid, ts in self.other_uids if ts >= cutoff_time]
                    
                    self.followed_uids = filtered_followed
                    self.trending_uids = filtered_trending
                    self.other_uids = filtered_other
            
            # 获取UUID列表
            if source_type == "followed":
                items = self.followed_uids
                uids = [uid for uid, _ in items]
                
                if clear:
                    self.followed_uids = []
            elif source_type == "trending":
                items = self.trending_uids
                uids = [uid for uid, _ in items]
                
                if clear:
                    self.trending_uids = []
            elif source_type == "all":
                items = self.followed_uids + self.trending_uids + self.other_uids
                uids = [uid for uid, _ in items]
                
                if clear:
                    self.followed_uids = []
                    self.trending_uids = []
                    self.other_uids = []
            else:
                items = self.other_uids
                uids = [uid for uid, _ in items]
                
                if clear:
                    self.other_uids = []
            
            # 检查最小项目数
            if len(uids) < min_items:
                return []
                
            return uids
    
    def check_recent_activity(self, threshold: int, timeframe_hours: int) -> bool:
        """检查最近的活动是否低于阈值
        
        Args:
            threshold: 阈值，如果最近活动数量低于此值，则返回True
            timeframe_hours: 时间范围（小时）
            
        Returns:
            如果最近活动低于阈值，则返回True，否则返回False
        """
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=timeframe_hours)
            
            # 计算最近时间范围内的活动数量
            recent_followed = sum(1 for _, ts in self.followed_uids if ts >= cutoff_time)
            recent_trending = sum(1 for _, ts in self.trending_uids if ts >= cutoff_time)
            recent_other = sum(1 for _, ts in self.other_uids if ts >= cutoff_time)
            
            total_recent = recent_followed + recent_trending + recent_other
            
            return total_recent < threshold

# 全局实例
uid_tracker = RecentUIDTracker()

def get_db_manager():
    """获取数据库管理器"""
    return WarehouseAPI()

@app.get("/")
async def root():
    """API根路径"""
    return {"status": "ok", "message": "DegenPy Warehouse API is running"}

@app.post("/data")
async def store_data(request: StoreRequest):
    """存储数据
    
    Args:
        request: 包含内容、作者ID、来源类型和可选UID的请求
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        
        result = db.connector.store_data(
            content=request.content,
            author_id=request.author_id,
            source_type=request.source_type,
            uid=request.uid
        )
        
        if result:
            # 添加到最近UID跟踪器
            uid_tracker.add_uid(result["uid"], result["source_type"])
            
            return Response(
                status="success",
                message="数据存储成功",
                data=result
            )
        else:
            return Response(
                status="error",
                message="数据存储失败"
            )
    except Exception as e:
        return Response(
            status="error",
            message=f"数据存储时出错: {str(e)}"
        )

@app.get("/content/{uid}")
async def get_content(uid: str):
    """获取指定UID的内容
    
    Args:
        uid: 内容UID
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        data = db.connector.get_data_by_uid(uid)
        
        if data:
            return Response(
                status="success",
                message="内容获取成功",
                data=data
            )
        else:
            return Response(
                status="error",
                message=f"未找到UID为 {uid} 的内容",
                data=None
            )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取内容时出错: {str(e)}"
        )

@app.get("/recent-content")
async def get_recent_content(source_type: Optional[str] = None, limit: int = 30):
    """获取最近的内容
    
    Args:
        source_type: 来源类型，可以是 "followed", "trending" 或 "other"
        limit: 最大返回数量
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        data = db.connector.get_recent_data(source_type, limit)
        
        return Response(
            status="success",
            message=f"获取到 {len(data)} 条最近内容",
            data={"content": data}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取最近内容时出错: {str(e)}"
        )

@app.get("/content-by-uids")
async def get_content_by_uids(uids: str):
    """根据多个UID获取内容
    
    Args:
        uids: 逗号分隔的UID列表
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        
        # 解析UID列表
        uid_list = [uid.strip() for uid in uids.split(",") if uid.strip()]
        
        if not uid_list:
            return Response(
                status="error",
                message="未提供有效的UID列表"
            )
        
        data = db.connector.get_data_by_uids(uid_list)
        
        return Response(
            status="success",
            message=f"获取到 {len(data)}/{len(uid_list)} 条内容",
            data={"content": data}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取内容时出错: {str(e)}"
        )

@app.get("/recent-uids")
async def get_recent_uids(source_type: Optional[str] = None):
    """获取最近添加的UID列表
    
    Args:
        source_type: 来源类型，可以是 "followed", "trending", "other" 或 "all"
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        uids = uid_tracker.get_uids(source_type)
        
        return Response(
            status="success",
            message=f"获取到 {len(uids)} 个最近UID",
            data={"uids": uids}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取最近UID时出错: {str(e)}"
        )

@app.get("/data-source")
async def get_data_from_source(
    source_type: str,
    min_items: int = 0,
    max_age_hours: Optional[int] = None,
    clear: bool = False
):
    """从指定的数据源获取数据
    
    Args:
        source_type: 来源类型，可以是 "followed", "trending", "other" 或 "all"
        min_items: 最小项目数，如果不满足则返回空列表
        max_age_hours: 最大年龄（小时），只返回不超过此年龄的项目
        clear: 是否在返回后清除列表
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        # 获取UID列表
        uids = uid_tracker.get_uids(
            source_type=source_type,
            min_items=min_items,
            max_age_hours=max_age_hours,
            clear=clear
        )
        
        if not uids:
            return Response(
                status="success",
                message="没有符合条件的数据",
                data={"content": []}
            )
        
        # 获取内容
        db = get_db_manager()
        data = db.connector.get_data_by_uids(uids)
        
        return Response(
            status="success",
            message=f"获取到 {len(data)} 条内容",
            data={"content": data}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取数据时出错: {str(e)}"
        )

@app.get("/check-activity")
async def check_recent_activity(threshold: int = 10, timeframe_hours: int = 1):
    """检查最近的活动是否低于阈值
    
    Args:
        threshold: 阈值，如果最近活动数量低于此值，则返回True
        timeframe_hours: 时间范围（小时）
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        result = uid_tracker.check_recent_activity(threshold, timeframe_hours)
        
        return Response(
            status="success",
            message=f"最近 {timeframe_hours} 小时内的活动{'低于' if result else '高于或等于'}阈值 {threshold}",
            data={"below_threshold": result}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"检查活动时出错: {str(e)}"
        )

@app.post("/apply-condition")
async def apply_condition(content: str, token_limit: Optional[int] = None, prompt_template: Optional[str] = None):
    """应用条件到内容
    
    Args:
        content: 原始内容
        token_limit: 令牌限制
        prompt_template: 提示模板
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        if not content:
            return Response(
                status="error",
                message="内容不能为空"
            )
        
        result = content
        
        # 应用令牌限制
        if token_limit:
            # 简单实现：假设1个字符约等于1个token
            if len(result) > token_limit:
                result = result[:token_limit]
        
        # 应用提示模板
        if prompt_template:
            result = prompt_template.replace("{{content}}", result)
        
        return Response(
            status="success",
            message="条件应用成功",
            data={"content": result}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"应用条件时出错: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("warehouse.api:app", host="0.0.0.0", port=8000, reload=True)

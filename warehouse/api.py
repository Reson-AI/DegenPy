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

app = FastAPI(title="DegenPy Warehouse API", description="Data warehouse API for DegenPy")

# 配置文件路径
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')
TAGS_CONFIG_PATH = os.path.join(CONFIG_DIR, 'tags.json')

# 确保配置目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

class WarehouseAPI:
    def __init__(self):
        self.connector = MongoDBConnector()

# In-memory storage for recent UIDs
recent_uids = []
MAX_RECENT_UIDS = 100  # 最多保存的最近UID数量

class ContentData(BaseModel):
    content: Dict[str, Any]
    time: Optional[str] = None

class StoreRequest(BaseModel):
    content: Dict[str, Any]  # 存储内容的字典，包含 speaker、time、text等字段
    tags: Optional[List[str]] = None  # 可选的标签数组
    uid: Optional[str] = None  # 如果不提供将自动生成 UUID

class Response(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

class TagsConfig(BaseModel):
    special_tags: List[str]

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
            
        self.uids = []
        self.lock = threading.Lock()
        self.last_activity_time = datetime.now()
        self._initialized = True
    
    def add_uid(self, uid: str):
        """添加一个UUID到跟踪器"""
        with self.lock:
            # 添加UUID和时间戳
            self.uids.append((uid, datetime.now()))
            
            # 保持列表大小在最大限制内
            if len(self.uids) > MAX_RECENT_UIDS:
                self.uids = self.uids[-MAX_RECENT_UIDS:]
            
            self.last_activity_time = datetime.now()
    
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
            recent_activity = sum(1 for _, ts in self.uids if ts >= cutoff_time)
            
            total_recent = recent_activity
            
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

@app.get("/tags")
async def get_tags():
    """获取特别关注的标签列表
    
    Returns:
        包含状态、消息和标签列表的响应
    """
    try:
        if os.path.exists(TAGS_CONFIG_PATH):
            with open(TAGS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return Response(
                    status="success",
                    message="获取标签列表成功",
                    data=config
                )
        else:
            # 如果配置文件不存在，返回空列表
            default_config = {"special_tags": []}
            with open(TAGS_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return Response(
                status="success",
                message="配置文件不存在，已创建默认配置",
                data=default_config
            )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取标签列表时出错: {str(e)}"
        )

@app.post("/tags")
async def update_tags(config: TagsConfig):
    """更新特别关注的标签列表
    
    Args:
        config: 包含标签列表的配置
        
    Returns:
        包含状态、消息和更新后的标签列表的响应
    """
    try:
        # 确保配置目录存在
        os.makedirs(os.path.dirname(TAGS_CONFIG_PATH), exist_ok=True)
        
        # 写入配置文件
        with open(TAGS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({"special_tags": config.special_tags}, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message="标签列表更新成功",
            data={"special_tags": config.special_tags}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"更新标签列表时出错: {str(e)}"
        )

@app.put("/tags/add/{tag}")
async def add_tag(tag: str):
    """添加一个特别关注的标签
    
    Args:
        tag: 要添加的标签名称
        
    Returns:
        包含状态、消息和更新后的标签列表的响应
    """
    try:
        # 读取当前配置
        current_config = {"special_tags": []}
        if os.path.exists(TAGS_CONFIG_PATH):
            with open(TAGS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        
        # 如果标签已存在，返回成功但不重复添加
        if tag in current_config.get("special_tags", []):
            return Response(
                status="success",
                message=f"标签 '{tag}' 已在列表中",
                data=current_config
            )
        
        # 添加新标签
        current_config.setdefault("special_tags", []).append(tag)
        
        # 写入配置文件
        with open(TAGS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message=f"标签 '{tag}' 添加成功",
            data=current_config
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"添加标签时出错: {str(e)}"
        )

@app.delete("/tags/remove/{tag}")
async def remove_tag(tag: str):
    """移除一个特别关注的标签
    
    Args:
        tag: 要移除的标签名称
        
    Returns:
        包含状态、消息和更新后的标签列表的响应
    """
    try:
        # 读取当前配置
        if not os.path.exists(TAGS_CONFIG_PATH):
            return Response(
                status="error",
                message="配置文件不存在"
            )
        
        with open(TAGS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        
        # 如果标签不在列表中，返回成功但不执行移除
        if tag not in current_config.get("special_tags", []):
            return Response(
                status="success",
                message=f"标签 '{tag}' 不在列表中",
                data=current_config
            )
        
        # 移除标签
        current_config["special_tags"].remove(tag)
        
        # 写入配置文件
        with open(TAGS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message=f"标签 '{tag}' 移除成功",
            data=current_config
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"移除标签时出错: {str(e)}"
        )

@app.post("/data")
async def store_data(request: StoreRequest):
    """存储数据
    
    Args:
        request: 包含内容字典、标签字典和可选UID的请求
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        
        # 直接使用请求中的content和tags，不需要额外解析
        result = db.connector.store_data(
            content=request.content,
            tags=request.tags,
            uid=request.uid
        )
        
        if result:
            # 添加到最近UID跟踪器
            uid_tracker.add_uid(result["uid"])
            
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


# 导出函数，用于其他模块直接导入
def get_data_by_uids(uid: Union[str, List[str]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    根据UID获取数据
    
    Args:
        uid: 单个UID字符串或UID列表
        
    Returns:
        当uid是单个字符串时返回数据字典，如果不存在则返回空字典
        当uid是列表时返回数据字典列表
    """
    db = get_db_manager()
    try:
        result = db.connector.get_data_by_uids(uid)
        if result is None:
            return {}
        return result
    except Exception as e:
        print(f"Error in get_data_by_uids: {str(e)}")
        return {} if not isinstance(uid, list) else []

if __name__ == "__main__":
    uvicorn.run("warehouse.api:app", host="0.0.0.0", port=8000, reload=True)

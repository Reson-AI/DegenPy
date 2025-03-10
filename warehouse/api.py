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

# 配置文件路径
CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')
SPEAKERS_CONFIG_PATH = os.path.join(CONFIG_DIR, 'speakers.json')

# 确保配置目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

class WarehouseAPI:
    def __init__(self):
        self.connector = MongoDBConnector()

# In-memory storage for recent UIDs
recent_uids = []
MAX_RECENT_UIDS = 100  # 最多保存的最近UID数量

class ContentData(BaseModel):
    speaker: str
    time: str
    text: str

class StoreRequest(BaseModel):
    content: Union[str, ContentData]  # 可以是JSON字符串或ContentData对象
    author_id: Optional[str] = None
    uid: Optional[str] = None  # 如果不提供将自动生成 UUID

class Response(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

class SpeakersConfig(BaseModel):
    special_speakers: List[str]

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
    
    def get_uids(self, clear: bool = False, min_items: int = 0, 
                 max_age_hours: Optional[int] = None) -> List[str]:
        """获取UUID列表
        
        Args:
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
                filtered_items = [(uid, ts) for uid, ts in self.uids if ts >= cutoff_time]
                self.uids = filtered_items
            
            # 获取UUID列表
            items = self.uids
            uids = [uid for uid, _ in items]
            
            if clear:
                self.uids = []
            
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

@app.get("/speakers")
async def get_speakers():
    """获取特别关注的发言人列表
    
    Returns:
        包含状态、消息和发言人列表的响应
    """
    try:
        if os.path.exists(SPEAKERS_CONFIG_PATH):
            with open(SPEAKERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return Response(
                    status="success",
                    message="获取发言人列表成功",
                    data=config
                )
        else:
            # 如果配置文件不存在，返回空列表
            default_config = {"special_speakers": []}
            with open(SPEAKERS_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return Response(
                status="success",
                message="配置文件不存在，已创建默认配置",
                data=default_config
            )
    except Exception as e:
        return Response(
            status="error",
            message=f"获取发言人列表时出错: {str(e)}"
        )

@app.post("/speakers")
async def update_speakers(config: SpeakersConfig):
    """更新特别关注的发言人列表
    
    Args:
        config: 包含发言人列表的配置
        
    Returns:
        包含状态、消息和更新后的发言人列表的响应
    """
    try:
        # 确保配置目录存在
        os.makedirs(os.path.dirname(SPEAKERS_CONFIG_PATH), exist_ok=True)
        
        # 写入配置文件
        with open(SPEAKERS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({"special_speakers": config.special_speakers}, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message="发言人列表更新成功",
            data={"special_speakers": config.special_speakers}
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"更新发言人列表时出错: {str(e)}"
        )

@app.put("/speakers/add/{speaker}")
async def add_speaker(speaker: str):
    """添加一个特别关注的发言人
    
    Args:
        speaker: 要添加的发言人名称
        
    Returns:
        包含状态、消息和更新后的发言人列表的响应
    """
    try:
        # 读取当前配置
        current_config = {"special_speakers": []}
        if os.path.exists(SPEAKERS_CONFIG_PATH):
            with open(SPEAKERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        
        # 如果发言人已存在，返回成功但不重复添加
        if speaker in current_config.get("special_speakers", []):
            return Response(
                status="success",
                message=f"发言人 '{speaker}' 已在列表中",
                data=current_config
            )
        
        # 添加新发言人
        current_config.setdefault("special_speakers", []).append(speaker)
        
        # 写入配置文件
        with open(SPEAKERS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message=f"发言人 '{speaker}' 添加成功",
            data=current_config
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"添加发言人时出错: {str(e)}"
        )

@app.delete("/speakers/remove/{speaker}")
async def remove_speaker(speaker: str):
    """移除一个特别关注的发言人
    
    Args:
        speaker: 要移除的发言人名称
        
    Returns:
        包含状态、消息和更新后的发言人列表的响应
    """
    try:
        # 读取当前配置
        if not os.path.exists(SPEAKERS_CONFIG_PATH):
            return Response(
                status="error",
                message="配置文件不存在"
            )
        
        with open(SPEAKERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            current_config = json.load(f)
        
        # 如果发言人不在列表中，返回成功但不执行移除
        if speaker not in current_config.get("special_speakers", []):
            return Response(
                status="success",
                message=f"发言人 '{speaker}' 不在列表中",
                data=current_config
            )
        
        # 移除发言人
        current_config["special_speakers"].remove(speaker)
        
        # 写入配置文件
        with open(SPEAKERS_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        
        return Response(
            status="success",
            message=f"发言人 '{speaker}' 移除成功",
            data=current_config
        )
    except Exception as e:
        return Response(
            status="error",
            message=f"移除发言人时出错: {str(e)}"
        )

@app.post("/data")
async def store_data(request: StoreRequest):
    """存储数据
    
    Args:
        request: 包含内容（三要素JSON）、作者ID、来源类型和可选UID的请求
        
    Returns:
        包含状态、消息和数据的响应
    """
    try:
        db = get_db_manager()
        
        # 处理content参数，确保它是正确的格式
        content = request.content
        if isinstance(content, ContentData):
            # 如果是ContentData对象，转换为字典
            content = {
                "speaker": content.speaker,
                "time": content.time,
                "text": content.text
            }
        
        result = db.connector.store_data(
            content=content,
            author_id=request.author_id,
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

# 导出函数，用于其他模块直接导入
def get_data_by_uid(uid: str) -> Dict[str, Any]:
    """
    根据UID获取数据
    
    Args:
        uid: 数据UID
        
    Returns:
        数据字典，如果不存在则返回空字典
    """
    db = get_db_manager()
    try:
        result = db.connector.get_data_by_uid(uid)
        if result:
            return result
        else:
            return {}
    except Exception as e:
        print(f"Error in get_data_by_uid: {str(e)}")
        return {}

if __name__ == "__main__":
    uvicorn.run("warehouse.api:app", host="0.0.0.0", port=8000, reload=True)

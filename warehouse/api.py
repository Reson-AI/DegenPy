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

# 导入UID跟踪器
from warehouse.utils.uid_tracker import uid_tracker

# 用于API服务的任务ID
API_TASK_ID = "warehouse_api"

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
            # 添加到UID跟踪器
            uid_tracker.add_uid(result["uid"], API_TASK_ID)
            
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
from typing import Dict, List, Optional, Union, Any
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Create necessary directories
os.makedirs("warehouse/text_data", exist_ok=True)

app = FastAPI(title="DegenPy Warehouse API", description="Data warehouse API for DegenPy")

# In-memory storage for recent UIDs
recent_uids = []

class StoreRequest(BaseModel):
    content: str
    uid: Optional[str] = None  # 现在 uid 是可选的，如果不提供将自动生成 UUID

class Response(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

class DatabaseManager:
    """Abstract database manager class"""
    
    def process_data(self, content: str, uid: Optional[str] = None) -> Dict[str, Any]:
        """处理数据，返回标准化的数据结构
        
        Args:
            content: 内容
            uid: 可选的 UID，如果不提供将自动生成 UUID
            
        Returns:
            包含 uid, content 和 timestamp 的字典
        """
        # 如果没有提供 uid，则生成一个 UUID
        if not uid:
            uid = str(uuid.uuid4())
            
        # 添加时间戳
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 组合内容和时间戳
        content_with_time = f"{content} [时间: {timestamp}]"
        
        return {
            "uid": uid,
            "content": content_with_time,
            "timestamp": timestamp  # 额外存储时间戳，方便将来处理
        }
    
    def store_data(self, content: str, uid: Optional[str] = None) -> Dict[str, Any]:
        """存储数据到存储介质
        
        Args:
            content: 内容
            uid: 可选的 UID，如果不提供将自动生成 UUID
            
        Returns:
            成功时返回包含生成/使用的 uid 的字典，失败时返回 None
        """
        try:
            # 处理数据
            data = self.process_data(content, uid)
            # 执行实际存储操作（由子类实现）
            success = self._store_data_impl(data)
            if success:
                return {"uid": data["uid"]}
            return None
        except Exception as e:
            print(f"Error storing data: {str(e)}")
            return None
    
    def _store_data_impl(self, data: Dict[str, Any]) -> bool:
        """实际存储操作的实现（由子类实现）"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_data_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """根据UID获取数据"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_recent_data(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取最近的数据"""
        raise NotImplementedError("Subclasses must implement this method")

class TextFileManager(DatabaseManager):
    def __init__(self):
        super().__init__()
        self.data_dir = "warehouse/text_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_file = f"{self.data_dir}/data.txt"
        # 创建数据文件（如果不存在）
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", encoding="utf-8") as f:
                pass
    
    def _store_data_impl(self, data: Dict[str, Any]) -> bool:
        """实际存储操作的实现"""
        try:
            # 写入格式: uid:content
            with open(self.data_file, "a", encoding="utf-8") as f:
                f.write(f"{data['uid']}:{data['content']}\n")
            return True
        except Exception as e:
            print(f"Error storing data in text file: {str(e)}")
            return False
            
    def get_data_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        try:
            if not os.path.exists(self.data_file):
                return None
                
            with open(self.data_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 解析行: uid:content
                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        continue
                    
                    line_uid, line_content = parts
                    
                    if line_uid == uid:
                        return {
                            "uid": line_uid,
                            "content": line_content
                        }
                    
            return None
        except Exception as e:
            print(f"Error retrieving data from text file: {str(e)}")
            return None
            
    def get_recent_data(self, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            if not os.path.exists(self.data_file):
                return []
                
            result = []
            with open(self.data_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # 获取最近的数据（从文件末尾开始）
            recent_lines = lines[-limit:] if len(lines) > limit else lines
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # 解析行: uid:content
                parts = line.split(":", 1)
                if len(parts) != 2:
                    continue
                
                uid, content = parts
                
                result.append({
                    "uid": uid,
                    "content": content
                })
                
            return result
        except Exception as e:
            print(f"Error retrieving recent data from text files: {str(e)}")
            return []

class MySQLManager(DatabaseManager):
    def __init__(self):
        super().__init__()
        # 数据库连接配置
        self.config = {
            "host": os.getenv("MYSQL_HOST", "localhost"),
            "user": os.getenv("MYSQL_USER", "root"),
            "password": os.getenv("MYSQL_PASSWORD", ""),
            "database": os.getenv("MYSQL_DATABASE", "degenpy")
        }
    
    def _store_data_impl(self, data: Dict[str, Any]) -> bool:
        """实际存储操作的实现"""
        # 这里是未来连接数据库并存储数据的代码
        # 目前只是占位符
        print(f"[MySQL] Would store data: {data}")
        return True

def get_db_manager(db_type: str = "text"):
    """Get the appropriate database manager based on the type"""
    if db_type == "text":
        return TextFileManager()
    elif db_type == "mysql":
        return MySQLManager()
    else:
        # Default to text file manager if the requested type is not available
        print(f"Database type '{db_type}' not available, using text file storage instead")
        return TextFileManager()

@app.get("/")
async def root():
    return {"status": "ok", "message": "DegenPy Warehouse API is running"}

@app.post("/store")
async def store_data(request: StoreRequest, db_type: str = "text"):
    """Store data in the warehouse"""
    try:
        db_manager = get_db_manager(db_type)
        
        # Store the data
        result = db_manager.store_data(request.content, request.uid)
        
        if result:
            # Add to recent UIDs list (limit to 100 items)
            global recent_uids
            uid = result["uid"]
            recent_uids.append(uid)
            if len(recent_uids) > 100:
                recent_uids = recent_uids[-100:]
                
            return Response(
                status="success",
                message=f"Data stored successfully with UID {uid}",
                data={"uid": uid}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to store data")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data")
async def get_data(
    p: str = "last30",  # last30 = last 30 items, by_uids = by specific UIDs
    db_type: str = "text",
    uids: Optional[str] = None
):
    """Get data from the warehouse"""
    try:
        db_manager = get_db_manager(db_type)
        
        if p == "by_uids" and uids:
            # Get data for specific UIDs
            uid_list = uids.split(",")
            items = []
            
            for uid in uid_list:
                data = db_manager.get_data_by_uid(uid)
                if data:
                    items.append(data)
            
            return Response(
                status="success",
                message=f"Retrieved {len(items)} items by UIDs",
                data={"items": items, "uids": uid_list}
            )
        
        elif p == "last30" or p == "sa":  # sa for backward compatibility
            # Get the most recent data
            limit = 30
            items = db_manager.get_recent_data(limit)
            
            return Response(
                status="success",
                message=f"Retrieved {len(items)} recent items",
                data={"items": items}
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Invalid parameter p={p}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/recent-uids")
async def get_recent_uids(clear: bool = False):
    """Get the list of recently added UIDs"""
    global recent_uids
    
    uids = recent_uids.copy()
    
    if clear:
        recent_uids = []
    
    return Response(
        status="success",
        message=f"Retrieved {len(uids)} recent UIDs",
        data={"uids": uids}
    )

if __name__ == "__main__":
    uvicorn.run("warehouse.api:app", host="0.0.0.0", port=8000, reload=True)

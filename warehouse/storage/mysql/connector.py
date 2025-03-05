#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_connector")

# 加载环境变量
load_dotenv()

class MySQLConnector:
    """MySQL 连接器"""
    
    def __init__(self):
        """初始化 MySQL 连接器"""
        # 这里是 MySQL 连接的占位符
        # 实际实现时，应该使用 mysql-connector-python 或 pymysql 库连接到 MySQL
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = os.getenv("MYSQL_PORT", "3306")
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "degenpy")
        
        logger.info(f"MySQL 连接器初始化: {self.host}:{self.port}, DB: {self.database}")
        
        # 目前使用文本文件模拟 MySQL
        self.data_dir = "warehouse/text_data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 为不同类型的内容创建不同的文件
        self.data_files = {
            "followed": f"{self.data_dir}/followed_data.txt",
            "trending": f"{self.data_dir}/trending_data.txt",
            "other": f"{self.data_dir}/other_data.txt"
        }
        
        # 确保所有文件都存在
        for file_path in self.data_files.values():
            if not os.path.exists(file_path):
                with open(file_path, "w", encoding="utf-8") as f:
                    pass
    
    def store_data(self, content: str, author_id: Optional[str] = None, 
                  source_type: str = "other", uid: Optional[str] = None) -> Dict[str, Any]:
        """存储数据到 MySQL
        
        Args:
            content: 内容
            author_id: 作者ID
            source_type: 来源类型，可以是 "followed", "trending" 或 "other"
            uid: 可选的 UID，如果不提供将自动生成 UUID
            
        Returns:
            成功时返回包含生成/使用的 uid 的字典
        """
        try:
            # 验证source_type
            if source_type not in ["followed", "trending", "other"]:
                source_type = "other"
                
            # 如果没有提供 uid，则生成一个 UUID
            if not uid:
                uid = str(uuid.uuid4())
                
            # 添加时间戳
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 创建数据对象
            data = {
                "uid": uid,
                "content": content,
                "author_id": author_id,
                "source_type": source_type,
                "timestamp": timestamp
            }
            
            # 确定使用哪个文件
            file_path = self.data_files.get(source_type, self.data_files["other"])
            
            # 写入文件
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"{json.dumps(data)}\n")
                
            logger.info(f"数据存储成功: {uid}, 类型: {source_type}")
            return {"uid": uid, "source_type": source_type}
        except Exception as e:
            logger.error(f"存储数据时出错: {str(e)}")
            return None
            
    def get_data_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """根据UID从 MySQL 获取数据
        
        Args:
            uid: 内容UID
            
        Returns:
            数据对象，如果未找到则返回 None
        """
        try:
            # 搜索所有文件
            for file_path in self.data_files.values():
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            if data.get("uid") == uid:
                                logger.info(f"找到数据: {uid}")
                                return data
                        except json.JSONDecodeError:
                            continue
            
            logger.warning(f"未找到数据: {uid}")
            return None
        except Exception as e:
            logger.error(f"获取数据时出错: {str(e)}")
            return None
            
    def get_recent_data(self, source_type: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """获取最近的数据
        
        Args:
            source_type: 来源类型，可以是 "followed", "trending" 或 "other"，如果为None则获取所有类型
            limit: 最大返回数量
            
        Returns:
            数据列表
        """
        try:
            result = []
            
            # 确定要搜索的文件
            if source_type and source_type in self.data_files:
                files_to_search = [self.data_files[source_type]]
            else:
                files_to_search = list(self.data_files.values())
                
            # 从每个文件中读取最新数据
            for file_path in files_to_search:
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    
                # 获取最近的数据（从文件末尾开始）
                recent_lines = lines[-limit:] if len(lines) > limit else lines
                
                for line in recent_lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        result.append(data)
                    except json.JSONDecodeError:
                        continue
                        
            # 按时间戳排序（最新的在前）
            result.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # 限制返回数量
            logger.info(f"获取到 {len(result)} 条最近数据")
            return result[:limit]
        except Exception as e:
            logger.error(f"获取最近数据时出错: {str(e)}")
            return []
            
    def get_data_by_uids(self, uids: List[str]) -> List[Dict[str, Any]]:
        """根据多个UID获取数据
        
        Args:
            uids: UID列表
            
        Returns:
            数据列表
        """
        result = []
        for uid in uids:
            data = self.get_data_by_uid(uid)
            if data:
                result.append(data)
        
        logger.info(f"根据UID列表获取到 {len(result)}/{len(uids)} 条数据")
        return result
        
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """执行SQL查询
        
        Args:
            query: SQL查询语句
            
        Returns:
            查询结果
        """
        # 这里是SQL查询的占位符
        # 实际实现时，应该使用 mysql-connector-python 或 pymysql 执行SQL查询
        logger.info(f"执行SQL查询: {query}")
        
        # 简单实现：返回最近的数据
        return self.get_recent_data(limit=50)

# 创建 MySQL 连接器实例
mysql_connector = MySQLConnector()

def get_connector():
    """获取 MySQL 连接器实例"""
    return mysql_connector

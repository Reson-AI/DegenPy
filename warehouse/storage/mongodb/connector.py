#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
import redis
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from warehouse.message_queue import MessageQueue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongodb_connector")

# 加载环境变量
load_dotenv()

class MongoDBConnector:
    """MongoDB 连接器"""
    
    def __init__(self, db_name='degenpy', collection_name='data'):
        """初始化 MongoDB 连接器"""
        self.client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.message_queue = MessageQueue()
        
        # 初始化Redis客户端
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True
        )
        
        logger.info(f"MongoDB 连接器初始化: {db_name}, Collection: {collection_name}")
        
    def store_data(self, content, author_id=None, source_type="other", uid=None):
        """存储数据到 MongoDB
        
        Args:
            content: 内容
            author_id: 作者ID（可选）
            source_type: 来源类型，可以是 "followed", "trending" 或 "other"
            uid: 内容UUID（可选，如果不提供将自动生成）
            
        Returns:
            成功时返回存储的文档
        """
        try:
            # 如果没有提供UID，自动生成
            if not uid:
                uid = str(uuid.uuid4())
                
            # 根据来源类型确定tag
            # "followed" 和 "trending" 是特别关注的数据 (tag=2)
            # "other" 是普通时间线数据 (tag=1)
            tag = 2 if source_type in ["followed", "trending"] else 1
            
            document = {
                'uuid': uid,
                'content': content,
                'author_id': author_id,
                'source_type': source_type,
                'createdAt': datetime.utcnow(),
                'tag': tag
            }
            result = self.collection.insert_one(document)
            
            # 根据标签处理数据
            if tag == 1:
                # 时间线数据，发送到Redis列表
                timeline_key = os.getenv('REDIS_TIMELINE_KEY', 'timeline')
                self.redis.lpush(timeline_key, uid)
                logger.info(f"将UUID {uid} 发送到Redis列表 {timeline_key}")
            elif tag == 2:
                # 特别关注数据，发送到消息队列
                self.message_queue.publish('special_attention', uid)
                logger.info(f"将UUID {uid} 发送到消息队列 special_attention")
            
            # 返回完整的文档
            return {
                'uuid': uid,
                'content': content,
                'author_id': author_id,
                'source_type': source_type,
                'tag': tag,
                'createdAt': datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"存储数据时出错: {str(e)}")
            return None
            
    def get_data_by_uid(self, uuid):
        """根据UUID从 MongoDB 获取数据
        
        Args:
            uuid: 内容UUID
            
        Returns:
            数据对象，如果未找到则返回 None
        """
        try:
            return self.collection.find_one({'uuid': uuid})
        except Exception as e:
            logger.error(f"获取数据时出错: {str(e)}")
            return None
            
    def get_recent_data(self, limit=10):
        """获取最近的数据
        
        Args:
            limit: 最大返回数量
            
        Returns:
            数据列表
        """
        try:
            return list(self.collection.find().sort('createdAt', -1).limit(limit))
        except Exception as e:
            logger.error(f"获取最近数据时出错: {str(e)}")
            return []
            
    def get_data_by_uids(self, uuids):
        """根据多个UUID获取数据
        
        Args:
            uuids: UUID列表
            
        Returns:
            数据列表
        """
        try:
            return list(self.collection.find({'uuid': {'$in': uuids}}))
        except Exception as e:
            logger.error(f"获取数据时出错: {str(e)}")
            return []
            
    def execute_query(self, query):
        """执行查询
        
        Args:
            query: 查询语句
            
        Returns:
            查询结果
        """
        try:
            return list(self.collection.find(query))
        except Exception as e:
            logger.error(f"执行查询时出错: {str(e)}")
            return []

# 创建 MongoDB 连接器实例
mongodb_connector = MongoDBConnector()

def get_connector():
    """获取 MongoDB 连接器实例"""
    return mongodb_connector

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# 尝试导入redis，如果不可用则设置为None
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis模块未安装，将禁用Redis功能")

# 尝试导入消息队列
try:
    from warehouse.message_queue import MessageQueue
    MQ_AVAILABLE = True
except ImportError:
    MQ_AVAILABLE = False
    logging.warning("消息队列模块导入失败，将禁用消息队列功能")

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
    
    def __init__(self, db_name=None, collection_name=None):
        """初始化 MongoDB 连接器"""
        # 使用环境变量中的连接字符串
        connection_string = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017')
        self.client = MongoClient(connection_string)
        
        # 使用环境变量中的数据库名和集合名
        db_name = db_name or os.getenv('MONGODB_DATABASE', 'degenpy')
        collection_name = collection_name or os.getenv('MONGODB_COLLECTION', 'content')
        
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        
        # 初始化消息队列
        if MQ_AVAILABLE:
            try:
                self.message_queue = MessageQueue()
                logger.info("消息队列初始化成功")
            except Exception as e:
                logger.warning(f"无法初始化消息队列: {str(e)}，将使用本地模式")
                self.message_queue = None
        else:
            logger.warning("消息队列模块不可用，将禁用消息队列功能")
            self.message_queue = None
        
        # 初始化Redis客户端
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    password=os.getenv('REDIS_PASSWORD', None),
                    db=int(os.getenv('REDIS_DB', 0)),
                    decode_responses=True
                )
                # 测试连接
                self.redis.ping()
                logger.info("成功连接到Redis服务器")
            except Exception as e:
                logger.warning(f"无法连接到Redis: {str(e)}，将使用本地模式")
                self.redis = None
        else:
            logger.warning("Redis模块不可用，将禁用Redis功能")
            self.redis = None
        
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
            if tag == 1 and self.redis is not None:
                try:
                    # 时间线数据，发送到Redis列表
                    timeline_key = os.getenv('REDIS_TIMELINE_KEY', 'timeline')
                    self.redis.lpush(timeline_key, uid)
                    logger.info(f"将UUID {uid} 发送到Redis列表 {timeline_key}")
                except Exception as redis_error:
                    logger.error(f"Redis操作失败: {str(redis_error)}")
            elif tag == 2 and self.message_queue is not None:
                try:
                    # 特别关注数据，发送到消息队列
                    self.message_queue.publish('special_attention', uid)
                    logger.info(f"将UUID {uid} 发送到消息队列 special_attention")
                except Exception as mq_error:
                    logger.error(f"消息队列操作失败: {str(mq_error)}")
            
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

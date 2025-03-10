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
# 强制重新加载.env文件，确保使用最新的配置
load_dotenv(override=True)

class MongoDBConnector:
    """MongoDB 连接器"""
    
    def __init__(self, db_name=None, collection_name=None):
        """初始化 MongoDB 连接器"""
        # 使用环境变量中的连接字符串，不提供默认值
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("环境变量MONGODB_CONNECTION_STRING未设置，请在.env文件中配置")
        self.client = MongoClient(connection_string)
        
        # 使用环境变量中的数据库名和集合名，不提供默认值
        db_name = db_name or os.getenv('MONGODB_DATABASE')
        if not db_name:
            raise ValueError("环境变量MONGODB_DATABASE未设置，请在.env文件中配置")
            
        collection_name = collection_name or os.getenv('MONGODB_COLLECTION')
        if not collection_name:
            raise ValueError("环境变量MONGODB_COLLECTION未设置，请在.env文件中配置")
        
        # 直接使用指定的数据库名称，不进行大小写处理
        self.db = self.client[db_name]
                
        self.collection = self.db[collection_name]
        
        # 输出详细的环境变量信息
        logger.info(f"MongoDB 连接器初始化环境变量详情:")
        logger.info(f"MONGODB_CONNECTION_STRING: {os.getenv('MONGODB_CONNECTION_STRING', '[未设置]')[:10]}...")
        logger.info(f"MONGODB_DATABASE: {os.getenv('MONGODB_DATABASE', '[未设置]')}")
        logger.info(f"MONGODB_COLLECTION: {os.getenv('MONGODB_COLLECTION', '[未设置]')}")
        logger.info(f"MongoDB 连接器实际使用的配置:")
        logger.info(f"Database: {db_name}, Collection: {collection_name}")
        
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
        
    def _load_special_speakers(self):
        """从配置文件加载特别关注的发言人列表"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'speakers.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 将列表转换为字典，便于快速查找
                    return {speaker: True for speaker in config.get('special_speakers', [])}
            else:
                logger.warning(f"特别关注的发言人配置文件不存在: {config_path}")
                return {}
        except Exception as e:
            logger.error(f"加载特别关注的发言人配置时出错: {str(e)}")
            return {}
    
    def store_data(self, content, author_id=None, uid=None):
        """存储数据到 MongoDB
        
        Args:
            content: 内容（JSON格式字符串或字典，包含发言人、时间、文本内容）
            author_id: 作者ID（可选）
            uid: 内容UUID（可选，如果不提供将自动生成）
            
        Returns:
            成功时返回存储的文档
        """
        try:
            # 如果没有提供UID，自动生成
            if not uid:
                uid = str(uuid.uuid4())
            
            # 解析内容（如果是字符串，则尝试解析为JSON）
            if isinstance(content, str):
                try:
                    content_data = json.loads(content)
                except json.JSONDecodeError:
                    # 如果不是有效的JSON，则创建默认结构
                    content_data = {
                        "speaker": "未知",
                        "time": datetime.utcnow().isoformat(),
                        "text": content
                    }
            else:
                content_data = content
            
            # 确保内容包含所需的三个要素
            if not isinstance(content_data, dict):
                content_data = {
                    "speaker": "未知",
                    "time": datetime.utcnow().isoformat(),
                    "text": str(content_data)
                }
            
            # 确保三个要素都存在
            if "speaker" not in content_data:
                content_data["speaker"] = "未知"
            if "time" not in content_data:
                content_data["time"] = datetime.utcnow().isoformat()
            if "text" not in content_data:
                content_data["text"] = ""
            
            # 加载特别关注的发言人列表
            special_speakers = self._load_special_speakers()
            
            # 根据发言人确定tag
            # 特别关注的发言人标记为2，其他标记为1
            speaker = content_data.get("speaker", "")
            tag = 2 if speaker in special_speakers else 1
            
            document = {
                '_id': uid,  # 使用UUID作为MongoDB的_id字段
                'content': content_data["text"],
                'speaker': speaker,
                'createdAt': content_data["time"],
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
                'content': content_data["text"],
                'speaker': speaker,
                'createdAt': content_data["time"],
                'tag': tag
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

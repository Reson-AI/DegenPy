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

# 移除Redis和消息队列的依赖，提高连接器的可复用性

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
        
        # 移除Redis和消息队列的初始化，提高连接器的可复用性
        
        logger.info(f"MongoDB 连接器初始化: {db_name}, Collection: {collection_name}")
        
    def store_data(self, content, tags=None, uid=None):
        """存储数据到 MongoDB
        
        Args:
            content: 内容字典
            tags: 标签数组（可选）
            uid: 内容UUID（可选，如果不提供将自动生成）
            
        Returns:
            成功时返回存储的文档
        """
        try:
            # 如果没有提供UID，自动生成
            if not uid:
                uid = str(uuid.uuid4())
            
            # 确保content是字典类型
            if not isinstance(content, dict):
                try:
                    # 尝试将字符串解析为JSON
                    if isinstance(content, str):
                        content = json.loads(content)
                    else:
                        # 如果不是字典也不是字符串，则创建一个默认的内容字典
                        logger.warning(f"内容不是字典类型: {type(content)}，将创建默认内容")
                        content = {"text": str(content)}
                except json.JSONDecodeError:
                    # 如果解析JSON失败，创建默认内容
                    content = {"text": content if isinstance(content, str) else str(content)}
            
            # 确保tags是数组类型
            if tags is None:
                tags = []
            elif not isinstance(tags, list):
                logger.warning(f"标签不是数组类型: {type(tags)}，将使用空数组")
                tags = []
            
            # 创建文档
            document = {
                '_id': uid,  # 使用UUID作为MongoDB的_id字段
                'content': content,  # 存储完整的内容字典
                'tags': tags  # 存储标签数组
            }
            result = self.collection.insert_one(document)
            
            # 返回完整的文档
            return {
                'uuid': uid,
                'content': content,
                'tags': tags
            }
        except Exception as e:
            logger.error(f"存储数据时出错: {str(e)}")
            return None
            
    def get_data_by_uids(self, uuids):
        """根据一个或多个UUID获取数据
        
        Args:
            uuids: 单个UUID或UUID列表
            
        Returns:
            当uuids是列表时返回数据列表，当uuids是单个UUID时返回单个数据对象或None
        """
        try:
            # 处理单个UUID的情况
            single_uuid = False
            if not isinstance(uuids, list):
                uuids = [uuids]
                single_uuid = True
            
            # 使用_id字段查询，因为我们现在使用UUID作为_id
            documents = list(self.collection.find({'_id': {'$in': uuids}}))
            
            # 格式化结果
            results = [{
                'uuid': doc['_id'],
                'content': doc['content'],
                'tags': doc.get('tags', [])
            } for doc in documents]
            
            # 如果是单个UUID，返回单个结果或None
            if single_uuid:
                return results[0] if results else None
            
            # 否则返回列表
            return results
        except Exception as e:
            logger.error(f"根据UID获取数据时出错: {str(e)}")
            return [] if not single_uuid else None

# 创建 MongoDB 连接器实例
mongodb_connector = MongoDBConnector()

def get_connector():
    """获取 MongoDB 连接器实例"""
    return mongodb_connector

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from dotenv import load_dotenv, set_key
from warehouse.storage.mongodb.connector import MongoDBConnector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_init")

def init_db_env():
    """初始化数据库环境变量"""
    # 加载当前环境变量
    load_dotenv()
    
    # 确保 .env 文件存在
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            pass
    
    # 设置数据库类型
    set_key(env_file, "DB_TYPE", "mongodb")
    logger.info("已设置数据库类型为: mongodb")
    
    # MongoDB 环境变量
    if not os.getenv("MONGODB_CONNECTION_STRING"):
        set_key(env_file, "MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
    if not os.getenv("MONGODB_DATABASE"):
        set_key(env_file, "MONGODB_DATABASE", "degenpy")
    if not os.getenv("MONGODB_COLLECTION"):
        set_key(env_file, "MONGODB_COLLECTION", "content")
        
    logger.info("已设置 MongoDB 环境变量")

def initialize_db():
    connector = MongoDBConnector()
    # Create indexes
    connector.collection.create_index('uuid', unique=True)
    connector.collection.create_index('createdAt')
    connector.collection.create_index('tag')

if __name__ == "__main__":
    import sys
    
    # 初始化数据库环境
    init_db_env()
    
    # 初始化数据库
    initialize_db()

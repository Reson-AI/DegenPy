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
    # 加载当前环境变量，强制覆盖现有环境变量
    load_dotenv(override=True)
    
    # 确保 .env 文件存在
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            pass
    
    # 设置数据库类型
    set_key(env_file, "DB_TYPE", "mongodb")
    logger.info("已设置数据库类型为: mongodb")
    
    # 从根目录下的.env文件读取MongoDB环境变量
    # 不再设置默认值，完全依赖.env文件中的配置
    logger.info("从.env文件读取MongoDB配置")
    
    # 检查必要的环境变量是否存在
    if not os.getenv("MONGODB_CONNECTION_STRING"):
        logger.warning("未设置MONGODB_CONNECTION_STRING环境变量，请在.env文件中配置")
    if not os.getenv("MONGODB_DATABASE"):
        logger.warning("未设置MONGODB_DATABASE环境变量，请在.env文件中配置")
    if not os.getenv("MONGODB_COLLECTION"):
        logger.warning("未设置MONGODB_COLLECTION环境变量，请在.env文件中配置")
        
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

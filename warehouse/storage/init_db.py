#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from dotenv import load_dotenv, set_key

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_init")

def init_db_env(db_type="mongodb"):
    """初始化数据库环境变量
    
    Args:
        db_type: 数据库类型，可以是 "mongodb", "mysql" 或 "pgsql"
    """
    # 加载当前环境变量
    load_dotenv()
    
    # 确保 .env 文件存在
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            pass
    
    # 设置数据库类型
    set_key(env_file, "DB_TYPE", db_type)
    logger.info(f"已设置数据库类型为: {db_type}")
    
    # 根据数据库类型设置相应的环境变量
    if db_type == "mongodb":
        # MongoDB 环境变量
        if not os.getenv("MONGODB_CONNECTION_STRING"):
            set_key(env_file, "MONGODB_CONNECTION_STRING", "mongodb://localhost:27017")
        if not os.getenv("MONGODB_DATABASE"):
            set_key(env_file, "MONGODB_DATABASE", "degenpy")
        if not os.getenv("MONGODB_COLLECTION"):
            set_key(env_file, "MONGODB_COLLECTION", "content")
        
        logger.info("已设置 MongoDB 环境变量")
    elif db_type == "mysql":
        # MySQL 环境变量
        if not os.getenv("MYSQL_HOST"):
            set_key(env_file, "MYSQL_HOST", "localhost")
        if not os.getenv("MYSQL_PORT"):
            set_key(env_file, "MYSQL_PORT", "3306")
        if not os.getenv("MYSQL_USER"):
            set_key(env_file, "MYSQL_USER", "root")
        if not os.getenv("MYSQL_PASSWORD"):
            set_key(env_file, "MYSQL_PASSWORD", "")
        if not os.getenv("MYSQL_DATABASE"):
            set_key(env_file, "MYSQL_DATABASE", "degenpy")
        
        logger.info("已设置 MySQL 环境变量")
    elif db_type == "pgsql":
        # PostgreSQL 环境变量
        if not os.getenv("PGSQL_HOST"):
            set_key(env_file, "PGSQL_HOST", "localhost")
        if not os.getenv("PGSQL_PORT"):
            set_key(env_file, "PGSQL_PORT", "5432")
        if not os.getenv("PGSQL_USER"):
            set_key(env_file, "PGSQL_USER", "postgres")
        if not os.getenv("PGSQL_PASSWORD"):
            set_key(env_file, "PGSQL_PASSWORD", "")
        if not os.getenv("PGSQL_DATABASE"):
            set_key(env_file, "PGSQL_DATABASE", "degenpy")
        
        logger.info("已设置 PostgreSQL 环境变量")
    else:
        logger.warning(f"不支持的数据库类型: {db_type}")
        return False
    
    logger.info(f"数据库环境初始化完成: {db_type}")
    return True

if __name__ == "__main__":
    import sys
    
    # 获取命令行参数
    db_type = "mongodb"  # 默认值
    if len(sys.argv) > 1:
        db_type = sys.argv[1].lower()
    
    # 初始化数据库环境
    init_db_env(db_type)

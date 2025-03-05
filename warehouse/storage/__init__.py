#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 默认数据库类型
DEFAULT_DB_TYPE = os.getenv("DB_TYPE", "mongodb")

def get_db_connector():
    """获取数据库连接器
    
    根据环境变量 DB_TYPE 选择合适的数据库连接器
    
    Returns:
        数据库连接器实例
    """
    db_type = os.getenv("DB_TYPE", DEFAULT_DB_TYPE).lower()
    
    if db_type == "mongodb":
        from warehouse.storage.mongodb.connector import get_connector
        return get_connector()
    elif db_type == "mysql":
        from warehouse.storage.mysql.connector import get_connector
        return get_connector()
    elif db_type == "pgsql":
        from warehouse.storage.pgsql.connector import get_connector
        return get_connector()
    else:
        # 默认使用 MongoDB
        from warehouse.storage.mongodb.connector import get_connector
        return get_connector()

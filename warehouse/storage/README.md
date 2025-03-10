# 数据库存储模块

本模块提供了与不同数据库的连接和交互功能。

## 支持的数据库

目前支持以下数据库：

- MongoDB: `warehouse/storage/mongodb/`
- MySQL: `warehouse/storage/mysql/`
- PostgreSQL: `warehouse/storage/pgsql/`

## 使用方法

### 初始化数据库环境

在使用数据库连接器之前，需要先初始化数据库环境变量：

```python
from warehouse.storage.init_db import init_db_env

# 初始化 MongoDB 环境
init_db_env("mongodb")

# 或者初始化 MySQL 环境
# init_db_env("mysql")

# 或者初始化 PostgreSQL 环境
# init_db_env("pgsql")
```

也可以通过命令行初始化：

```bash
python -m warehouse.storage.init_db mongodb
```

### 获取数据库连接器

```python
from warehouse.storage import get_db_connector

# 获取数据库连接器
db = get_db_connector()

# 存储数据
result = db.store_data(
    content="测试内容",
    author_id="user123",
    source_type="followed"
)

# 获取数据
data = db.get_data_by_uid(result["uid"])
```

## 环境变量配置

各数据库的环境变量配置如下：

### MongoDB

```
DB_TYPE=mongodb
MONGODB_CONNECTION_STRING=mongodb://localhost:27017
MONGODB_DATABASE=degenpy
MONGODB_COLLECTION=content
```

### MySQL

```
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=degenpy
```

### PostgreSQL

```
DB_TYPE=pgsql
PGSQL_HOST=localhost
PGSQL_PORT=5432
PGSQL_USER=postgres
PGSQL_PASSWORD=
PGSQL_DATABASE=degenpy
```

## 数据库连接器接口

所有数据库连接器都实现了以下接口：

- `store_data(content, author_id, source_type, uid)`: 存储数据
- `get_data_by_uid(uid)`: 根据UID获取数据
- `get_data_by_uids(uids)`: 根据多个UID获取数据
- `execute_query(query)`: 执行查询

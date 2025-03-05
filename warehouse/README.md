# DegenPy Warehouse 模块

Warehouse 模块是 DegenPy 项目的数据存储和检索系统。它提供了一个统一的 API 来存储和检索数据，支持多种数据库后端。

## 模块结构

```
warehouse/
├── api.py                # API 接口定义
├── text_data/            # 文本文件存储目录
└── storage/              # 数据库存储模块
    ├── __init__.py       # 数据库连接器选择
    ├── init_db.py        # 数据库环境初始化
    ├── README.md         # 数据库模块说明
    ├── mongodb/          # MongoDB 连接器
    │   ├── __init__.py
    │   └── connector.py
    ├── mysql/            # MySQL 连接器
    │   ├── __init__.py
    │   └── connector.py
    └── pgsql/            # PostgreSQL 连接器
        ├── __init__.py
        └── connector.py
```

## API 接口

Warehouse API 提供了以下接口：

- `/data`: 存储数据
- `/content/{uid}`: 获取指定 UID 的内容
- `/recent-content`: 获取最近的内容
- `/content-by-uids`: 根据多个 UID 获取内容
- `/recent-uids`: 获取最近添加的 UID 列表
- `/data-source`: 从指定的数据源获取数据
- `/check-activity`: 检查最近的活动是否低于阈值
- `/apply-condition`: 应用条件到内容

## 数据库支持

Warehouse 模块支持以下数据库：

- MongoDB
- MySQL
- PostgreSQL

默认使用 MongoDB。可以通过环境变量 `DB_TYPE` 来选择使用的数据库。

## 使用示例

### 存储数据

```python
import requests
import json

url = "http://localhost:8000/data"
data = {
    "content": "测试内容",
    "author_id": "user123",
    "source_type": "followed"
}
response = requests.post(url, json=data)
print(json.dumps(response.json(), indent=2))
```

### 获取数据

```python
import requests

uid = "your-uid-here"
url = f"http://localhost:8000/content/{uid}"
response = requests.get(url)
print(json.dumps(response.json(), indent=2))
```

### 获取最近内容

```python
import requests

url = "http://localhost:8000/recent-content?source_type=followed&limit=10"
response = requests.get(url)
print(json.dumps(response.json(), indent=2))
```

## 启动 API 服务

```bash
uvicorn warehouse.api:app --host 0.0.0.0 --port 8000 --reload
```

## 数据库环境初始化

在使用数据库连接器之前，需要先初始化数据库环境变量：

```bash
python -m warehouse.storage.init_db mongodb
```

可选的数据库类型有：`mongodb`、`mysql` 和 `pgsql`。

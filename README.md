# DegenPy

An automated content generation and publishing system for cryptocurrency and financial news.

## Project Structure

```
DegenPy/
├── warehouse/             # 数据仓库组件
│   ├── api.py             # 仓库 API 实现
│   ├── message_queue.py   # 消息队列管理
│   ├── storage/           # 数据库连接器
│   │   ├── mongodb/       # MongoDB 连接器
│   │   └── init_db.py     # 数据库初始化脚本
│   └── text_data/         # 文本数据存储 (运行时创建)
├── server/                # 服务器组件
│   ├── agents/            # 代理配置
│   │   ├── trump-xbt.json # 特朗普风格加密货币代理
│   │   ├── tiktok-agent.json # TikTok优化代理
│   │   └── engine.py      # 代理引擎实现
│   ├── tasks/             # 任务定义
│   │   ├── timeline_task.json      # 处理时间线数据（每30分钟）
│   │   ├── special_attention_task.json  # 处理特别关注数据（实时）
│   │   ├── combined_task.json      # 综合处理任务
│   │   └── task_executor.py        # 任务执行器
│   ├── actions/           # 动作实现
│   │   ├── text2v.py      # 文本到视频生成
│   │   ├── webhook.py     # Webhook通知
│   │   ├── tiktok.py      # TikTok发布
│   │   └── twitter.py     # Twitter发布
│   ├── services/          # 服务层组件
│   │   ├── text2video.py  # 文本到视频服务
│   │   ├── video_pool.py  # 视频池管理服务
│   │   └── action_dispatcher.py # 动作调度服务
│   ├── models/            # AI模型连接器
│   │   └── openrouter.py  # OpenRouter API客户端
│   └── api.py             # 服务器API
├── plugins/               # 插件系统目录
│   ├── example/           # 示例插件
│   └── README.md          # 插件开发指南
├── video_pool/            # 视频池存储目录 (运行时创建)
├── run.py                 # 主应用程序运行器
├── test_warehouse.py      # 仓库API测试脚本
├── .env                   # 环境变量
└── requirements.txt       # Python依赖
```

## 系统架构

1. **数据仓库** (`warehouse/api.py`): 接收并存储来自外部源的数据，使用MongoDB作为主要存储后端:
   - MongoDB: 主要数据库存储，支持文档型数据和灵活的数据模型
   - Redis: 用于存储时间线数据的UUID列表和消息队列集成
   
2. **消息队列** (`warehouse/message_queue.py`): 管理消息的发送和接收:
   - 特别关注数据发送到RabbitMQ消息队列
   - 支持实时通知和异步处理

3. **代理引擎** (`server/agents/engine.py`): 管理AI代理的行为和交互:
   - 加载和管理代理配置
   - 处理代理与任务的关联
   - 根据代理的个性和偏好生成内容

4. **任务执行器** (`server/tasks/task_executor.py`):
   - 根据数据来源自动选择处理方式
   - 从消息队列获取特别关注数据并进行验证和AI处理
   - 从Redis列表获取时间线数据并直接生成视频

5. **服务组件** (`server/services/`):
   - **Text2Video服务**: 管理从文本内容生成视频
   - **视频池服务**: 管理视频任务及其元数据
   - **动作调度器**: 处理视频生成后的动作执行

6. **动作模块** (`server/actions/`):
   - 各种动作的实现，如视频生成、社交媒体发布等

## 异步文生视频流程

1. 触发器被激活并获取数据。
2. AI 使用代理的个性处理数据。
3. 文生视频请求被发送到 `text2video` 服务，主流程结束。
4. 视频异步生成，结果存储在视频池中。
5. 视频生成完成后，通过 Redis 发送通知。
6. 动作调度服务接收通知，根据任务配置执行后续动作（如发布到社交媒体）。

## 数据处理流程

系统实现了两种不同的数据处理流程：

1. **时间线数据处理**（`timeline_task.json`）：
   - 每30分钟执行一次
   - 从Redis列表中获取时间线数据的UUID
   - 直接生成视频，不需要额外的真实性验证
   - 适用于一般新闻和信息更新

2. **特别关注数据处理**（`special_attention_task.json`）：
   - 实时执行，监听消息队列
   - 从消息队列获取特别关注数据的UUID
   - 进行真实性验证和AI处理
   - 生成高优先级的突发新闻视频
   - 适用于重要新闻和紧急事件

3. **综合处理任务**（`combined_task.json`）：
   - 同时支持实时监听和定时生成
   - 可以处理多种数据源
   - 提供灵活的配置选项

### 数据标签系统

系统使用标签区分不同类型的数据：

- **标签1（时间线）**：
  - 源类型为 `other` 的数据
  - UUID被发送到Redis列表
  - 定时处理，不需要额外验证

- **标签2（特别关注）**：
  - 源类型为 `followed` 或 `trending` 的数据
  - UUID被发送到消息队列
  - 实时处理，需要真实性验证和AI处理

### 数据存储集成

- **MongoDB**：存储所有类型的数据内容
- **Redis**：存储时间线数据的UUID列表
- **RabbitMQ**：用于特别关注数据的消息队列

### 数据接收API

- `POST /data`：接收并存储数据
  - 参数：`content`（内容）, `author_id`（作者ID）, `source_type`（来源类型）, `metadata`（元数据）
  - 返回：生成的内容ID

- `GET /content/{content_id}`：获取指定ID的内容
  - 返回：内容详情

- `GET /recent-content`：获取最近的内容
  - 参数：`source_type`（可选，筛选来源类型）, `limit`（限制返回数量）
  - 返回：内容列表

## 数据库集成

系统使用多种数据存储技术来满足不同的需求：

### MongoDB 主要存储
- 系统的主要数据存储后端
- 存储所有类型的数据内容，包括时间线和特别关注数据
- 提供灵活的文档型数据模型和高效的查询能力
- 存储的文档包含完整的元数据，如作者ID、来源类型、标签和创建时间

### Redis 集成
- 用于存储时间线数据的UUID列表
- 提供高性能的列表操作，支持快速的数据检索
- 通过环境变量配置（REDIS_HOST、REDIS_PORT、REDIS_DB）
- 使用REDIS_TIMELINE_KEY环境变量配置时间线数据的键名

### RabbitMQ 消息队列
- 用于特别关注数据的实时处理
- 提供可靠的消息传递和分发机制
- 支持多个消费者订阅同一频道
- 通过环境变量配置连接参数

## 数据存储接口

数据仓库提供统一的接口来存储和检索数据：

1. **数据存储接口**：
   - `store_data`: 存储数据到MongoDB，并根据标签将UUID发送到Redis或消息队列
   - 自动根据源类型确定标签：`followed`和`trending`为标签2，`other`为标签1

2. **数据检索接口**：
   - `get_data_by_uid`: 根据UID获取数据
   - `get_recent_data`: 获取最近的数据
   - `get_data_by_uids`: 根据多个UID获取数据
   - `execute_query`: 执行自定义查询

3. **UUID跟踪器**：
   - `RecentUIDTracker`: 跟踪最近添加的UUID
   - 按源类型分类存储，支持检索和清除操作

## 触发器流程

1. 触发器根据其计划激活。
2. 从指定源获取数据（API、数据库或来自仓库的最近 UID）。
3. AI 使用代理的个性处理数据。
4. 内容转换为视频。
5. 内容发布到社交媒体平台。
6. 发送 Webhook 通知。

## 设置说明

1. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

2. 配置环境变量：
   - 复制 `.env.example` 到 `.env`（如果提供）
   - 设置 API 密钥和数据库凭据

3. 初始化数据库环境：
   ```
   python -m warehouse.storage.init_db [mongodb|mysql|pgsql]
   ```

4. 启动应用程序：
   ```
   python run.py
   ```

5. 测试数据仓库 API：
   ```
   python test_warehouse.py
   ```

## API 端点

### 数据仓库 API

- `GET /`: 健康检查
- `POST /data`: 存储数据
  - 参数：`content`, `author_id`, `source_type`, `uid`(可选)
- `GET /content/{uid}`: 获取特定 UID 的数据
- `GET /recent-content`: 获取最近存储的项目
  - 参数：`source_type`(可选), `limit`(默认30)
- `GET /content-by-uids`: 获取特定 UID 列表的数据
  - 参数：`uids`(逗号分隔的 UID 列表)
- `GET /recent-uids`: 获取最近添加的 UID 列表
  - 参数：`source_type`(可选)

### 服务器 API

- `GET /agents`: 列出所有代理
- `GET /agents/{agent_id}`: 获取代理详情
- `GET /tasks`: 列出所有可用任务
- `GET /tasks/{task_id}`: 获取特定任务的详情
- `POST /run-task/{task_id}`: 手动运行特定任务
- `GET /conditions`: 列出所有可用条件
- `GET /conditions/{condition_id}`: 获取特定条件的详情

## 许可证

[MIT License](LICENSE)

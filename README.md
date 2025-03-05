# DegenPy

An automated content generation and publishing system for cryptocurrency and financial news.

## Project Structure

```
DegenPy/
├── warehouse/             # 数据仓库组件
│   ├── api.py             # 仓库 API 实现
│   ├── storage/           # 数据库连接器
│   │   ├── mongodb/       # MongoDB 连接器
│   │   ├── mysql/         # MySQL 连接器
│   │   └── pgsql/         # PostgreSQL 连接器
│   └── text_data/         # 文本数据存储 (运行时创建)
├── server/                # 服务器组件
│   ├── agents/            # 代理配置
│   │   ├── trump-xbt.json # 特朗普风格加密货币代理
│   │   └── tiktok-agent.json # TikTok优化代理
│   ├── tasks/             # 任务定义
│   │   ├── followed_news.json   # 处理关注人信息（每10分钟）
│   │   ├── trending_news.json   # 处理Twitter趋势信息（每30分钟）
│   │   ├── historical_news.json # 处理历史数据（信息不足时）
│   │   └── conditions/    # 条件定义
│   │       ├── followed_condition.json    # 关注人信息处理条件
│   │       ├── trending_condition.json    # Twitter趋势信息处理条件
│   │       └── historical_condition.json  # 历史数据处理条件
│   ├── actions/           # 动作实现
│   │   ├── text2v.py      # 文本到视频生成
│   │   ├── webhook.py     # Webhook通知
│   │   ├── tiktok.py      # TikTok发布
│   │   └── twitter.py     # Twitter发布
│   ├── services/          # 服务层组件
│   │   ├── text2video.py  # 文本到视频服务
│   │   ├── video_pool.py  # 视频池管理服务
│   │   └── action_dispatcher.py # 动作调度服务
│   ├── infrastructure/    # 基础设施组件
│   │   └── message_broker.py # 消息代理服务
│   ├── models/            # AI模型连接器
│   │   └── openrouter.py  # OpenRouter API客户端
│   ├── api.py             # 服务器API
│   └── .env               # 服务器环境变量
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

1. **数据仓库** (`warehouse/api.py`): 接收并存储来自外部源的数据，支持多种存储后端:
   - 文本文件: 简单的基于文件的存储，用于开发和测试
   - MongoDB: 默认的数据库存储，支持文档型数据
   - MySQL: 关系型数据库存储，用于结构化数据
   - PostgreSQL: 高级关系型数据库，支持复杂查询
   
2. **代理** (`server/agents/`): 定义AI个性和行为模式:
   - 每个代理都有个性档案、说话风格和输出偏好
   - 代理与他们可以执行的特定任务相关联

3. **任务和条件** (`server/tasks/`):
   - **任务**: 定义要执行的动作、何时执行以及使用哪些数据源
   - **条件**: 定义处理数据的标准，包括事实检查、令牌限制和提示模板
   - 这种分离允许在不同任务中重用条件

4. **服务** (`server/services/`):
   - **Text2Video服务**: 管理从文本内容生成视频
   - **视频池服务**: 管理视频任务及其元数据
   - **动作调度器**: 处理视频生成后的动作执行

5. **基础设施** (`server/infrastructure/`):
   - **消息代理**: 促进不同组件之间的通信

6. **动作** (`server/actions/`):
   - 各种动作的实现，如视频生成、社交媒体发布等

## 异步文生视频流程

1. 触发器被激活并获取数据。
2. AI 使用代理的个性处理数据。
3. 文生视频请求被发送到 `text2video` 服务，主流程结束。
4. 视频异步生成，结果存储在视频池中。
5. 视频生成完成后，通过 Redis 发送通知。
6. 动作调度服务接收通知，根据任务配置执行后续动作（如发布到社交媒体）。

## 数据源处理

系统支持三种不同的数据收集任务模式：

1. **关注人信息处理**（`followed_news.json`）：
   - 每10分钟执行一次
   - 收集来自关注人的信息并生成新闻摘要
   - 如果收集的数据不足，会从数据库查询最近数据作为备用

2. **Twitter趋势信息处理**（`trending_news.json`）：
   - 每30分钟执行一次
   - 收集Twitter上的趋势信息并生成摘要
   - 同样具有数据库备用机制

3. **历史数据回顾**（`historical_news.json`）：
   - 在新信息较少时执行
   - 从数据库获取最近的数据进行回顾和总结
   - 提供对历史数据的深度分析

### 数据源类型区分

- 系统通过`source_type`字段区分不同来源的数据：
  - `followed`：来自关注人的信息
  - `trending`：来自Twitter趋势的信息
  - `other`：其他来源的信息

- 每种数据源有独立的UUID跟踪器，确保任务处理时能获取正确类型的数据

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

数据仓库服务支持多种数据库后端：

### 文本文件存储
- 以简单的文本格式存储数据，具有 `uid:content` 结构
- 不需要额外的数据库设置
- 适用于开发、测试或简单部署

### MongoDB 集成
- 默认数据库，存储文档型数据
- 提供灵活的数据模型和查询能力
- 通过环境变量配置连接参数

### MySQL 集成
- 将数据存储在关系数据库中，具有简单的模式
- 需要 MySQL 服务器运行并在 `.env` 中配置
- 提供对结构化数据的高效查询

### PostgreSQL 集成
- 高级关系数据库支持
- 适用于需要复杂查询和事务的场景
- 通过环境变量配置连接参数

## 统一存储接口

数据仓库 API 为不同的存储后端提供统一的接口：

1. **通用数据处理**：所有存储后端使用相同的数据处理管道
2. **一致的数据结构**：数据以一致的结构存储（`uid` 和 `content`）
3. **无缝过渡**：应用程序可以在不更改代码的情况下切换存储后端
4. **环境变量配置**：通过 `DB_TYPE` 环境变量选择数据库类型

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

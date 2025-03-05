# DegenPy

An automated content generation and publishing system for cryptocurrency and financial news.

## Project Structure

```
DegenPy/
├── warehouse/             # Data warehouse components
│   ├── api.py             # Warehouse API implementation
│   ├── db/                # Database connectors
│   └── text_data/         # Text-based storage (created at runtime)
├── server/                # Server components
│   ├── agents/            # Agent configurations
│   │   ├── trump-xbt.json # Trump-like cryptocurrency agent
│   │   └── tiktok-agent.json # TikTok-optimized agent
│   ├── tasks/             # Task definitions
│   │   ├── followed_news.json   # 处理关注人信息（每10分钟）
│   │   ├── trending_news.json   # 处理Twitter趋势信息（每30分钟）
│   │   ├── historical_news.json # 处理历史数据（信息不足时）
│   │   └── conditions/    # Condition definitions
│   │       ├── followed_condition.json    # 关注人信息处理条件
│   │       ├── trending_condition.json    # Twitter趋势信息处理条件
│   │       └── historical_condition.json  # 历史数据处理条件
│   ├── actions/           # Action implementations
│   │   ├── text2v.py      # Text-to-video generation
│   │   ├── webhook.py     # Webhook notifications
│   │   ├── tiktok.py      # TikTok publishing
│   │   └── twitter.py     # Twitter publishing
│   ├── services/          # Service layer components
│   │   ├── text2video.py  # Text-to-video service
│   │   ├── video_pool.py  # Video pool management service
│   │   └── action_dispatcher.py # Action dispatcher service
│   ├── infrastructure/    # Infrastructure components
│   │   └── message_broker.py # Message broker service
│   ├── models/            # AI model connectors
│   │   └── openrouter.py  # OpenRouter API client
│   ├── api.py             # Server API
│   └── .env               # Server environment variables
├── plugins/               # 插件系统目录
│   ├── example/           # 示例插件
│   └── README.md          # 插件开发指南
├── video_pool/            # 视频池存储目录 (created at runtime)
├── run.py                 # Main application runner
├── test_warehouse.py      # Test script for warehouse API
├── .env                   # Environment variables
└── requirements.txt       # Python dependencies
```

## System Architecture

1. **Data Warehouse** (`warehouse/api.py`): Receives and stores data from external sources with support for multiple storage backends:
   - Text files: Simple file-based storage for development and testing
   - MySQL: Relational database storage for structured data (future implementation)
   
2. **Agents** (`server/agents/`): Define AI personalities and behavior patterns:
   - Each agent has a personality profile, speaking style, and output preferences
   - Agents are associated with specific tasks they can perform

3. **Tasks and Conditions** (`server/tasks/`):
   - **Tasks**: Define what actions to perform, when to perform them, and which data sources to use
   - **Conditions**: Define criteria for processing data, including fact-checking, token limits, and prompt templates
   - This separation allows for reusing conditions across different tasks

4. **Services** (`server/services/`):
   - **Text2Video Service**: Manages the generation of videos from text content
   - **Video Pool Service**: Manages video tasks and their metadata
   - **Action Dispatcher**: Handles the execution of actions after video generation

5. **Infrastructure** (`server/infrastructure/`):
   - **Message Broker**: Facilitates communication between different components

6. **Actions** (`server/actions/`):
   - Implementations for various actions like video generation, social media publishing, etc.

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

## Storage Integration

The warehouse service supports multiple storage backends:

### Text File Storage
- Stores data in a simple text format with `uid:content` structure
- No additional database setup required
- Useful for development, testing, or simple deployments

### MySQL Integration (Future)
- Will store data in a relational database with a simple schema
- Will require MySQL server to be running and configured in `.env`
- Will provide efficient querying for structured data

## Unified Storage Interface

The warehouse API provides a unified interface for different storage backends:

1. **Common Data Processing**: All storage backends use the same data processing pipeline
2. **Consistent Data Structure**: Data is stored with a consistent structure (`uid` and `content`)
3. **Seamless Transition**: Applications can switch between storage backends without changing code

## Trigger Flow

1. Trigger is activated based on its schedule.
2. Data is fetched from the specified source (API, database, or recent UIDs from warehouse).
3. AI processes the data using the agent's personality.
4. Content is converted to video.
5. Content is published to social media platforms.
6. Webhook notifications are sent.

## Setup Instructions

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Copy `.env.example` to `.env` (if provided)
   - Set API keys and database credentials (for future database integration)

3. Start the application:
   ```
   python run.py
   ```

4. Test the warehouse API:
   ```
   python test_warehouse.py
   ```

## API Endpoints

### Data Warehouse API

- `GET /`: Health check
- `POST /store`: Store data
  - Parameters: `db_type` (text, mysql)
  - Body: `{"uid": "unique_id", "content": "data_content"}`
- `GET /data?p=last30`: Get last 30 stored items
- `GET /data?p=by_uids&uids=id1,id2`: Get data for specific UIDs

### Server API

- `GET /agents`: List all agents
- `GET /agents/{agent_id}`: Get agent details
- `GET /tasks`: List all available tasks
- `GET /tasks/{task_id}`: Get details of a specific task
- `POST /run-task/{task_id}`: Manually run a specific task
- `GET /conditions`: List all available conditions
- `GET /conditions/{condition_id}`: Get details of a specific condition

## License

[MIT License](LICENSE)

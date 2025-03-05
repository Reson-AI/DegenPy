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
│   ├── trigger/           # Trigger rules
│   │   ├── rule-0.json    # Process recent data (every 2 minutes)
│   │   ├── rule-1.json    # Hourly trend analysis
│   │   └── rule-2.json    # Historical content review
│   ├── actions/           # Action implementations
│   │   ├── text2v.py      # Text-to-video generation
│   │   ├── webhook.py     # Webhook notifications
│   │   ├── tiktok.py      # TikTok publishing
│   │   └── twitter.py     # Twitter publishing
│   ├── models/            # AI model connectors
│   │   └── openrouter.py  # OpenRouter API client
│   ├── video_pool.py      # 视频池管理服务
│   ├── text2video.py      # 文生视频异步处理服务
│   ├── action_dispatcher.py # 动作调度服务
│   ├── message_broker.py  # 消息发布/订阅服务
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
2. **Agents** (`server/agents/`): Different personalities for content generation.
3. **Triggers** (`server/trigger/`): Rules that determine when and how to process data.
4. **Actions** (`server/actions/`): Implementations for text-to-video, social media publishing, etc.
5. **Models** (`server/models/`): AI model connectors for content generation.
6. **Video Pool** (`server/video_pool.py`): 管理文生视频任务和结果的服务。
7. **Action Dispatcher** (`server/action_dispatcher.py`): 处理视频生成后的后续动作，如发布到社交媒体。
8. **Message Broker** (`server/message_broker.py`): 基于 Redis 的消息发布/订阅系统，用于组件间通信。
9. **Plugins** (`plugins/`): 插件系统，用于扩展功能。

## 异步文生视频流程

1. 触发器被激活并获取数据。
2. AI 使用代理的个性处理数据。
3. 文生视频请求被发送到 `text2video` 服务，主流程结束。
4. 视频异步生成，结果存储在视频池中。
5. 视频生成完成后，通过 Redis 发送通知。
6. 动作调度服务接收通知，根据任务配置执行后续动作（如发布到社交媒体）。

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
- `GET /triggers`: List all triggers
- `GET /triggers/{trigger_id}`: Get trigger details
- `POST /run-trigger/{trigger_id}`: Manually run a trigger

## License

[MIT License](LICENSE)

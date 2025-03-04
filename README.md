# DegenPy

An automated content generation and publishing system for cryptocurrency and financial news.

## Project Structure

```
DegenPy/
├── warehouse/             # Data warehouse components
│   ├── api.py             # Warehouse API implementation
│   ├── db/                # Database connectors
│   └── txt_storage/       # Text-based storage (created at runtime)
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
│   ├── api.py             # Server API
│   └── .env               # Server environment variables
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

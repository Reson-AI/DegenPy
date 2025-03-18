# DegenPy

DegenPy is an advanced automated content generation and publishing platform designed for cryptocurrency and financial news. The system leverages AI to process data from various sources, generate engaging video content, and publish it to social media platforms like TikTok and Twitter.

## 🌟 Key Features

- **AI-Powered Content Generation**: Transform financial data into engaging narratives using customizable AI agents
- **Automated Video Creation**: Convert text content to high-quality videos using D-ID's API
- **Multi-Platform Publishing**: Seamlessly publish content to TikTok, Twitter, and other platforms
- **Flexible Database Integration**: Support for MongoDB, MySQL, and PostgreSQL
- **Modular Architecture**: Easily extendable with new data sources, AI models, and publishing platforms
- **Real-time Processing**: Handle both scheduled and real-time data processing workflows

## 📂 Project Structure

```
DegenPy/
├── warehouse/                # Data warehouse components
│   ├── api.py                # Warehouse API implementation
│   ├── storage/              # Database connectors
│   │   ├── mongodb/          # MongoDB connector
│   │   ├── mysql/            # MySQL connector
│   │   ├── pgsql/            # PostgreSQL connector
│   │   └── init_db.py        # Database initialization script
│   └── utils/                # Utility functions and classes
├── server/                   # Server components
│   ├── agents/               # Agent configurations
│   │   ├── trump-xbt.json    # Trump-style crypto agent
│   │   ├── tiktok-agent.json # TikTok-optimized agent
│   │   └── engine.py         # Agent engine implementation
│   ├── tasks/                # Task definitions
│   │   ├── timeline_task/    # Timeline data processing (every 30 min)
│   │   ├── special_attention_task/ # Special attention data (real-time)
│   │   └── task_executor.py  # Task executor
│   ├── actions/              # Action implementations
│   │   ├── text2v.py         # Text-to-video generation
│   │   ├── webhook.py        # Webhook notifications
│   │   ├── tiktok.py         # TikTok publishing
│   │   └── twitter.py        # Twitter publishing
│   └── api.py                # Server API
├── examples/                 # Example scripts and usage demos
├── plugins/                  # Plugin system directory
├── run.py                    # Main application runner
├── .env.example              # Example environment variables
└── requirements.txt          # Python dependencies
```

## 🏗️ System Architecture

### Core Components

1. **Data Warehouse** (`warehouse/api.py`)
   - Centralized data storage and retrieval system
   - Supports multiple database backends (MongoDB, MySQL, PostgreSQL)
   - Simplified data structure with uid, content (dict), and tags (dict)
   - Provides unified interface for data operations

2. **Agent Engine** (`server/agents/engine.py`)
   - Manages AI agent behaviors and interactions
   - Loads and configures agent personalities
   - Processes data according to agent preferences
   - Generates content with consistent tone and style

3. **Task Executor** (`server/tasks/task_executor.py`)
   - Orchestrates task execution workflows
   - Manages timeline and special attention data processing
   - Uses UID tracker to monitor processing status
   - Handles both scheduled and real-time tasks

4. **Action Modules** (`server/actions/`)
   - **text2v.py**: Text-to-video generation using D-ID API
   - **tiktok.py**: TikTok publishing and token management
   - **twitter.py**: Twitter content publishing
   - **webhook.py**: External notification system

### Data Processing Workflows

#### Timeline Task Workflow
- Scheduled execution (every 30 minutes)
- Processes general news and updates
- Direct video generation without additional verification
- Suitable for regular content updates

#### Special Attention Task Workflow
- Real-time execution for high-priority data
- Enhanced verification and AI processing
- Generates breaking news videos
- Suitable for important events requiring immediate attention

### Text-to-Video Pipeline

1. Task is triggered and retrieves data from the warehouse
2. AI agent processes the data and generates narrative content
3. Text-to-video request is sent to D-ID API
4. Video is generated and status is monitored
5. Upon completion, video is published to configured platforms
6. Webhook notifications are sent to external systems

## 🗄️ Database Integration

### Flexible Database Support

The system provides a unified interface for different database backends:

- **MongoDB**: Document-based storage with flexible schema
- **MySQL**: Relational database for structured data
- **PostgreSQL**: Advanced relational database with JSON support

The active database is selected through the `DB_TYPE` environment variable.

### Database Connector Interface

All database connectors implement the following methods:

- `store_data`: Store data with optional tags
- `get_data_by_uid`: Retrieve data by a single UID
- `get_recent_data`: Get recently added data
- `get_data_by_uids`: Retrieve data by multiple UIDs
- `execute_query`: Run custom database queries

### UID Tracking System

The `RecentUIDTracker` class maintains a record of recently added UIDs:

- Categorizes UIDs by source type
- Provides retrieval and clearing operations
- Facilitates efficient data processing workflows

## 🔌 API Endpoints

### Data Management

- `POST /warehouse/data`: Store new data
  - Parameters: `content` (dict), `tags` (optional dict)
  - Returns: Generated UID

- `GET /warehouse/data/{uid}`: Retrieve data by UID
  - Returns: Complete data object

- `GET /warehouse/recent`: Get recent data entries
  - Parameters: `limit` (optional, default=10)
  - Returns: List of recent data objects

### Video Generation

- `POST /server/generate-video`: Create a new video
  - Parameters: `text`, `presenter`, `voice` (optional)
  - Returns: Video task ID

- `GET /server/video-status/{task_id}`: Check video generation status
  - Returns: Status and result URL when complete

## 🚀 Getting Started

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/DegenPy.git
cd DegenPy

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Create your environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your API keys and database credentials

3. Initialize the database:
   ```bash
   python -m warehouse.storage.init_db [mongodb|mysql|pgsql]
   ```

### Running the Application

```bash
python run.py
```

### Example Usage

Check the `examples/` directory for sample scripts demonstrating how to:

- Configure the environment variables
- Generate videos using the D-ID API
- Publish content to TikTok
- Implement custom data processing workflows

## Additional API Endpoints

### Warehouse API

- `POST /data`: Store data
  - Parameters: `content`, `author_id`, `source_type`, `uid` (optional)
- `GET /content/{uid}`: Get data for a specific UID
- `GET /recent-content`: Get recently stored items
  - Parameters: `source_type` (optional), `limit` (default 30)
- `GET /content-by-uids`: Get data for a list of UIDs
  - Parameters: `uids` (comma-separated list of UIDs)
- `GET /recent-uids`: Get list of recently added UIDs
  - Parameters: `source_type` (optional)

### Server API

- `GET /agents`: List all agents
- `GET /agents/{agent_id}`: Get agent details
- `GET /tasks`: List all available tasks
- `GET /tasks/{task_id}`: Get details for a specific task
- `POST /run-task/{task_id}`: Manually run a specific task
- `GET /conditions`: List all available conditions
- `GET /conditions/{condition_id}`: Get details for a specific condition

## License

[MIT License](LICENSE)

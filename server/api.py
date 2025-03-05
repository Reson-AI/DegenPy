#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks

# 加载环境变量
load_dotenv()

# 导入视频生成服务
from server.services.text2video import generate_video_from_text
from server.services.video_pool import get_video_task, get_video_task_count, get_video_path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

# Load environment variables
load_dotenv()

app = FastAPI(title="DegenPy Server API", description="Agent and trigger management API")

class AgentConfig(BaseModel):
    name: str
    description: str
    personality: Dict[str, Any]
    triggers: List[str]

class TriggerRule(BaseModel):
    id: str
    name: str
    description: str
    schedule: str
    data_source: str
    conditions: Dict[str, Any]
    actions: List[str]

class Response(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

# In-memory storage for scheduled jobs
scheduled_jobs = {}

# Warehouse API configuration
WAREHOUSE_API_URL = os.getenv("WAREHOUSE_API_URL", "http://localhost:8000")

@app.get("/")
async def root():
    return {"status": "ok", "message": "DegenPy Server API is running"}

@app.get("/agents")
async def list_agents():
    """List all available agents"""
    try:
        agents_dir = "agents"
        agents = []
        
        for filename in os.listdir(agents_dir):
            if filename.endswith(".json"):
                with open(os.path.join(agents_dir, filename), "r", encoding="utf-8") as f:
                    agent_data = json.load(f)
                    agents.append({
                        "id": filename.replace(".json", ""),
                        "name": agent_data.get("name", "Unnamed Agent"),
                        "description": agent_data.get("description", "")
                    })
                    
        return Response(status="success", message=f"Found {len(agents)} agents", data={"agents": agents})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details by ID"""
    try:
        agent_file = f"agents/{agent_id}.json"
        
        with open(agent_file, "r", encoding="utf-8") as f:
            agent_data = json.load(f)
            
        return Response(status="success", message=f"Agent found", data={"agent": agent_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/triggers")
async def list_triggers():
    """List all available triggers"""
    try:
        triggers_dir = "trigger"
        triggers = []
        
        for filename in os.listdir(triggers_dir):
            if filename.endswith(".json"):
                with open(os.path.join(triggers_dir, filename), "r", encoding="utf-8") as f:
                    trigger_data = json.load(f)
                    triggers.append({
                        "id": filename.replace(".json", ""),
                        "name": trigger_data.get("name", "Unnamed Trigger"),
                        "description": trigger_data.get("description", "")
                    })
                    
        return Response(status="success", message=f"Found {len(triggers)} triggers", data={"triggers": triggers})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/triggers/{trigger_id}")
async def get_trigger(trigger_id: str):
    """Get trigger details by ID"""
    try:
        trigger_file = f"trigger/{trigger_id}.json"
        
        with open(trigger_file, "r", encoding="utf-8") as f:
            trigger_data = json.load(f)
            
        return Response(status="success", message=f"Trigger found", data={"trigger": trigger_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-trigger/{trigger_id}")
async def run_trigger(trigger_id: str, background_tasks: BackgroundTasks):
    """Manually run a trigger"""
    try:
        trigger_file = f"trigger/{trigger_id}.json"
        
        with open(trigger_file, "r", encoding="utf-8") as f:
            trigger_data = json.load(f)
            
        # Execute the trigger in the background
        background_tasks.add_task(execute_trigger, trigger_id, trigger_data)
            
        return Response(status="success", message=f"Trigger {trigger_id} execution started")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def execute_trigger(trigger_id, trigger_data):
    """Execute a trigger based on its configuration"""
    print(f"Executing trigger: {trigger_id}")
    
    try:
        # 1. Fetch data from the specified source
        data = fetch_data_from_source(trigger_data.get("data_source", {}))
        
        if not data or not data.get("items"):
            print(f"No data found for trigger {trigger_id}")
            return
            
        # Get the UIDs list
        uids = data.get("uids", [])
        if not uids and data.get("items"):
            # Extract UIDs from items if not provided directly
            uids = [item.get("uid") for item in data.get("items", []) if item.get("uid")]
            
        print(f"Found {len(uids)} UIDs for processing")
        
        # 2. Apply the conditions/rules
        if len(uids) < trigger_data.get("conditions", {}).get("min_items", 1):
            print(f"Not enough items to process for trigger {trigger_id}")
            return
            
        # Process the data
        processed_content = process_data(data.get("items", []), trigger_data.get("conditions", {}))
        
        if not processed_content:
            print(f"Failed to process data for trigger {trigger_id}")
            return
            
        # 3. Execute the specified actions
        execute_actions(trigger_id, processed_content, trigger_data.get("actions", []))
        
        print(f"Trigger {trigger_id} execution completed successfully")
        
    except Exception as e:
        print(f"Error executing trigger {trigger_id}: {str(e)}")

def fetch_data_from_source(data_source):
    """Fetch data from the specified source"""
    source_type = data_source.get("type")
    
    if source_type == "api":
        url = data_source.get("url")
        params = data_source.get("params", {})
        
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            else:
                print(f"Error fetching data from API: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception fetching data from API: {str(e)}")
            return None
            
    elif source_type == "database":
        # For database sources, we would query the database directly
        # This is a placeholder for actual database query implementation
        query = data_source.get("query")
        print(f"Would execute database query: {query}")
        return {"items": [], "uids": []}
        
    elif source_type == "warehouse":
        # Fetch data directly from the warehouse API
        endpoint = data_source.get("endpoint", "/data")
        params = data_source.get("params", {"p": "sa"})
        
        try:
            response = requests.get(f"{WAREHOUSE_API_URL}{endpoint}", params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {})
            else:
                print(f"Error fetching data from warehouse: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception fetching data from warehouse: {str(e)}")
            return None
            
    elif source_type == "recent_uids":
        # Fetch recent UIDs from the warehouse API
        try:
            response = requests.get(f"{WAREHOUSE_API_URL}/recent-uids", params={"clear": True})
            
            if response.status_code == 200:
                data = response.json()
                uids = data.get("data", {}).get("uids", [])
                
                if uids:
                    # Now fetch the actual data for these UIDs
                    uids_str = ",".join(uids)
                    response = requests.get(
                        f"{WAREHOUSE_API_URL}/data", 
                        params={"p": "by_uids", "uids": uids_str}
                    )
                    
                    if response.status_code == 200:
                        return response.json().get("data", {})
                
                return {"items": [], "uids": []}
            else:
                print(f"Error fetching recent UIDs: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Exception fetching recent UIDs: {str(e)}")
            return None
    
    else:
        print(f"Unknown data source type: {source_type}")
        return None

def process_data(items, conditions):
    """Process the data based on the conditions"""
    # This is a placeholder for actual data processing logic
    # In a real implementation, this would involve:
    # 1. Fact checking if required
    # 2. Applying AI processing with the specified prompt
    # 3. Formatting the output
    
    if not items:
        return None
        
    # For demonstration purposes
    content = "\n\n".join([item.get("content", "") for item in items])
    
    # Apply token limit if specified
    token_limit = conditions.get("token_limit")
    if token_limit and len(content) > token_limit:
        content = content[:token_limit] + "..."
        
    return content

def execute_actions(trigger_id, content, actions):
    """
    执行动作序列
    
    Args:
        trigger_id: 触发器ID
        content: 生成的内容
        actions: 动作列表
    
    Returns:
        执行结果
    """
    # 解析动作序列
    action_sequence = []
    for action in actions:
        action_type = action.get("type")
        if action_type:
            action_sequence.append(action_type)
    
    # 获取触发器信息
    trigger = get_trigger(trigger_id)
    if not trigger:
        return {"status": "error", "message": f"Trigger not found: {trigger_id}"}
    
    # 获取代理信息
    agent_id = trigger.get("agent_id")
    if not agent_id:
        return {"status": "error", "message": f"Agent ID not found in trigger: {trigger_id}"}
    
    agent = get_agent(agent_id)
    if not agent:
        return {"status": "error", "message": f"Agent not found: {agent_id}"}
    
    # 检查队列长度
    from server.video_pool import get_video_task_count
    pending_count = get_video_task_count("pending")
    max_queue_length = int(os.getenv("MAX_QUEUE_LENGTH", "100"))
    
    if pending_count >= max_queue_length:
        return {"status": "rejected", "reason": f"Queue full ({pending_count}/{max_queue_length})"}
    
    # 确定任务优先级
    priority = 0  # 默认优先级
    
    # 根据触发器和代理设置优先级
    if "priority" in trigger:
        priority = int(trigger.get("priority", 0))
    elif "priority" in agent:
        priority = int(agent.get("priority", 0))
    
    # 生成视频
    try:
        from server.services.text2video import generate_video_from_text
        task_id = generate_video_from_text(content, trigger_id, agent_id, action_sequence, priority)
        return {"status": "success", "task_id": task_id}
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Error generating video: {str(e)}"}

def start_scheduler():
    """Start the scheduler for all triggers"""
    triggers_dir = "trigger"
    
    for filename in os.listdir(triggers_dir):
        if filename.endswith(".json"):
            trigger_id = filename.replace(".json", "")
            
            with open(os.path.join(triggers_dir, filename), "r", encoding="utf-8") as f:
                trigger_data = json.load(f)
                
            # Schedule the trigger based on its cron expression
            if "schedule" in trigger_data:
                cron_expr = trigger_data["schedule"]
                
                # Parse cron expression (simplified for this example)
                # Format: "*/2 * * * *" -> every 2 minutes
                parts = cron_expr.split()
                if len(parts) == 5 and parts[0].startswith("*/"):
                    minutes = int(parts[0].replace("*/", ""))
                    schedule.every(minutes).minutes.do(execute_trigger, trigger_id, trigger_data)
                    scheduled_jobs[trigger_id] = f"Every {minutes} minutes"
                    print(f"Scheduled trigger {trigger_id} to run every {minutes} minutes")

@app.on_event("startup")
async def startup_event():
    """Start the scheduler when the API starts"""
    start_scheduler()

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)

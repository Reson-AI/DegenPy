#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks

# 加载环境变量
load_dotenv()

# 导入视频生成服务
from server.services.text2video import generate_video_from_text
from server.services.video_pool import get_video_task, get_video_task_count, get_video_path
# 导入 warehouse API 功能
from warehouse.api import app as warehouse_app
from warehouse.storage import get_db_connector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

# Load environment variables
load_dotenv()

app = FastAPI(title="DegenPy Server API", description="Agent and trigger management API")

# Warehouse API 配置
WAREHOUSE_API_URL = os.getenv("WAREHOUSE_API_URL", "http://localhost:8000")

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

class Agent(BaseModel):
    name: str
    description: str
    personality: Dict[str, Any]
    tasks: List[str]
    output_format: Dict[str, Any]

# In-memory storage for scheduled jobs
scheduled_jobs = {}

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

@app.get("/tasks")
async def list_tasks():
    """List all available tasks"""
    try:
        tasks_dir = "tasks"
        tasks = []
        
        for filename in os.listdir(tasks_dir):
            if filename.endswith(".json"):
                with open(os.path.join(tasks_dir, filename), "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                    tasks.append({
                        "id": task_data.get("id", os.path.splitext(filename)[0]),
                        "name": task_data.get("name", "Unnamed Task"),
                        "description": task_data.get("description", "")
                    })
                    
        return Response(status="success", message=f"Found {len(tasks)} tasks", data={"tasks": tasks})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tasks: {str(e)}")

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task details by ID"""
    try:
        task_file = f"tasks/{task_id}.json"
        
        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
            
        return Response(status="success", message=f"Task found", data={"task": task_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conditions")
async def list_conditions():
    """List all available conditions"""
    try:
        conditions_dir = "tasks/conditions"
        conditions = []
        
        for filename in os.listdir(conditions_dir):
            if filename.endswith(".json"):
                with open(os.path.join(conditions_dir, filename), "r", encoding="utf-8") as f:
                    condition_data = json.load(f)
                    conditions.append({
                        "id": condition_data.get("id", os.path.splitext(filename)[0]),
                        "name": condition_data.get("name", "Unnamed Condition"),
                        "description": condition_data.get("description", "")
                    })
                    
        return Response(status="success", message=f"Found {len(conditions)} conditions", data={"conditions": conditions})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing conditions: {str(e)}")

@app.get("/conditions/{condition_id}")
async def get_condition(condition_id: str):
    """Get condition details by ID"""
    try:
        condition_file = f"tasks/conditions/{condition_id}.json"
        
        with open(condition_file, "r", encoding="utf-8") as f:
            condition_data = json.load(f)
            
        return Response(status="success", message=f"Condition found", data={"condition": condition_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Condition {condition_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-task/{task_id}")
async def run_task(task_id: str, background_tasks: BackgroundTasks):
    """Manually run a task"""
    try:
        task_file = f"tasks/{task_id}.json"
        
        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
            
        # 获取条件信息
        condition_id = task_data.get("condition_id")
        condition_data = {}
        
        if condition_id:
            condition_file = f"tasks/conditions/{condition_id}.json"
            
            try:
                with open(condition_file, "r", encoding="utf-8") as f:
                    condition_data = json.load(f)
            except FileNotFoundError:
                logger.warning(f"Condition {condition_id} not found, proceeding without condition")
                
        # 执行任务
        background_tasks.add_task(execute_task, task_id, task_data, condition_data)
        
        return Response(status="success", message=f"Task {task_id} execution started")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/data")
async def receive_data(data: Dict):
    """接收数据并存储到数据库"""
    try:
        content = data.get("content")
        if not content:
            raise HTTPException(status_code=400, detail="内容不能为空")
            
        author_id = data.get("author_id")
        source_type = data.get("source_type", "other")  # 默认为other
        
        # 验证source_type
        if source_type not in ["followed", "trending", "other"]:
            source_type = "other"
        
        # 准备请求数据
        request_data = {
            "content": content,
            "author_id": author_id,
            "source_type": source_type
        }
        
        # 调用warehouse API存储数据
        response = requests.post(f"{WAREHOUSE_API_URL}/data", json=request_data)
        response.raise_for_status()
        result = response.json()
        
        # 获取生成的UID
        content_id = result.get("data", {}).get("uid")
        
        # 将UUID添加到最近处理队列
        # 使用 warehouse API 添加 UID
        requests.post(f"{WAREHOUSE_API_URL}/data", json={
            "content": "Placeholder content",
            "author_id": "system",
            "source_type": source_type,
            "uid": content_id
        })
        
        return Response(status="success", message="数据接收成功", data={"id": content_id})
    except Exception as e:
        logger.error(f"接收数据时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"接收数据时出错: {str(e)}")

@app.get("/content/{content_id}")
async def get_content(content_id: str):
    """获取指定ID的内容"""
    try:
        # 调用warehouse API获取内容
        response = requests.get(f"{WAREHOUSE_API_URL}/content/{content_id}")
        response.raise_for_status()
        result = response.json()
        
        content_data = result.get("data", {}).get("content")
        if not content_data:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {content_id} 的内容")
            
        return Response(status="success", message="内容获取成功", data={"content": content_data})
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"未找到ID为 {content_id} 的内容")
        else:
            logger.error(f"获取内容时出错: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取内容时出错: {str(e)}")
    except Exception as e:
        logger.error(f"获取内容时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取内容时出错: {str(e)}")

@app.get("/recent-content")
async def get_recent_contents(source_type: Optional[str] = None, limit: int = 50):
    """获取最近的内容"""
    try:
        # 准备请求参数
        params = {}
        if source_type:
            params["source_type"] = source_type
        if limit:
            params["limit"] = limit
            
        # 调用warehouse API获取最近内容
        response = requests.get(f"{WAREHOUSE_API_URL}/recent-content", params=params)
        response.raise_for_status()
        result = response.json()
        
        content_data = result.get("data", {}).get("content", [])
        
        return Response(status="success", message=f"获取到 {len(content_data)} 条最近内容", data={"content": content_data})
    except Exception as e:
        logger.error(f"获取最近内容时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取最近内容时出错: {str(e)}")

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
        # 使用warehouse API替代直接数据库查询
        query = data_source.get("query")
        logger.info(f"使用warehouse API替代数据库查询: {query}")
        
        # 调用warehouse API获取最近内容
        try:
            response = requests.get(f"{WAREHOUSE_API_URL}/recent-content")
            response.raise_for_status()
            result = response.json()
            
            content_data = result.get("data", {}).get("content", [])
            
            # 提取内容和UID
            items = []
            uids = []
            
            for item in content_data:
                if isinstance(item, dict):
                    content = item.get("content")
                    uid = item.get("uid")
                    if content:
                        items.append(content)
                    if uid:
                        uids.append(uid)
            
            return {"items": items, "uids": uids}
        except Exception as e:
            logger.error(f"调用warehouse API时出错: {str(e)}")
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

def execute_task(task_id, task_data, condition_data):
    """Execute a task with its condition"""
    try:
        logger.info(f"Executing task {task_id}: {task_data.get('name')}")
        
        # 获取数据源
        data_source = task_data.get("data_source", {})
        
        # 获取数据内容
        content = get_data_from_source(data_source)
        
        # 如果没有内容，跳过任务
        if not content:
            logger.info(f"Task {task_id} skipped: no content available")
            return
        
        # 应用条件
        if condition_data:
            # 使用 warehouse API 应用条件
            token_limit = condition_data.get("token_limit")
            prompt_template = condition_data.get("prompt_template")
            
            response = requests.post(f"{WAREHOUSE_API_URL}/apply-condition", json={
                "content": content,
                "token_limit": token_limit,
                "prompt_template": prompt_template
            })
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("data", {}).get("content", content)
            
        # 获取动作序列
        actions = task_data.get("actions", [])
        action_sequence = []

        for action in actions:
            action_type = action.get("type")
            
            if action_type == "publish":
                platforms = action.get("platforms", [])
                action_sequence.extend(platforms)
            elif action_type == "webhook":
                action_sequence.append("webhook")
                
        # 获取优先级
        priority = task_data.get("priority", 0)
        
        # 执行动作
        execute_actions(task_id, content, actions, priority)
        
        logger.info(f"Task {task_id} executed successfully")
    except Exception as e:
        logger.error(f"Error executing task {task_id}: {str(e)}")

def get_data_from_source(data_source):
    """Get data from the specified source"""
    try:
        source_type = data_source.get("type", "other")
        
        # 使用 warehouse API 获取数据
        response = requests.get(f"{WAREHOUSE_API_URL}/data-source?source_type={source_type}&min_items=1")
        
        if response.status_code == 200:
            result = response.json()
            content_list = result.get("data", {}).get("content", [])
            
            if content_list:
                # 返回第一条内容
                return content_list[0].get("content", "")
        
        # 如果没有数据，使用备用数据源
        fallback = data_source.get("fallback")
        if fallback:
            return get_data_from_source(fallback)
            
        return "Sample data for testing"
    except Exception as e:
        logger.error(f"Error getting data from source: {str(e)}")
        return "Error data"
    
def apply_condition(content, condition_data):
    """Apply condition to the content"""
    try:
        # 使用 warehouse API 应用条件
        token_limit = condition_data.get("token_limit")
        prompt_template = condition_data.get("prompt_template")
        
        response = requests.post(f"{WAREHOUSE_API_URL}/apply-condition", json={
            "content": content,
            "token_limit": token_limit,
            "prompt_template": prompt_template
        })
        
        if response.status_code == 200:
            result = response.json()
            return result.get("data", {}).get("content", content)
        
        return content
    except Exception as e:
        logger.error(f"Error applying condition: {str(e)}")
        return content
    
def execute_actions(task_id, content, actions, priority=0):
    """Execute the specified actions"""

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

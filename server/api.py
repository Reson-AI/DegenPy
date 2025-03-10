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
from pydantic import BaseModel

# 加载环境变量
load_dotenv()

# 导入视频生成服务
from server.services.text2video import generate_video_from_text
from server.services.video_pool import get_video_task, get_video_task_count, get_video_path
# 导入 warehouse API 功能
from warehouse.api import app as warehouse_app
from warehouse.storage import get_db_connector
# 导入 agent 引擎
from server.agents.engine import agent_engine

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
        agents_dir = "server/agents"
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
        agent_file = f"server/agents/{agent_id}.json"
        
        with open(agent_file, "r", encoding="utf-8") as f:
            agent_data = json.load(f)
            
        return Response(status="success", message=f"Agent found", data={"agent": agent_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks():
    """List all available tasks"""
    try:
        tasks_dir = "tasks"
        tasks = []
        
        # 只检查根目录下的任务文件
        for filename in os.listdir(tasks_dir):
            if filename.endswith(".json") and os.path.isfile(os.path.join(tasks_dir, filename)):
                with open(os.path.join(tasks_dir, filename), "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                    tasks.append({
                        "id": task_data.get("id", os.path.splitext(filename)[0]),
                        "name": task_data.get("name", "Unnamed Task"),
                        "description": task_data.get("description", ""),
                        "type": task_data.get("type", "general")
                    })
                    
        return Response(status="success", message=f"Found {len(tasks)} tasks", data={"tasks": tasks})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing tasks: {str(e)}")

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task details by ID"""
    try:
        # 直接在tasks根目录下查找任务文件
        task_file = f"tasks/{task_id}.json"
        
        if not os.path.exists(task_file):
            raise FileNotFoundError(f"Task {task_id} not found")
        
        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)
            
        return Response(status="success", message=f"Task found", data={"task": task_data})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

# API启动事件
@app.on_event("startup")
async def startup_event():
    """在API启动时自动启动TikTok-agent"""
    logger.info("自动启动TikTok-agent...")
    try:
        # 检查agent是否存在
        agent_id = "tiktok-agent"
        agent_file = f"server/agents/{agent_id}.json"
        
        if os.path.exists(agent_file):
            # 启动TikTok-agent
            agent_engine.run_agent(agent_id)
            logger.info(f"TikTok-agent ({agent_id}) 启动成功")
        else:
            logger.warning(f"TikTok-agent ({agent_id}) 配置文件不存在")
    except Exception as e:
        logger.error(f"启动TikTok-agent时出错: {str(e)}")

@app.post("/run-agent/{agent_id}")
async def run_agent(agent_id: str, background_tasks: BackgroundTasks):
    """启动指定的agent"""
    try:
        # 检查agent是否存在
        agent_file = f"server/agents/{agent_id}.json"
        
        if not os.path.exists(agent_file):
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
            
        # 在后台运行agent
        background_tasks.add_task(agent_engine.run_agent, agent_id)
            
        return Response(status="success", message=f"Agent {agent_id} 启动成功")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error running agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error running agent: {str(e)}")

@app.get("/running-agents")
async def get_running_agents():
    """获取正在运行的agents列表"""
    try:
        # 使用新的get_running_tasks方法获取所有正在运行的任务
        running_tasks_by_agent = agent_engine.get_running_tasks()
        
        running_agents = []
        for agent_id, tasks in running_tasks_by_agent.items():
            # 获取agent配置
            agent_config = agent_engine.agents.get(agent_id, {})
            
            running_agents.append({
                "id": agent_id,
                "name": agent_config.get("name", "Unnamed Agent"),
                "running_tasks": [task["id"] for task in tasks],
                "task_details": tasks
            })
        
        return Response(status="success", message=f"Found {len(running_agents)} running agents", data={"agents": running_agents})
    except Exception as e:
        logger.error(f"Error getting running agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting running agents: {str(e)}")

@app.post("/stop-agent/{agent_id}")
async def stop_agent(agent_id: str):
    """停止指定的agent及其所有任务"""
    try:
        # 检查agent是否存在且正在运行
        if agent_id not in agent_engine.agents:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
            
        agent_config = agent_engine.agents[agent_id]
        tasks = agent_config.get('tasks', [])
        stopped_tasks = []
        
        # 停止该agent的所有任务
        for task_file in tasks:
            task_id = os.path.basename(task_file).replace('.json', '')
            # 使用agent_id:task_id格式查找任务
            unique_task_id = f"{agent_id}:{task_id}"
            if agent_engine.stop_task(unique_task_id):
                stopped_tasks.append(task_id)
        
        return Response(status="success", message=f"Agent {agent_id} 停止成功", data={"stopped_tasks": stopped_tasks})
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error stopping agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error stopping agent: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=True)

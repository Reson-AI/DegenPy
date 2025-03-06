#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import importlib
import threading
from pathlib import Path

# 导入任务执行器
from server.tasks.task_executor import TaskExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("agent_engine")

class AgentEngine:
    """Agent引擎，负责加载和运行agent"""
    
    def __init__(self):
        self.agents_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.tasks_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "tasks"
        self.agents = {}
        self.task_executors = {}
        self.task_threads = {}
        
    def load_agent(self, agent_name):
        """加载指定的agent"""
        agent_file = self.agents_dir / f"{agent_name}.json"
        
        if not agent_file.exists():
            logger.error(f"Agent配置文件不存在: {agent_file}")
            return None
            
        try:
            with open(agent_file, 'r', encoding='utf-8') as f:
                agent_config = json.load(f)
                
            logger.info(f"已加载Agent配置: {agent_name}")
            self.agents[agent_name] = agent_config
            return agent_config
        except Exception as e:
            logger.error(f"加载Agent配置失败: {str(e)}")
            return None
            
    def run_agent(self, agent_name):
        """运行指定的agent"""
        if agent_name not in self.agents:
            agent_config = self.load_agent(agent_name)
            if not agent_config:
                return False
        else:
            agent_config = self.agents[agent_name]
            
        # 执行agent的所有任务
        for task_file in agent_config.get('tasks', []):
            self._run_task(task_file)
            
        return True
        
    def _run_task(self, task_file):
        """运行指定的任务"""
        task_path = self.tasks_dir / task_file
        
        if not task_path.exists():
            logger.error(f"任务配置文件不存在: {task_path}")
            return False
            
        try:
            with open(task_path, 'r', encoding='utf-8') as f:
                task_config = json.load(f)
                
            task_id = task_config.get('id')
            if not task_id:
                logger.error(f"任务配置缺少id: {task_path}")
                return False
                
            # 检查任务是否已经在运行
            if task_id in self.task_executors and self.task_executors[task_id].running:
                logger.info(f"任务已经在运行: {task_id}")
                return True
                
            # 获取当前agent配置
            agent_name = None
            for name, config in self.agents.items():
                if task_file in config.get('tasks', []):
                    agent_name = name
                    break
                    
            if not agent_name:
                logger.error(f"无法确定任务所属的agent: {task_file}")
                return False
                
            agent_config = self.agents[agent_name]
                
            # 创建任务执行器
            executor = TaskExecutor(task_config, agent_config)
            self.task_executors[task_id] = executor
            
            # 启动任务
            executor.start()
            
            # 创建监控线程
            def monitor_thread():
                while executor.running:
                    # 检查任务状态
                    import time
                    time.sleep(60)  # 每分钟检查一次
                    
                # 任务已停止
                logger.info(f"任务已停止: {task_id}")
                
            thread = threading.Thread(
                target=monitor_thread,
                name=f"Monitor-{task_id}",
                daemon=True
            )
            thread.start()
            self.task_threads[task_id] = thread
            
            logger.info(f"任务已启动: {task_id}")
            return True
                
        except Exception as e:
            logger.error(f"启动任务失败: {str(e)}")
            return False
            
    def stop_task(self, task_id):
        """停止指定的任务"""
        if task_id in self.task_executors:
            executor = self.task_executors[task_id]
            executor.stop()
            logger.info(f"已停止任务: {task_id}")
            return True
        else:
            logger.error(f"任务不存在: {task_id}")
            return False
            
    def stop_all_tasks(self):
        """停止所有任务"""
        for task_id, executor in self.task_executors.items():
            executor.stop()
            logger.info(f"已停止任务: {task_id}")
            
        return True

# 创建全局引擎实例
agent_engine = AgentEngine()

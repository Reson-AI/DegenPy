#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import importlib
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

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
        self.task_instances = {}  # 存储任务实例
        self.task_threads = {}   # 存储任务线程
        
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
        
        logger.info(f"开始运行agent: {agent_name}")
            
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
            
            # 使用agent_name和task_id组合作为唯一标识符，确保不同agent的同名任务不会冲突
            unique_task_id = f"{agent_name}:{task_id}"
                
            # 检查任务是否已经在运行
            if unique_task_id in self.task_instances and hasattr(self.task_instances[unique_task_id], 'running') and self.task_instances[unique_task_id].running:
                logger.info(f"任务已经在运行: {unique_task_id}")
                return True
            
            # 从配置中获取执行器类路径
            executor_path = task_config.get('executor')
            if not executor_path:
                logger.error(f"任务配置缺少executor: {task_path}")
                return False
            
            # 动态导入执行器类
            try:
                # 解析模块路径和类名
                module_path, class_name = executor_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                task_class = getattr(module, class_name)
                
                # 创建任务实例
                task_instance = task_class(task_config, agent_config)
                self.task_instances[unique_task_id] = task_instance
                
                # 启动任务
                task_instance.start()
                
                # 记录启动时间
                task_instance.start_time = time.time()
                
                # 创建监控线程
                def monitor_thread():
                    while hasattr(task_instance, 'running') and task_instance.running:
                        # 检查任务状态
                        time.sleep(60)  # 每分钟检查一次
                        
                    # 任务已停止
                    logger.info(f"任务已停止: {unique_task_id}")
                    
                thread = threading.Thread(
                    target=monitor_thread,
                    name=f"Monitor-{unique_task_id}",
                    daemon=True
                )
                thread.start()
                self.task_threads[unique_task_id] = thread
                
                logger.info(f"任务已启动: {unique_task_id} (原始ID: {task_id})")
                return True
                
            except (ImportError, AttributeError) as e:
                logger.error(f"导入任务执行器失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"启动任务失败: {str(e)}")
            return False
            
    def stop_task(self, task_id):
        """停止指定的任务"""
        # 首先尝试精确匹配
        if task_id in self.task_instances:
            task_instance = self.task_instances[task_id]
            if hasattr(task_instance, 'stop'):
                task_instance.stop()
                logger.info(f"已停止任务: {task_id}")
                return True
            else:
                logger.error(f"任务实例没有stop方法: {task_id}")
                return False
        else:
            # 尝试查找以task_id结尾的任务（兼容agent_name:task_id格式）
            matching_tasks = [t for t in self.task_instances.keys() if t.endswith(f":{task_id}")]
            if matching_tasks:
                for match in matching_tasks:
                    task_instance = self.task_instances[match]
                    if hasattr(task_instance, 'stop'):
                        task_instance.stop()
                        logger.info(f"已停止任务: {match}")
                    else:
                        logger.error(f"任务实例没有stop方法: {match}")
                return True
            else:
                logger.error(f"任务不存在: {task_id}")
                return False
            
    def stop_all_tasks(self):
        """停止所有任务"""
        for task_id, task_instance in list(self.task_instances.items()):
            if hasattr(task_instance, 'stop'):
                task_instance.stop()
                logger.info(f"已停止任务: {task_id}")
            else:
                logger.error(f"任务实例没有stop方法: {task_id}")
            
        return True
        
    def get_running_tasks(self):
        """获取所有正在运行的任务"""
        running_tasks = {}
        for task_id, task_instance in self.task_instances.items():
            if hasattr(task_instance, 'running') and task_instance.running:
                # 提取原始任务ID和agent名称
                if ":" in task_id:
                    agent_name, original_task_id = task_id.split(":", 1)
                else:
                    agent_name = "unknown"
                    original_task_id = task_id
                    
                if agent_name not in running_tasks:
                    running_tasks[agent_name] = []
                    
                running_tasks[agent_name].append({
                    "id": original_task_id,
                    "full_id": task_id,
                    "start_time": task_instance.start_time if hasattr(task_instance, "start_time") else None,
                    "type": task_instance.__class__.__name__
                })
                
        return running_tasks

# 创建全局引擎实例
agent_engine = AgentEngine()

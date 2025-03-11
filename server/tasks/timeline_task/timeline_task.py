#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import asyncio
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("timeline_task")

# 导入数据库连接器
from warehouse.api import get_data_by_uids
from warehouse.storage.mongodb.connector import mongodb_connector
from warehouse.utils.uid_tracker import uid_tracker

# 导入视频生成服务
from server.services.text2video import generate_video_from_text

# 导入OpenRouter API
from server.models.openrouter import generate_content

class TimelineTask:
    """时间线任务执行器，负责定期获取内容，生成汇总视频"""
    
    def __init__(self, task_config, agent_config):
        """
        初始化任务执行器
        
        Args:
            task_config: 任务配置
            agent_config: Agent配置
        """
        self.task_config = task_config
        self.agent_config = agent_config
        self.task_id = task_config.get('id', 'unknown_task')
        self.running = False
        self.poll_thread = None
        
        # 加载组件
        self.components = task_config.get('components', [])
        logger.info(f"时间线任务 {self.task_id} 使用组件: {', '.join(self.components)}")
        
        # 获取批量大小配置
        data_source = self.task_config.get('data_source', {})
        self.batch_size = data_source.get('batch_size', 10)
        self.time_window = data_source.get('time_window', 1800)  # 默认30分钟
        
        logger.info(f"时间线任务 {self.task_id} 初始化完成，批量大小: {self.batch_size}, 时间窗口: {self.time_window}秒")
    
    def start(self):
        """启动任务"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动时间线任务: {self.task_id}")
        
        # 获取轮询配置
        poll_config = self.task_config.get('schedule', {})
        if isinstance(poll_config, str) or not poll_config:
            # 简化配置，默认每30分钟执行一次
            poll_config = {
                'type': 'interval',
                'minutes': 30
            }
        
        # 启动轮询线程
        self._start_polling(poll_config)
    
    def _start_polling(self, poll_config: Dict[str, Any]):
        """启动轮询线程
        
        Args:
            poll_config: 轮询配置，包含type和时间间隔
        """
        poll_type = poll_config.get('type', 'interval')
        
        if poll_type == 'interval':
            # 计算间隔秒数
            seconds = poll_config.get('seconds', 0)
            minutes = poll_config.get('minutes', 0)
            hours = poll_config.get('hours', 0)
            
            interval_seconds = seconds + minutes * 60 + hours * 3600
            if interval_seconds <= 0:
                interval_seconds = 300  # 默认5分钟
            
            logger.info(f"时间线任务 {self.task_id} 启动轮询，间隔 {interval_seconds} 秒")
            
            # 启动轮询线程
            def poll_thread_func():
                logger.info(f"时间线任务 {self.task_id} 轮询线程启动")
                
                # 立即执行一次
                self._execute_and_handle_exceptions()
                
                while self.running:
                    time.sleep(interval_seconds)
                    if not self.running:
                        break
                    
                    self._execute_and_handle_exceptions()
                
                logger.info(f"时间线任务 {self.task_id} 轮询线程停止")
            
            self.poll_thread = threading.Thread(
                target=poll_thread_func,
                name=f"Poll-{self.task_id}",
                daemon=True
            )
            self.poll_thread.start()
        else:
            logger.error(f"不支持的轮询类型: {poll_type}")
    
    def _execute_and_handle_exceptions(self):
        """执行任务并处理异常"""
        try:
            # 检查新数据并执行任务
            asyncio.run(self.check_and_execute())
        except Exception as e:
            logger.error(f"时间线任务 {self.task_id} 执行出错: {str(e)}", exc_info=True)
            
    async def check_and_execute(self):
        """检查是否有新数据并执行任务"""
        logger.info(f"检查时间线任务新数据: {self.task_id}")
        
        # 获取最近时间窗口内的新数据
        data = await self._get_new_data()
        if not data:
            logger.info(f"没有新的时间线数据: {self.task_id}")
            return
        
        # 执行任务处理
        self.execute(data)
    
    def execute(self, data=None):
        """
        执行任务
        
        Args:
            data: 待处理的数据
        """
        logger.info(f"执行时间线任务: {self.task_id}")
        
        if not data:
            logger.warning(f"没有数据可处理: {self.task_id}")
            return
            
        # 确保数据是列表形式
        items_list = data if isinstance(data, list) else [data]
        
        # 如果没有数据，直接返回
        if not items_list:
            logger.warning(f"没有可处理的数据项: {self.task_id}")
            return
            
        # 直接使用原始数据项列表
        raw_items = items_list
        
        # 内容处理和汇总生成
        if "content_processor" in self.components and raw_items:
            # 直接将整个字典列表传递给处理方法
            summary_content = self._process_all_items(raw_items)
        else:
            # 如果没有内容处理组件，将原始数据转换为JSON字符串
            summary_content = json.dumps(raw_items, ensure_ascii=False, indent=2)
            
        # 生成视频
        if "video_generator" in self.components:
            # 计算原始数据项目数量
            item_count = len(raw_items) if raw_items else 1
            self._generate_video(summary_content, item_count)
        
    async def _get_new_data(self):
        """
        获取新数据
        
        Returns:
            新的数据列表
        """
        try:
            # 获取时间窗口配置
            time_threshold = datetime.now() - timedelta(seconds=self.time_window)
            
            # 查询最近时间窗口内的数据
            query = {
                "timestamp": {"$gte": time_threshold}
            }
            
            # 从MongoDB中查询数据，按时间戳降序排序，限制批量大小
            recent_data = list(mongodb_connector.db.data.find(query).sort("timestamp", -1).limit(self.batch_size))
            
            if not recent_data:
                return None
            
            # 提取UID列表
            uids = [item.get("_id") for item in recent_data if "_id" in item]
            
            # 使用UID跟踪器过滤出未处理的UID
            unprocessed_uids = uid_tracker.get_unprocessed(uids, self.task_id)
            
            if not unprocessed_uids:
                return None
            
            # 获取未处理数据的完整内容
            unprocessed_data = get_data_by_uids(unprocessed_uids)
            
            # 标记为已处理
            for uid in unprocessed_uids:
                uid_tracker.add_uid(uid, self.task_id)
            
            return unprocessed_data
            
        except Exception as e:
            logger.error(f"获取新数据失败: {str(e)}", exc_info=True)
            return None
            
    def _process_all_items(self, raw_items):
        """
        一次性处理所有数据项
        
        Args:
            raw_items: 原始数据项列表（字典格式）
            
        Returns:
            处理后的汇总内容
        """
        if not raw_items:
            return ""
            
        try:
            # 准备提示词
            task_name = self.task_config.get('name', '时间线汇总')
            
            # 为每个项目添加ID（如果没有）
            for i, item in enumerate(raw_items):
                if "id" not in item:
                    item["id"] = i + 1
                
            # 将字典列表转换为JSON字符串
            content_json = json.dumps(raw_items, ensure_ascii=False, indent=2)
            
            prompt = f"""请分析以下多条信息，并创建一份完整的时间线汇总报告。报告应该：
                        1. 提供一个简洁的总体概述
                        2. 按重要性和时间顺序组织信息
                        3. 保留所有关键细节和数据点
                        4. 使用清晰、专业的语言
                        5. 适合作为{task_name}的内容
                        6. 不要输出原始JSON数据，只输出整理后的报告

                        原始信息（JSON格式）：
                        {content_json}

                        时间线汇总报告："""
            
            # 使用OpenRouter API生成内容
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-sonnet:beta')  # 使用更强大的模型进行汇总
            temperature = ai_config.get('temperature', 0.5)
            max_tokens = ai_config.get('max_tokens', 4000)  # 增加token上限以处理更多内容
            summary_content = generate_content(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            
            if summary_content:
                logger.info(f"使用AI成功生成时间线汇总: {self.task_id}")
                return summary_content
            else:
                logger.warning(f"AI生成汇总失败，返回原始JSON: {self.task_id}")
                # 如果失败，直接返回原始数据的JSON字符串
                return content_json
                
        except Exception as e:
            logger.error(f"AI生成汇总异常: {str(e)}")
            # 如果发生异常，尝试返回原始数据的JSON字符串
            try:
                return json.dumps(raw_items, ensure_ascii=False, indent=2)
            except:
                return "处理数据时发生错误"
            
    def _generate_video(self, content, item_count=1):
        """
        生成视频
        
        Args:
            content: 内容
            item_count: 包含的项目数量
        """
        try:
            # 获取视频配置
            video_config = self.task_config.get('video_config', {})
            
            # 设置默认值
            style = video_config.get('style', 'news_report')
            priority_str = video_config.get('priority', 'normal')
            
            # 转换优先级为数字
            priority_map = {
                'low': 0,
                'normal': 1,
                'high': 2
            }
            priority = priority_map.get(priority_str, 1)  # 时间线任务默认为正常优先级
            
            # 获取发布平台
            platforms = self.task_config.get('platforms', [])
            
            # 创建动作序列
            action_sequence = platforms.copy()
            
            # 如果配置了webhook，添加webhook动作
            if self.task_config.get('webhook'):
                action_sequence.append('webhook')
            
            # 添加汇总标记
            summary_title = self.task_config.get('name', '时间线汇总')
            summary_content = f"{summary_title}\n\n{content}"
            
            # 调用视频生成服务
            task_id = generate_video_from_text(
                content=summary_content,
                trigger_id=self.task_id,
                agent_id=self.agent_config.get('id'),
                action_sequence=action_sequence,
                priority=priority,
                style=style,
                metadata={"type": "timeline", "count": item_count, "style": style}
            )
            
            logger.info(f"时间线视频生成任务已创建: {task_id}, 包含{item_count}条内容")
            return task_id
            
        except Exception as e:
            logger.error(f"创建时间线视频生成任务失败: {str(e)}")
            return None
            
    def stop(self):
        """停止任务"""
        if not self.running:
            return
            
        logger.info(f"停止时间线任务: {self.task_id}")
        self.running = False
        
        # 等待轮询线程结束
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

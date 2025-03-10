#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import redis
import logging
import schedule
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("timeline_task")

# 导入数据库连接器
from warehouse.api import get_data_by_uid

# 导入视频生成服务
from server.services.text2video import generate_video_from_text

# 导入OpenRouter API
from server.models.openrouter import generate_content

class TimelineTask:
    """时间线任务执行器，负责定期获取普通推文，生成汇总视频内容"""
    
    def __init__(self, task_config, agent_config):
        """
        初始化任务执行器
        
        Args:
            task_config: 任务配置
            agent_config: Agent配置
        """
        self.task_config = task_config
        self.agent_config = agent_config
        self.task_id = task_config.get('id')
        self.running = False
        
        # 初始化Redis连接
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True
        )
        
        # 加载组件
        self.components = task_config.get('components', [])
        logger.info(f"时间线任务 {self.task_id} 使用组件: {', '.join(self.components)}")
        
    def start(self):
        """启动任务"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动时间线任务: {self.task_id}")
        
        # 时间线任务使用定时执行模式
        schedule_str = self.task_config.get('schedule')
        if schedule_str and schedule_str != 'realtime':
            self._start_scheduled_mode(schedule_str)
        else:
            logger.error(f"时间线任务缺少有效的定时配置: {self.task_id}")
            
    def _start_scheduled_mode(self, schedule_str):
        """启动定时执行模式"""
        logger.info(f"启动定时执行: {schedule_str}")
        
        # 解析cron表达式
        parts = schedule_str.split()
        if len(parts) == 5:
            minute, hour, day, month, weekday = parts
            
            # 创建调度任务
            if minute.startswith('*/'):
                # 每X分钟执行
                interval = int(minute[2:])
                schedule.every(interval).minutes.do(self.execute)
            else:
                # 其他复杂cron表达式
                # 这里简化处理，实际应该使用更完善的cron解析库
                schedule.every().day.at(f"{hour.replace('*', '0')}:{minute.replace('*', '0')}").do(self.execute)
            
            # 启动调度线程
            def schedule_thread():
                while self.running:
                    schedule.run_pending()
                    time.sleep(1)
            
            thread = threading.Thread(
                target=schedule_thread,
                name=f"Schedule-{self.task_id}",
                daemon=True
            )
            thread.start()
        else:
            logger.error(f"无效的cron表达式: {schedule_str}")
            
    def execute(self, trigger_data=None):
        """
        执行任务
        
        Args:
            trigger_data: 触发数据，一般为None，因为时间线任务是定时触发的
        """
        logger.info(f"执行时间线任务: {self.task_id}")
        
        # 1. 获取数据 (data_fetcher组件)
        if "data_fetcher" in self.components:
            data = self._get_data(trigger_data)
            if not data:
                logger.warning(f"没有获取到数据: {self.task_id}")
                return
        else:
            data = trigger_data
            
        # 2. 内容处理 (content_processor组件)
        if "content_processor" in self.components:
            processed_items = []
            if isinstance(data, list):
                for item in data:
                    processed_item = self._process_item(item)
                    if processed_item:
                        processed_items.append(processed_item)
            else:
                processed_item = self._process_item(data)
                if processed_item:
                    processed_items.append(processed_item)
        else:
            processed_items = data if isinstance(data, list) else [data]
            
        # 3. 汇总生成 (summary_generator组件)
        if "summary_generator" in self.components and len(processed_items) > 1:
            summary_content = self._generate_summary(processed_items)
        else:
            summary_content = "\n\n".join([str(item) for item in processed_items if item])
            
        # 4. 生成视频 (video_generator组件)
        if "video_generator" in self.components:
            self._generate_video(summary_content, len(processed_items))
        
    def _get_data(self, trigger_data=None):
        """
        获取数据
        
        Args:
            trigger_data: 触发数据
            
        Returns:
            处理后的数据
        """
        source_config = self.task_config.get('data_source', {})
        source_type = source_config.get('type')
        
        # 如果有触发数据，优先使用
        if trigger_data:
            return trigger_data
                
        # 从数据源获取数据
        if source_type == 'redis_list':
            key = source_config.get('key')
            batch_size = source_config.get('batch_size', 10)
            
            if not key:
                logger.error(f"Redis列表模式缺少key配置: {self.task_id}")
                return None
                
            # 获取指定数量的消息
            messages = []
            for _ in range(batch_size):
                message = self.redis.lpop(key)
                if message:
                    try:
                        messages.append(json.loads(message))
                    except:
                        messages.append(message)
                else:
                    break
                    
            return messages
            
        elif source_type == 'recent_uids':
            source_type = source_config.get('source_type')
            min_items = source_config.get('min_items', 3)
            
            return None
                    
        return None
            
    def _process_item(self, item):
        """
        处理单个项目
        
        Args:
            item: 数据项
            
        Returns:
            处理后的内容
        """
        # 提取原始内容
        raw_content = ""
        if isinstance(item, dict):
            raw_content = item.get('content', '')
        else:
            raw_content = str(item)
            
        if not raw_content.strip():
            return raw_content
            
        try:
            # 准备提示词
            task_name = self.task_config.get('name', '时间线消息')
            
            prompt = f"""请将以下内容整理成一条简洁、专业的新闻报道。保留所有重要信息，但要使用清晰、直接的语言。新闻类型：{task_name}

原始内容：
{raw_content}

整理后的新闻报道："""
            
            # 使用OpenRouter API生成内容
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-haiku:beta')
            temperature = ai_config.get('temperature', 0.5)
            max_tokens = ai_config.get('max_tokens', 3000)
            processed_content = generate_content(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            
            if processed_content:
                logger.info(f"使用AI成功整理内容项目: {self.task_id}")
                return processed_content
            else:
                logger.warning(f"AI整理内容失败，使用原始内容: {self.task_id}")
                return raw_content
                
        except Exception as e:
            logger.error(f"AI整理内容异常: {str(e)}")
            return raw_content
    
    def _generate_summary(self, items):
        """
        生成汇总内容
        
        Args:
            items: 处理后的项目列表
            
        Returns:
            汇总内容
        """
        if not items:
            return ""
            
        try:
            # 将列表转换为汇总文本
            items_text = "\n\n---\n\n".join([str(item) for item in items if item])
            
            # 准备提示词
            task_name = self.task_config.get('name', '时间线汇总')
            
            prompt = f"""请将以下多条新闻内容整理为一个汇总报告。创建一个简洁的概述，然后按重要性顺序列出主要内容点。新闻类型：{task_name}

原始内容：
{items_text}

整理后的汇总报告："""
            
            # 使用OpenRouter API生成内容
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-sonnet:beta')
            temperature = ai_config.get('temperature', 0.5)
            max_tokens = ai_config.get('max_tokens', 3000)
            summary_content = generate_content(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            
            if summary_content:
                logger.info(f"使用AI成功生成汇总内容: {self.task_id}")
                return summary_content
            else:
                logger.warning(f"AI生成汇总内容失败，使用原始列表: {self.task_id}")
                return items_text
                
        except Exception as e:
            logger.error(f"AI生成汇总内容异常: {str(e)}")
            return "\n\n".join([str(item) for item in items if item])
            
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
        self.running = False
        logger.info(f"停止时间线任务: {self.task_id}")

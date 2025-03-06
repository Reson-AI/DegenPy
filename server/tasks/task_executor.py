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
logger = logging.getLogger("task_executor")

# 导入数据库连接器
from warehouse.api import get_data_by_uid, get_recent_data

# 导入视频生成服务
from server.services.text2video import generate_video_from_text

# 导入OpenRouter API
from server.models.openrouter import generate_content, fact_check

class TaskExecutor:
    """任务执行器，负责执行任务配置"""
    
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
        

        
    def start(self):
        """启动任务"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动任务: {self.task_id}")
        
        # 获取数据源配置
        source_config = self.task_config.get('data_source', {})
        
        # 检查是否配置了实时监听
        if source_config.get('channel'):
            # 启动实时监听模式
            logger.info(f"启动实时监听模式: {self.task_id}")
            self._start_realtime_mode()
        
        # 获取调度配置
        schedule_str = self.task_config.get('schedule')
        
        # 检查是否配置了定时任务
        if schedule_str and schedule_str != 'realtime':
            # 启动定时执行模式
            logger.info(f"启动定时执行模式: {self.task_id}")
            self._start_scheduled_mode(schedule_str)
            
    def _start_realtime_mode(self):
        """启动实时监听模式"""
        source_config = self.task_config.get('data_source', {})
        channel = source_config.get('channel')
        
        if not channel:
            logger.error(f"实时监听模式缺少channel配置: {self.task_id}")
            return
            
        logger.info(f"启动实时监听: {channel}")
        
        # 创建Redis订阅
        pubsub = self.redis.pubsub()
        pubsub.subscribe(channel)
        
        # 启动监听线程
        def listen_thread():
            for message in pubsub.listen():
                if not self.running:
                    break
                    
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # 记录数据来源为channel
                        self.trigger_source = 'channel'
                        self.execute(data)
                    except Exception as e:
                        logger.error(f"处理消息失败: {str(e)}")
        
        thread = threading.Thread(
            target=listen_thread,
            name=f"Redis-{channel}",
            daemon=True
        )
        thread.start()
        
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
            trigger_data: 触发数据，实时模式下由Redis提供
        """
        logger.info(f"执行任务: {self.task_id}")
        
        # 如果没有设置数据来源，默认为key
        if not hasattr(self, 'trigger_source'):
            self.trigger_source = 'key'
        
        # 获取数据
        data = self._get_data(trigger_data)
        if not data:
            logger.warning(f"没有获取到数据: {self.task_id}")
            return
            
        # 提取内容
        content = self._extract_content(data)
        if not content:
            logger.warning(f"无法提取内容: {self.task_id}")
            return
            
        # 生成视频
        self._generate_video(content)
        
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
            # 如果是列表，处理每一项
            if isinstance(trigger_data, list):
                complete_data_list = []
                for item in trigger_data:
                    # 如果项目只包含UUID，获取完整数据
                    if isinstance(item, dict) and 'uuid' in item and 'content' not in item:
                        uid = item.get('uuid')
                        complete_data = get_data_by_uid(uid)
                        if complete_data:
                            complete_data_list.append(complete_data)
                        else:
                            complete_data_list.append(item)
                    else:
                        complete_data_list.append(item)
                return complete_data_list
            # 如果是单个对象，检查是否只包含UUID
            elif isinstance(trigger_data, dict) and 'uuid' in trigger_data and 'content' not in trigger_data:
                uid = trigger_data.get('uuid')
                complete_data = get_data_by_uid(uid)
                if complete_data:
                    return complete_data
                else:
                    return trigger_data
            else:
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
            
            # 获取最近数据
            recent_data = get_recent_data(source_type=source_type, limit=min_items)
            
            if recent_data and len(recent_data) >= min_items:
                return recent_data
                
            # 如果数据不足，使用备用数据源
            fallback = source_config.get('fallback')
            if fallback:
                fallback_type = fallback.get('type')
                
                if fallback_type == 'warehouse':
                    endpoint = fallback.get('endpoint')
                    params = fallback.get('params', {})
                    
                    # 这里应该调用warehouse API获取数据
                    # 简化处理，直接使用get_recent_data
                    return get_recent_data(
                        source_type=params.get('source_type'),
                        limit=params.get('limit', 20)
                    )
                    
        return None
        
    def _check_condition(self, data):
        """
        检查条件
        
        Args:
            data: 数据
            
        Returns:
            条件是否满足
        """
        # 简化实现，始终返回True
        return True
            
    def _extract_content(self, data):
        """
        从数据中提取内容，验证真实性，并使用AI整理成新闻
        
        Args:
            data: 数据
            
        Returns:
            提取、验证并整理后的内容
        """
        # 提取原始内容
        raw_content = ""
        if isinstance(data, dict):
            raw_content = data.get('content', '')
        elif isinstance(data, list):
            raw_content = "\n\n".join([item.get('content', '') for item in data if 'content' in item])
        else:
            raw_content = str(data)
            
        if not raw_content.strip():
            return raw_content
            
        # 确定数据来源
        source_config = self.task_config.get('data_source', {})
        source_type = source_config.get('type')
        
        # 判断是否是从channel获取的数据（特别关注新闻）
        is_from_channel = False
        if source_type == 'redis_subscribe':
            # 检查数据是否来自channel
            trigger_source = getattr(self, 'trigger_source', None)
            if trigger_source == 'channel':
                is_from_channel = True
        
        # 如果是从channel获取的数据，进行真实性验证
        verified_content = raw_content
        if is_from_channel:
            try:
                logger.info(f"开始验证新闻真实性: {self.task_id}")
                verification_results = fact_check(raw_content)
                
                # 如果验证结果表明内容可能不真实，添加警告
                if verification_results and 'is_verified' in verification_results:
                    if verification_results['is_verified']:
                        logger.info(f"新闻真实性验证通过: {self.task_id}")
                        verified_content = raw_content
                    else:
                        warning = verification_results.get('warning', '此新闻内容真实性无法确认，请谨慎对待。')
                        logger.warning(f"新闻真实性验证不通过: {self.task_id}")
                        verified_content = f"[警告: {warning}]\n\n{raw_content}"
                else:
                    logger.warning(f"新闻真实性验证结果不完整: {self.task_id}")
                    verified_content = raw_content
            except Exception as e:
                logger.error(f"新闻真实性验证异常: {str(e)}")
                verified_content = raw_content
        
        # 从channel获取的数据需要使用AI整理
        # 从普通的key获取的数据不需要AI整理
        if not is_from_channel:
            return verified_content
            
        try:
            # 准备提示词
            task_name = self.task_config.get('name', '新闻整理')
            
            # 根据数据来源准备不同的提示词
            if is_from_channel:
                prompt = f"""请将以下内容整理成一条特别关注的新闻报道。保留所有重要信息，但要使用清晰、直接的语言。强调新闻的重要性。新闻类型：特别关注 - {task_name}

原始内容：
{verified_content}

整理后的特别关注新闻报道："""
            else:
                prompt = f"""请将以下内容整理成一条简洁、专业的新闻报道。保留所有重要信息，但要使用清晰、直接的语言。新闻类型：{task_name}

原始内容：
{verified_content}

整理后的新闻报道："""
            
            # 使用OpenRouter API生成内容
            model = self.task_config.get('ai_config', {}).get('model', 'anthropic/claude-3-opus:beta')
            processed_content = generate_content(prompt, model=model)
            
            if processed_content:
                logger.info(f"使用AI成功整理内容: {self.task_id}")
                return processed_content
            else:
                logger.warning(f"AI整理内容失败，使用验证后的内容: {self.task_id}")
                return verified_content
                
        except Exception as e:
            logger.error(f"AI整理内容异常: {str(e)}")
            return verified_content
            
    def _generate_video(self, content):
        """
        生成视频
        
        Args:
            content: 内容，可能是字符串或列表
        """
        try:
            # 获取视频配置
            video_config = self.task_config.get('video_config', {})
            
            # 设置默认值
            style = video_config.get('style', 'default')
            priority_str = video_config.get('priority', 'normal')
            
            # 转换优先级为数字
            priority_map = {
                'low': 0,
                'normal': 1,
                'high': 2
            }
            priority = priority_map.get(priority_str, 1)
            
            # 获取发布平台
            platforms = self.task_config.get('platforms', [])
            
            # 创建动作序列
            action_sequence = platforms.copy()
            
            # 如果配置了webhook，添加webhook动作
            if self.task_config.get('webhook'):
                action_sequence.append('webhook')
            
            # 如果是列表，生成汇总视频
            if isinstance(content, list):
                # 将列表转换为汇总文本
                summary_content = "\n\n".join([str(item) for item in content if item])
                
                # 添加汇总标记
                summary_title = self.task_config.get('name', '新闻汇总')
                summary_content = f"{summary_title}\n\n{summary_content}"
                
                # 调用视频生成服务
                task_id = generate_video_from_text(
                    content=summary_content,
                    trigger_id=self.task_id,
                    agent_id=self.agent_config.get('id'),
                    action_sequence=action_sequence,
                    priority=priority,
                    metadata={"type": "summary", "count": len(content)}
                )
                
                logger.info(f"汇总视频生成任务已创建: {task_id}, 包含{len(content)}条内容")
            else:
                # 单条内容生成视频
                task_id = generate_video_from_text(
                    content=content,
                    trigger_id=self.task_id,
                    agent_id=self.agent_config.get('id'),
                    action_sequence=action_sequence,
                    priority=priority
                )
                
                logger.info(f"视频生成任务已创建: {task_id}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"创建视频生成任务失败: {str(e)}")
            return None
            
    def stop(self):
        """停止任务"""
        self.running = False
        logger.info(f"停止任务: {self.task_id}")

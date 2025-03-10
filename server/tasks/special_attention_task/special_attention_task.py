#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import redis
import logging
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
logger = logging.getLogger("special_attention_task")

# 导入数据库连接器
from warehouse.api import get_data_by_uid

# 导入视频生成服务
from server.services.text2video import generate_video_from_text

# 导入OpenRouter API
from server.models.openrouter import generate_content, fact_check

class SpecialAttentionTask:
    """特别关注任务执行器，负责实时监听特别关注的推文，生成视频内容"""
    
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
        redis_password = os.getenv('REDIS_PASSWORD', '')
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            password=redis_password,  # 添加密码认证
            db=int(os.getenv('REDIS_DB', 0)),
            decode_responses=True
        )
        
        # 加载组件
        self.components = task_config.get('components', [])
        logger.info(f"特别关注任务 {self.task_id} 使用组件: {', '.join(self.components)}")
        
    def start(self):
        """启动任务"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动特别关注任务: {self.task_id}")
        
        # 特别关注任务始终使用实时监听模式
        self._start_realtime_mode()
            
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
        
    def execute(self, trigger_data=None):
        """
        执行任务
        
        Args:
            trigger_data: 触发数据，实时模式下由Redis提供
        """
        logger.info(f"执行特别关注任务: {self.task_id}")
        
        # 如果没有设置数据来源，默认为key
        if not hasattr(self, 'trigger_source'):
            self.trigger_source = 'key'
        
        # 1. 获取数据 (data_fetcher组件)
        if "data_fetcher" in self.components:
            data = self._get_data(trigger_data)
            if not data:
                logger.warning(f"没有获取到数据: {self.task_id}")
                return
        else:
            data = trigger_data
            
        # 2. 内容事实核查 (fact_checker组件)
        if "fact_checker" in self.components:
            verified_content = self._fact_check(data)
            if not verified_content:
                logger.warning(f"内容核查失败: {self.task_id}")
                return
        else:
            verified_content = self._extract_raw_content(data)
            
        # 3. 内容处理 (content_processor组件)
        if "content_processor" in self.components:
            processed_content = self._process_content(verified_content)
            if not processed_content:
                logger.warning(f"内容处理失败: {self.task_id}")
                return
        else:
            processed_content = verified_content
            
        # 4. 生成视频 (video_generator组件)
        if "video_generator" in self.components:
            self._generate_video(processed_content)
        
    def _get_data(self, trigger_data=None):
        """
        获取数据
        
        Args:
            trigger_data: 触发数据
            
        Returns:
            处理后的数据
        """
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
                
        # 特别关注任务一般不会主动获取数据，默认返回None
        return None
    
    def _extract_raw_content(self, data):
        """
        从数据中提取原始内容
        
        Args:
            data: 数据
            
        Returns:
            提取的原始内容
        """
        raw_content = ""
        if isinstance(data, dict):
            raw_content = data.get('content', '')
        elif isinstance(data, list):
            raw_content = "\n\n".join([item.get('content', '') for item in data if 'content' in item])
        else:
            raw_content = str(data)
            
        return raw_content.strip()
        
    def _fact_check(self, data):
        """
        验证内容的真实性
        
        Args:
            data: 数据
            
        Returns:
            验证后的内容
        """
        # 提取原始内容
        raw_content = self._extract_raw_content(data)
        
        if not raw_content:
            return raw_content
        
        # 特别关注任务需要严格的真实性验证
        try:
            logger.info(f"开始验证特别关注新闻真实性: {self.task_id}")
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-opus:beta')
            verification_results = fact_check(raw_content, model=model)
            
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
            
        return verified_content
            
    def _process_content(self, content):
        """
        使用AI处理内容，整理成特别关注新闻
        
        Args:
            content: 内容
            
        Returns:
            处理后的内容
        """
        try:
            # 准备提示词
            task_name = self.task_config.get('name', '特别关注')
            
            prompt = f"""请将以下内容整理成一条特别关注的新闻报道。保留所有重要信息，但要使用清晰、直接的语言。强调新闻的重要性和紧急性。新闻类型：特别关注 - {task_name}

原始内容：
{content}

整理后的特别关注新闻报道："""
            
            # 使用OpenRouter API生成内容
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-opus:beta')
            temperature = ai_config.get('temperature', 0.7)
            max_tokens = ai_config.get('max_tokens', 4000)
            processed_content = generate_content(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            
            if processed_content:
                logger.info(f"使用AI成功整理特别关注内容: {self.task_id}")
                return processed_content
            else:
                logger.warning(f"AI整理内容失败，使用原始内容: {self.task_id}")
                return content
                
        except Exception as e:
            logger.error(f"AI整理内容异常: {str(e)}")
            return content
            
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
            style = video_config.get('style', 'breaking_news')
            priority_str = video_config.get('priority', 'high')
            
            # 转换优先级为数字
            priority_map = {
                'low': 0,
                'normal': 1,
                'high': 2
            }
            priority = priority_map.get(priority_str, 2)  # 特别关注默认为高优先级
            
            # 获取发布平台
            platforms = self.task_config.get('platforms', [])
            
            # 创建动作序列
            action_sequence = platforms.copy()
            
            # 如果配置了webhook，添加webhook动作
            if self.task_config.get('webhook'):
                action_sequence.append('webhook')
            
            # 特别关注通常是单条内容
            task_id = generate_video_from_text(
                content=content,
                trigger_id=self.task_id,
                agent_id=self.agent_config.get('id'),
                action_sequence=action_sequence,
                priority=priority,
                style=style,
                metadata={"type": "special_attention", "style": style}
            )
            
            logger.info(f"特别关注视频生成任务已创建: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"创建特别关注视频生成任务失败: {str(e)}")
            return None
            
    def stop(self):
        """停止任务"""
        self.running = False
        logger.info(f"停止特别关注任务: {self.task_id}")

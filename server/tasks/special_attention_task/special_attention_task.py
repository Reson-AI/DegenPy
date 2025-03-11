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
logger = logging.getLogger("special_attention_task")

# 导入数据库连接器
from warehouse.api import get_data_by_uids
from warehouse.storage.mongodb.connector import mongodb_connector
from warehouse.utils.uid_tracker import uid_tracker

# 导入视频生成服务
from server.services.text2video import generate_video_from_text

# 导入OpenRouter API
from server.models.openrouter import generate_content

class SpecialAttentionTask:
    """特别关注任务执行器，负责监控特别关注标签的内容，生成视频内容"""
    
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
        logger.info(f"特别关注任务 {self.task_id} 使用组件: {', '.join(self.components)}")
        
        # 获取特别关注标签列表
        self.special_tags = self._load_special_tags()
        logger.info(f"特别关注任务 {self.task_id} 监控标签: {self.special_tags}")
    
    def _load_special_tags(self):
        """
        加载特别关注标签列表
        
        Returns:
            特别关注标签列表
        """
        # 直接从配置中获取标签
        tags = self.task_config.get('data_source', {}).get('tags', [])
        
        # 如果标签是字符串，转换为列表
        return [tags] if isinstance(tags, str) else (tags if isinstance(tags, list) else [])
    
    def start(self):
        """启动任务"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动特别关注任务: {self.task_id}")
        
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
                interval_seconds = 60  # 默认1分钟
            
            logger.info(f"特别关注任务 {self.task_id} 启动轮询，间隔 {interval_seconds} 秒")
            
            # 启动轮询线程
            def poll_thread_func():
                logger.info(f"特别关注任务 {self.task_id} 轮询线程启动")
                
                # 立即执行一次
                self._execute_and_handle_exceptions()
                
                while self.running:
                    time.sleep(interval_seconds)
                    if not self.running:
                        break
                    
                    self._execute_and_handle_exceptions()
                
                logger.info(f"特别关注任务 {self.task_id} 轮询线程停止")
            
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
            logger.error(f"特别关注任务 {self.task_id} 执行出错: {str(e)}", exc_info=True)
    
    async def check_and_execute(self):
        """检查是否有新数据并执行任务"""
        logger.info(f"检查特别关注任务新数据: {self.task_id}")
        
        # 获取新数据
        data = await self._get_new_data()
        if not data:
            logger.info(f"没有新的特别关注数据: {self.task_id}")
            return
        
        # 执行任务处理
        self.execute(data)
    
    def execute(self, data=None):
        """
        执行任务
        
        Args:
            data: 待处理的数据
        """
        logger.info(f"执行特别关注任务: {self.task_id}")
        
        if not data:
            logger.warning(f"没有数据可处理: {self.task_id}")
            return
            
        # 内容事实核查和处理 (合并fact_checker和content_processor组件)
        if "fact_checker" in self.components or "content_processor" in self.components:
            processed_content = self._process_and_verify_content(data)
            if not processed_content:
                logger.warning(f"内容验证和处理失败: {self.task_id}")
                return
        else:
            processed_content = self._extract_raw_content(data)
            
        # 生成视频 (video_generator组件)
        if "video_generator" in self.components:
            self._generate_video(processed_content)
    
    async def _get_new_data(self):
        """
        获取新数据
        
        Returns:
            新的数据列表
        """
        try:
            # 如果没有特别关注标签，则无法获取数据
            if not self.special_tags:
                logger.warning(f"特别关注任务没有配置标签: {self.task_id}")
                return None
            
            # 构建查询条件：查找包含特定标签的数据
            query = {
                "tags": {"$in": self.special_tags}
            }
            
            # 从MongoDB中查询数据，按时间戳降序排序
            recent_data = list(mongodb_connector.db.data.find(query).sort("timestamp", -1).limit(10))
            
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
    
    def _extract_raw_content(self, data):
        """
        从数据中提取原始内容，直接返回整个字典数据，确保多条资讯被打包成列表
        
        Args:
            data: 数据
            
        Returns:
            原始数据列表
        """
        if not data:
            return []
            
        # 确保数据是列表形式
        if isinstance(data, list):
            return data
        else:
            # 非列表数据，包装成列表
            return [data]
    
    def _process_and_verify_content(self, data):
        """
        验证内容真实性并整理成特别关注新闻（合并了_fact_check和_process_content功能）
        
        Args:
            data: 原始数据
            
        Returns:
            处理后的内容
        """
        # 获取原始数据列表
        raw_data_list = self._extract_raw_content(data)
        
        if not raw_data_list:
            return "没有找到有效内容"
            
        try:
            # 获取AI配置
            ai_config = self.task_config.get('ai_config', {})
            model = ai_config.get('model', 'anthropic/claude-3-opus:beta')
            temperature = ai_config.get('temperature', 0.7)
            max_tokens = ai_config.get('max_tokens', 4000)
            task_name = self.task_config.get('name', '特别关注')
            
            # 将原始数据转换为JSON字符串
            raw_content_json = json.dumps(raw_data_list, ensure_ascii=False, indent=2)
            
            # 准备融合了验证和整理功能的高级提示词
            prompt = f"""# 任务：特别关注新闻验证与整理

## 背景
你是一位专业的新闻编辑和事实核查专家，负责处理标记为"{task_name}"的特别关注新闻。

## 步骤
1. **事实核查**：仔细分析以下JSON格式的内容，评估其真实性和可信度
2. **新闻整理**：将内容重新组织为简洁、清晰的特别关注新闻报道

## 要求
- 保留所有关键事实和重要信息
- 使用简洁有力的语言，突出新闻的重要性和紧急性
- 如发现可疑或无法验证的信息，在报道开头添加明确的警告标签
- 确保最终报道具有专业新闻风格，适合紧急播报
- 报道应包含标题和正文，标题要简洁有力，能够吸引读者注意
- 如果内容涉及数据或统计，请确保准确呈现
- 不要输出原始JSON数据，只输出整理后的报道

## 原始内容（JSON格式）
{raw_content_json}

## 输出格式
如果内容可信：直接输出整理后的新闻报道

## 特别关注新闻报道：
"""
            
            # 使用OpenRouter API生成内容
            processed_content = generate_content(prompt, model=model, temperature=temperature, max_tokens=max_tokens)
            
            if processed_content:
                # 检查是否包含警告标签
                if processed_content.startswith('[警告:'):
                    logger.warning(f"新闻真实性验证不通过: {self.task_id}")
                else:
                    logger.info(f"新闻验证通过并成功整理: {self.task_id}")
                    
                return processed_content
            else:
                logger.warning(f"AI处理内容失败，使用原始内容: {self.task_id}")
                # 如果AI处理失败，返回原始数据的JSON字符串
                return raw_content_json
                
        except Exception as e:
            logger.error(f"新闻验证和整理异常: {str(e)}", exc_info=True)
            # 发生异常时，尝试返回原始数据的JSON字符串
            try:
                return json.dumps(raw_data_list, ensure_ascii=False, indent=2)
            except:
                return "处理数据时发生错误"
    
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
                'low': 3,
                'normal': 2,
                'high': 1,
                'urgent': 0
            }
            priority = priority_map.get(priority_str, 1)  # 默认为high
            
            # 设置视频时长
            duration = video_config.get('duration', 30)
            
            # 生成视频
            logger.info(f"开始生成特别关注视频: {self.task_id}")
            
            # 调用视频生成服务
            video_result = generate_video_from_text(
                content=content,
                style=style,
                duration=duration,
                priority=priority,
                task_id=self.task_id
            )
            
            if video_result and 'video_id' in video_result:
                logger.info(f"特别关注视频生成成功: {video_result['video_id']}")
            else:
                logger.warning(f"特别关注视频生成结果不完整: {video_result}")
                
        except Exception as e:
            logger.error(f"特别关注视频生成异常: {str(e)}")
    
    def stop(self):
        """停止任务"""
        if not self.running:
            return
            
        logger.info(f"停止特别关注任务: {self.task_id}")
        self.running = False
        
        # 等待轮询线程结束
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

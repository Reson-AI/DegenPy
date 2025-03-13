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
from server.actions.text2v import create_video

# 导入推文转新闻功能
from server.actions.tweet2news import generate_news_from_tweet

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
            result = self._process_and_verify_content(data)
            if not result:
                logger.warning(f"内容验证和处理失败: {self.task_id}")
                return
            else:
                # 如果是突发新闻，开始生成视频
                if result.startswith('[警告:内容不是突发新闻]'):
                    logger.warning(f"内容不是突发新闻，不生成视频: {self.task_id}")
                else:
                    processed_content = result
                    # 只有突发新闻才生成视频
                    if "video_generator" in self.components:
                        logger.info(f"内容是突发新闻，开始生成视频: {self.task_id}")
                        self._generate_video(processed_content)
                    else:
                        logger.info(f"内容不是突发新闻，不生成视频: {self.task_id}")
    
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
            
            # 获取MongoDB中的实际集合名称
            collection_names = mongodb_connector.db.list_collection_names()
            
            # 使用正确的集合名称（从环境变量获取）
            collection_name = os.getenv('MONGODB_COLLECTION', 'twitterTweets')
            
            # 计算一分钟前的时间点
            one_minute_ago = datetime.now() - timedelta(minutes=1)
            
            # 构建查询条件：查找包含特定标签且时间在1分钟内的数据
            query = {
                "tags": {"$in": self.special_tags},
                "createdAt": {"$gte": one_minute_ago}
            }
            
            # 记录查询条件
            logger.info(f"查询条件: {query}")
            
            # 从MongoDB中查询数据，按创建时间降序排序
            recent_data = list(mongodb_connector.db[collection_name].find(query).sort("createdAt", -1))
            
            # 记录查询结果数量
            logger.info(f"查询到 {len(recent_data)} 条数据")
            
            if not recent_data:
                logger.info("未找到符合条件的数据")
                return None
            
            # 提取有效的UID列表
            uids = [item.get("_id") for item in recent_data if "_id" in item and item.get("_id") is not None]
            
            if not uids:
                logger.warning("未找到有效的UID")
                return None
                
            logger.info(f"提取到的UID列表: {uids}")
            
            # 使用UID跟踪器过滤出未处理的UID
            unprocessed_uids = uid_tracker.get_unprocessed(uids, self.task_id)
            logger.info(f"未处理的UID: {unprocessed_uids}")
            
            if not unprocessed_uids:
                logger.info("所有UID已处理")
                return None
            
            # 获取未处理数据的完整内容
            try:
                unprocessed_data = mongodb_connector.get_data_by_uids(unprocessed_uids)
                if not unprocessed_data:
                    logger.warning("未能获取未处理数据的内容")
                    return None
                    
                # 标记为已处理
                for uid in unprocessed_uids:
                    if uid is not None:  # 确保不添加None作为UID
                        uid_tracker.add_uid(uid, self.task_id)
                        
                # 如果unprocessed_data不是列表，将其转换为列表
                if not isinstance(unprocessed_data, list):
                    unprocessed_data = [unprocessed_data]
                    
                return unprocessed_data
            except Exception as e:
                logger.error(f"获取或处理未处理数据时出错: {str(e)}")
                return None
            
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
            task_name = self.task_config.get('name', '特别关注')
            
            # 将原始数据转换为JSON字符串
            raw_content_json = json.dumps(raw_data_list, ensure_ascii=False, indent=2)
            
            # 准备突发新闻风格的提示词
            prompt = f"""帮我分析这些推文，是否是币圈发突发：{raw_content_json}。如果是请直接输出新闻报道内容，不要包含任何前缀说明。如果内容不是突发新闻，请在报道开头添加[警告:内容不是突发新闻]标签。
"""
            
            # 使用新的generate_news_from_tweet函数生成新闻
            processed_content = generate_news_from_tweet(
                prompt=prompt
            )
            return processed_content
                
        except Exception as e:
            logger.error(f"新闻验证和整理异常: {str(e)}", exc_info=True)
            return None
    
    def _generate_video(self, content):
        """生成视频
        
        Args:
            content: 用于生成视频的内容
            
        Returns:
            视频生成结果
        """
        try:
            # 调用D-ID API生成视频
            logger.info(f"开始为时间线任务生成视频: {self.task_id}")
            video_result = create_video(content)
            
            # 处理视频生成结果
            if video_result and video_result.get('status', '') == 'created':
                # 提取关键信息
                d_id_video_id = video_result.get('video_id')
                status = video_result.get('status', 'created')
                created_at = video_result.get('created_at')
                
                # 保存视频信息到任务记录
                video_info = {
                    "task_id": self.task_id,
                    "d_id_video_id": d_id_video_id,
                    "status": status,
                    "created_at": created_at
                }
                
                # 将视频信息保存到MongoDB
                try:
                    collection = self.db['video_tasks']
                    collection.update_one(
                        {"task_id": self.task_id},
                        {"$set": video_info},
                        upsert=True
                    )
                    logger.info(f"视频信息已保存到数据库: task_id={self.task_id}, d_id_video_id={d_id_video_id}")
                except Exception as db_err:
                    logger.error(f"保存视频信息到数据库失败: {str(db_err)}")
                
                logger.info(f"时间线视频生成成功: task_id={self.task_id}, d_id_video_id={d_id_video_id}, status={status}")
                
                # 返回视频信息
                return {
                    "task_id": self.task_id,
                    "d_id_video_id": d_id_video_id,
                    "status": status,
                    "message": "视频生成任务已提交"
                }
            else:
                # 记录失败信息
                error_msg = video_result.get('error', '未知错误') if video_result else '无返回结果'
                logger.warning(f"时间线视频生成失败: {error_msg}")
                
                # 记录失败信息到数据库
                try:
                    collection = self.db['video_tasks']
                    collection.update_one(
                        {"task_id": self.task_id},
                        {"$set": {
                            "task_id": self.task_id,
                            "status": "error",
                            "error": error_msg,
                            "updated_at": int(time.time())
                        }},
                        upsert=True
                    )
                except Exception as db_err:
                    logger.error(f"保存视频错误信息到数据库失败: {str(db_err)}")
                
                # 失败时返回错误信息
                return {
                    "task_id": self.task_id,
                    "status": "error",
                    "error": error_msg,
                    "message": "视频生成失败"
                }
        except Exception as e:
            logger.error(f"生成视频异常: {str(e)}")
            return {
                "task_id": self.task_id,
                "status": "error",
                "error": str(e),
                "message": "视频生成异常"
            }

    def stop(self):
        """停止任务"""
        if not self.running:
            return
            
        logger.info(f"停止特别关注任务: {self.task_id}")
        self.running = False
        
        # 等待轮询线程结束
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

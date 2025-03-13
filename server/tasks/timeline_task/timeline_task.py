#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import asyncio
import threading
import time
import uuid
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
from server.actions.text2v import create_video

# 导入推文转新闻功能
from server.actions.tweet2news import generate_news_from_tweet

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
        
        # 如果没有原始数据，直接跳过内容处理和视频生成
        if not raw_items:
            logger.info("没有要处理的数据，跳过内容处理和视频生成")
            return
            
        # 内容处理和汇总生成
        summary_content = None
        if "content_processor" in self.components:
            # 直接将整个字典列表传递给处理方法
            summary_content = self._process_all_items(raw_items)
        
        # 只有在成功生成新闻内容后，才生成视频
        if summary_content and "video_generator" in self.components:
            logger.info("新闻内容生成成功，开始生成视频")
            self._generate_video(summary_content)  # 只传递一条汇总内容
        
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
                "createdAt": {"$gte": time_threshold}
            }
            
            # 获取MongoDB中的实际集合名称
            collection_name = os.getenv('MONGODB_COLLECTION', 'twitterTweets')
            
            # 从MongoDB中查询数据，按创建时间降序排序
            recent_data = list(mongodb_connector.db[collection_name].find(query).sort("createdAt", -1))
            
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
            
            # 准备社交媒体汇总风格的提示词
            prompt = f"""Summarize the following tweet content into a social media hot topic summary, highlighting key viewpoints and public reactions：

                    {content_json}

                    Please directly output the news report content without any prefix explanation.The generated content should be approximately 100 words,in the style of a news manuscript,to be used for broadcast news.
                    """
            
            # 调用AI接口，生成新闻
            logger.info(f"开始为时间线任务生成新闻: {self.task_id}")
            news_content = generate_news_from_tweet(prompt)
            return news_content
                
        except Exception as e:
            logger.error(f"AI生成汇总异常: {str(e)}")
            # 如果发生异常，尝试返回原始数据的JSON字符串
            try:
                return json.dumps(raw_items, ensure_ascii=False, indent=2)
            except:
                return "处理数据时发生错误"
            
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
            if video_result and video_result.get('success'):
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
                
                # 将视频信息保存到MongoDB，使用d_id_video_id作为唯一标识符
                try:
                    collection = mongodb_connector.db['video_tasks']
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
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
                    # 注意：这里需要mongodb_connector，而不是self.db
                    collection = mongodb_connector.db['video_tasks']
                    
                    # 如果无法获取d_id_video_id（失败的情况），则生成一个唯一标识
                    # 这样可以保证错误记录也不会覆盖现有记录
                    error_record_id = str(uuid.uuid4())
                    
                    collection.update_one(
                        {"error_id": error_record_id},
                        {"$set": {
                            "task_id": self.task_id,
                            "error_id": error_record_id,
                            "status": "error",
                            "error": error_msg
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
            
        logger.info(f"停止时间线任务: {self.task_id}")
        self.running = False
        
        # 等待轮询线程结束
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

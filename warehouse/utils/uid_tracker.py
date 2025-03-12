#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import List, Optional

# 设置日志
logger = logging.getLogger(__name__)

class DBUIDTracker:
    """基于数据库的UID跟踪器，用于记录已处理的UID
    
    此跟踪器将处理状态存储在MongoDB中，确保服务重启后数据不会丢失，
    并支持多个任务分别跟踪各自的处理状态。
    """
    
    def __init__(self, collection_name="processed_uids", max_size=1000):
        """初始化跟踪器
        
        Args:
            collection_name: MongoDB中用于存储处理状态的集合名称
            max_size: 每个任务最多保存的记录数量
        """
        from warehouse.storage.mongodb.connector import mongodb_connector
        self.db = mongodb_connector
        self.collection_name = collection_name
        self.max_size = max_size
        self._ensure_collection()
    
    def _ensure_collection(self):
        """确保集合存在"""
        if self.collection_name not in self.db.db.list_collection_names():
            self.db.db.create_collection(self.collection_name)
            # 创建索引以提高查询性能
            # 不将_id和task_id设置为联合唯一索引，因为_id已经是唯一的
            self.db.db[self.collection_name].create_index([("task_id", 1)])
            self.db.db[self.collection_name].create_index([("task_id", 1), ("processed_at", 1)])
    
    def add_uid(self, uid: str, task_id: str):
        """添加一个已处理的UID
        
        Args:
            uid: 要标记为已处理的UID
            task_id: 处理该UID的任务ID
        """
        # 确保uid不为None且task_id不为空
        if uid is None:
            logger.warning(f"尝试添加None作为UID到任务{task_id}，已跳过")
            return
            
        if not task_id:
            logger.warning(f"任务ID为空，无法添加UID: {uid}")
            return
            
        try:
            # 先检查记录是否存在
            existing = self.db.db[self.collection_name].find_one({"_id": uid})
            
            if existing:
                # 如果记录已存在，只更新processed_at和task_id
                self.db.db[self.collection_name].update_one(
                    {"_id": uid},
                    {"$set": {"processed_at": datetime.now(), "task_id": task_id}}
                )
            else:
                # 如果记录不存在，则创建新记录
                self.db.db[self.collection_name].insert_one({
                    "_id": uid,
                    "task_id": task_id,
                    "processed_at": datetime.now()
                })
            
            # 保持集合大小在限制内
            self._trim_collection(task_id)
        
        except Exception as e:
            logger.error(f"添加UID到数据库时出错: {str(e)}")
    
    def _trim_collection(self, task_id: str):
        """修剪集合大小，删除最旧的记录
        
        Args:
            task_id: 任务ID
        """
        try:
            # 计算当前记录数
            count = self.db.db[self.collection_name].count_documents({"task_id": task_id})
            
            if count > self.max_size:
                # 找出最旧的记录
                oldest = list(self.db.db[self.collection_name].find(
                    {"task_id": task_id}, 
                    sort=[("processed_at", 1)]
                ).limit(count - self.max_size))
                
                if oldest:
                    # 批量删除
                    oldest_ids = [doc["_id"] for doc in oldest if "_id" in doc]
                    if oldest_ids:
                        self.db.db[self.collection_name].delete_many({"_id": {"$in": oldest_ids}})
                        logger.debug(f"已从{task_id}任务中删除{len(oldest_ids)}条旧记录")
        except Exception as e:
            logger.error(f"修剪集合大小时出错: {str(e)}")
    
    def is_processed(self, uid: str, task_id: str) -> bool:
        """检查UID是否已被特定任务处理
        
        Args:
            uid: 要检查的UID
            task_id: 任务ID
            
        Returns:
            如果UID已被处理则返回True，否则返回False
        """
        if uid is None or not task_id:
            return False
            
        try:
            return self.db.db[self.collection_name].find_one({
                "_id": uid,
                "task_id": task_id
            }) is not None
        except Exception as e:
            logger.error(f"检查UID是否处理时出错: {str(e)}")
            return False
    
    def get_unprocessed(self, uids: List[str], task_id: str) -> List[str]:
        """获取未被特定任务处理的UIDs
        
        Args:
            uids: UID列表
            task_id: 任务ID
            
        Returns:
            未处理的UID列表
        """
        if not uids or not task_id:
            return []
            
        # 过滤掉None值
        uids = [uid for uid in uids if uid is not None]
        if not uids:
            return []
            
        try:
            # 查找已处理的UID
            processed_docs = list(self.db.db[self.collection_name].find(
                {"_id": {"$in": uids}, "task_id": task_id},
                {"_id": 1}
            ))
            
            # 提取已处理的UID
            processed_uids = set(doc["_id"] for doc in processed_docs if "_id" in doc)
            
            # 返回未处理的UID
            return [uid for uid in uids if uid not in processed_uids]
        except Exception as e:
            logger.error(f"获取未处理UIDs时出错: {str(e)}")
            return uids
    
    def get_last_processed_uid(self, task_id: str) -> Optional[str]:
        """获取任务最后处理的UID
        
        Args:
            task_id: 任务ID
            
        Returns:
            最后处理的UID，如果没有则返回None
        """
        if not task_id:
            return None
            
        try:
            last_record = self.db.db[self.collection_name].find_one(
                {"task_id": task_id},
                sort=[("processed_at", -1)]
            )
            
            return last_record["_id"] if last_record else None
        except Exception as e:
            logger.error(f"获取最后处理的UID时出错: {str(e)}")
            return None
    
    def clear_task_records(self, task_id: str):
        """清除任务的所有记录
        
        Args:
            task_id: 任务ID
        """
        try:
            result = self.db.db[self.collection_name].delete_many({"task_id": task_id})
            logger.info(f"已清除任务{task_id}的{result.deleted_count}条记录")
        except Exception as e:
            logger.error(f"清除任务记录时出错: {str(e)}")

# 全局实例，方便直接导入使用
uid_tracker = DBUIDTracker()

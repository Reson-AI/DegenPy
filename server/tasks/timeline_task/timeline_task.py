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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("timeline_task")

# Import database connectors
from warehouse.api import get_data_by_uids
from warehouse.storage.mongodb.connector import mongodb_connector
from warehouse.utils.uid_tracker import uid_tracker

# Import video generation service
from server.actions.text2v import create_video

# Import tweet to news conversion functionality
from server.actions.tweet2news import generate_news_from_tweet

class TimelineTask:
    """Timeline task executor, responsible for periodically retrieving content and generating summary videos"""
    
    def __init__(self, task_config, agent_config):
        """
        Initialize task executor
        
        Args:
            task_config: Task configuration
            agent_config: Agent configuration
        """
        self.task_config = task_config
        self.agent_config = agent_config
        self.task_id = task_config.get('id', 'unknown_task')
        self.running = False
        self.poll_thread = None
        
        # Load components
        self.components = task_config.get('components', [])
        logger.info(f"Timeline task {self.task_id} using components: {', '.join(self.components)}")
        
        # Get batch size configuration
        data_source = self.task_config.get('data_source', {})
        self.batch_size = data_source.get('batch_size', 10)
        self.time_window = data_source.get('time_window', 1800)  # Default 30 minutes
        
        logger.info(f"Timeline task {self.task_id} initialization complete, batch size: {self.batch_size}, time window: {self.time_window} seconds")
    
    def start(self):
        """Start the task"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"Starting timeline task: {self.task_id}")
        
        # Get polling configuration
        poll_config = self.task_config.get('schedule', {})
        if isinstance(poll_config, str) or not poll_config:
            # Simplified configuration, default execution every 30 minutes
            poll_config = {
                'type': 'interval',
                'minutes': 30
            }
        
        # 启动轮询线程
        self._start_polling(poll_config)
    
    def _start_polling(self, poll_config: Dict[str, Any]):
        """Start polling thread
        
        Args:
            poll_config: Polling configuration, including type and time interval
        """
        poll_type = poll_config.get('type', 'interval')
        
        if poll_type == 'interval':
            # Calculate interval in seconds
            seconds = poll_config.get('seconds', 0)
            minutes = poll_config.get('minutes', 0)
            hours = poll_config.get('hours', 0)
            
            interval_seconds = seconds + minutes * 60 + hours * 3600
            if interval_seconds <= 0:
                interval_seconds = 300  # Default 5 minutes
            
            logger.info(f"Timeline task {self.task_id} starting polling, interval {interval_seconds} seconds")
            
            # Start polling thread
            def poll_thread_func():
                logger.info(f"Timeline task {self.task_id} polling thread started")
                
                # Execute immediately once
                self._execute_and_handle_exceptions()
                
                while self.running:
                    time.sleep(interval_seconds)
                    if not self.running:
                        break
                    
                    self._execute_and_handle_exceptions()
                
                logger.info(f"Timeline task {self.task_id} polling thread stopped")
            
            self.poll_thread = threading.Thread(
                target=poll_thread_func,
                name=f"Poll-{self.task_id}",
                daemon=True
            )
            self.poll_thread.start()
        else:
            logger.error(f"Unsupported polling type: {poll_type}")
    
    def _execute_and_handle_exceptions(self):
        """Execute task and handle exceptions"""
        try:
            # Check for new data and execute task
            asyncio.run(self.check_and_execute())
        except Exception as e:
            logger.error(f"Timeline task {self.task_id} execution error: {str(e)}", exc_info=True)
            
    async def check_and_execute(self):
        """Check if there is new data and execute the task"""
        logger.info(f"Checking timeline task for new data: {self.task_id}")
        
        # Get new data within the recent time window
        data = await self._get_new_data()
        if not data:
            logger.info(f"No new timeline data: {self.task_id}")
            return
        
        # Execute task processing
        self.execute(data)
    
    def execute(self, data=None):
        """
        Execute task
        
        Args:
            data: Data to be processed
        """
        logger.info(f"Executing timeline task: {self.task_id}")
        
        if not data:
            logger.warning(f"No data to process: {self.task_id}")
            return
            
        # Ensure data is in list form
        items_list = data if isinstance(data, list) else [data]
        
        # If there is no data, return directly
        if not items_list:
            logger.warning(f"No data items to process: {self.task_id}")
            return
            
        # Use the original data items list directly
        raw_items = items_list
        
        # If there is no raw data, skip content processing and video generation
        if not raw_items:
            logger.info("No data to process, skipping content processing and video generation")
            return
            
        # Content processing and summary generation
        summary_content = None
        if "content_processor" in self.components:
            # Pass the entire dictionary list directly to the processing method
            summary_content = self._process_all_items(raw_items)
        
        # Only generate video after successfully generating news content
        if summary_content and "video_generator" in self.components:
            logger.info("News content generated successfully, starting video generation")
            self._generate_video(summary_content)  # Only pass one summary content
        
    async def _get_new_data(self):
        """
        Get new data
        
        Returns:
            List of new data
        """
        try:
            # Get time window configuration
            time_threshold = datetime.now() - timedelta(seconds=self.time_window)
            
            # Query data within the recent time window
            query = {
                "createdAt": {"$gte": time_threshold}
            }
            
            # Get the actual collection name in MongoDB
            collection_name = os.getenv('MONGODB_COLLECTION', 'twitterTweets')
            
            # 从MongoDB中查询数据，按创建时间降序排序
            recent_data = list(mongodb_connector.db[collection_name].find(query).sort("createdAt", -1))
            
            if not recent_data:
                return None
            
            # Extract UID list
            uids = [item.get("_id") for item in recent_data if "_id" in item]
            
            # Use UID tracker to filter out unprocessed UIDs
            unprocessed_uids = uid_tracker.get_unprocessed(uids, self.task_id)
            
            if not unprocessed_uids:
                return None
            
            # Get the complete content of unprocessed data
            unprocessed_data = get_data_by_uids(unprocessed_uids)
            
            # Mark as processed
            for uid in unprocessed_uids:
                uid_tracker.add_uid(uid, self.task_id)
            
            return unprocessed_data
            
        except Exception as e:
            logger.error(f"Failed to get new data: {str(e)}", exc_info=True)
            return None
            
    def _process_all_items(self, raw_items):
        """
        Process all data items at once
        
        Args:
            raw_items: List of raw data items (dictionary format)
            
        Returns:
            Processed summary content
        """
        if not raw_items:
            return ""
            
        try:
            # Prepare prompt
            task_name = self.task_config.get('name', 'Timeline Summary')
            
            # Add ID for each item (if not present)
            for i, item in enumerate(raw_items):
                if "id" not in item:
                    item["id"] = i + 1
                
            # Convert dictionary list to JSON string
            content_json = json.dumps(raw_items, ensure_ascii=False, indent=2)
            
            # Prepare social media summary style prompt
            prompt = f"""Summarize the following tweet content into a social media hot topic summary, highlighting key viewpoints and public reactions：

                    {content_json}

                    Please directly output the news report content without any prefix explanation.The generated content should be approximately 100 words,in the style of a news manuscript,to be used for broadcast news.
                    """
            
            # Call AI interface to generate news
            logger.info(f"Starting to generate news for timeline task: {self.task_id}")
            news_content = generate_news_from_tweet(prompt)
            return news_content
                
        except Exception as e:
            logger.error(f"AI summary generation exception: {str(e)}")
            # If an exception occurs, try to return the JSON string of the original data
            try:
                return json.dumps(raw_items, ensure_ascii=False, indent=2)
            except:
                return "Error occurred while processing data"
            
    def _generate_video(self, content):
        """Generate video
        
        Args:
            content: Content used to generate the video
            
        Returns:
            Video generation result
        """
        try:
            # Call D-ID API to generate video
            logger.info(f"Starting to generate video for timeline task: {self.task_id}")
            video_result = create_video(content)
            
            # Process video generation result
            if video_result and video_result.get('success'):
                # Extract key information
                d_id_video_id = video_result.get('video_id')
                status = video_result.get('status', 'created')
                created_at = video_result.get('created_at')
                
                # Save video information to task record
                video_info = {
                    "task_id": self.task_id,
                    "d_id_video_id": d_id_video_id,
                    "status": status,
                    "created_at": created_at
                }
                
                # Save video information to MongoDB, using d_id_video_id as a unique identifier
                try:
                    collection = mongodb_connector.db['video_tasks']
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
                        {"$set": video_info},
                        upsert=True
                    )
                    logger.info(f"Video information saved to database: task_id={self.task_id}, d_id_video_id={d_id_video_id}")
                except Exception as db_err:
                    logger.error(f"Failed to save video information to database: {str(db_err)}")
                
                logger.info(f"Timeline video generated successfully: task_id={self.task_id}, d_id_video_id={d_id_video_id}, status={status}")
                
                # Return video information
                return {
                    "task_id": self.task_id,
                    "d_id_video_id": d_id_video_id,
                    "status": status,
                    "message": "Video generation task submitted"
                }
            else:
                # 记录失败信息
                error_msg = video_result.get('error', 'Unknown error') if video_result else 'No result returned'
                logger.warning(f"Timeline video generation failed: {error_msg}")
                
                # Record failure information to database
                try:
                    # Note: mongodb_connector is needed here, not self.db
                    collection = mongodb_connector.db['video_tasks']
                    
                    # If d_id_video_id cannot be obtained (failure case), generate a unique identifier
                    # This ensures that error records will not overwrite existing records
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
                    logger.error(f"Failed to save video error information to database: {str(db_err)}")
                
                # Return error information on failure
                return {
                    "task_id": self.task_id,
                    "status": "error",
                    "error": error_msg,
                    "message": "Video generation failed"
                }
        except Exception as e:
            logger.error(f"Video generation exception: {str(e)}")
            return {
                "task_id": self.task_id,
                "status": "error",
                "error": str(e),
                "message": "Video generation exception"
            }
    
    def stop(self):
        """Stop the task"""
        if not self.running:
            return
            
        logger.info(f"Stopping timeline task: {self.task_id}")
        self.running = False
        
        # Wait for polling thread to end
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=1.0)

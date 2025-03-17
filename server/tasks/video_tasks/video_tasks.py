#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import traceback
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import MongoDB connection
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError

# Import MongoDB connector
from warehouse.storage.mongodb.connector import mongodb_connector

# Import D-ID API functions
from server.actions.text2v import get_video_status

# Import TikTok API functions
from server.actions.tiktok import publish_to_tiktok, check_publish_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('video_tasks')

class VideoTaskMonitor:
    """Video Task Monitoring Class
    
    Responsible for periodically monitoring the status of video generation tasks and updating to the database
    Automatically calls the TikTok API to publish videos when completed
    """
    
    def __init__(self, task_config, agent_config):
        """Initialize the monitor"""
        self.task_config = task_config
        self.agent_config = agent_config
        self.task_id = task_config.get('id', 'unknown_task')
        self.max_check_attempts = 30  # Maximum number of check attempts
        self.running = False
        self.poll_thread = None
    
    def start(self) -> Dict[str, Any]:
        """Execute task monitoring
        
        Returns:
            Dictionary containing task execution results
        """
        # Check if already running
        if self.running:
            return {"success": True, "message": f"Video task monitor {self.task_id} is already running"}
        
        self.running = True
        
        # Get polling configuration
        poll_config = self.task_config.get('schedule', {})
        if isinstance(poll_config, str) or not poll_config:
            # Simplified configuration, default to execute once every 1 minute
            poll_config = {
                'type': 'interval',
                'minutes': 1
            }
        
        # Start polling thread
        self._start_polling(poll_config)
        logger.info(f"Starting video task monitoring: {self.task_id}")
        
        return {"success": True, "message": f"Video task monitor {self.task_id} has been started"}
        
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
                interval_seconds = 60  # Default 1 minute
            
            logger.info(f"Video task monitor {self.task_id} starting polling with interval of {interval_seconds} seconds")
            
            # Start polling thread
            def poll_thread_func():
                logger.info(f"Video task monitor {self.task_id} polling thread started")
                
                # Execute immediately once
                self._execute_and_handle_exceptions()
                
                while self.running:
                    time.sleep(interval_seconds)
                    if not self.running:
                        break
                    
                    self._execute_and_handle_exceptions()
                
                logger.info(f"Video task monitor {self.task_id} polling thread stopped")
            
            self.poll_thread = threading.Thread(
                target=poll_thread_func,
                name=f"VideoTaskPoll-{self.task_id}",
                daemon=True
            )
            self.poll_thread.start()
        else:
            logger.error(f"Unsupported polling type: {poll_type}")
        
    def _execute_and_handle_exceptions(self):
        """Execute tasks and handle exceptions"""
        try:
            # Get video tasks that need status updates
            pending_tasks = self._get_pending_tasks()
            
            if not pending_tasks:
                logger.info("No video tasks need updating")
                return
            
            # Update task status
            updated_count = 0
            completed_count = 0
            for task in pending_tasks:
                result = self._update_task_status(task)
                if result["updated"]:
                    updated_count += 1
                    if result["completed"]:
                        completed_count += 1
            
            logger.info(f"Video task monitoring completed: Updated {updated_count} video task statuses, completed and published {completed_count} videos")
            
        except Exception as e:
            error_msg = f"Video task monitoring exception: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
    
    def _get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get video tasks that need status updates
        
        Returns:
            List of tasks that need updating
        """
        try:
            collection = mongodb_connector.db['video_tasks']
            
            # Query condition: only get tasks with 'created' and 'started' status
            query = {
                "status": {"$in": ["created", "started"]}
            }
            
            # Sort by creation time, prioritize processing earlier tasks
            tasks = list(collection.find(query).sort("created_at", DESCENDING))
            
            logger.info(f"Found {len(tasks)} video tasks that need status updates")
            return tasks
            
        except PyMongoError as e:
            logger.error(f"Exception getting pending video tasks: {str(e)}")
            return []
    
    def _update_task_status(self, task: Dict[str, Any]) -> Dict[str, bool]:
        """Update the status of a single task
        
        Args:
            task: Task information to update
            
        Returns:
            Dictionary containing update status, including updated and completed flags
        """
        d_id_video_id = task.get("d_id_video_id")
        task_id = task.get("task_id", "unknown")
        
        result = {"updated": False, "completed": False}
        
        if not d_id_video_id:
            logger.warning(f"Task missing required d_id_video_id: {task}")
            return result
        
        try:
            # Call D-ID API to get video status
            api_result = get_video_status(d_id_video_id)
            
            # Current attempt count
            current_attempt = task.get("attempt", 0) + 1
            
            # Map D-ID API status to our simplified status
            api_status = api_result.get("status", "unknown")
            
            # Simplified status mapping
            if api_status in ["done", "ready", "completed"]:
                mapped_status = "done"
            elif api_status in ["created", "pending"]:
                mapped_status = "created"
            elif api_status in ["processing", "in_progress"]:
                mapped_status = "started"
            else:
                # Error status remains unchanged
                mapped_status = api_status
            
            # Update data
            update_data = {
                "status": mapped_status,# Save original status for debugging
                "attempt": current_attempt
            }
            
            # If there is a result URL, add it to the update data
            if "result_url" in api_result:
                update_data["result_url"] = api_result["result_url"]
            
            # If there is error information, add it to the update data
            if "error" in api_result:
                update_data["error"] = api_result["error"]
            
            # Update task status in MongoDB, using d_id_video_id as the primary key
            collection = mongodb_connector.db['video_tasks']
            collection.update_one(
                {"d_id_video_id": d_id_video_id},
                {"$set": update_data}
            )
            
            result["updated"] = True
            
            # Check if completed, if completed then call TikTok interface
            if mapped_status == "done" and "result_url" in update_data:
                result_url = update_data["result_url"]
                logger.info(f"Video generation completed, preparing to publish to TikTok: ID={task_id}, URL={result_url}")
                # Proxy the URL, Replace the domain name
                result_url = result_url.replace("https://d-id-talks-prod.s3.us-west-2.amazonaws.com", "https://tbt.kip.pro")
                
                # Try to publish to TikTok
                try:
                    # Get task content as title
                    caption = task.get("title", f"Video {task_id}")
                    
                    # Get any related tags
                    raw_tags = task.get("tags", ["AIGenerated", "News"])
                    hashtags = [f"#{tag}" if not tag.startswith('#') else tag for tag in raw_tags]
                    
                    # Call TikTok publishing interface
                    success, publish_id = publish_to_tiktok(
                        video_url=result_url,
                        caption=caption,
                        hashtags=hashtags
                    )
                    
                    # Update publishing results
                    publish_update = {
                        "tiktok_published": success,
                        "tiktok_publish_id": publish_id if success else None,
                        "tiktok_status": None
                    }
                    
                    # If publishing was successful, check the status
                    if success and publish_id:
                        # Check the publish status
                        status_success, status = check_publish_status(publish_id)
                        if status_success:
                            publish_update["tiktok_status"] = status
                            logger.info(f"TikTok publish status: {status}")
                    
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
                        {"$set": publish_update}
                    )
                    
                    logger.info(f"Video successfully published to TikTok: ID={task_id}")
                    result["completed"] = True
                    
                except Exception as pub_err:
                    logger.error(f"Failed to publish video to TikTok: ID={task_id}, Error={str(pub_err)}")
                    collection.update_one(
                        {"d_id_video_id": d_id_video_id},
                        {"$set": {
                            "tiktok_published": False,
                            "tiktok_error": str(pub_err)
                        }}
                    )
            elif mapped_status == "done" and "result_url" not in update_data:
                logger.warning(f"Video marked as completed but has no URL: ID={task_id}")
            elif current_attempt >= self.max_check_attempts:
                # Exceeded maximum number of attempts, mark as timeout
                collection.update_one(
                    {"d_id_video_id": d_id_video_id},
                    {"$set": {"status": "timeout"}}
                )
                logger.warning(f"Video generation timeout: ID={task_id}, reached maximum attempt count {self.max_check_attempts}")
            else:
                logger.info(f"Video status updated: ID={task_id}, Status={mapped_status}, Attempt={current_attempt}/{self.max_check_attempts}")
            
            return result
            
        except Exception as e:
            logger.error(f"Exception updating video task status: d_id_video_id={d_id_video_id}, error={str(e)}")
            return result


def stop(task_id=None):
    """Stop video task monitoring"""
    # This is just an interface placeholder, needs to be implemented in actual use
    logger.info(f"Stopping video task monitoring: {task_id if task_id else 'all'}")
    return {"success": True, "message": "Video task monitoring has been stopped"}

def execute(task_config=None, agent_config=None):
    """Execute video task monitoring
    
    Args:
        task_config: Task configuration, if None then use default configuration
        agent_config: Agent configuration, if None then use default configuration
        
    Returns:
        Dictionary containing task execution results
    """
    # If no configuration is provided, use default configuration
    if task_config is None:
        task_config = {
            'id': 'video_task_monitor',
            'name': 'Video Task Monitor',
            'schedule': {
                'type': 'interval',
                'minutes': 1
            }
        }
    
    if agent_config is None:
        agent_config = {}
    
    monitor = VideoTaskMonitor(task_config, agent_config)
    return monitor.start()


if __name__ == "__main__":
    # For testing
    result = execute()
    print(result)
    
    # Keep the main thread running, allowing daemon threads to execute
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Received interrupt signal, program exiting")

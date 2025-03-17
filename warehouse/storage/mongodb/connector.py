#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import uuid
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime

# Removed Redis and message queue dependencies to improve connector reusability

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongodb_connector")

# Load environment variables
# Force reload of .env file to ensure the latest configuration is used
load_dotenv(override=True)

class MongoDBConnector:
    """MongoDB Connector"""
    
    def __init__(self, db_name=None, collection_name=None):
        """Initialize MongoDB Connector"""
        # Use connection string from environment variables, no default value provided
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("Environment variable MONGODB_CONNECTION_STRING not set, please configure in .env file")
        self.client = MongoClient(connection_string)
        
        # Use database and collection names from environment variables, no default values provided
        db_name = db_name or os.getenv('MONGODB_DATABASE')
        if not db_name:
            raise ValueError("Environment variable MONGODB_DATABASE not set, please configure in .env file")
            
        collection_name = collection_name or os.getenv('MONGODB_COLLECTION')
        if not collection_name:
            raise ValueError("Environment variable MONGODB_COLLECTION not set, please configure in .env file")
        
        # Use the specified database name directly, without case processing
        self.db = self.client[db_name]
                
        self.collection = self.db[collection_name]
        
        # Removed Redis and message queue initialization to improve connector reusability
        
        logger.info(f"MongoDB Connector initialized: {db_name}, Collection: {collection_name}")
        
    def store_data(self, content, tags=None, uid=None):
        """Store data in MongoDB
        
        Args:
            content: Content dictionary
            tags: Tags array (optional)
            uid: Content UUID (optional, will be auto-generated if not provided)
            
        Returns:
            The stored document on success
        """
        try:
            # Auto-generate UUID if not provided
            if not uid:
                uid = str(uuid.uuid4())
            
            # Ensure content is a dictionary
            if not isinstance(content, dict):
                try:
                    # Try to parse string as JSON
                    if isinstance(content, str):
                        content = json.loads(content)
                    else:
                        # If not a dictionary or string, create a default content dictionary
                        logger.warning(f"Content is not a dictionary: {type(content)}, creating default content")
                        content = {"text": str(content)}
                except json.JSONDecodeError:
                    # If JSON parsing fails, create default content
                    content = {"text": content if isinstance(content, str) else str(content)}
            
            # Ensure tags is an array
            if tags is None:
                tags = []
            elif not isinstance(tags, list):
                logger.warning(f"Tags is not an array: {type(tags)}, using empty array instead")
                tags = []
            
            # Create document
            document = {
                '_id': uid,  # Use UUID as MongoDB's _id field
                'content': content,  # Store the complete content dictionary
                'tags': tags,
                'createdAt': datetime.now()  # Store creation timestamp
            }
            result = self.collection.insert_one(document)
            
            # Return the complete document
            return {
                'uuid': uid,
                'content': content,
                'tags': tags
            }
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")
            return None
            
    def get_data_by_uids(self, uuids):
        """Get data by one or more UUIDs
        
        Args:
            uuids: Single UUID or list of UUIDs
            
        Returns:
            List of data when uuids is a list, single data object or None when uuids is a single UUID
        """
        try:
            # Handle single UUID case
            single_uuid = False
            if not isinstance(uuids, list):
                uuids = [uuids]
                single_uuid = True
            
            # Query using _id field, as we now use UUID as _id
            documents = list(self.collection.find({'_id': {'$in': uuids}}))
            
            # Format results
            results = [{
                'uuid': doc['_id'],
                'content': doc['content'],
                'tags': doc.get('tags', [])
            } for doc in documents]
            
            # If single UUID, return single result or None
            if single_uuid:
                return results[0] if results else None
            
            # Otherwise return the list
            return results
        except Exception as e:
            logger.error(f"Error retrieving data by UID: {str(e)}")
            return [] if not single_uuid else None

# Create MongoDB connector instance
mongodb_connector = MongoDBConnector()

def get_connector():
    """Get MongoDB connector instance"""
    return mongodb_connector

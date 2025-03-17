#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from dotenv import load_dotenv, set_key
from warehouse.storage.mongodb.connector import MongoDBConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_init")

def init_db_env():
    """Initialize database environment variables"""
    # Load current environment variables, force override existing environment variables
    load_dotenv(override=True)
    
    # Ensure .env file exists
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            pass
    
    # Set database type
    set_key(env_file, "DB_TYPE", "mongodb")
    logger.info("Database type set to: mongodb")
    
    # Read MongoDB environment variables from .env file in the root directory
    # No longer set default values, completely rely on the configuration in the .env file
    logger.info("Reading MongoDB configuration from .env file")
    
    # Check if necessary environment variables exist
    if not os.getenv("MONGODB_CONNECTION_STRING"):
        logger.warning("MONGODB_CONNECTION_STRING environment variable not set, please configure in .env file")
    if not os.getenv("MONGODB_DATABASE"):
        logger.warning("MONGODB_DATABASE environment variable not set, please configure in .env file")
    if not os.getenv("MONGODB_COLLECTION"):
        logger.warning("MONGODB_COLLECTION environment variable not set, please configure in .env file")
        
    logger.info("MongoDB environment variables set")

def initialize_db():
    connector = MongoDBConnector()
    # Create indexes
    connector.collection.create_index('uuid', unique=True)
    connector.collection.create_index('createdAt')
    connector.collection.create_index('tag')

if __name__ == "__main__":
    import sys
    
    # Initialize database environment
    init_db_env()
    
    # Initialize database
    initialize_db()

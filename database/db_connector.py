# database/db_connector.py
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import config

logger = logging.getLogger(__name__)

def get_db_connection():
    """Connect to the PostgreSQL database"""
    try:
        # First try using DATABASE_URL if available
        if config.DATABASE_URL:
            logger.info("Connecting to database using DATABASE_URL")
            conn = psycopg2.connect(config.DATABASE_URL)
            return conn
        
        # Fall back to individual parameters
        logger.info("Connecting to database using individual parameters")
        logger.info(f"Host: {config.DB_HOST}, Port: {config.DB_PORT}, DB: {config.DB_NAME}")
        conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

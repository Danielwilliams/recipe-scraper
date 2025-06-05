#!/usr/bin/env python
# test_db_connection.py - Test database connection and configuration

import sys
import os
import logging
from datetime import datetime
import json
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('test_db_connection')

def test_connection():
    """Test the database connection and print configuration"""
    try:
        # Import config and db_connector
        import config
        from database.db_connector import get_db_connection
        
        # Print database configuration
        logger.info("Database Configuration:")
        logger.info(f"DATABASE_URL: {config.DATABASE_URL}")
        logger.info(f"DB_NAME: {config.DB_NAME}")
        logger.info(f"DB_USER: {config.DB_USER}")
        logger.info(f"DB_HOST: {config.DB_HOST}")
        logger.info(f"DB_PORT: {config.DB_PORT}")
        
        # Test the connection
        logger.info("Testing database connection...")
        conn = get_db_connection()
        
        with conn.cursor() as cursor:
            # Check database info
            cursor.execute("SELECT current_database(), current_user, version()")
            db_info = cursor.fetchone()
            logger.info(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
            logger.info(f"PostgreSQL version: {db_info[2]}")
            
            # Check scraped_recipes table structure
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'scraped_recipes'
                ORDER BY ordinal_position
            """)
            
            columns = cursor.fetchall()
            logger.info("Table structure for 'scraped_recipes':")
            for column in columns:
                logger.info(f"  {column[0]}: {column[1]}")
            
            # Count recipes
            cursor.execute("SELECT COUNT(*) FROM scraped_recipes")
            count = cursor.fetchone()[0]
            logger.info(f"Found {count} recipes in the database")
            
            # Check for duplicate IDs
            cursor.execute("""
                SELECT id, COUNT(*) 
                FROM scraped_recipes 
                GROUP BY id 
                HAVING COUNT(*) > 1
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                logger.warning(f"Found {len(duplicates)} duplicate IDs!")
                for dup in duplicates:
                    logger.warning(f"  ID {dup[0]} appears {dup[1]} times")
            else:
                logger.info("No duplicate IDs found")
        
        logger.info("✅ Database connection test successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    test_connection()
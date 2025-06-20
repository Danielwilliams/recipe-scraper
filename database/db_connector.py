# database/db_connector.py
import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
import config
import traceback

logger = logging.getLogger(__name__)

def get_db_connection():
    """Connect to the PostgreSQL database"""
    try:
        # First try using DATABASE_URL if available
        if config.DATABASE_URL:
            logger.info(f"Connecting to database using DATABASE_URL: {config.DATABASE_URL}")
            conn = psycopg2.connect(config.DATABASE_URL)
            logger.info("Successfully connected using DATABASE_URL")

            # Log connection details for verification
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user, version()")
                db_info = cursor.fetchone()
                logger.info(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
                logger.info(f"PostgreSQL version: {db_info[2]}")

            return conn

        # Fall back to individual parameters
        logger.info("DATABASE_URL not available, connecting using individual parameters")
        logger.info(f"DB: {config.DB_NAME}, User: {config.DB_USER}, Host: {config.DB_HOST}, Port: {config.DB_PORT}")

        conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT
        )

        # Log connection details for verification
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            db_info = cursor.fetchone()
            logger.info(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
            logger.info(f"PostgreSQL version: {db_info[2]}")

        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def create_tables_if_not_exist():
    """Create necessary tables if they don't exist"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Create scraped_recipes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraped_recipes (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    source VARCHAR(100) NOT NULL,
                    source_url TEXT,
                    instructions JSONB NOT NULL,
                    date_scraped TIMESTAMP NOT NULL,
                    date_processed TIMESTAMP NOT NULL,
                    complexity VARCHAR(20),
                    prep_time INTEGER,
                    cook_time INTEGER,
                    total_time INTEGER,
                    servings INTEGER,
                    cuisine VARCHAR(50),
                    is_verified BOOLEAN DEFAULT FALSE,
                    raw_content TEXT,
                    metadata JSONB
                );
            """)
            
            # Create recipe_ingredients table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipe_ingredients (
                    id SERIAL PRIMARY KEY,
                    recipe_id INTEGER REFERENCES scraped_recipes(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    amount VARCHAR(50),
                    unit VARCHAR(30),
                    notes TEXT,
                    category VARCHAR(50),
                    is_main_ingredient BOOLEAN DEFAULT FALSE
                );
            """)
            
            # Create recipe_tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipe_tags (
                    id SERIAL PRIMARY KEY,
                    recipe_id INTEGER REFERENCES scraped_recipes(id) ON DELETE CASCADE,
                    tag VARCHAR(50) NOT NULL
                );
            """)
            
            # Create indexes for faster searching
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recipe_title ON scraped_recipes(title);
                CREATE INDEX IF NOT EXISTS idx_recipe_complexity ON scraped_recipes(complexity);
                CREATE INDEX IF NOT EXISTS idx_recipe_tags ON recipe_tags(tag);
                CREATE INDEX IF NOT EXISTS idx_recipe_ingredients ON recipe_ingredients(name);
            """)
            
            conn.commit()
            logger.info("Database tables created successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating database tables: {str(e)}")
        raise
    finally:
        conn.close()

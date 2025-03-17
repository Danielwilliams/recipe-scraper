# database/db_connector.py
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

logger = logging.getLogger(__name__)

def get_db_connection():
    """Connect to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
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
            
            # Create recipe_nutrition table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recipe_nutrition (
                    id SERIAL PRIMARY KEY,
                    recipe_id INTEGER REFERENCES scraped_recipes(id) ON DELETE CASCADE,
                    calories INTEGER,
                    protein REAL,
                    carbs REAL,
                    fat REAL,
                    fiber REAL,
                    sugar REAL,
                    is_calculated BOOLEAN DEFAULT TRUE
                );
            """)
            
            # Create indexes
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
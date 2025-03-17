import argparse
import logging
import sys
import time
from datetime import datetime
from database.recipe_storage import RecipeStorage
import config
import os
import traceback

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Check environment variables
logger.info("Environment variable check:")
logger.info(f"DATABASE_URL from environ: {'Set' if os.environ.get('DATABASE_URL') else 'Not set'}")
logger.info(f"DATABASE_URL from config: {'Set' if config.DATABASE_URL else 'Not set'}")
logger.info(f"DB_NAME from environ: {'Set' if os.environ.get('DB_NAME') else 'Not set'}")
logger.info(f"DB_NAME from config: {'Set' if config.DB_NAME else 'Not set'}")
logger.info(f"DB_HOST from environ: {'Set' if os.environ.get('DB_HOST') else 'Not set'}")
logger.info(f"DB_HOST from config: {config.DB_HOST}")

logger.info("Testing database connection...")
try:
    from database.db_connector import get_db_connection
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
    conn.close()
    logger.info("Database connection successful!")
except Exception as e:
    logger.error(f"Database connection failed: {str(e)}")
    logger.error(traceback.format_exc())

# Import project modules
from database.db_connector import create_tables_if_not_exist
from scrapers.allrecipes_scraper import AllRecipesScraper
# Additional imports here based on what you implement

def main():
    """Main entry point for the recipe scraper"""
    try:
        logger.info("Starting recipe scraper")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Recipe scraper")
        parser.add_argument('--source', choices=['all', 'websites', 'facebook'], default='websites',
                            help='Source to scrape (default: websites)')
        parser.add_argument('--limit', type=int, default=50,
                            help='Maximum number of recipes to scrape per source (default: 50)')
        
        args = parser.parse_args()
        
        # Create database tables if they don't exist
        try:
            logger.info("Ensuring database tables exist")
            create_tables_if_not_exist()
            logger.info("Database tables check completed")
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Scrape from websites
        if args.source in ['all', 'websites']:
            try:
                logger.info("Initializing AllRecipes scraper")
                allrecipes_scraper = AllRecipesScraper()
                logger.info("Starting AllRecipes scraping process")
                recipes = allrecipes_scraper.scrape(args.limit)
                logger.info(f"Found {len(recipes)} recipes from AllRecipes")
                
                # Save recipes to database
                logger.info("Preparing to save recipes")
                saved_count = 0
                
                # Initialize recipe storage
                from database.recipe_storage import RecipeStorage
                storage = RecipeStorage()
                
                for recipe in recipes:
                    try:
                        logger.info(f"Saving recipe: {recipe.get('title', 'Untitled')}")
                        if storage.save_recipe(recipe):
                            saved_count += 1
                    except Exception as e:
                        logger.error(f"Error saving recipe: {str(e)}")
                        logger.error(traceback.format_exc())
                
                logger.info(f"Successfully saved {saved_count} out of {len(recipes)} recipes")
                
            except Exception as e:
                logger.error(f"AllRecipes scraping error: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info("Recipe scraping completed")
        
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

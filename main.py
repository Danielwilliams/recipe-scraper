import argparse
import logging
import sys
import time
from datetime import datetime
from database.recipe_storage import RecipeStorage
import config
impot os

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

# Import project modules
from database.db_connector import create_tables_if_not_exist
from scrapers.allrecipes_scraper import AllRecipesScraper
# Additional imports here based on what you implement

def main():
    """Main entry point for the recipe scraper"""
    logger.info("Starting recipe scraper")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Recipe scraper")
    parser.add_argument('--source', choices=['all', 'websites'], default='websites',
                        help='Source to scrape (default: websites)')
    parser.add_argument('--limit', type=int, default=50,
                        help='Maximum number of recipes to scrape per source (default: 50)')
    
    args = parser.parse_args()
    
    # Create database tables if they don't exist
    try:
        logger.info("Ensuring database tables exist")
        create_tables_if_not_exist()
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        return
    
    # Initialize recipe storage
    storage = RecipeStorage()
    
    # Scrape from websites
    if args.source in ['all', 'websites']:
        try:
            logger.info("Scraping from AllRecipes")
            allrecipes_scraper = AllRecipesScraper()
            recipes = allrecipes_scraper.scrape(args.limit)
            logger.info(f"Found {len(recipes)} recipes from AllRecipes")
            
            # Save recipes to database
            saved_count = 0
            for recipe in recipes:
                if storage.save_recipe(recipe):
                    saved_count += 1
            
            logger.info(f"Successfully saved {saved_count} out of {len(recipes)} recipes")
            
        except Exception as e:
            logger.error(f"AllRecipes scraping error: {str(e)}")
    
    logger.info("Recipe scraping completed")

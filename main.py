import argparse
import logging
import sys
import traceback
from database.recipe_storage import RecipeStorage
from scrapers.allrecipes_scraper import AllRecipesScraper
from scrapers.eatingwell_scraper import EatingWellScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the recipe scraper"""
    try:
        logger.info("Starting recipe scraper")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Recipe scraper")
        parser.add_argument('--source', choices=['all', 'websites'], default='websites',
                            help='Source to scrape (default: websites)')
        parser.add_argument('--limit', type=int, default=50,
                            help='Maximum number of recipes to scrape per source (default: 50)')
        
        args = parser.parse_args()
        
        # Scrapers to use
        scrapers = [
            ('AllRecipes', AllRecipesScraper()),
            ('EatingWell', EatingWellScraper())
        ]
        
        # Scrape from websites
        if args.source in ['all', 'websites']:
            for scraper_name, scraper in scrapers:
                try:
                    logger.info(f"Starting {scraper_name} scraping process")
                    recipes = scraper.scrape(args.limit)
                    logger.info(f"Found {len(recipes)} recipes from {scraper_name}")
                    
                    # Save recipes to database
                    storage = RecipeStorage()
                    saved_count = 0
                    
                    for recipe in recipes:
                        try:
                            if storage.save_recipe(recipe):
                                saved_count += 1
                        except Exception as e:
                            logger.error(f"Error saving {scraper_name} recipe: {str(e)}")
                            logger.error(traceback.format_exc())
                    
                    logger.info(f"Successfully saved {saved_count} out of {len(recipes)} recipes from {scraper_name}")
                    
                except Exception as e:
                    logger.error(f"{scraper_name} scraping error: {str(e)}")
                    logger.error(traceback.format_exc())
        
        logger.info("Recipe scraping completed")
        
    except Exception as e:
        logger.error(f"Unexpected error in main: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

# main.py
import argparse
import logging
import sys
import traceback
from database.recipe_storage import RecipeStorage
from scrapers.allrecipes_scraper import AllRecipesScraper
from scrapers.eatingwell_scraper import EatingWellScraper
from scrapers.foodnetwork_scraper import FoodNetworkScraper
from scrapers.epicurious_scraper import EpicuriousScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('recipe_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the recipe scraper"""
    try:
        logger.info("Starting recipe scraper")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Recipe scraper")
        parser.add_argument('--source', choices=['all', 'websites', 'allrecipes', 'eatingwell', 'foodnetwork', 'epicurious'], 
                            default='websites', help='Source to scrape (default: websites)')
        parser.add_argument('--limit', type=int, default=50,
                            help='Maximum number of recipes to scrape per source (default: 50)')
        
        args = parser.parse_args()
        
        # Determine which scrapers to use
        scrapers = []
        
        if args.source in ['all', 'websites']:
            scrapers = [
                ('AllRecipes', AllRecipesScraper()),
                ('EatingWell', EatingWellScraper()),
                ('FoodNetwork', FoodNetworkScraper()),
                ('Epicurious', EpicuriousScraper())
            ]
        elif args.source == 'allrecipes':
            scrapers = [('AllRecipes', AllRecipesScraper())]
        elif args.source == 'eatingwell':
            scrapers = [('EatingWell', EatingWellScraper())]
        elif args.source == 'foodnetwork':
            scrapers = [('FoodNetwork', FoodNetworkScraper())]
        elif args.source == 'epicurious':
            scrapers = [('Epicurious', EpicuriousScraper())]
        
        # Scrape from each source
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

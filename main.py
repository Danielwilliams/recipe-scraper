# main.py
import argparse
import logging
import sys
import traceback
from database.recipe_storage import RecipeStorage
from scrapers.allrecipes_scraper import AllRecipesScraper
from scrapers.eatingwell_scraper import EatingWellScraper
from scrapers.foodnetwork_scraper import FoodNetworkScraper
from scrapers.pinchofyum_scraper import PinchOfYumScraper
from scrapers.enhanced_pinchofyum_scraper import EnhancedPinchOfYumScraper
from scrapers.simplyrecipes_scraper import SimplyRecipesScraper
from scrapers.enhanced_simplyrecipes_scraper import EnhancedSimplyRecipesScraper
from scrapers.host_the_toast_scraper import HostTheToastScraper
from scrapers.fit_fab_fodmap_scraper import FitFabFodmapScraper
from scrapers.pickled_plum_scraper import PickledPlumScraper
from database.db_connector import get_db_connection
from psycopg2.extras import RealDictCursor
from scrapers.myprotein_scraper import MyProteinScraper


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

def update_image_urls():
    """
    Update missing image URLs for existing recipes in the database
    """
    try:
        logger.info("Starting bulk image URL update process")
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find recipes with missing image URLs
        cursor.execute("""
            SELECT id, title, source, source_url 
            FROM scraped_recipes 
            WHERE image_url IS NULL OR image_url = ''
            ORDER BY date_scraped DESC
        """)
        
        recipes_to_update = cursor.fetchall()
        logger.info(f"Found {len(recipes_to_update)} recipes with missing image URLs")
        
        if not recipes_to_update:
            logger.info("No recipes need updating. Exiting.")
            return
        
        # Group recipes by source for more efficient processing
        recipes_by_source = {}
        for recipe in recipes_to_update:
            source = recipe['source']
            if source not in recipes_by_source:
                recipes_by_source[source] = []
            recipes_by_source[source].append(recipe)
        
        # Initialize scrapers
        scrapers = {
            #'AllRecipes': AllRecipesScraper(),
            #'EatingWell': EatingWellScraper(),
            #'Food Network': FoodNetworkScraper(),
            'Pinch of Yum': EnhancedPinchOfYumScraper(),  # Use enhanced scraper
            'SimplyRecipes': EnhancedSimplyRecipesScraper(),  # Use enhanced scraper
            'MyProtein': MyProteinScraper(),
            'Host the Toast': HostTheToastScraper(),  # New scraper
            'Fit Fab Fodmap': FitFabFodmapScraper(),  # New scraper
            'Pickled Plum': PickledPlumScraper()  # New scraper
        }
        
        storage = RecipeStorage()
        updated_count = 0
        failed_count = 0
        
        # Process each source
        for source, recipes in recipes_by_source.items():
            if source in scrapers:
                logger.info(f"Processing {len(recipes)} recipes from {source}")
                scraper = scrapers[source]
                
                for recipe in recipes:
                    try:
                        url = recipe['source_url']
                        logger.info(f"Updating recipe: {recipe['title']} ({url})")
                        
                        # Request the page
                        import requests
                        response = requests.get(url, headers=scraper.headers, timeout=30)
                        
                        if response.status_code != 200:
                            logger.error(f"Failed to access URL: {url}, Status: {response.status_code}")
                            failed_count += 1
                            continue
                        
                        # Extract recipe info with updated code
                        updated_info = scraper._extract_recipe_info(response.text, url)
                        
                        if updated_info and updated_info.get('image_url'):
                            # Update the database
                            cursor.execute("""
                                UPDATE scraped_recipes 
                                SET image_url = %s 
                                WHERE id = %s
                            """, (updated_info['image_url'], recipe['id']))
                            
                            conn.commit()
                            updated_count += 1
                            logger.info(f"Updated image URL for recipe ID {recipe['id']}: {updated_info['image_url']}")
                        else:
                            logger.warning(f"Could not extract image URL for recipe ID {recipe['id']}")
                            failed_count += 1
                        
                        # Be polite to the servers
                        import time
                        time.sleep(2)
                    
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"Error updating recipe ID {recipe['id']}: {str(e)}")
                        failed_count += 1
            else:
                logger.warning(f"No scraper available for source: {source}")
                failed_count += len(recipes)
        
        logger.info(f"Update complete. Updated: {updated_count}, Failed: {failed_count}")
        
    except Exception as e:
        logger.error(f"Unexpected error in update_image_urls: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        cursor.close()
        conn.close()

def main():
    """Main entry point for the recipe scraper"""
    try:
        logger.info("Starting recipe scraper")
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Recipe scraper")
        parser.add_argument('--source', choices=['all', 'websites', 'allrecipes', 'eatingwell', 'foodnetwork', 'epicurious',
                                               'pinchofyum', 'simplyrecipes', 'myprotein', 'hostthetoast', 'fitfabfodmap', 'pickledplum'],
                            default='websites', help='Source to scrape (default: websites)')
        parser.add_argument('--limit', type=int, default=50,
                            help='Maximum number of recipes to scrape per source (default: 50)')
        parser.add_argument('--update-images', action='store_true', 
                            help='Update missing image URLs for existing recipes')
        
        args = parser.parse_args()
        
        # If --update-images flag is provided, run update on existing recipes
        if args.update_images:
            update_image_urls()
            return
        
        # Determine which scrapers to use
        scrapers = []

        if args.source in ['all', 'websites']:
            scrapers = [
                #('AllRecipes', AllRecipesScraper()),
                #('EatingWell', EatingWellScraper()),
                #('FoodNetwork', FoodNetworkScraper()),
                ('PinchOfYum', EnhancedPinchOfYumScraper()),  # Use enhanced scraper
                ('SimplyRecipes', EnhancedSimplyRecipesScraper()),  # Use enhanced scraper
                ('MyProtein', MyProteinScraper()),
                ('HostTheToast', HostTheToastScraper()),  # New scraper
                ('FitFabFodmap', FitFabFodmapScraper()),  # New scraper
                ('PickledPlum', PickledPlumScraper())     # New scraper
            ]
        #elif args.source == 'allrecipes':
        #    scrapers = [('AllRecipes', AllRecipesScraper())]
        #elif args.source == 'eatingwell':
        #    scrapers = [('EatingWell', EatingWellScraper())]
        #elif args.source == 'foodnetwork':
        #    scrapers = [('FoodNetwork', FoodNetworkScraper())]
        elif args.source == 'pinchofyum':
            scrapers = [('PinchOfYum', EnhancedPinchOfYumScraper())]  # Use enhanced scraper
        elif args.source == 'simplyrecipes':
            scrapers = [('SimplyRecipes', EnhancedSimplyRecipesScraper())]  # Use enhanced scraper
        elif args.source == 'myprotein':
            scrapers = [('MyProtein', MyProteinScraper())]
        elif args.source == 'hostthetoast':
            scrapers = [('HostTheToast', HostTheToastScraper())]
        elif args.source == 'fitfabfodmap':
            scrapers = [('FitFabFodmap', FitFabFodmapScraper())]
        elif args.source == 'pickledplum':
            scrapers = [('PickledPlum', PickledPlumScraper())]
        
        # Scrape from each source
        for scraper_name, scraper in scrapers:
            try:
                logger.info(f"Starting {scraper_name} scraping process")
                recipes = scraper.scrape(args.limit)
                logger.info(f"Found {len(recipes)} recipes from {scraper_name}")
                
                # Save recipes to database
                storage = RecipeStorage()
                saved_count = 0
                updated_count = 0
                
                for recipe in recipes:
                    try:
                        result = storage.save_recipe(recipe)
                        if result:
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
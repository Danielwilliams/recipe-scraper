#!/usr/bin/env python
# update_recipes.py - Script to update existing recipes with missing data

import logging
import sys
import time
import traceback
import argparse
import requests
from datetime import datetime
from psycopg2.extras import RealDictCursor
from database.db_connector import get_db_connection, create_tables_if_not_exist
from scrapers.allrecipes_scraper import AllRecipesScraper
from scrapers.eatingwell_scraper import EatingWellScraper
from scrapers.foodnetwork_scraper import FoodNetworkScraper
from scrapers.epicurious_scraper import EpicuriousScraper
from scrapers.pinchofyum_scraper import PinchOfYumScraper
from scrapers.simplyrecipes_scraper import SimplyRecipesScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('recipe_updates.log')
    ]
)
logger = logging.getLogger('update_recipes')

def get_recipes_needing_updates(criteria):
    """
    Get recipes that need updates based on specified criteria
    
    Args:
        criteria (dict): Dictionary of update criteria
    
    Returns:
        list: Recipes needing updates
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build the WHERE clause based on criteria
            where_clauses = []
            params = []
            
            if criteria.get('missing_images', False):
                where_clauses.append("(image_url IS NULL OR image_url = '')")
            
            if criteria.get('missing_prep_time', False):
                where_clauses.append("prep_time IS NULL")
            
            if criteria.get('missing_cook_time', False):
                where_clauses.append("cook_time IS NULL")
            
            if criteria.get('missing_servings', False):
                where_clauses.append("servings IS NULL")
            
            if criteria.get('older_than_days'):
                days = criteria['older_than_days']
                where_clauses.append("date_scraped < NOW() - INTERVAL %s DAY")
                params.append(days)
            
            if not where_clauses:
                logger.warning("No update criteria specified. Please provide at least one criterion.")
                return []
            
            # Combine WHERE clauses with OR
            where_clause = " OR ".join(where_clauses)
            
            # Add source filter if specified
            if criteria.get('source'):
                source_clause = "source = %s"
                params.append(criteria['source'])
                where_clause = f"({where_clause}) AND {source_clause}"
            
            # Construct and execute the query
            query = f"""
                SELECT id, title, source, source_url, date_scraped::TEXT
                FROM scraped_recipes
                WHERE {where_clause}
                ORDER BY date_scraped DESC
                LIMIT %s
            """
            
            params.append(criteria.get('limit', 100))
            cursor.execute(query, params)
            
            return cursor.fetchall()
    finally:
        conn.close()

def update_recipe(recipe_data, scrapers):
    """
    Update a recipe by re-scraping its URL
    
    Args:
        recipe_data (dict): Recipe data from database
        scrapers (dict): Dictionary of scrapers by source
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    recipe_id = recipe_data['id']
    url = recipe_data['source_url']
    source = recipe_data['source']
    
    logger.info(f"Updating recipe ID {recipe_id}: {recipe_data['title']}")
    
    # Check if we have a scraper for this source
    if source not in scrapers:
        logger.warning(f"No scraper available for source: {source}")
        return False
    
    scraper = scrapers[source]
    
    try:
        # Get headers dynamically (handle both old and new scraper designs)
        headers = getattr(scraper, 'headers', None)
        if headers is None and hasattr(scraper, '_get_headers'):
            headers = scraper._get_headers()
        if headers is None:
            logger.error(f"Scraper for {source} has no headers or _get_headers method")
            return False
        
        # Request the page
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to access URL: {url}, Status: {response.status_code}")
            return False
        
        # Extract updated recipe info
        updated_info = scraper._extract_recipe_info(response.text, url)
        
        if not updated_info:
            logger.error(f"Failed to extract recipe info from {url}")
            return False
        
        # Update the database
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Determine which fields to update
                fields_to_update = []
                params = []
                
                # Image URL
                if updated_info.get('image_url') and (not recipe_data.get('image_url') or recipe_data.get('image_url') == ''):
                    fields_to_update.append("image_url = %s")
                    params.append(updated_info['image_url'])
                
                # Metadata
                metadata = updated_info.get('metadata', {})
                
                if metadata.get('prep_time') and recipe_data.get('prep_time') is None:
                    fields_to_update.append("prep_time = %s")
                    params.append(metadata['prep_time'])
                
                if metadata.get('cook_time') and recipe_data.get('cook_time') is None:
                    fields_to_update.append("cook_time = %s")
                    params.append(metadata['cook_time'])
                
                if metadata.get('total_time') and recipe_data.get('total_time') is None:
                    fields_to_update.append("total_time = %s")
                    params.append(metadata['total_time'])
                
                if metadata.get('servings') and recipe_data.get('servings') is None:
                    fields_to_update.append("servings = %s")
                    params.append(metadata['servings'])
                
                # Update date_processed
                fields_to_update.append("date_processed = %s")
                params.append(datetime.now())
                
                if not fields_to_update:
                    logger.info(f"No updates needed for recipe ID {recipe_id}")
                    return True
                
                # Build and execute update query
                query = f"""
                    UPDATE scraped_recipes
                    SET {', '.join(fields_to_update)}
                    WHERE id = %s
                """
                params.append(recipe_id)
                
                cursor.execute(query, params)
                conn.commit()
                
                logger.info(f"Successfully updated recipe ID {recipe_id} with new data")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error updating recipe ID {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error updating recipe ID {recipe_id}: {str(e)}")
        return False

def main():
    """Main entry point for updating recipes"""
    parser = argparse.ArgumentParser(description="Update recipes with missing data")
    
    parser.add_argument('--missing-images', action='store_true', 
                      help='Update recipes with missing image URLs')
    parser.add_argument('--missing-prep-time', action='store_true', 
                      help='Update recipes with missing prep time')
    parser.add_argument('--missing-cook-time', action='store_true', 
                      help='Update recipes with missing cook time')
    parser.add_argument('--missing-servings', action='store_true', 
                      help='Update recipes with missing servings info')
    parser.add_argument('--older-than', type=int, metavar='DAYS',
                      help='Update recipes older than specified days')
    parser.add_argument('--source', choices=['AllRecipes', 'EatingWell', 'Food Network', 'Epicurious', 'Pinch of Yum', 'SimplyRecipes'],
                      help='Update recipes from a specific source')
    parser.add_argument('--limit', type=int, default=100,
                      help='Maximum number of recipes to update (default: 100)')
    parser.add_argument('--delay', type=float, default=2.0,
                      help='Delay in seconds between requests (default: 2.0)')
    
    args = parser.parse_args()
    
    # Initialize scrapers
    scrapers = {
        'AllRecipes': AllRecipesScraper(),
        'EatingWell': EatingWellScraper(),
        'Food Network': FoodNetworkScraper(),
        'Epicurious': EpicuriousScraper(),
        'Pinch of Yum': PinchOfYumScraper(),
        'SimplyRecipes': SimplyRecipesScraper()
    }
    
    # Build criteria dictionary from arguments
    criteria = {
        'missing_images': args.missing_images,
        'missing_prep_time': args.missing_prep_time,
        'missing_cook_time': args.missing_cook_time,
        'missing_servings': args.missing_servings,
        'older_than_days': args.older_than,
        'source': args.source,
        'limit': args.limit
    }
    
    # Ensure at least one criterion is specified
    if not any([args.missing_images, args.missing_prep_time, args.missing_cook_time, 
                args.missing_servings, args.older_than]):
        logger.error("Please specify at least one update criterion")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Get recipes needing updates
        recipes = get_recipes_needing_updates(criteria)
        logger.info(f"Found {len(recipes)} recipes to update")
        
        if not recipes:
            logger.info("No recipes found that match the update criteria")
            return
        
        # Update each recipe
        success_count = 0
        failure_count = 0
        
        for recipe in recipes:
            if update_recipe(recipe, scrapers):
                success_count += 1
            else:
                failure_count += 1
            
            # Delay between requests
            time.sleep(args.delay)
        
        logger.info(f"Update complete. Successful: {success_count}, Failed: {failure_count}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
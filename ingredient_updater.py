#!/usr/bin/env python3
"""
Ingredient Updater Job

This script finds recipes in the database that have incomplete metadata and attempts to
re-scrape them from their source URLs to get the missing data including ingredients,
cook time, prep time, notes and nutrition data.
"""

import logging
import json
import time
import requests
import traceback
from bs4 import BeautifulSoup
from datetime import datetime
from database.db_connector import get_db_connection
from processors.ingredient_parser import IngredientParser
import config
import re

# Import enhanced scrapers
from scrapers.enhanced_simplyrecipes_scraper import EnhancedSimplyRecipesScraper
from scrapers.enhanced_pinchofyum_scraper import EnhancedPinchOfYumScraper
from scrapers.host_the_toast_scraper import HostTheToastScraper
from scrapers.fit_fab_fodmap_scraper import FitFabFodmapScraper
from scrapers.pickled_plum_scraper import PickledPlumScraper
from scrapers.myprotein_scraper import MyProteinScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ingredient_updater.log')
    ]
)
logger = logging.getLogger(__name__)

class IngredientUpdater:
    """Updates recipes that have missing or incomplete metadata"""
    
    def __init__(self):
        self.ingredient_parser = IngredientParser()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })
        
        # Initialize enhanced scrapers
        self.scrapers = {
            'SimplyRecipes': EnhancedSimplyRecipesScraper(),
            'Pinch of Yum': EnhancedPinchOfYumScraper(),
            'Host the Toast': HostTheToastScraper(),
            'Fit Fab Fodmap': FitFabFodmapScraper(),
            'Pickled Plum': PickledPlumScraper(),
            'MyProtein': MyProteinScraper(),
        }
        
    def find_recipes_with_incomplete_metadata(self, limit=50):
        """
        Find recipes that have incomplete metadata in the database

        Args:
            limit (int): Maximum number of recipes to process

        Returns:
            list: List of recipe dictionaries with id, title, source, source_url
        """
        conn = get_db_connection()
        try:
            # Log database connection details
            logger.info(f"Connected to database: {config.DB_NAME} at {config.DB_HOST}:{config.DB_PORT}")

            # First check if the scraped_recipes table exists
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'scraped_recipes'
                    );
                """)
                table_exists = cursor.fetchone()[0]
                if not table_exists:
                    logger.error("Table 'scraped_recipes' does not exist in the database!")
                    return []

                # Get total count of recipes
                cursor.execute("SELECT COUNT(*) FROM scraped_recipes")
                total_recipes = cursor.fetchone()[0]
                logger.info(f"Total recipes in database: {total_recipes}")

                # Find recipes with missing metadata or specific metadata fields
                cursor.execute("""
                    SELECT DISTINCT sr.id, sr.title, sr.source, sr.source_url
                    FROM scraped_recipes sr
                    WHERE (
                        sr.metadata IS NULL
                        OR sr.metadata->>'ingredients_list' IS NULL
                        OR sr.metadata->>'ingredients_list' = '[]'
                        OR sr.metadata->>'ingredients_list' = '""'
                        OR sr.metadata->>'cook_time' IS NULL
                        OR sr.metadata->>'prep_time' IS NULL
                        OR sr.metadata->>'notes' IS NULL
                        OR sr.metadata->>'nutrition' IS NULL
                    )
                    AND sr.source_url IS NOT NULL
                    AND sr.source_url != ''
                    ORDER BY sr.id DESC
                    LIMIT %s
                """, (limit,))

                recipes = cursor.fetchall()
                logger.info(f"Found {len(recipes)} recipes with incomplete metadata")

                # Convert to list of dictionaries
                recipe_list = []
                for recipe in recipes:
                    recipe_list.append({
                        'id': recipe[0],
                        'title': recipe[1],
                        'source': recipe[2],
                        'source_url': recipe[3]
                    })

                return recipe_list
                
        except Exception as e:
            logger.error(f"Error finding recipes with incomplete metadata: {str(e)}")
            return []
        finally:
            conn.close()
    
    def scrape_recipe_data_from_url(self, url, source):
        """
        Scrape complete recipe data from a URL using the appropriate enhanced scraper
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source (e.g., 'SimplyRecipes', 'Pinch of Yum')
            
        Returns:
            dict: Complete recipe data including ingredients, times, notes, etc.
        """
        try:
            logger.info(f"Scraping recipe data from: {url}")
            
            # Get the page content
            response = None
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Request error for {url}: {str(e)}")
                return {}
                
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check if we have an enhanced scraper for this source
            if source in self.scrapers:
                scraper = self.scrapers[source]
                logger.info(f"Using enhanced {source} scraper")
                
                try:
                    # Try extraction with enhanced scrapers
                    recipe_data = scraper._extract_recipe_info(response.text, url)
                    
                    if recipe_data:
                        logger.info(f"Successfully extracted recipe data using enhanced scraper")
                        return {
                            'ingredients': recipe_data.get('ingredients', []),
                            'cook_time': recipe_data.get('metadata', {}).get('cook_time'),
                            'prep_time': recipe_data.get('metadata', {}).get('prep_time'),
                            'total_time': recipe_data.get('metadata', {}).get('total_time'),
                            'servings': recipe_data.get('metadata', {}).get('servings'),
                            'notes': recipe_data.get('notes', []),
                            'nutrition': recipe_data.get('nutrition', {})
                        }
                except Exception as e:
                    logger.error(f"Error with enhanced scraper for {source}: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # If we get here, enhanced scraper didn't work or we don't have one for this source
            
            # Fallback to JSON-LD for structured data
            recipe_data = self._extract_from_json_ld(soup)
            if recipe_data and recipe_data.get('ingredients'):
                logger.info(f"Successfully extracted recipe data from JSON-LD")
                return recipe_data
            
            # Fallback to legacy extraction methods
            return self._legacy_scrape_recipe_data(soup, source)
            
        except Exception as e:
            logger.error(f"Error scraping recipe data from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
    
    def _legacy_scrape_recipe_data(self, soup, source):
        """
        Legacy recipe data scraping method as fallback
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            source (str): Recipe source
            
        Returns:
            dict: Recipe data including ingredients, times, etc.
        """
        recipe_data = {
            'ingredients': [],
            'cook_time': None,
            'prep_time': None,
            'total_time': None,
            'servings': None,
            'notes': [],
            'nutrition': {}
        }
        
        try:
            # Extract ingredients
            ingredients = []
            
            # Try different common ingredient selectors based on source
            ingredient_selectors = self._get_ingredient_selectors(source)
            ingredient_elements = []
            
            for selector in ingredient_selectors:
                ingredient_elements = soup.select(selector)
                if ingredient_elements:
                    logger.info(f"Found {len(ingredient_elements)} ingredients using selector: {selector}")
                    break
            
            # Extract text from ingredient elements
            for element in ingredient_elements:
                ingredient_text = element.get_text().strip()
                if ingredient_text and len(ingredient_text) > 2:
                    ingredients.append(ingredient_text)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_ingredients = []
            for ing in ingredients:
                if ing not in seen:
                    seen.add(ing)
                    unique_ingredients.append(ing)
            
            recipe_data['ingredients'] = unique_ingredients[:50]  # Limit to reasonable number
            
            # Extract cook time
            cook_time_selectors = [
                '.cook-time', 
                '[itemprop="cookTime"]',
                '.recipe-meta-item:contains("Cook Time")',
                '.recipe-meta:contains("Cook Time")'
            ]
            
            for selector in cook_time_selectors:
                cook_time_elem = soup.select_one(selector)
                if cook_time_elem:
                    cook_time_text = cook_time_elem.get_text().strip()
                    cook_time_minutes = self._parse_time(cook_time_text)
                    if cook_time_minutes:
                        recipe_data['cook_time'] = cook_time_minutes
                        break
            
            # Extract prep time
            prep_time_selectors = [
                '.prep-time', 
                '[itemprop="prepTime"]',
                '.recipe-meta-item:contains("Prep Time")',
                '.recipe-meta:contains("Prep Time")'
            ]
            
            for selector in prep_time_selectors:
                prep_time_elem = soup.select_one(selector)
                if prep_time_elem:
                    prep_time_text = prep_time_elem.get_text().strip()
                    prep_time_minutes = self._parse_time(prep_time_text)
                    if prep_time_minutes:
                        recipe_data['prep_time'] = prep_time_minutes
                        break
            
            # Extract total time
            total_time_selectors = [
                '.total-time', 
                '[itemprop="totalTime"]',
                '.recipe-meta-item:contains("Total Time")',
                '.recipe-meta:contains("Total Time")'
            ]
            
            for selector in total_time_selectors:
                total_time_elem = soup.select_one(selector)
                if total_time_elem:
                    total_time_text = total_time_elem.get_text().strip()
                    total_time_minutes = self._parse_time(total_time_text)
                    if total_time_minutes:
                        recipe_data['total_time'] = total_time_minutes
                        break
            
            # Extract servings
            servings_selectors = [
                '.recipe-yield', 
                '[itemprop="recipeYield"]',
                '.recipe-meta-item:contains("Serving")',
                '.recipe-meta:contains("Serving")',
                '.recipe-meta-item:contains("Yield")',
                '.recipe-meta:contains("Yield")'
            ]
            
            for selector in servings_selectors:
                servings_elem = soup.select_one(selector)
                if servings_elem:
                    servings_text = servings_elem.get_text().strip()
                    servings_match = self._extract_number(servings_text)
                    if servings_match:
                        recipe_data['servings'] = servings_match
                        break
            
            # Extract notes
            notes_selectors = [
                '.recipe-notes', 
                '.notes',
                '.recipe-tips',
                '.tips'
            ]
            
            for selector in notes_selectors:
                notes_elem = soup.select_one(selector)
                if notes_elem:
                    for p in notes_elem.select('p'):
                        note_text = p.get_text().strip()
                        if note_text:
                            recipe_data['notes'].append(note_text)
                    
                    if not recipe_data['notes']:
                        # If no paragraphs, try direct text
                        note_text = notes_elem.get_text().strip()
                        if note_text:
                            recipe_data['notes'] = [note_text]
                    
                    break
            
            # Extract nutrition
            nutrition_selectors = [
                '.nutrition-info',
                '.nutrition',
                '[itemprop="nutrition"]'
            ]
            
            for selector in nutrition_selectors:
                nutrition_elem = soup.select_one(selector)
                if nutrition_elem:
                    nutrition_text = nutrition_elem.get_text().strip()
                    
                    # Extract calories
                    calories_match = re.search(r'calories:?\s*(\d+)', nutrition_text, re.IGNORECASE)
                    if calories_match:
                        recipe_data['nutrition']['calories'] = calories_match.group(1)
                    
                    # Extract fat
                    fat_match = re.search(r'fat:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                    if fat_match:
                        recipe_data['nutrition']['fat'] = fat_match.group(1)
                    
                    # Extract carbs
                    carbs_match = re.search(r'carb(?:ohydrate)?s?:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                    if carbs_match:
                        recipe_data['nutrition']['carbs'] = carbs_match.group(1)
                    
                    # Extract protein
                    protein_match = re.search(r'protein:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                    if protein_match:
                        recipe_data['nutrition']['protein'] = protein_match.group(1)
                    
                    break
            
            logger.info(f"Extracted {len(recipe_data['ingredients'])} ingredients using legacy method")
            return recipe_data
            
        except Exception as e:
            logger.error(f"Error in legacy scraping: {str(e)}")
            logger.error(traceback.format_exc())
            return recipe_data
    
    def _get_ingredient_selectors(self, source):
        """
        Get ingredient CSS selectors based on the recipe source
        
        Args:
            source (str): Recipe source
            
        Returns:
            list: List of CSS selectors to try
        """
        selectors = {
            'SimplyRecipes': [
                '.structured-ingredients__list-item',
                '.mntl-structured-ingredients__list-item',
                '.recipe-ingredients li',
                '.ingredient-list li',
                '.ingredients li',
                '[data-module="recipe"] .ingredients li',
                '[data-ingredient-name]',
                'li[data-tr-ingredient-checkbox]'
            ],
            'Pinch of Yum': [
                'li[data-tr-ingredient-checkbox]',
                '.tasty-recipes-ingredients li',
                '.tasty-recipes-ingredients-body li',
                '.recipe-ingredients li',
                '.ingredients li',
                'ul.ingredients li'
            ],
            'AllRecipes': [
                '.recipe-ingred_txt',
                '.ingredients-item-name',
                '.recipe-ingredients li',
                'span[data-testid="recipe-ingredients-item-name"]'
            ],
            'Food Network': [
                '.o-RecipeIngredients__a-Ingredient',
                '.recipe-ingredients li',
                '.ingredients li'
            ],
            'EatingWell': [
                '.ingredients li',
                '.recipe-ingredients li',
                '.ingredient-list li'
            ],
            'Epicurious': [
                '[data-testid="IngredientList"] li',
                '.ingredients li',
                '.recipe-ingredients li'
            ],
            'Host the Toast': [
                'li[data-tr-ingredient-checkbox]',
                '.tasty-recipes-ingredients li',
                '.tasty-recipes-ingredients-body li',
                '.recipe-ingredients li'
            ],
            'Fit Fab Fodmap': [
                'li[data-tr-ingredient-checkbox]',
                '.tasty-recipes-ingredients li',
                '.tasty-recipes-ingredients-body li',
                '.recipe-ingredients li'
            ],
            'Pickled Plum': [
                'li[data-tr-ingredient-checkbox]',
                '.tasty-recipes-ingredients li',
                '.tasty-recipes-ingredients-body li',
                '.recipe-ingredients li'
            ],
            'MyProtein': [
                '.ingredients-list li',
                '.ingredients li',
                '.recipe-ingredients li'
            ]
        }
        
        # Get source-specific selectors, fallback to common ones
        source_selectors = selectors.get(source, [])
        
        # Add common fallback selectors
        fallback_selectors = [
            'li[data-tr-ingredient-checkbox]',
            '.tasty-recipes-ingredients li',
            '.recipe-ingredients li',
            '.ingredients li',
            '.ingredient-list li',
            '.recipe-ingredient',
            'li[itemprop="recipeIngredient"]',
            '[itemprop="recipeIngredient"]',
            '.ingredient',
            '.wprm-recipe-ingredient',
            '.wprm-recipe-ingredients li'
        ]
        
        return source_selectors + fallback_selectors
    
    def _extract_from_json_ld(self, soup):
        """
        Extract recipe data from JSON-LD structured data
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Recipe data
        """
        recipe_data = {
            'ingredients': [],
            'cook_time': None,
            'prep_time': None,
            'total_time': None,
            'servings': None,
            'notes': [],
            'nutrition': {}
        }
        
        try:
            # Find JSON-LD script tags
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle different JSON-LD structures
                    if isinstance(data, list):
                        for item in data:
                            recipe_object = self._extract_data_from_recipe_object(item)
                            if recipe_object and recipe_object.get('ingredients'):
                                return recipe_object
                    elif isinstance(data, dict):
                        # Check for @graph property (collection of items)
                        if '@graph' in data and isinstance(data['@graph'], list):
                            for item in data['@graph']:
                                recipe_object = self._extract_data_from_recipe_object(item)
                                if recipe_object and recipe_object.get('ingredients'):
                                    return recipe_object
                                    
                        # Regular recipe object
                        recipe_object = self._extract_data_from_recipe_object(data)
                        if recipe_object and recipe_object.get('ingredients'):
                            return recipe_object
                            
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting from JSON-LD: {str(e)}")
            
        return recipe_data
    
    def _extract_data_from_recipe_object(self, data):
        """
        Extract recipe data from a recipe object in JSON-LD
        
        Args:
            data (dict): JSON-LD data object
            
        Returns:
            dict: Recipe data
        """
        recipe_data = {
            'ingredients': [],
            'cook_time': None,
            'prep_time': None,
            'total_time': None,
            'servings': None,
            'notes': [],
            'nutrition': {}
        }
        
        if not isinstance(data, dict):
            return recipe_data
            
        # Check if this is a Recipe object
        schema_type = data.get('@type', '')
        if isinstance(schema_type, list):
            if 'Recipe' not in schema_type:
                return recipe_data
        elif 'Recipe' not in schema_type:
            return recipe_data
            
        # Extract ingredients
        ingredients = data.get('recipeIngredient', [])
        
        if isinstance(ingredients, list):
            recipe_data['ingredients'] = [ing for ing in ingredients if ing and isinstance(ing, str)]
        
        # Extract times
        if data.get('cookTime'):
            recipe_data['cook_time'] = self._parse_iso_duration(data['cookTime'])
            
        if data.get('prepTime'):
            recipe_data['prep_time'] = self._parse_iso_duration(data['prepTime'])
            
        if data.get('totalTime'):
            recipe_data['total_time'] = self._parse_iso_duration(data['totalTime'])
        
        # Extract servings
        if data.get('recipeYield'):
            yield_info = data['recipeYield']
            
            if isinstance(yield_info, list) and len(yield_info) > 0:
                servings_match = self._extract_number(yield_info[0])
                if servings_match:
                    recipe_data['servings'] = servings_match
            else:
                servings_match = self._extract_number(str(yield_info))
                if servings_match:
                    recipe_data['servings'] = servings_match
        
        # Extract nutrition
        if data.get('nutrition') and isinstance(data['nutrition'], dict):
            nutrition = data['nutrition']
            
            if nutrition.get('calories'):
                recipe_data['nutrition']['calories'] = self._extract_number(nutrition['calories'])
                
            if nutrition.get('fatContent'):
                recipe_data['nutrition']['fat'] = self._extract_number(nutrition['fatContent'])
                
            if nutrition.get('carbohydrateContent'):
                recipe_data['nutrition']['carbs'] = self._extract_number(nutrition['carbohydrateContent'])
                
            if nutrition.get('proteinContent'):
                recipe_data['nutrition']['protein'] = self._extract_number(nutrition['proteinContent'])
        
        return recipe_data
    
    def _parse_time(self, time_string):
        """
        Parse time string to minutes
        
        Args:
            time_string (str): Time string like "30 mins" or "1 hr 15 mins"
            
        Returns:
            int: Time in minutes
        """
        if not time_string:
            return None
            
        total_minutes = 0
        
        # Look for hours
        hours_match = re.search(r'(\d+)\s*(?:hours?|hrs?)', time_string, re.IGNORECASE)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        
        # Look for minutes
        mins_match = re.search(r'(\d+)\s*(?:minutes?|mins?)', time_string, re.IGNORECASE)
        if mins_match:
            total_minutes += int(mins_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes
        
        Args:
            iso_duration (str): ISO duration string (e.g., "PT30M", "PT1H30M")
            
        Returns:
            int: Duration in minutes
        """
        if not iso_duration:
            return None
            
        total_minutes = 0
        
        # Parse hours
        hours_match = re.search(r'PT(\d+)H', iso_duration)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        
        # Parse minutes
        mins_match = re.search(r'PT(?:\d+H)?(\d+)M', iso_duration)
        if mins_match:
            total_minutes += int(mins_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
    def _extract_number(self, text):
        """
        Extract first number from text
        
        Args:
            text (str): Text containing a number
            
        Returns:
            int: Extracted number or None
        """
        if not text:
            return None
            
        match = re.search(r'(\d+)', str(text))
        if match:
            return int(match.group(1))
            
        return None
    
    def update_recipe_metadata(self, recipe_id, recipe_data):
        """
        Update a recipe's metadata in the database

        Args:
            recipe_id (int): Recipe ID
            recipe_data (dict): Recipe data to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not recipe_data or not recipe_data.get('ingredients'):
            return False

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # First, get the current metadata for the recipe
                cursor.execute("SELECT metadata FROM scraped_recipes WHERE id = %s", (recipe_id,))
                result = cursor.fetchone()

                if not result:
                    logger.error(f"Recipe {recipe_id} not found in database")
                    return False

                # Get existing metadata or initialize empty dict if None
                metadata = result[0] if result[0] else {}

                # Update the metadata with new data
                if recipe_data.get('ingredients'):
                    metadata['ingredients_list'] = recipe_data['ingredients']
                
                if recipe_data.get('cook_time'):
                    metadata['cook_time'] = recipe_data['cook_time']
                
                if recipe_data.get('prep_time'):
                    metadata['prep_time'] = recipe_data['prep_time']
                
                if recipe_data.get('total_time'):
                    metadata['total_time'] = recipe_data['total_time']
                
                if recipe_data.get('servings'):
                    metadata['servings'] = recipe_data['servings']
                
                if recipe_data.get('notes'):
                    metadata['notes'] = recipe_data['notes']
                
                if recipe_data.get('nutrition'):
                    metadata['nutrition'] = recipe_data['nutrition']

                # Update the recipe's metadata in the database
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET metadata = %s::jsonb
                    WHERE id = %s
                """, (json.dumps(metadata), recipe_id))

                # Also update top-level columns if available
                if recipe_data.get('cook_time') or recipe_data.get('prep_time') or recipe_data.get('servings'):
                    update_fields = []
                    update_values = []
                    
                    if recipe_data.get('cook_time'):
                        update_fields.append("cook_time = %s")
                        update_values.append(recipe_data['cook_time'])
                    
                    if recipe_data.get('prep_time'):
                        update_fields.append("prep_time = %s")
                        update_values.append(recipe_data['prep_time'])
                    
                    if recipe_data.get('servings'):
                        update_fields.append("servings = %s")
                        update_values.append(recipe_data['servings'])
                    
                    if update_fields:
                        # Add recipe_id to values
                        update_values.append(recipe_id)
                        
                        # Build and execute update query
                        update_query = f"""
                            UPDATE scraped_recipes
                            SET {', '.join(update_fields)}
                            WHERE id = %s
                        """
                        cursor.execute(update_query, update_values)

                conn.commit()
                logger.info(f"Updated recipe {recipe_id} with complete metadata")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating metadata for recipe {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def run_update_job(self, limit=50):
        """
        Run the metadata update job
        
        Args:
            limit (int): Maximum number of recipes to process
            
        Returns:
            dict: Summary of results
        """
        logger.info(f"Starting metadata update job (limit: {limit})")
        start_time = datetime.now()
        
        # Find recipes with incomplete metadata
        recipes = self.find_recipes_with_incomplete_metadata(limit)
        
        if not recipes:
            logger.info("No recipes found that need metadata updates")
            return {
                'total_processed': 0,
                'successful_updates': 0,
                'failed_updates': 0,
                'duration_seconds': 0
            }
        
        successful_updates = 0
        failed_updates = 0
        
        for i, recipe in enumerate(recipes, 1):
            logger.info(f"Processing recipe {i}/{len(recipes)}: {recipe['title']}")
            
            try:
                # Scrape recipe data from source URL
                recipe_data = self.scrape_recipe_data_from_url(
                    recipe['source_url'], 
                    recipe['source']
                )
                
                if recipe_data and recipe_data.get('ingredients'):
                    # Update database
                    success = self.update_recipe_metadata(recipe['id'], recipe_data)
                    if success:
                        successful_updates += 1
                        logger.info(f"✅ Successfully updated: {recipe['title']}")
                    else:
                        failed_updates += 1
                        logger.error(f"❌ Failed to update database for: {recipe['title']}")
                else:
                    failed_updates += 1
                    logger.warning(f"⚠️ No recipe data found for: {recipe['title']}")
                    
                # Be polite - don't hammer the server
                time.sleep(2)
                    
            except Exception as e:
                failed_updates += 1
                logger.error(f"❌ Error processing {recipe['title']}: {str(e)}")
                logger.error(traceback.format_exc())
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Summary
        summary = {
            'total_processed': len(recipes),
            'successful_updates': successful_updates,
            'failed_updates': failed_updates,
            'duration_seconds': duration
        }
        
        logger.info("=" * 60)
        logger.info("METADATA UPDATE JOB COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Total recipes processed: {summary['total_processed']}")
        logger.info(f"Successful updates: {summary['successful_updates']}")
        logger.info(f"Failed updates: {summary['failed_updates']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return summary

def main():
    """Main function for running as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update missing recipe metadata')
    parser.add_argument('--limit', type=int, default=50, 
                       help='Maximum number of recipes to process (default: 50)')
    
    args = parser.parse_args()
    
    updater = IngredientUpdater()
    results = updater.run_update_job(limit=args.limit)
    
    # Exit with error code if all updates failed
    if results['total_processed'] > 0 and results['successful_updates'] == 0:
        exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Recipe Metadata Updater Job

This script finds recipes in the database that have missing metadata fields and attempts to
re-scrape them from their source URLs to get the missing data (ingredients, prep time,
cook time, servings, nutrition, and notes).
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RecipeMetadataUpdater:
    """Updates recipes that have missing metadata fields"""
    
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
        
    def find_recipes_with_missing_metadata(self, limit=50):
        """
        Find recipes that have missing metadata fields in the database

        Args:
            limit (int): Maximum number of recipes to process

        Returns:
            list: List of recipe dictionaries with id, title, source, source_url, metadata
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Find recipes with missing important metadata fields
                cursor.execute("""
                    SELECT DISTINCT sr.id, sr.title, sr.source, sr.source_url, sr.metadata
                    FROM scraped_recipes sr
                    WHERE (
                        sr.metadata IS NULL
                        OR sr.metadata->>'ingredients_list' IS NULL
                        OR sr.metadata->>'ingredients_list' = '[]'
                        OR sr.metadata->>'ingredients_list' = '""'
                        OR sr.metadata->>'servings' IS NULL
                        OR sr.metadata->>'prep_time' IS NULL
                        OR sr.metadata->>'cook_time' IS NULL
                        OR sr.nutrition IS NULL
                    )
                    AND sr.source_url IS NOT NULL
                    AND sr.source_url != ''
                    ORDER BY sr.id DESC
                    LIMIT %s
                """, (limit,))

                recipes = cursor.fetchall()
                logger.info(f"Found {len(recipes)} recipes with missing metadata")

                # Convert to list of dictionaries
                recipe_list = []
                for recipe in recipes:
                    recipe_list.append({
                        'id': recipe[0],
                        'title': recipe[1],
                        'source': recipe[2],
                        'source_url': recipe[3],
                        'metadata': recipe[4] if recipe[4] else {}
                    })

                return recipe_list
                
        except Exception as e:
            logger.error(f"Error finding recipes with missing metadata: {str(e)}")
            return []
        finally:
            conn.close()
    
    def scrape_recipe_metadata(self, url, source):
        """
        Scrape recipe metadata from a URL using the appropriate enhanced scraper
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source (e.g., 'SimplyRecipes', 'Pinch of Yum')
            
        Returns:
            dict: Recipe metadata including ingredients, times, servings, nutrition, notes
        """
        try:
            logger.info(f"Scraping recipe metadata from: {url}")
            
            # Get the page content directly first for efficient extraction
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
                    # Use the enhanced scraper to extract recipe info
                    recipe_info = scraper._extract_recipe_info(response.text, url)
                    
                    if recipe_info:
                        metadata = {}
                        
                        # Extract ingredients
                        if 'ingredients' in recipe_info and recipe_info['ingredients']:
                            metadata['ingredients_list'] = recipe_info['ingredients']
                            logger.info(f"Extracted {len(recipe_info['ingredients'])} ingredients")
                        
                        # Extract times and servings
                        if 'metadata' in recipe_info:
                            for key in ['prep_time', 'cook_time', 'total_time', 'servings', 'yield']:
                                if key in recipe_info['metadata'] and recipe_info['metadata'][key]:
                                    metadata[key] = recipe_info['metadata'][key]
                        
                        # Extract notes
                        if 'notes' in recipe_info and recipe_info['notes']:
                            metadata['notes'] = recipe_info['notes']
                            logger.info(f"Extracted {len(recipe_info['notes'])} recipe notes")
                        
                        # Extract nutrition
                        nutrition = {}
                        if 'nutrition' in recipe_info and recipe_info['nutrition']:
                            nutrition = recipe_info['nutrition']
                            logger.info(f"Extracted nutrition data: {nutrition}")
                        
                        return {
                            'metadata': metadata,
                            'nutrition': nutrition
                        }
                        
                    logger.warning(f"Enhanced scraper failed to extract recipe info")
                except Exception as e:
                    logger.error(f"Error with enhanced scraper for {source}: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # If we get here, enhanced scraper didn't work or we don't have one for this source
            # Try fallback methods
            return self._legacy_scrape_metadata(soup, source)
            
        except Exception as e:
            logger.error(f"Error scraping recipe metadata from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
    
    def _legacy_scrape_metadata(self, soup, source):
        """
        Legacy method to scrape recipe metadata as fallback
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            source (str): Recipe source
            
        Returns:
            dict: Extracted metadata and nutrition
        """
        try:
            metadata = {}
            nutrition = {}
            
            # Extract ingredients
            ingredients = []
            ingredient_selectors = self._get_ingredient_selectors(source)
            
            for selector in ingredient_selectors:
                ingredient_elements = soup.select(selector)
                if ingredient_elements:
                    logger.info(f"Found {len(ingredient_elements)} ingredients using selector: {selector}")
                    for element in ingredient_elements:
                        ingredient_text = element.get_text().strip()
                        if ingredient_text and len(ingredient_text) > 2:
                            ingredients.append(ingredient_text)
                    break
            
            # Try JSON-LD for ingredients if none found with selectors
            if not ingredients:
                json_ld_ingredients = self._extract_from_json_ld(soup, 'recipeIngredient')
                if json_ld_ingredients:
                    ingredients = json_ld_ingredients
                    logger.info(f"Extracted {len(ingredients)} ingredients from JSON-LD")
            
            if ingredients:
                # Remove duplicates while preserving order
                seen = set()
                unique_ingredients = []
                for ing in ingredients:
                    if ing not in seen:
                        seen.add(ing)
                        unique_ingredients.append(ing)
                
                metadata['ingredients_list'] = unique_ingredients
                logger.info(f"Extracted {len(unique_ingredients)} ingredients using legacy method")
            
            # Extract times from JSON-LD
            json_ld_times = self._extract_times_from_json_ld(soup)
            if json_ld_times:
                for key, value in json_ld_times.items():
                    metadata[key] = value
            
            # Extract nutrition from JSON-LD
            json_ld_nutrition = self._extract_nutrition_from_json_ld(soup)
            if json_ld_nutrition:
                nutrition = json_ld_nutrition
            
            return {
                'metadata': metadata,
                'nutrition': nutrition
            }
            
        except Exception as e:
            logger.error(f"Error in legacy metadata scraping: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
    
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
    
    def _extract_from_json_ld(self, soup, property_name):
        """
        Extract property from JSON-LD structured data
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            property_name (str): Name of the property to extract
            
        Returns:
            list: List of extracted values
        """
        try:
            # Find JSON-LD script tags
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle different JSON-LD structures
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe' and property_name in item:
                                return self._process_json_ld_property(item[property_name])
                    elif isinstance(data, dict):
                        # Check for @graph property (collection of items)
                        if '@graph' in data and isinstance(data['@graph'], list):
                            for item in data['@graph']:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe' and property_name in item:
                                    return self._process_json_ld_property(item[property_name])
                                    
                        # Regular recipe object
                        if data.get('@type') == 'Recipe' and property_name in data:
                            return self._process_json_ld_property(data[property_name])
                            
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting {property_name} from JSON-LD: {str(e)}")
            
        return []
    
    def _process_json_ld_property(self, prop_value):
        """
        Process a property value from JSON-LD
        
        Args:
            prop_value: Property value from JSON-LD
            
        Returns:
            list: Processed property values
        """
        result = []
        
        if isinstance(prop_value, list):
            for item in prop_value:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict) and 'text' in item:
                    result.append(item['text'])
        elif isinstance(prop_value, str):
            result.append(prop_value)
        
        return result
    
    def _extract_times_from_json_ld(self, soup):
        """
        Extract cooking times and servings from JSON-LD
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Dictionary with prep_time, cook_time, total_time, servings
        """
        times = {}
        
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    recipe_data = None
                    
                    # Find recipe data
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                recipe_data = item
                                break
                    elif isinstance(data, dict):
                        if '@graph' in data and isinstance(data['@graph'], list):
                            for item in data['@graph']:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                    recipe_data = item
                                    break
                        elif data.get('@type') == 'Recipe':
                            recipe_data = data
                    
                    if recipe_data:
                        # Extract prep time
                        if 'prepTime' in recipe_data:
                            times['prep_time'] = self._parse_iso_duration(recipe_data['prepTime'])
                        
                        # Extract cook time
                        if 'cookTime' in recipe_data:
                            times['cook_time'] = self._parse_iso_duration(recipe_data['cookTime'])
                        
                        # Extract total time
                        if 'totalTime' in recipe_data:
                            times['total_time'] = self._parse_iso_duration(recipe_data['totalTime'])
                        
                        # Extract servings
                        if 'recipeYield' in recipe_data:
                            yield_info = recipe_data['recipeYield']
                            
                            if isinstance(yield_info, list) and len(yield_info) > 0:
                                times['yield'] = yield_info[0]
                            else:
                                times['yield'] = str(yield_info)
                            
                            # Try to extract servings number
                            servings_match = re.search(r'(\d+)', str(yield_info))
                            if servings_match:
                                times['servings'] = int(servings_match.group(1))
                        
                        # If we found at least one time, return the times
                        if times:
                            return times
                
                except Exception as e:
                    logger.debug(f"Error parsing times from JSON-LD: {str(e)}")
                    continue
        
        except Exception as e:
            logger.debug(f"Error extracting times from JSON-LD: {str(e)}")
        
        return times
    
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
        
        try:
            import re
            total_minutes = 0
            
            # Parse hours
            hours_match = re.search(r'(\d+)H', iso_duration)
            if hours_match:
                total_minutes += int(hours_match.group(1)) * 60
            
            # Parse minutes
            mins_match = re.search(r'(\d+)M', iso_duration)
            if mins_match:
                total_minutes += int(mins_match.group(1))
            
            return total_minutes if total_minutes > 0 else None
        except Exception:
            return None
    
    def _extract_nutrition_from_json_ld(self, soup):
        """
        Extract nutrition information from JSON-LD
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Dictionary with nutrition information
        """
        nutrition = {}
        
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    recipe_data = None
                    
                    # Find recipe data
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                recipe_data = item
                                break
                    elif isinstance(data, dict):
                        if '@graph' in data and isinstance(data['@graph'], list):
                            for item in data['@graph']:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                    recipe_data = item
                                    break
                        elif data.get('@type') == 'Recipe':
                            recipe_data = data
                    
                    if recipe_data and 'nutrition' in recipe_data:
                        nutrition_data = recipe_data['nutrition']
                        
                        # Extract common nutrition values
                        for key, json_key in {
                            'calories': 'calories',
                            'fat': 'fatContent',
                            'carbs': 'carbohydrateContent',
                            'protein': 'proteinContent',
                            'fiber': 'fiberContent',
                            'sugar': 'sugarContent',
                            'sodium': 'sodiumContent'
                        }.items():
                            if json_key in nutrition_data:
                                nutrition[key] = self._extract_numeric_value(nutrition_data[json_key])
                        
                        # If we found at least one nutrition value, return the nutrition
                        if nutrition:
                            return nutrition
                
                except Exception as e:
                    logger.debug(f"Error parsing nutrition from JSON-LD: {str(e)}")
                    continue
        
        except Exception as e:
            logger.debug(f"Error extracting nutrition from JSON-LD: {str(e)}")
        
        return nutrition
    
    def _extract_numeric_value(self, value):
        """
        Extract numeric value from string or number
        
        Args:
            value: Value to extract number from
            
        Returns:
            float: Extracted numeric value
        """
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            import re
            match = re.search(r'(\d+(?:\.\d+)?)', str(value))
            if match:
                return float(match.group(1))
        except Exception:
            pass
        
        return None
    
    def update_recipe_metadata(self, recipe_id, metadata_dict, nutrition_dict):
        """
        Update a recipe's metadata and nutrition in the database

        Args:
            recipe_id (int): Recipe ID
            metadata_dict (dict): Dictionary with metadata to update
            nutrition_dict (dict): Dictionary with nutrition to update

        Returns:
            bool: True if successful, False otherwise
        """
        if not metadata_dict and not nutrition_dict:
            return False

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if metadata_dict:
                    # First, get the current metadata for the recipe
                    cursor.execute("SELECT metadata FROM scraped_recipes WHERE id = %s", (recipe_id,))
                    result = cursor.fetchone()

                    if not result:
                        logger.error(f"Recipe {recipe_id} not found in database")
                        return False

                    # Get existing metadata or initialize empty dict if None
                    current_metadata = result[0] if result[0] else {}
                    
                    # Update metadata with new values
                    for key, value in metadata_dict.items():
                        if value:  # Only update if the value is not None/empty
                            current_metadata[key] = value
                    
                    # Update the recipe's metadata
                    cursor.execute("""
                        UPDATE scraped_recipes
                        SET metadata = %s::jsonb
                        WHERE id = %s
                    """, (json.dumps(current_metadata), recipe_id))
                
                if nutrition_dict:
                    # Update nutrition
                    cursor.execute("""
                        UPDATE scraped_recipes
                        SET nutrition = %s::jsonb
                        WHERE id = %s
                    """, (json.dumps(nutrition_dict), recipe_id))

                conn.commit()
                logger.info(f"Updated recipe {recipe_id} with metadata and nutrition")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating metadata for recipe {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def run_update_job(self, limit=50):
        """
        Run the recipe metadata update job
        
        Args:
            limit (int): Maximum number of recipes to process
            
        Returns:
            dict: Summary of results
        """
        logger.info(f"Starting recipe metadata update job (limit: {limit})")
        start_time = datetime.now()
        
        # Find recipes with missing metadata
        recipes = self.find_recipes_with_missing_metadata(limit)
        
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
                # Determine what fields are missing
                missing_fields = []
                metadata = recipe.get('metadata', {})
                
                if not metadata or 'ingredients_list' not in metadata or not metadata['ingredients_list']:
                    missing_fields.append('ingredients')
                
                if 'prep_time' not in metadata or not metadata['prep_time']:
                    missing_fields.append('prep_time')
                
                if 'cook_time' not in metadata or not metadata['cook_time']:
                    missing_fields.append('cook_time')
                
                if 'servings' not in metadata or not metadata['servings']:
                    missing_fields.append('servings')
                
                logger.info(f"Recipe {recipe['title']} is missing: {', '.join(missing_fields)}")
                
                # Scrape metadata from source URL
                scraped_data = self.scrape_recipe_metadata(
                    recipe['source_url'], 
                    recipe['source']
                )
                
                if scraped_data and (scraped_data.get('metadata') or scraped_data.get('nutrition')):
                    # Update database
                    success = self.update_recipe_metadata(
                        recipe['id'], 
                        scraped_data.get('metadata', {}),
                        scraped_data.get('nutrition', {})
                    )
                    
                    if success:
                        successful_updates += 1
                        logger.info(f"✅ Successfully updated: {recipe['title']}")
                    else:
                        failed_updates += 1
                        logger.error(f"❌ Failed to update database for: {recipe['title']}")
                else:
                    failed_updates += 1
                    logger.warning(f"⚠️ No metadata found for: {recipe['title']}")
                    
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
        logger.info("RECIPE METADATA UPDATE JOB COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Total recipes processed: {summary['total_processed']}")
        logger.info(f"Successful updates: {summary['successful_updates']}")
        logger.info(f"Failed updates: {summary['failed_updates']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return summary

def main():
    """Main function for running as a script"""
    import argparse
    import re
    
    parser = argparse.ArgumentParser(description='Update missing recipe metadata')
    parser.add_argument('--limit', type=int, default=50, 
                       help='Maximum number of recipes to process (default: 50)')
    
    args = parser.parse_args()
    
    updater = RecipeMetadataUpdater()
    results = updater.run_update_job(limit=args.limit)
    
    # Exit with error code if all updates failed
    if results['total_processed'] > 0 and results['successful_updates'] == 0:
        exit(1)

if __name__ == "__main__":
    main()
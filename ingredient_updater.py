#!/usr/bin/env python3
"""
Ingredient Updater Job

This script finds recipes in the database that have no ingredients and attempts to
re-scrape them from their source URLs to get the missing ingredient data.
"""

import logging
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from database.db_connector import get_db_connection
from processors.ingredient_parser import IngredientParser
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IngredientUpdater:
    """Updates recipes that are missing ingredients"""
    
    def __init__(self):
        self.ingredient_parser = IngredientParser()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })
        
    def find_recipes_without_ingredients(self, limit=50):
        """
        Find recipes that have no ingredients in the database
        
        Args:
            limit (int): Maximum number of recipes to process
            
        Returns:
            list: List of recipe dictionaries with id, title, source, source_url
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Find recipes with no ingredients
                cursor.execute("""
                    SELECT DISTINCT sr.id, sr.title, sr.source, sr.source_url
                    FROM scraped_recipes sr
                    LEFT JOIN recipe_ingredients ri ON sr.id = ri.recipe_id
                    WHERE ri.recipe_id IS NULL
                    AND sr.source_url IS NOT NULL
                    AND sr.source_url != ''
                    ORDER BY sr.id DESC
                    LIMIT %s
                """, (limit,))
                
                recipes = cursor.fetchall()
                logger.info(f"Found {len(recipes)} recipes without ingredients")
                
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
            logger.error(f"Error finding recipes without ingredients: {str(e)}")
            return []
        finally:
            conn.close()
    
    def scrape_ingredients_from_url(self, url, source):
        """
        Scrape ingredients from a recipe URL
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source (e.g., 'SimplyRecipes', 'AllRecipes')
            
        Returns:
            list: List of ingredient strings or dictionaries
        """
        try:
            logger.info(f"Scraping ingredients from: {url}")
            
            # Add delay to be respectful
            time.sleep(config.SCRAPE_DELAY)
            
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            ingredients = []
            
            # Try different common ingredient selectors based on source
            ingredient_selectors = self._get_ingredient_selectors(source)
            
            for selector in ingredient_selectors:
                ingredient_elements = soup.select(selector)
                if ingredient_elements:
                    logger.info(f"Found ingredients using selector: {selector}")
                    break
            
            if not ingredient_elements:
                # Try JSON-LD structured data
                ingredients = self._extract_from_json_ld(soup)
                if ingredients:
                    logger.info("Found ingredients in JSON-LD structured data")
                    return ingredients
            
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
            
            logger.info(f"Extracted {len(unique_ingredients)} ingredients")
            return unique_ingredients[:50]  # Limit to reasonable number
            
        except requests.RequestException as e:
            logger.error(f"Request error scraping {url}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error scraping ingredients from {url}: {str(e)}")
            return []
    
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
                '.recipe-ingredients li',
                '.ingredient-list li',
                '.ingredients li',
                '[data-module="recipe"] .ingredients li'
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
            'Pinch of Yum': [
                '.recipe-ingredients li',
                '.ingredients li',
                'ul.ingredients li'
            ],
            'Epicurious': [
                '[data-testid="IngredientList"] li',
                '.ingredients li',
                '.recipe-ingredients li'
            ]
        }
        
        # Get source-specific selectors, fallback to common ones
        source_selectors = selectors.get(source, [])
        
        # Add common fallback selectors
        fallback_selectors = [
            '.recipe-ingredients li',
            '.ingredients li',
            '.ingredient-list li',
            '.recipe-ingredient',
            'li[itemprop="recipeIngredient"]',
            '[itemprop="recipeIngredient"]',
            '.ingredient'
        ]
        
        return source_selectors + fallback_selectors
    
    def _extract_from_json_ld(self, soup):
        """
        Extract ingredients from JSON-LD structured data
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: List of ingredients
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
                            ingredients = self._extract_ingredients_from_recipe_object(item)
                            if ingredients:
                                return ingredients
                    else:
                        ingredients = self._extract_ingredients_from_recipe_object(data)
                        if ingredients:
                            return ingredients
                            
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting from JSON-LD: {str(e)}")
            
        return []
    
    def _extract_ingredients_from_recipe_object(self, data):
        """
        Extract ingredients from a recipe object in JSON-LD
        
        Args:
            data (dict): JSON-LD data object
            
        Returns:
            list: List of ingredients
        """
        if not isinstance(data, dict):
            return []
            
        # Check if this is a Recipe object
        schema_type = data.get('@type', '')
        if 'Recipe' not in schema_type:
            return []
            
        # Extract ingredients
        ingredients = data.get('recipeIngredient', [])
        
        if isinstance(ingredients, list):
            return [ing for ing in ingredients if ing and isinstance(ing, str)]
        
        return []
    
    def update_recipe_ingredients(self, recipe_id, ingredients):
        """
        Update a recipe's ingredients in the database
        
        Args:
            recipe_id (int): Recipe ID
            ingredients (list): List of ingredient strings
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not ingredients:
            return False
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Clear existing ingredients (shouldn't be any, but just in case)
                cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = %s", (recipe_id,))
                
                # Insert new ingredients
                for ingredient_text in ingredients:
                    # Parse ingredient into components if possible
                    try:
                        parsed = self.ingredient_parser.parse_ingredient(ingredient_text)
                        cursor.execute("""
                            INSERT INTO recipe_ingredients
                            (recipe_id, name, amount, unit, notes, category)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            recipe_id,
                            parsed.get('name', ingredient_text),
                            parsed.get('amount'),
                            parsed.get('unit'),
                            parsed.get('notes'),
                            parsed.get('category', 'unknown')
                        ))
                    except:
                        # If parsing fails, just store the raw text
                        cursor.execute("""
                            INSERT INTO recipe_ingredients
                            (recipe_id, name, category)
                            VALUES (%s, %s, %s)
                        """, (
                            recipe_id,
                            ingredient_text,
                            'unknown'
                        ))
                
                conn.commit()
                logger.info(f"Updated recipe {recipe_id} with {len(ingredients)} ingredients")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating ingredients for recipe {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def run_update_job(self, limit=50):
        """
        Run the ingredient update job
        
        Args:
            limit (int): Maximum number of recipes to process
            
        Returns:
            dict: Summary of results
        """
        logger.info(f"Starting ingredient update job (limit: {limit})")
        start_time = datetime.now()
        
        # Find recipes without ingredients
        recipes = self.find_recipes_without_ingredients(limit)
        
        if not recipes:
            logger.info("No recipes found that need ingredient updates")
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
                # Scrape ingredients from source URL
                ingredients = self.scrape_ingredients_from_url(
                    recipe['source_url'], 
                    recipe['source']
                )
                
                if ingredients:
                    # Update database
                    success = self.update_recipe_ingredients(recipe['id'], ingredients)
                    if success:
                        successful_updates += 1
                        logger.info(f"✅ Successfully updated: {recipe['title']}")
                    else:
                        failed_updates += 1
                        logger.error(f"❌ Failed to update database for: {recipe['title']}")
                else:
                    failed_updates += 1
                    logger.warning(f"⚠️ No ingredients found for: {recipe['title']}")
                    
            except Exception as e:
                failed_updates += 1
                logger.error(f"❌ Error processing {recipe['title']}: {str(e)}")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Summary
        summary = {
            'total_processed': len(recipes),
            'successful_updates': successful_updates,
            'failed_updates': failed_updates,
            'duration_seconds': duration
        }
        
        logger.info("=" * 60)
        logger.info("INGREDIENT UPDATE JOB COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Total recipes processed: {summary['total_processed']}")
        logger.info(f"Successful updates: {summary['successful_updates']}")
        logger.info(f"Failed updates: {summary['failed_updates']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return summary

def main():
    """Main function for running as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update missing recipe ingredients')
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
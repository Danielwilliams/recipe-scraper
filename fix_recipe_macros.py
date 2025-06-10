#!/usr/bin/env python3
"""
Fix Recipe Macros Script

This script identifies recipes with unrealistic or inconsistent macro values in the database
and attempts to correct them by:
1. Checking for discrepancies between 'nutrition' and 'nutrition_per_serving' fields
2. Re-scraping the source URL to get the correct nutrition data
3. Applying basic validation rules to ensure macros are realistic
4. Updating the database with corrected values

It can be run as a standalone script or as part of a GitHub Actions workflow.
"""

import logging
import json
import time
import requests
import traceback
import re
import sys
from bs4 import BeautifulSoup
from datetime import datetime
from database.db_connector import get_db_connection
import config

# Import scrapers
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
    filename='recipe_macro_fix.log',
    filemode='a'
)
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

class RecipeMacroFixer:
    """Identifies and fixes recipes with unrealistic or inconsistent macro values"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })
        
        # Initialize scrapers
        self.scrapers = {
            'SimplyRecipes': EnhancedSimplyRecipesScraper(),
            'Pinch of Yum': EnhancedPinchOfYumScraper(),
            'Host the Toast': HostTheToastScraper(),
            'Fit Fab Fodmap': FitFabFodmapScraper(),
            'Pickled Plum': PickledPlumScraper(),
            'MyProtein': MyProteinScraper(),
        }
        
        # Define validation ranges for macros
        self.validation_ranges = {
            'calories': {'min': 20, 'max': 1500},   # Per serving
            'protein': {'min': 0, 'max': 100},      # Grams per serving
            'carbs': {'min': 0, 'max': 150},        # Grams per serving
            'fat': {'min': 0, 'max': 100},          # Grams per serving
            'fiber': {'min': 0, 'max': 30},         # Grams per serving
            'sugar': {'min': 0, 'max': 100},        # Grams per serving
        }
    
    def find_recipes_with_unrealistic_macros(self, limit=50):
        """
        Find recipes with potentially unrealistic macro values

        Args:
            limit (int): Maximum number of recipes to process

        Returns:
            list: List of recipe dictionaries with id, title, source, source_url, macros
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Find recipes with suspicious macro values
                cursor.execute("""
                    SELECT 
                        sr.id, 
                        sr.title, 
                        sr.source, 
                        sr.source_url, 
                        sr.metadata
                    FROM 
                        scraped_recipes sr
                    WHERE 
                        sr.source_url IS NOT NULL
                        AND sr.source_url != ''
                        AND (
                            -- Metadata nutrition exists but has unrealistic values
                            (sr.metadata->'nutrition'->>'calories' IS NOT NULL AND (
                                (sr.metadata->'nutrition'->>'calories')::numeric < 20 OR 
                                (sr.metadata->'nutrition'->>'calories')::numeric > 2000 OR
                                (sr.metadata->'nutrition'->>'protein')::numeric > 200 OR
                                (sr.metadata->'nutrition'->>'carbs')::numeric > 300 OR
                                (sr.metadata->'nutrition'->>'fat')::numeric > 200
                            ))
                            -- Or metadata nutrition_per_serving exists but has unrealistic values
                            OR (sr.metadata->'nutrition_per_serving'->>'calories' IS NOT NULL AND (
                                (sr.metadata->'nutrition_per_serving'->>'calories')::numeric < 20 OR 
                                (sr.metadata->'nutrition_per_serving'->>'calories')::numeric > 2000 OR
                                (sr.metadata->'nutrition_per_serving'->>'protein')::numeric > 200 OR
                                (sr.metadata->'nutrition_per_serving'->>'carbs')::numeric > 300 OR
                                (sr.metadata->'nutrition_per_serving'->>'fat')::numeric > 200
                            ))
                            -- Or mismatch between nutrition and nutrition_per_serving
                            OR (
                                sr.metadata->'nutrition'->>'calories' IS NOT NULL AND
                                sr.metadata->'nutrition_per_serving'->>'calories' IS NOT NULL AND
                                ABS((sr.metadata->'nutrition'->>'calories')::numeric - 
                                    (sr.metadata->'nutrition_per_serving'->>'calories')::numeric) > 50
                            )
                        )
                    ORDER BY 
                        sr.id DESC
                    LIMIT %s
                """, (limit,))

                recipes = cursor.fetchall()
                logger.info(f"Found {len(recipes)} recipes with potentially unrealistic macros")

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
            logger.error(f"Error finding recipes with unrealistic macros: {str(e)}")
            logger.error(traceback.format_exc())
            return []
        finally:
            conn.close()
    
    def validate_macros(self, nutrition_data):
        """
        Check if nutrition values are within realistic ranges
        
        Args:
            nutrition_data (dict): Nutrition data with macros
            
        Returns:
            tuple: (is_valid, issues)
        """
        if not nutrition_data:
            return False, ["No nutrition data available"]
        
        issues = []
        
        # Convert all values to numeric
        for key, value in nutrition_data.items():
            if value is not None:
                try:
                    nutrition_data[key] = float(value)
                except (ValueError, TypeError):
                    issues.append(f"Invalid value for {key}: {value}")
        
        # Check if macro values are within realistic ranges
        for key, range_values in self.validation_ranges.items():
            if key in nutrition_data and nutrition_data[key] is not None:
                value = nutrition_data[key]
                if value < range_values['min'] or value > range_values['max']:
                    issues.append(f"{key} value {value} is outside realistic range ({range_values['min']}-{range_values['max']})")
        
        # Check if macronutrients add up to reasonable total calories (rough check)
        if all(key in nutrition_data for key in ['protein', 'carbs', 'fat', 'calories']):
            estimated_calories = (nutrition_data['protein'] * 4) + (nutrition_data['carbs'] * 4) + (nutrition_data['fat'] * 9)
            actual_calories = nutrition_data['calories']
            
            # Allow for a 30% margin of error
            if abs(estimated_calories - actual_calories) / actual_calories > 0.3:
                issues.append(f"Macros don't add up: estimated {estimated_calories} vs actual {actual_calories} calories")
        
        return len(issues) == 0, issues
    
    def scrape_recipe_nutrition(self, url, source):
        """
        Scrape nutrition data from a recipe URL
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source
            
        Returns:
            dict: Nutrition data
        """
        try:
            logger.info(f"Scraping nutrition data from: {url}")
            
            # Get the page content
            response = None
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Request error for {url}: {str(e)}")
                return {}
                
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check if we have a specialized scraper for this source
            if source in self.scrapers:
                scraper = self.scrapers[source]
                logger.info(f"Using enhanced {source} scraper")
                
                try:
                    # Use the enhanced scraper to extract recipe info
                    recipe_info = scraper._extract_recipe_info(response.text, url)
                    
                    if recipe_info and 'nutrition' in recipe_info and recipe_info['nutrition']:
                        logger.info(f"Successfully extracted nutrition using enhanced scraper: {recipe_info['nutrition']}")
                        return recipe_info['nutrition']
                        
                    logger.warning(f"Enhanced scraper failed to extract nutrition info")
                except Exception as e:
                    logger.error(f"Error with enhanced scraper for {source}: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # If we get here, enhanced scraper didn't work or we don't have one for this source
            # Try fallback methods
            nutrition = self._extract_nutrition_from_json_ld(soup)
            if nutrition:
                logger.info(f"Extracted nutrition from JSON-LD: {nutrition}")
                return nutrition
            
            # Try looking for structured nutrition data in the HTML
            nutrition = self._extract_nutrition_from_html(soup)
            if nutrition:
                logger.info(f"Extracted nutrition from HTML: {nutrition}")
                return nutrition
                
            logger.warning(f"Failed to extract nutrition data from {url}")
            return {}
            
        except Exception as e:
            logger.error(f"Error scraping nutrition data from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
    
    def _extract_nutrition_from_json_ld(self, soup):
        """
        Extract nutrition from JSON-LD structured data
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Nutrition data
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
                        
                        # If we found at least calories and one macro, return the nutrition
                        if 'calories' in nutrition and any(key in nutrition for key in ['protein', 'carbs', 'fat']):
                            return nutrition
                
                except Exception as e:
                    logger.debug(f"Error parsing nutrition from JSON-LD: {str(e)}")
                    continue
        
        except Exception as e:
            logger.debug(f"Error extracting nutrition from JSON-LD: {str(e)}")
        
        return nutrition
    
    def _extract_nutrition_from_html(self, soup):
        """
        Extract nutrition from HTML structure
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Nutrition data
        """
        nutrition = {}
        
        try:
            # Common selectors for nutrition sections
            nutrition_selectors = [
                '.nutrition-info',
                '.nutrition-facts',
                '.wprm-recipe-nutrition-container',
                '.recipe-nutrition',
                '[itemprop="nutrition"]',
                '.nutrition',
                '.nutritional-info',
                '.tasty-recipes-nutritional'
            ]
            
            for selector in nutrition_selectors:
                nutrition_section = soup.select_one(selector)
                if nutrition_section:
                    # Try to extract calories
                    calories_pattern = re.compile(r'calories[:\s]+(\d+)', re.IGNORECASE)
                    calories_match = calories_pattern.search(nutrition_section.text)
                    if calories_match:
                        nutrition['calories'] = int(calories_match.group(1))
                    
                    # Try to extract protein
                    protein_pattern = re.compile(r'protein[:\s]+(\d+(?:\.\d+)?)\s*g', re.IGNORECASE)
                    protein_match = protein_pattern.search(nutrition_section.text)
                    if protein_match:
                        nutrition['protein'] = float(protein_match.group(1))
                    
                    # Try to extract carbs
                    carbs_pattern = re.compile(r'carb(?:ohydrate)?s?[:\s]+(\d+(?:\.\d+)?)\s*g', re.IGNORECASE)
                    carbs_match = carbs_pattern.search(nutrition_section.text)
                    if carbs_match:
                        nutrition['carbs'] = float(carbs_match.group(1))
                    
                    # Try to extract fat
                    fat_pattern = re.compile(r'fat[:\s]+(\d+(?:\.\d+)?)\s*g', re.IGNORECASE)
                    fat_match = fat_pattern.search(nutrition_section.text)
                    if fat_match:
                        nutrition['fat'] = float(fat_match.group(1))
                    
                    # If we found at least calories and one macro, return the nutrition
                    if 'calories' in nutrition and any(key in nutrition for key in ['protein', 'carbs', 'fat']):
                        return nutrition
        
        except Exception as e:
            logger.debug(f"Error extracting nutrition from HTML: {str(e)}")
        
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
            
            match = re.search(r'(\d+(?:\.\d+)?)', str(value))
            if match:
                return float(match.group(1))
        except Exception:
            pass
        
        return None
    
    def fix_unrealistic_macros(self, recipe):
        """
        Fix unrealistic macro values for a recipe
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            dict: Updated metadata with fixed macros, or None if no fix needed/possible
        """
        recipe_id = recipe['id']
        title = recipe['title']
        source_url = recipe['source_url']
        source = recipe['source']
        metadata = recipe['metadata']
        
        logger.info(f"Processing recipe {recipe_id}: {title}")
        
        # Extract current nutrition data
        nutrition = metadata.get('nutrition', {})
        nutrition_per_serving = metadata.get('nutrition_per_serving', {})
        
        # Log current values
        logger.info(f"Current nutrition: {nutrition}")
        logger.info(f"Current nutrition_per_serving: {nutrition_per_serving}")
        
        # Check if either nutrition or nutrition_per_serving seems valid
        is_nutrition_valid, nutrition_issues = self.validate_macros(nutrition)
        is_nutrition_per_serving_valid, nutrition_per_serving_issues = self.validate_macros(nutrition_per_serving)
        
        logger.info(f"Nutrition valid: {is_nutrition_valid}, issues: {nutrition_issues}")
        logger.info(f"Nutrition per serving valid: {is_nutrition_per_serving_valid}, issues: {nutrition_per_serving_issues}")
        
        updated_metadata = metadata.copy()
        
        # If both are valid, make them consistent (use nutrition_per_serving as the truth)
        if is_nutrition_valid and is_nutrition_per_serving_valid:
            updated_metadata['nutrition'] = nutrition_per_serving.copy()
            logger.info(f"Both nutrition fields valid, using nutrition_per_serving as the truth")
            return updated_metadata
        
        # If only one is valid, use it for both
        elif is_nutrition_valid:
            updated_metadata['nutrition_per_serving'] = nutrition.copy()
            logger.info(f"Only nutrition field valid, using it for both")
            return updated_metadata
        
        elif is_nutrition_per_serving_valid:
            updated_metadata['nutrition'] = nutrition_per_serving.copy()
            logger.info(f"Only nutrition_per_serving valid, using it for both")
            return updated_metadata
        
        # If neither is valid, try to scrape fresh data
        logger.info(f"Neither nutrition field is valid, trying to scrape fresh data")
        scraped_nutrition = self.scrape_recipe_nutrition(source_url, source)
        
        # If we got valid nutrition data, update both fields
        if scraped_nutrition:
            is_scraped_valid, scraped_issues = self.validate_macros(scraped_nutrition)
            
            if is_scraped_valid:
                logger.info(f"Successfully scraped valid nutrition data: {scraped_nutrition}")
                updated_metadata['nutrition'] = scraped_nutrition
                updated_metadata['nutrition_per_serving'] = scraped_nutrition.copy()
                return updated_metadata
            else:
                logger.warning(f"Scraped nutrition data failed validation: {scraped_issues}")
        else:
            logger.warning(f"Failed to scrape nutrition data")
        
        # If we couldn't get valid data, check if we can fix the existing data
        fixed_nutrition = self._attempt_to_fix_nutrition(nutrition, nutrition_per_serving, metadata.get('servings'))
        
        if fixed_nutrition:
            is_fixed_valid, fixed_issues = self.validate_macros(fixed_nutrition)
            
            if is_fixed_valid:
                logger.info(f"Fixed nutrition data: {fixed_nutrition}")
                updated_metadata['nutrition'] = fixed_nutrition
                updated_metadata['nutrition_per_serving'] = fixed_nutrition.copy()
                return updated_metadata
            else:
                logger.warning(f"Fixed nutrition data failed validation: {fixed_issues}")
        
        # If we couldn't fix it, return None to indicate no fix was possible
        logger.warning(f"Unable to fix nutrition data for recipe {recipe_id}")
        return None
    
    def _attempt_to_fix_nutrition(self, nutrition, nutrition_per_serving, servings):
        """
        Attempt to fix nutrition data using existing values
        
        Args:
            nutrition (dict): Current nutrition data
            nutrition_per_serving (dict): Current nutrition per serving data
            servings (int): Number of servings
            
        Returns:
            dict: Fixed nutrition data or None if fix not possible
        """
        fixed_nutrition = {}
        
        # If we have servings and both nutrition fields, check if one is per recipe and one is per serving
        if servings and nutrition and nutrition_per_serving:
            try:
                servings = int(servings)
                
                # Check if nutrition values are roughly servings times nutrition_per_serving values
                if 'calories' in nutrition and 'calories' in nutrition_per_serving:
                    calories = float(nutrition['calories'])
                    calories_per_serving = float(nutrition_per_serving['calories'])
                    
                    # If nutrition is approximately servings times nutrition_per_serving
                    if 0.8 <= calories / (calories_per_serving * servings) <= 1.2:
                        logger.info(f"nutrition appears to be for whole recipe, nutrition_per_serving is correct")
                        return nutrition_per_serving
                    
                    # If nutrition_per_serving is approximately nutrition / servings
                    elif 0.8 <= calories_per_serving / (calories / servings) <= 1.2:
                        logger.info(f"nutrition appears to be correct, nutrition_per_serving may be wrong")
                        return nutrition
            except Exception as e:
                logger.debug(f"Error comparing nutrition values: {str(e)}")
        
        # Try to correct common errors like missing decimal points
        for source in [nutrition, nutrition_per_serving]:
            if not source:
                continue
            
            try:
                corrected = source.copy()
                
                # If calories are too low, try fixing missing decimal point in calories
                if 'calories' in corrected and 'protein' in corrected and 'carbs' in corrected and 'fat' in corrected:
                    calories = float(corrected['calories'])
                    protein = float(corrected['protein'])
                    carbs = float(corrected['carbs'])
                    fat = float(corrected['fat'])
                    
                    # Calculate estimated calories from macros
                    estimated_calories = (protein * 4) + (carbs * 4) + (fat * 9)
                    
                    # If actual calories are way too low
                    if calories < 50 and estimated_calories > 100:
                        # Maybe actual is missing a zero or two
                        if 0.8 <= (calories * 10) / estimated_calories <= 1.2:
                            corrected['calories'] = calories * 10
                            logger.info(f"Fixed missing zero in calories: {calories} -> {corrected['calories']}")
                        elif 0.8 <= (calories * 100) / estimated_calories <= 1.2:
                            corrected['calories'] = calories * 100
                            logger.info(f"Fixed missing two zeros in calories: {calories} -> {corrected['calories']}")
                
                # Check if corrected values pass validation
                is_valid, issues = self.validate_macros(corrected)
                if is_valid:
                    logger.info(f"Successfully fixed nutrition data: {corrected}")
                    return corrected
            except Exception as e:
                logger.debug(f"Error fixing nutrition values: {str(e)}")
        
        return None
    
    def update_recipe_metadata(self, recipe_id, updated_metadata):
        """
        Update a recipe's metadata in the database
        
        Args:
            recipe_id (int): Recipe ID
            updated_metadata (dict): Updated metadata with fixed macros
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not updated_metadata:
            return False
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Update the recipe's metadata
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET metadata = %s::jsonb
                    WHERE id = %s
                """, (json.dumps(updated_metadata), recipe_id))
                
                conn.commit()
                logger.info(f"Updated recipe {recipe_id} with fixed macros")
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating metadata for recipe {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def run_fix_job(self, limit=50):
        """
        Run the recipe macro fixing job
        
        Args:
            limit (int): Maximum number of recipes to process
            
        Returns:
            dict: Summary of results
        """
        logger.info(f"Starting recipe macro fixing job (limit: {limit})")
        start_time = datetime.now()
        
        # Find recipes with unrealistic macros
        recipes = self.find_recipes_with_unrealistic_macros(limit)
        
        if not recipes:
            logger.info("No recipes found with unrealistic macros")
            return {
                'total_processed': 0,
                'successful_fixes': 0,
                'failed_fixes': 0,
                'duration_seconds': 0
            }
        
        successful_fixes = 0
        failed_fixes = 0
        
        for i, recipe in enumerate(recipes, 1):
            logger.info(f"Processing recipe {i}/{len(recipes)}: {recipe['title']}")
            
            try:
                # Try to fix the macros
                updated_metadata = self.fix_unrealistic_macros(recipe)
                
                if updated_metadata:
                    # Update database
                    success = self.update_recipe_metadata(recipe['id'], updated_metadata)
                    
                    if success:
                        successful_fixes += 1
                        logger.info(f"✅ Successfully fixed macros for: {recipe['title']}")
                    else:
                        failed_fixes += 1
                        logger.error(f"❌ Failed to update database for: {recipe['title']}")
                else:
                    failed_fixes += 1
                    logger.warning(f"⚠️ Unable to fix macros for: {recipe['title']}")
                    
                # Be polite - don't hammer the server
                time.sleep(2)
                    
            except Exception as e:
                failed_fixes += 1
                logger.error(f"❌ Error processing {recipe['title']}: {str(e)}")
                logger.error(traceback.format_exc())
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Summary
        summary = {
            'total_processed': len(recipes),
            'successful_fixes': successful_fixes,
            'failed_fixes': failed_fixes,
            'duration_seconds': duration
        }
        
        logger.info("=" * 60)
        logger.info("RECIPE MACRO FIXING JOB COMPLETED")
        logger.info("=" * 60)
        logger.info(f"Total recipes processed: {summary['total_processed']}")
        logger.info(f"Successful fixes: {summary['successful_fixes']}")
        logger.info(f"Failed fixes: {summary['failed_fixes']}")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        return summary

def main():
    """Main function for running as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix unrealistic recipe macros')
    parser.add_argument('--limit', type=int, default=50, 
                       help='Maximum number of recipes to process (default: 50)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without updating the database')
    
    args = parser.parse_args()
    
    fixer = RecipeMacroFixer()
    
    if args.dry_run:
        logger.info("Running in dry-run mode - no database updates will be performed")
        # Just find and analyze recipes without updating
        recipes = fixer.find_recipes_with_unrealistic_macros(limit=args.limit)
        for recipe in recipes:
            updated_metadata = fixer.fix_unrealistic_macros(recipe)
            if updated_metadata:
                logger.info(f"Would update recipe {recipe['id']}: {recipe['title']}")
            else:
                logger.info(f"Would NOT update recipe {recipe['id']}: {recipe['title']}")
    else:
        # Run the full job
        results = fixer.run_fix_job(limit=args.limit)
        
        # Exit with error code if all fixes failed
        if results['total_processed'] > 0 and results['successful_fixes'] == 0:
            sys.exit(1)

if __name__ == "__main__":
    main()
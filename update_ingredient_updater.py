#!/usr/bin/env python3
"""
Script to update ingredient_updater.py to correctly use enhanced scrapers
"""

import os
import shutil

def read_file(file_path):
    with open(file_path, 'r') as f:
        return f.read()

def write_file(file_path, content):
    with open(file_path, 'w') as f:
        f.write(content)

def update_file(file_path, old_content, new_content):
    if os.path.exists(file_path):
        content = read_file(file_path)
        if old_content in content:
            content = content.replace(old_content, new_content)
            write_file(file_path, content)
            print(f"Updated {file_path}")
            return True
        else:
            print(f"Could not find the pattern to replace in {file_path}")
            return False
    else:
        print(f"File not found: {file_path}")
        return False

def main():
    # Path to ingredient updater
    updater_path = "ingredient_updater.py"
    
    # Backup the file
    backup_path = "ingredient_updater.py.bak"
    if os.path.exists(updater_path):
        shutil.copy2(updater_path, backup_path)
        print(f"Created backup at {backup_path}")
    
    # Update the scrape_ingredients_from_url method
    old_method = """    def scrape_ingredients_from_url(self, url, source):
        \"\"\"
        Scrape ingredients from a recipe URL using the appropriate enhanced scraper
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source (e.g., 'SimplyRecipes', 'Pinch of Yum')
            
        Returns:
            list: List of ingredient strings
        \"\"\"
        try:
            logger.info(f"Scraping ingredients from: {url}")
            
            # Check if we have an enhanced scraper for this source
            if source in self.scrapers:
                scraper = self.scrapers[source]
                logger.info(f"Using enhanced {source} scraper")
                
                # Use the scraper to get the recipe
                recipe_info = scraper._scrape_recipe(url)
                
                if recipe_info and 'ingredients' in recipe_info and recipe_info['ingredients']:
                    logger.info(f"Successfully extracted {len(recipe_info['ingredients'])} ingredients using enhanced scraper")
                    return recipe_info['ingredients']
                else:
                    logger.warning(f"Enhanced scraper for {source} failed to extract ingredients")
            
            # Fallback to legacy scraping method if no enhanced scraper or enhanced scraper failed
            logger.info(f"Falling back to generic scraping for {source}")
            return self._legacy_scrape_ingredients(url, source)
            
        except Exception as e:
            logger.error(f"Error scraping ingredients from {url}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []"""
    
    new_method = """    def scrape_ingredients_from_url(self, url, source):
        \"\"\"
        Scrape ingredients from a recipe URL using the appropriate enhanced scraper
        
        Args:
            url (str): Recipe URL
            source (str): Recipe source (e.g., 'SimplyRecipes', 'Pinch of Yum')
            
        Returns:
            list: List of ingredient strings
        \"\"\"
        try:
            logger.info(f"Scraping ingredients from: {url}")
            
            # Check if we have an enhanced scraper for this source
            if source in self.scrapers:
                scraper = self.scrapers[source]
                logger.info(f"Using enhanced {source} scraper")
                
                try:
                    # Get the page content
                    response = requests.get(url, headers=self.session.headers, timeout=config.REQUEST_TIMEOUT)
                    response.raise_for_status()
                    
                    # Extract recipe info directly
                    recipe_info = scraper._extract_recipe_info(response.text, url)
                    
                    if recipe_info and 'ingredients' in recipe_info and recipe_info['ingredients']:
                        logger.info(f"Successfully extracted {len(recipe_info['ingredients'])} ingredients using enhanced scraper")
                        return recipe_info['ingredients']
                    else:
                        logger.warning(f"Enhanced scraper extract_recipe_info failed, trying direct extraction")
                        
                        # For Pinch of Yum, try to extract ingredients directly
                        if source == 'Pinch of Yum':
                            # Parse the HTML
                            soup = BeautifulSoup(response.text, 'lxml')
                            
                            # Try direct extraction of ingredients with modern format
                            tasty_container = soup.select_one('.tasty-recipes')
                            if tasty_container:
                                # First try the modern format with checkboxes
                                ingredients = []
                                checkbox_ingredients = tasty_container.select('li[data-tr-ingredient-checkbox]')
                                if checkbox_ingredients:
                                    logger.info(f"Found {len(checkbox_ingredients)} ingredients with modern checkbox format")
                                    for item in checkbox_ingredients:
                                        ingredient_text = item.get_text().strip()
                                        if ingredient_text:
                                            ingredients.append(ingredient_text)
                                    
                                    if ingredients:
                                        logger.info(f"Successfully extracted {len(ingredients)} ingredients using direct extraction")
                                        return ingredients
                                
                                # Try JSON-LD
                                json_ld_scripts = soup.select('script[type="application/ld+json"]')
                                for script in json_ld_scripts:
                                    try:
                                        data = json.loads(script.string)
                                        
                                        # Look for Recipe type
                                        if isinstance(data, dict) and data.get('@type') == 'Recipe' and 'recipeIngredient' in data:
                                            ingredients = data['recipeIngredient']
                                            logger.info(f"Found {len(ingredients)} ingredients in JSON-LD")
                                            return ingredients
                                        elif isinstance(data, list):
                                            for item in data:
                                                if isinstance(item, dict) and item.get('@type') == 'Recipe' and 'recipeIngredient' in item:
                                                    ingredients = item['recipeIngredient']
                                                    logger.info(f"Found {len(ingredients)} ingredients in JSON-LD array")
                                                    return ingredients
                                    except Exception as e:
                                        logger.error(f"Error parsing JSON-LD: {str(e)}")
                                        continue
                except Exception as e:
                    logger.error(f"Error during direct extraction: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # Fallback to legacy scraping method if no enhanced scraper or enhanced scraper failed
            logger.info(f"Falling back to generic scraping for {source}")
            return self._legacy_scrape_ingredients(url, source)
            
        except Exception as e:
            logger.error(f"Error scraping ingredients from {url}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []"""
    
    # Update the file
    updated = update_file(updater_path, old_method, new_method)
    
    if updated:
        print("Successfully updated the ingredient_updater.py file with improved scraping logic.")
    else:
        print("Failed to update the ingredient_updater.py file.")

if __name__ == "__main__":
    main()
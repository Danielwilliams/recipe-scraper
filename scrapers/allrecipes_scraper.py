import requests
import time
import logging
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup
import traceback

# Import database connection from your existing db_connector
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('allrecipes_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class AllRecipesScraper:
    def __init__(self):
        """
        Initialize the AllRecipes scraper with headers and category URLs
        """
        logger.info("Initializing AllRecipes Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # List of category URLs to scrape
        self.category_urls = [
            "https://www.allrecipes.com/recipes/76/appetizers-and-snacks/",
            "https://www.allrecipes.com/recipes/80/main-dish/",
            "https://www.allrecipes.com/recipes/78/breakfast-and-brunch/",
            "https://www.allrecipes.com/recipes/17561/lunch/",
            "https://www.allrecipes.com/recipes/94/soups-stews-and-chili/",
            "https://www.allrecipes.com/recipes/96/salad/",
            "https://www.allrecipes.com/recipes/156/bread/",
            "https://www.allrecipes.com/recipes/79/desserts/",
            "https://www.allrecipes.com/recipes/1947/everyday-cooking/quick-and-easy/"
        ]
        
        logger.info(f"Initialized with {len(self.category_urls)} category URLs")

    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes

        Args:
            iso_duration (str): ISO 8601 duration string

        Returns:
            int: Duration in minutes or None
        """
        if not iso_duration:
            return None
        
        try:
            # Handle PT1H30M format (ISO 8601 duration)
            match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                return hours * 60 + minutes
            
            return None
        except Exception as e:
            logger.error(f"Error parsing ISO duration {iso_duration}: {str(e)}")
            return None

    def _parse_time_text(self, time_text):
        """
        Parse time text like "30 mins" or "1 hr 15 mins" into minutes
        
        Args:
            time_text (str): Time text to parse
            
        Returns:
            int: Time in minutes or None if parsing fails
        """
        if not time_text:
            return None
        
        total_minutes = 0
        
        # Look for hours
        hr_match = re.search(r'(\d+)\s*(?:hour|hr)s?', time_text, re.IGNORECASE)
        if hr_match:
            total_minutes += int(hr_match.group(1)) * 60
        
        # Look for minutes
        min_match = re.search(r'(\d+)\s*(?:minute|min)s?', time_text, re.IGNORECASE)
        if min_match:
            total_minutes += int(min_match.group(1))
        
        return total_minutes if total_minutes > 0 else None

    def scrape(self, limit=100):
        """
        Scrape recipes from AllRecipes
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting AllRecipes scraping with limit: {limit}")
        recipes = []
        recipes_per_category = max(3, limit // len(self.category_urls))  # Distribute limit across categories
        
        # Loop through each category URL
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
                break
                
            try:
                logger.info(f"Scraping category page: {category_url}")
                
                response = requests.get(category_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Error accessing URL: {category_url} - Status code: {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find all recipe card links - try different selectors
                recipe_links = []
                
                # Try different possible selectors for the links
                selectors = [
                    'a.card__titleLink', 
                    'a.mntl-card-list-items__link',
                    'a.comp.mntl-card-list-items.mntl-document-card',
                    '.mntl-card-list-items .card__title a',
                    '.card__content a',
                    '.card__title a',
                    '.mntl-card-title',
                    '.card-list__title a',
                    'a[data-doc-id]',
                    'a.link-list__link',
                    'a[href*="/recipe/"]'  # This more generic selector will catch many recipe links
                ]
                
                for selector in selectors:
                    links = soup.select(selector)
                    logger.info(f"Found {len(links)} links with selector: {selector}")
                    
                    for link in links:
                        href = link.get('href')
                        if href and '/recipe/' in href:
                            recipe_links.append(href)
                
                # Remove duplicates
                recipe_links = list(set(recipe_links))
                logger.info(f"Found {len(recipe_links)} unique recipe links in {category_url}")
                
                # Process only up to recipes_per_category for this category
                category_count = 0
                for url in recipe_links:
                    if len(recipes) >= limit or category_count >= recipes_per_category:
                        logger.info(f"Reached limit for category {category_url}")
                        break
                        
                    try:
                        # Make sure URL is absolute
                        if not url.startswith('http'):
                            url = "https://www.allrecipes.com" + url
                        
                        logger.info(f"Scraping recipe: {url}")
                        
                        recipe_response = requests.get(url, headers=self.headers, timeout=30)
                        if recipe_response.status_code != 200:
                            logger.error(f"Error accessing recipe URL: {url} - Status: {recipe_response.status_code}")
                            continue
                        
                        recipe_info = self._extract_recipe_info(recipe_response.text, url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            category_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info['title']}")
                        
                        # Be polite - don't hammer the server
                        time.sleep(3)
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Be polite between categories
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error scraping category page {category_url}: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"Total recipes scraped: {len(recipes)}")
        return recipes

    def _extract_recipe_info(self, html_content, url):
        """
        Extract structured recipe information from HTML
        
        Args:
            html_content (str): HTML content of the recipe page
            url (str): URL of the recipe
            
        Returns:
            dict: Extracted recipe information
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        try:
            # First try to extract from JSON-LD (original method)
            recipe_info = self._extract_from_json_ld(soup, url)
            
            # If JSON-LD extraction failed, fallback to HTML parsing
            if not recipe_info:
                logger.info(f"Falling back to HTML parsing for {url}")
                recipe_info = self._extract_from_html(soup, url, html_content)
            
            return recipe_info
                
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def _extract_from_json_ld(self, soup, url):
        """
        Extract recipe data from JSON-LD
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): URL of the recipe
            
        Returns:
            dict: Extracted recipe information or None
        """
        script_tag = soup.find('script', {'type': 'application/ld+json'})
        if not script_tag:
            logger.warning(f"No JSON-LD data found in {url}")
            return None
        
        try:
            json_data = json.loads(script_tag.string)
            
            # Sometimes the data is in an array
            if isinstance(json_data, list):
                recipe_data = next((item for item in json_data if item.get('@type') == 'Recipe'), None)
            else:
                recipe_data = json_data if json_data.get('@type') == 'Recipe' else None
            
            if not recipe_data:
                logger.warning(f"No recipe data found in JSON-LD for {url}")
                return None
            
            # Extract basic recipe information
            title = recipe_data.get('name', 'Untitled Recipe')
            
            # Extract ingredients
            ingredients = recipe_data.get('recipeIngredient', [])
            
            # Extract instructions
            instructions = []
            instruction_data = recipe_data.get('recipeInstructions', [])
            
            if isinstance(instruction_data, list):
                for step in instruction_data:
                    if isinstance(step, dict) and 'text' in step:
                        instructions.append(step['text'])
                    elif isinstance(step, str):
                        instructions.append(step)
            
            # Skip recipes with minimal information
            if len(ingredients) < 3 or len(instructions) < 2:
                logger.warning(f"Recipe has too few ingredients or instructions in JSON-LD: {url}")
                return None
            
            # Extract metadata
            metadata = {}
            
            # Prep time
            if 'prepTime' in recipe_data:
                prep_time = recipe_data['prepTime']
                # Convert ISO duration to minutes
                minutes = self._parse_iso_duration(prep_time)
                if minutes:
                    metadata['prep_time'] = minutes
            
            # Cook time
            if 'cookTime' in recipe_data:
                cook_time = recipe_data['cookTime']
                # Convert ISO duration to minutes
                minutes = self._parse_iso_duration(cook_time)
                if minutes:
                    metadata['cook_time'] = minutes
            
            # Total time
            if 'totalTime' in recipe_data:
                total_time = recipe_data['totalTime']
                # Convert ISO duration to minutes
                minutes = self._parse_iso_duration(total_time)
                if minutes:
                    metadata['total_time'] = minutes
            
            # Servings
            if 'recipeYield' in recipe_data:
                servings = recipe_data['recipeYield']
                if isinstance(servings, list):
                    servings = servings[0]
                # Try to extract number
                servings_match = re.search(r'(\d+)', str(servings))
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Categories and keywords
            categories = []
            if 'recipeCategory' in recipe_data:
                categories.extend(recipe_data['recipeCategory'] if isinstance(recipe_data['recipeCategory'], list) else [recipe_data['recipeCategory']])
            
            if 'recipeCuisine' in recipe_data:
                cuisine = recipe_data['recipeCuisine']
                if isinstance(cuisine, list):
                    cuisine = cuisine[0] if cuisine else None
                metadata['cuisine'] = cuisine
            
            tags = []
            if 'keywords' in recipe_data:
                keywords = recipe_data['keywords']
                if isinstance(keywords, str):
                    tags = [k.strip() for k in keywords.split(',')]
                elif isinstance(keywords, list):
                    tags = keywords
            
            # Determine complexity based on number of ingredients and steps
            complexity = "easy"
            if len(ingredients) >= 10 or len(instructions) >= 7:
                complexity = "complex"
            elif len(ingredients) >= 6 or len(instructions) >= 4:
                complexity = "medium"
            
            # UPDATED: Extract image URL with better handling
            image_url = None
            if 'image' in recipe_data:
                image_data = recipe_data['image']
                if isinstance(image_data, list) and image_data:
                    # Handle array of images - take the first one
                    first_image = image_data[0]
                    if isinstance(first_image, dict) and 'url' in first_image:
                        image_url = first_image['url']
                    else:
                        image_url = first_image
                elif isinstance(image_data, dict) and 'url' in image_data:
                    # Handle image object with url property
                    image_url = image_data['url']
                else:
                    # Handle direct image URL
                    image_url = image_data
            
            # If no image in JSON-LD, try to find it in HTML
            if not image_url:
                og_image = soup.find('meta', {'property': 'og:image'})
                if og_image:
                    image_url = og_image.get('content')
                
                if not image_url:
                    img_tag = soup.find('img', {'class': 'primary-image__image'}) or \
                              soup.find('img', {'class': 'recipe-lead-image'}) or \
                              soup.find('img', {'data-src': True, 'alt': lambda x: x and 'recipe' in x.lower()})
                    if img_tag:
                        image_url = img_tag.get('src') or img_tag.get('data-src')
            
            # Return the parsed recipe data
            return {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'AllRecipes',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'metadata': metadata,
                'raw_content': ''  # Placeholder, full content can be added if needed
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON-LD in {url}: {str(e)}")
            return None 

    def _extract_from_html(self, soup, url, html_content=None):
        """
        Extract recipe information from HTML using direct parsing
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): URL of the recipe
            html_content (str, optional): Raw HTML content
            
        Returns:
            dict: Extracted recipe information
        """
        try:
            # Extract title
            title_elem = soup.select_one('h1')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients
            ingredients = []
            ingredient_elems = soup.select('.mm-recipes-structured-ingredients__list-item')
            for elem in ingredient_elems:
                quantity_elem = elem.select_one('[data-ingredient-quantity="true"]')
                unit_elem = elem.select_one('[data-ingredient-unit="true"]')
                name_elem = elem.select_one('[data-ingredient-name="true"]')
                
                ingredient_text = ""
                if quantity_elem:
                    ingredient_text += quantity_elem.text.strip() + " "
                if unit_elem:
                    ingredient_text += unit_elem.text.strip() + " "
                if name_elem:
                    ingredient_text += name_elem.text.strip()
                
                if ingredient_text.strip():
                    ingredients.append(ingredient_text.strip())
            
            # Extract instructions
            instructions = []
            instruction_elems = soup.select('.mm-recipes-steps .mntl-sc-block-group--LI p')
            for elem in instruction_elems:
                step = elem.text.strip()
                if step:
                    instructions.append(step)
            
            # Extract metadata
            metadata = {}
            
            # Time details
            time_details = soup.select('.mm-recipes-details__item')
            for detail in time_details:
                label_elem = detail.select_one('.mm-recipes-details__label')
                value_elem = detail.select_one('.mm-recipes-details__value')
                
                if label_elem and value_elem:
                    label = label_elem.text.strip().lower()
                    value = value_elem.text.strip()
                    
                    time_match = re.search(r'(\d+)\s*(mins?|hrs?)?', value, re.IGNORECASE)
                    if time_match:
                        time_value = int(time_match.group(1))
                        time_unit = time_match.group(2) or 'mins'
                        
                        if 'hr' in time_unit.lower():
                            time_value *= 60
                        
                        if 'prep time' in label:
                            metadata['prep_time'] = time_value
                        elif 'cook time' in label:
                            metadata['cook_time'] = time_value
                        elif 'total time' in label:
                            metadata['total_time'] = time_value
                    
                    # Servings
                    if 'servings' in label or 'yield' in label:
                        servings_match = re.search(r'(\d+)', value)
                        if servings_match:
                            metadata['servings'] = int(servings_match.group(1))
            
            # Extract nutrition information
            nutrition = self._extract_nutrition(soup)
            
            # Extract image URL
            image_elem = soup.select_one('.primary-image__image')
            image_url = image_elem.get('src') if image_elem else None
            
            # Determine complexity
            complexity = "easy"
            if len(ingredients) >= 10 or len(instructions) >= 7:
                complexity = "complex"
            elif len(ingredients) >= 6 or len(instructions) >= 4:
                complexity = "medium"
            
            # Extract breadcrumb/categories/cuisine
            categories = []
            breadcrumbs = soup.select('.mntl-breadcrumbs__link')
            for crumb in breadcrumbs:
                crumb_text = crumb.text.strip()
                if crumb_text and crumb_text.lower() not in ['home', 'recipes']:
                    categories.append(crumb_text)
            
            # Infer cuisine
            cuisine = None
            known_cuisines = ['Italian', 'Mexican', 'Chinese', 'Indian', 
                              'Japanese', 'Thai', 'French', 'Greek', 
                              'Mediterranean', 'Spanish', 'Korean', 'Vietnamese']
            
            for crumb in categories:
                if crumb in known_cuisines:
                    cuisine = crumb
                    break
            
            # Generate tags
            tags = []
            
            # Combine text for tag generation
            combined_text = (
                title + ' ' + 
                ' '.join(ingredients) + ' ' + 
                ' '.join(instructions)
            ).lower()
            
            # Diet and meal type tags
            diet_terms = [
                'vegetarian', 'vegan', 'gluten-free', 'dairy-free', 
                'keto', 'paleo', 'low-carb', 'low-fat', 'sugar-free'
            ]
            meal_types = [
                'breakfast', 'lunch', 'dinner', 'appetizer', 
                'dessert', 'snack', 'salad', 'soup'
            ]
            
            for term in diet_terms:
                if term in combined_text:
                    tags.append(term)
            
            for meal in meal_types:
                if meal in combined_text:
                    tags.append(meal)
            
            tags.append(complexity + ' recipe')
            
            # If cuisine found, add to tags
            if cuisine:
                tags.append(cuisine.lower())
            
            # Build recipe dictionary
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'AllRecipes',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'categories': categories,
                'cuisine': cuisine,
                'tags': list(set(tags)),
                'image_url': image_url,
                'metadata': metadata,
                'nutrition': nutrition,
                'raw_content': html_content[:5000]  # Limit raw content
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _extract_nutrition(self, soup):
        """
        Extract detailed nutrition information from the page
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            
        Returns:
            dict: Nutrition information
        """
        try:
            # Find the nutrition facts table
            nutrition_table = soup.select_one('.mm-recipes-nutrition-facts-summary__table')
            
            if not nutrition_table:
                return None
            
            # Initialize nutrition data dictionary
            nutrition_data = {
                'calories': None,
                'fat': None,
                'carbs': None,
                'protein': None,
                'saturated_fat': None,
                'cholesterol': None,
                'sodium': None,
                'fiber': None,
                'sugars': None
            }
            
            # Extract nutrition values from table rows
            rows = nutrition_table.select('.mm-recipes-nutrition-facts-summary__table-row')
            for row in rows:
                value_cell = row.select_one('.mm-recipes-nutrition-facts-summary__table-cell.text-body-100-prominent')
                label_cell = row.select_one('.mm-recipes-nutrition-facts-summary__table-cell.text-body-100')
                
                if value_cell and label_cell:
                    value = value_cell.text.strip().rstrip('g ')
                    label = label_cell.text.strip().lower()
                    
                    try:
                        # Convert to float, removing any non-numeric characters
                        numeric_value = float(value)
                        
                        # Map labels to nutrition keys
                        if 'calories' in label:
                            nutrition_data['calories'] = numeric_value
                        elif 'fat' in label and 'saturated' not in label:
                            nutrition_data['fat'] = numeric_value
                        elif 'saturated fat' in label:
                            nutrition_data['saturated_fat'] = numeric_value
                        elif 'carbs' in label:
                            nutrition_data['carbs'] = numeric_value
                        elif 'protein' in label:
                            nutrition_data['protein'] = numeric_value
                        elif 'cholesterol' in label:
                            nutrition_data['cholesterol'] = numeric_value
                        elif 'sodium' in label:
                            nutrition_data['sodium'] = numeric_value
                        elif 'fiber' in label:
                            nutrition_data['fiber'] = numeric_value
                        elif 'sugars' in label:
                            nutrition_data['sugars'] = numeric_value
                    except (ValueError, TypeError):
                        pass  # Skip if conversion fails
            
            logger.info(f"Extracted nutrition data: {nutrition_data}")
            return nutrition_data
        
        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            return None

    def save_recipe(self, recipe):
        """
        Save a recipe to the database
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            int: Recipe ID if successful, None otherwise
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check if recipe already exists
                cursor.execute("""
                    SELECT id FROM scraped_recipes
                    WHERE title = %s AND source = %s
                    LIMIT 1
                """, (recipe['title'], recipe['source']))
                
                existing = cursor.fetchone()
                if existing:
                    logger.info(f"Recipe already exists: {recipe['title']}")
                    return existing[0]
                
                # Extract metadata fields for logging and clarity
                metadata = recipe.get('metadata', {})
                prep_time = metadata.get('prep_time')
                cook_time = metadata.get('cook_time')
                total_time = metadata.get('total_time')
                servings = metadata.get('servings')
                
                # Log the extracted times
                logger.info(f"Saving recipe '{recipe['title']}' with prep_time={prep_time}, cook_time={cook_time}")
                
                # Insert recipe
                cursor.execute("""
                    INSERT INTO scraped_recipes (
                        title, source, source_url, instructions, date_scraped, date_processed,
                        complexity, prep_time, cook_time, total_time, servings, cuisine,
                        is_verified, raw_content, metadata, image_url, categories
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    recipe['title'],
                    recipe['source'],
                    recipe['source_url'],
                    json.dumps(recipe['instructions']),
                    datetime.now(),
                    datetime.now(),
                    recipe['complexity'],
                    prep_time,
                    cook_time,
                    total_time,
                    servings,
                    recipe.get('cuisine'),
                    False,  # Not verified initially
                    recipe.get('raw_content', '')[:5000],  # Limit raw content size
                    json.dumps(metadata),
                    recipe.get('image_url'),
                    json.dumps(recipe.get('categories', []))
                ))
                
                recipe_id = cursor.fetchone()[0]
                
                # Insert ingredients
                if 'ingredients' in recipe and recipe['ingredients']:
                    for ing in recipe['ingredients']:
                        # Handle structured ingredient parsing
                        if isinstance(ing, dict):
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, amount, unit, notes, category)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                recipe_id,
                                ing.get('name', ''),
                                str(ing.get('amount')) if ing.get('amount') is not None else None,
                                ing.get('unit'),
                                ing.get('notes'),
                                ing.get('category', 'unknown')
                            ))
                        else:
                            # Fallback for string ingredients
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, category)
                                VALUES (%s, %s, %s)
                            """, (
                                recipe_id,
                                str(ing),
                                'unknown'
                            ))
                
                # Insert tags
                if 'tags' in recipe and recipe['tags']:
                    for tag in recipe['tags']:
                        cursor.execute("""
                            INSERT INTO recipe_tags
                            (recipe_id, tag)
                            VALUES (%s, %s)
                        """, (
                            recipe_id,
                            tag
                        ))
                
                # Insert comprehensive nutrition information
                if recipe.get('nutrition'):
                    nutrition = recipe['nutrition']
                    cursor.execute("""
                        INSERT INTO recipe_nutrition (
                            recipe_id, calories, protein, carbs, fat, 
                            saturated_fat, cholesterol, sodium, 
                            total_sugars, fiber, 
                            potassium, is_calculated
                        ) VALUES (
                            %s, %s, %s, %s, %s, 
                            %s, %s, %s, 
                            %s, %s, 
                            %s, %s
                        )
                    """, (
                        recipe_id,
                        nutrition.get('calories'),
                        nutrition.get('protein'),
                        nutrition.get('carbs'),
                        nutrition.get('fat'),
                        nutrition.get('saturated_fat'),
                        nutrition.get('cholesterol'),
                        nutrition.get('sodium'),
                        nutrition.get('sugars'),
                        nutrition.get('fiber'),
                        nutrition.get('potassium'),
                        True
                    ))
                
                conn.commit()
                logger.info(f"Saved recipe '{recipe['title']}' with ID {recipe_id}")
                return recipe_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
            logger.error(traceback.format_exc())
            return None
        finally:
            conn.close()

# If this script is run directly, create tables
if __name__ == "__main__":
    from database.db_connector import create_tables_if_not_exist
    create_tables_if_not_exist()
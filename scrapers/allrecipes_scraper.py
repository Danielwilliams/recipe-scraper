# scrapers/allrecipes_scraper.py
import requests
import time
import logging
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class AllRecipesScraper:
    def __init__(self):
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
    
    def scrape(self, limit=50):
        """Scrape recipes from AllRecipes"""
        recipes = []
        recipes_per_category = max(3, limit // len(self.category_urls))  # Distribute limit across categories
        
        # Loop through each category URL
        for category_url in self.category_urls:
            if len(recipes) >= limit:
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
                
                # Be polite between categories
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error scraping category page {category_url}: {str(e)}")
        
        logger.info(f"Total recipes scraped: {len(recipes)}")
        return recipes
    
    def _extract_recipe_info(self, html_content, url):
        """Extract structured recipe information from HTML"""
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
            return None
    
    def _extract_from_json_ld(self, soup, url):
        """Extract recipe data from JSON-LD"""
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
            
            return {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'AllRecipes',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'tags': tags,
                'categories': categories,
                'metadata': metadata,
                'raw_content': html_content[:1000]  # Store just a portion to save space
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON-LD in {url}: {str(e)}")
            return None
    
    def _extract_from_html(self, soup, url, html_content=None):
        """Extract recipe data from HTML structure when JSON-LD fails"""
        try:
            # If html_content wasn't passed, get it from the soup object
            if html_content is None:
                html_content = str(soup)[:1000]  # Just store the first 1000 chars to save space
                
            # Extract title
            title_elem = soup.select_one('h1')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients - using the structure you found
            ingredients = []
            ingredient_items = soup.select('.mm-recipes-structured-ingredients__list-item')
            
            if ingredient_items:
                for item in ingredient_items:
                    quantity = item.select_one('[data-ingredient-quantity]')
                    unit = item.select_one('[data-ingredient-unit]')
                    name = item.select_one('[data-ingredient-name]')
                    
                    if name:
                        ingredient_text = ""
                        if quantity:
                            ingredient_text += quantity.text.strip() + " "
                        if unit:
                            ingredient_text += unit.text.strip() + " "
                        if name:
                            ingredient_text += name.text.strip()
                        
                        ingredients.append(ingredient_text.strip())
            
            # If we didn't find ingredients with the modern structure, try alternative selectors
            if not ingredients:
                # Try other selectors for ingredients
                alt_selectors = [
                    '.ingredients-item-name',
                    '.ingredients-section .paragraph',
                    '.ingredients-section li',
                    '.ingredient-lists .ingredients-item',
                    '[itemprop="recipeIngredient"]'
                ]
                
                for selector in alt_selectors:
                    ing_elements = soup.select(selector)
                    if ing_elements:
                        ingredients = [elem.text.strip() for elem in ing_elements if elem.text.strip()]
                        if ingredients:
                            break
            
            # Extract instructions
            instructions = []
            
            # Try the modern structure first
            instruction_items = soup.select('.mm-recipes-steps .mntl-sc-block-group--LI p')
            
            if instruction_items:
                for item in instruction_items:
                    step = item.text.strip()
                    if step:
                        instructions.append(step)
            
            # If we didn't find instructions with the modern structure, try alternative selectors
            if not instructions:
                # Try other selectors for instructions
                alt_selectors = [
                    '.instructions-section .paragraph',
                    '.recipe-instructions .paragraph',
                    '.directions-list li',
                    '.recipe-directions__list--item',
                    '[itemprop="recipeInstructions"] li',
                    '.instructions-section ol li'
                ]
                
                for selector in alt_selectors:
                    instr_elements = soup.select(selector)
                    if instr_elements:
                        instructions = [elem.text.strip() for elem in instr_elements if elem.text.strip()]
                        if instructions:
                            break
            
            # Skip recipes with minimal information
            if len(ingredients) < 3 or len(instructions) < 2:
                logger.warning(f"Recipe has too few ingredients or instructions from HTML: {url}")
                return None
            
            # Extract metadata
            metadata = {}
            
            # Try different methods to extract prep and cook times
            time_selectors = {
                'prep_time': ['[data-testid="prep-time"]', '.recipe-meta-item:contains("Prep Time")'],
                'cook_time': ['[data-testid="cook-time"]', '.recipe-meta-item:contains("Cook Time")'],
                'total_time': ['[data-testid="total-time"]', '.recipe-meta-item:contains("Total Time")']
            }
            
            for time_type, selectors in time_selectors.items():
                for selector in selectors:
                    time_elem = None
                    if ':contains' in selector:
                        # BeautifulSoup doesn't directly support :contains, so we need a different approach
                        key_text = selector.split(':contains("')[1].split('")')[0]
                        meta_items = soup.select('.recipe-meta-item')
                        for item in meta_items:
                            if key_text in item.text:
                                time_elem = item
                                break
                    else:
                        time_elem = soup.select_one(selector)
                    
                    if time_elem:
                        time_text = time_elem.text.strip()
                        time_match = re.search(r'(\d+)\s*(mins|min|minutes|minute|hrs|hr|hours|hour)', time_text, re.IGNORECASE)
                        if time_match:
                            value = int(time_match.group(1))
                            unit = time_match.group(2).lower()
                            if 'hr' in unit:
                                value *= 60
                            metadata[time_type] = value
                        break
            
            # Servings
            servings_elem = soup.select_one('[data-testid="recipe-servings"]')
            if servings_elem:
                servings_text = servings_elem.text.strip()
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Extract possible cuisine from breadcrumbs
            cuisine = None
            breadcrumbs = soup.select('.breadcrumbs__link')
            for crumb in breadcrumbs:
                crumb_text = crumb.text.strip().lower()
                # Check if this breadcrumb might be a cuisine
                cuisines = ["italian", "mexican", "chinese", "indian", "french", "thai", "japanese", 
                           "greek", "mediterranean", "spanish", "american", "korean", "vietnamese"]
                if crumb_text in cuisines:
                    cuisine = crumb_text.capitalize()
                    break
            
            if cuisine:
                metadata['cuisine'] = cuisine
            
            # Extract categories from breadcrumbs
            categories = []
            for crumb in breadcrumbs:
                crumb_text = crumb.text.strip()
                if crumb_text and crumb_text.lower() not in ['home', 'recipes']:
                    categories.append(crumb_text)
            
            # Generate tags
            tags = []
            tags.extend(categories)
            
            # Add meal type tags if applicable
            meal_types = ['breakfast', 'lunch', 'dinner', 'dessert', 'snack', 'appetizer']
            page_text = soup.get_text().lower()
            for meal in meal_types:
                if meal in page_text:
                    tags.append(meal)
            
            # Determine complexity based on number of ingredients and steps
            complexity = "easy"
            if len(ingredients) >= 10 or len(instructions) >= 7:
                complexity = "complex"
            elif len(ingredients) >= 6 or len(instructions) >= 4:
                complexity = "medium"
            
            return {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'AllRecipes',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'tags': tags,
                'categories': categories,
                'metadata': metadata,
                'raw_content': html_content[:1000]  # Store just a portion to save space
            }
            
        except Exception as e:
            logger.error(f"Error extracting recipe from HTML in {url}: {str(e)}")
            return None
    
    def _parse_iso_duration(self, iso_duration):
        """Parse ISO 8601 duration to minutes"""
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
        except Exception:
            return None

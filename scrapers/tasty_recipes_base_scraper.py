import requests
import time
import logging
import re
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TastyRecipesBaseScraper:
    """Base scraper for websites using the Tasty Recipes WordPress plugin"""
    
    def __init__(self, site_name, base_url, category_urls):
        """
        Initialize the Tasty Recipes scraper
        
        Args:
            site_name (str): Name of the website (e.g., 'Pinch of Yum')
            base_url (str): Base URL of the website (e.g., 'https://pinchofyum.com')
            category_urls (list): List of category URLs to scrape
        """
        logger.info(f"Initializing {site_name} Tasty Recipes Scraper")
        
        self.site_name = site_name
        self.base_url = base_url
        self.category_urls = category_urls
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': base_url
        }
        
        # Cache of seen recipe links to avoid duplicates
        self.seen_recipe_links = set()
        
        logger.info(f"Initialized {site_name} scraper with {len(self.category_urls)} category URLs")

    def scrape(self, limit=50):
        """
        Scrape recipes from the website
        
        Args:
            limit (int): Maximum number of recipes to scrape
                
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting {self.site_name} scraping with limit: {limit}")
        recipes = []
        processed_urls = set()
        
        # Randomly shuffle categories for variety
        random.shuffle(self.category_urls)
        
        # Process each category
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                break
                
            try:
                logger.info(f"Processing category: {category_url}")
                
                # Get recipe links from this category
                recipe_links = self._get_recipe_links(category_url, limit - len(recipes))
                
                for url in recipe_links:
                    if url in processed_urls or len(recipes) >= limit:
                        continue
                        
                    processed_urls.add(url)
                    recipe_info = self._scrape_recipe(url)
                    
                    if recipe_info:
                        recipes.append(recipe_info)
                        logger.info(f"Successfully scraped recipe: {recipe_info['title']}")
                    
                    # Add a small delay between requests
                    time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error processing category {category_url}: {str(e)}")
                logger.error(f"Error details: {e}", exc_info=True)
        
        logger.info(f"Total {self.site_name} recipes scraped: {len(recipes)}")
        return recipes
    
    def _get_recipe_links(self, category_url, limit):
        """
        Get recipe links from a category page
        
        Args:
            category_url (str): Category URL
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        
        try:
            logger.info(f"Getting recipe links from: {category_url}")
            
            # Get the page content
            response = requests.get(category_url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error accessing category page: {category_url} - Status: {response.status_code}")
                return recipe_links
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all article links that might be recipes
            link_selectors = [
                'article.post a[href]', 
                '.post-item a[href]', 
                '.recipe-card a[href]',
                '.entry-title a[href]',
                '.loop-wrapper a[href]',
                '.post-summary a[href]',
                '.entry a[href]',
                '.archive-post a[href]',
                '.recipe a[href]'
            ]
            
            all_links = []
            for selector in link_selectors:
                all_links.extend(soup.select(selector))
            
            # Process links
            for link in all_links:
                href = link.get('href')
                
                # Skip if no href
                if not href:
                    continue
                
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(self.base_url, href)
                
                # Skip if not from the target website
                if self.base_url not in href:
                    continue
                
                # Skip category pages
                if '/category/' in href or '/recipes/' in href or '/tag/' in href:
                    if href == category_url:
                        continue
                    
                    # Skip if it's a category page
                    parsed_url = urlparse(href)
                    path_parts = parsed_url.path.strip('/').split('/')
                    if path_parts and (path_parts[0] == 'recipes' or path_parts[0] == 'category') and len(path_parts) <= 2:
                        continue
                
                # Skip if already seen
                if href in self.seen_recipe_links:
                    continue
                
                recipe_links.append(href)
                self.seen_recipe_links.add(href)
                
                # Stop if reached limit
                if len(recipe_links) >= limit:
                    break
            
            logger.info(f"Found {len(recipe_links)} recipe links on category page {category_url}")
            
        except Exception as e:
            logger.error(f"Error getting recipe links from {category_url}: {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)
        
        return recipe_links
    
    def _scrape_recipe(self, url):
        """
        Scrape a single recipe URL
        
        Args:
            url (str): Recipe URL
            
        Returns:
            dict: Recipe information or None if failed
        """
        try:
            logger.info(f"Scraping recipe: {url}")
            
            # Get the page content
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error accessing recipe URL: {url} - Status: {response.status_code}")
                return None
            
            # Extract recipe info
            recipe_info = self._extract_recipe_info(response.text, url)
            
            return recipe_info
            
        except Exception as e:
            logger.error(f"Error scraping recipe {url}: {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)
            return None
    
    def _extract_recipe_info(self, html_content, url):
        """
        Extract structured recipe information from HTML, optimized for Tasty Recipes format

        Args:
            html_content (str): HTML content of the recipe page
            url (str): URL of the recipe

        Returns:
            dict: Extracted recipe information
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')

            # Find Tasty Recipes container
            tasty_recipes_container = soup.select_one('div[id^="tasty-recipes-"], .tasty-recipes')

            if not tasty_recipes_container:
                logger.warning(f"No Tasty Recipes container found in {url}")
                # Try to find any recipe container as fallback
                tasty_recipes_container = soup.select_one('.recipe-container, article.post, .entry-content')
                if not tasty_recipes_container:
                    return None

            # Extract recipe details from Tasty Recipes format
            title = self._extract_tasty_title(tasty_recipes_container, soup)
            ingredients = self._extract_tasty_ingredients(tasty_recipes_container)
            instructions = self._extract_tasty_instructions(tasty_recipes_container)
            notes = self._extract_tasty_notes(tasty_recipes_container)

            # Extract times and servings
            times_and_servings = self._extract_tasty_times_and_servings(tasty_recipes_container)

            # Extract image
            image_url = self._extract_tasty_image(tasty_recipes_container, soup)

            # Extract category, cuisine
            categories, cuisine = self._extract_tasty_categories(tasty_recipes_container, soup)
            
            # Extract tags
            tags = self._extract_tasty_tags(tasty_recipes_container, soup, ingredients, instructions, categories)

            # Extract nutrition facts
            nutrition = self._extract_tasty_nutrition(tasty_recipes_container, soup)

            # Skip if we couldn't extract required data
            if not title or not ingredients or not instructions:
                logger.warning(f"Missing essential recipe data for {url}")
                return None

            # Determine complexity based on ingredients and instructions
            complexity = self._determine_complexity(ingredients, instructions)

            # Create recipe object with consistent metadata structure
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': self.site_name,
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'metadata': {
                    'ingredients_list': ingredients,
                    'cook_time': times_and_servings.get('cook_time'),
                    'prep_time': times_and_servings.get('prep_time'),
                    'total_time': times_and_servings.get('total_time'),
                    'servings': times_and_servings.get('servings'),
                    'yield': times_and_servings.get('yield'),
                    'notes': notes,
                    'nutrition': nutrition,
                    'nutrition_per_serving': nutrition  # Include both formats for compatibility
                },
                'notes': notes,
                'categories': categories,
                'cuisine': cuisine,
                'tags': tags,
                'nutrition': nutrition,
                'image_url': image_url,
                # Also add top-level fields for easy access
                'cook_time': times_and_servings.get('cook_time'),
                'prep_time': times_and_servings.get('prep_time'),
                'total_time': times_and_servings.get('total_time'),
                'servings': times_and_servings.get('servings')
            }

            logger.info(f"Successfully extracted recipe: {title}")
            return recipe

        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)
            return None
    
    def _extract_tasty_title(self, container, soup):
        """Extract title from Tasty Recipes format"""
        # Try specific Tasty Recipes title
        title_elem = container.select_one('.tasty-recipes-title')
        if title_elem:
            return title_elem.get_text().strip()
        
        # Fallbacks
        title_elem = soup.select_one('h1.entry-title') or soup.select_one('h1')
        if title_elem:
            return title_elem.get_text().strip()
        
        return None
    
    def _extract_tasty_ingredients(self, container):
        """Extract ingredients from Tasty Recipes format"""
        ingredients = []
        
        # First try the modern format with checkboxes
        checkbox_ingredients = container.select('li[data-tr-ingredient-checkbox]')
        if checkbox_ingredients:
            logger.info("Found modern Tasty Recipes ingredient format with checkboxes")
            for item in checkbox_ingredients:
                # Extract text with all spans combined (amount, unit, name)
                ingredient_text = item.get_text().strip()
                if ingredient_text:
                    ingredients.append(ingredient_text)
            
            if ingredients:
                return ingredients
        
        # Get ingredients section
        ingredients_body = container.select_one('.tasty-recipes-ingredients-body, .tasty-recipes-ingredients')
        
        if ingredients_body:
            # Check for ingredient sections/groups
            ingredient_sections = {}
            current_section = "Main Ingredients"
            
            # Look for ingredient section headers
            headers = ingredients_body.select('strong, b, h4')
            for header in headers:
                header_text = header.get_text().strip()
                if header_text and ':' not in header_text and len(header_text) > 3:
                    # This is likely a section header
                    if header.find_next('ul'):
                        # This header has ingredients after it
                        ingredient_sections[header_text] = []
                        current_section = header_text
                
            # If no sections found, use default
            if not ingredient_sections:
                ingredient_sections[current_section] = []
            
            # Find all ingredient lists
            ingredient_lists = ingredients_body.select('ul')
            if not ingredient_lists:
                # Some Tasty Recipes use p tags instead of lists
                ingredient_items = ingredients_body.select('p')
                for item in ingredient_items:
                    text = item.get_text().strip()
                    if text and len(text) > 2 and not text.startswith('For the'):
                        ingredient_sections[current_section].append(text)
            else:
                # Process each list
                for ul in ingredient_lists:
                    # Find closest header to determine section
                    prev_header = None
                    for header in headers:
                        if header.find_next('ul') == ul:
                            prev_header = header.get_text().strip()
                            break
                    
                    # Determine which section this list belongs to
                    section = prev_header if prev_header in ingredient_sections else current_section
                    
                    # Extract ingredients from this list
                    for li in ul.select('li'):
                        text = li.get_text().strip()
                        if text:
                            ingredient_sections[section].append(text)
            
            # Combine all ingredients into a flat list with section prefixes if needed
            for section, items in ingredient_sections.items():
                if section != "Main Ingredients" and items:
                    # Add section header as a separate "ingredient" for clarity
                    ingredients.append(f"FOR THE {section.upper()}:")
                
                ingredients.extend(items)
        else:
            # Fallback to any ul in the container
            ingredient_items = container.select('.tasty-recipes-ingredients li, ul li')
            for item in ingredient_items:
                text = item.get_text().strip()
                if text and len(text) > 2 and not text.startswith('For the'):
                    ingredients.append(text)
        
        # If still no ingredients, try JSON-LD
        if not ingredients:
            json_ld_ingredients = self._extract_from_json_ld(soup, 'recipeIngredient')
            if json_ld_ingredients:
                ingredients = json_ld_ingredients
        
        return ingredients
    
    def _extract_tasty_instructions(self, container):
        """Extract instructions from Tasty Recipes format"""
        instructions = []
        
        # Get instructions section
        instructions_body = container.select_one('.tasty-recipes-instructions-body, .tasty-recipes-instructions')
        
        if instructions_body:
            # Check for ordered list
            instruction_list = instructions_body.select('ol li, .tasty-recipes-instructions li')
            if instruction_list:
                for li in instruction_list:
                    text = li.get_text().strip()
                    if text:
                        instructions.append(text)
            else:
                # Some recipes use p tags instead of lists
                for p in instructions_body.select('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 5:
                        instructions.append(text)
        else:
            # Fallback to any ol in the container
            instruction_items = container.select('.tasty-recipes-instructions li, ol li')
            for item in instruction_items:
                text = item.get_text().strip()
                if text and len(text) > 5:
                    instructions.append(text)
        
        # If still no instructions, try JSON-LD
        if not instructions:
            json_ld_instructions = self._extract_from_json_ld(soup, 'recipeInstructions')
            if json_ld_instructions:
                instructions = json_ld_instructions
        
        return instructions
    
    def _extract_tasty_notes(self, container):
        """Extract recipe notes from Tasty Recipes format"""
        notes = []
        
        # Get notes section
        notes_body = container.select_one('.tasty-recipes-notes-body, .tasty-recipes-notes')
        
        if notes_body:
            # Find all paragraphs in notes
            for p in notes_body.select('p'):
                text = p.get_text().strip()
                if text and len(text) > 5:
                    notes.append(text)
            
            # Find list items in notes
            for li in notes_body.select('li'):
                text = li.get_text().strip()
                if text and len(text) > 5:
                    notes.append(text)
        
        return notes
    
    def _extract_from_json_ld(self, soup, property_name):
        """Extract property from JSON-LD schema"""
        try:
            # Find all script tags with JSON-LD
            json_ld_scripts = soup.select('script[type="application/ld+json"]')
            
            for script in json_ld_scripts:
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
                        
                        # Direct recipe object
                        if data.get('@type') == 'Recipe' and property_name in data:
                            return self._process_json_ld_property(data[property_name])
                        
                except Exception as e:
                    logger.error(f"Error parsing JSON-LD: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting from JSON-LD: {e}")
        
        return None
    
    def _process_json_ld_property(self, prop_value):
        """Process a property value from JSON-LD"""
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
    
    def _extract_tasty_times_and_servings(self, container):
        """Extract cooking times and servings from Tasty Recipes format"""
        metadata = {
            'prep_time': None,
            'cook_time': None,
            'total_time': None,
            'servings': None,
            'yield': None
        }
        
        # Get details section
        details_section = container.select_one('.tasty-recipes-details, .tasty-recipes-details-container')
        
        if details_section:
            # Look for prep time
            prep_time_elem = details_section.select_one('.tasty-recipes-prep-time')
            if prep_time_elem:
                metadata['prep_time'] = self._parse_time(prep_time_elem.get_text().strip())
            
            # Look for cook time
            cook_time_elem = details_section.select_one('.tasty-recipes-cook-time')
            if cook_time_elem:
                metadata['cook_time'] = self._parse_time(cook_time_elem.get_text().strip())
            
            # Look for total time
            total_time_elem = details_section.select_one('.tasty-recipes-total-time')
            if total_time_elem:
                metadata['total_time'] = self._parse_time(total_time_elem.get_text().strip())
            
            # Look for yield/servings
            yield_elem = details_section.select_one('.tasty-recipes-yield')
            if yield_elem:
                yield_text = yield_elem.get_text().strip()
                metadata['yield'] = yield_text
                
                # Try to extract servings number
                servings_match = re.search(r'(\d+)', yield_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
        
        # If times are missing, look for time labels
        if not metadata['prep_time'] or not metadata['cook_time'] or not metadata['total_time']:
            time_labels = container.select('.tasty-recipes-label:contains("Time")')
            for label in time_labels:
                label_text = label.get_text().strip().lower()
                value_elem = label.find_next(class_='tasty-recipes-value')
                
                if value_elem:
                    time_value = self._parse_time(value_elem.get_text().strip())
                    
                    if 'prep' in label_text and not metadata['prep_time']:
                        metadata['prep_time'] = time_value
                    elif 'cook' in label_text and not metadata['cook_time']:
                        metadata['cook_time'] = time_value
                    elif 'total' in label_text and not metadata['total_time']:
                        metadata['total_time'] = time_value
        
        return metadata
    
    def _parse_time(self, time_string):
        """Parse time string to minutes"""
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
    
    def _extract_tasty_image(self, container, soup):
        """Extract recipe image from Tasty Recipes format"""
        # Try container image first
        img_elem = container.select_one('.tasty-recipes-image img')
        if img_elem:
            return img_elem.get('src', '')
        
        # Try Open Graph image
        og_img = soup.select_one('meta[property="og:image"]')
        if og_img:
            return og_img.get('content', '')
        
        # Try featured image
        featured_img = soup.select_one('.post-thumbnail img, .featured-image img')
        if featured_img:
            return featured_img.get('src', '')
        
        return None
    
    def _extract_tasty_categories(self, container, soup):
        """Extract recipe categories and cuisine from page"""
        categories = []
        cuisine = None
        
        # Look for category links
        category_links = soup.select('a[href*="/category/"], a[href*="/recipes/"]')
        for link in category_links:
            category = link.get_text().strip()
            if category and category not in categories:
                categories.append(category)
        
        # Check for cuisine
        cuisine_keywords = [
            'italian', 'mexican', 'chinese', 'indian', 'french', 'japanese',
            'thai', 'greek', 'spanish', 'lebanese', 'moroccan', 'turkish',
            'korean', 'vietnamese', 'american', 'cajun', 'mediterranean',
            'middle eastern', 'german', 'british', 'irish'
        ]
        
        for category in categories:
            if category.lower() in cuisine_keywords:
                cuisine = category
                break
        
        return categories, cuisine
    
    def _extract_tasty_nutrition(self, container, soup):
        """Extract nutrition information"""
        nutrition = {}

        # Look for Nutrifox iframe or div
        nutrifox_elem = soup.select_one('iframe[id^="nutrifox-label-"], .tasty-recipes-nutrifox, .tasty-recipes-nutrition')
        if nutrifox_elem:
            # Try to find nutrition text
            nutrition_text = nutrifox_elem.get_text() or container.get_text()

            # Extract common nutrition values with more robust regex patterns
            # Calories (without unit)
            calories_match = re.search(r'(?:calories|kcal|cal):?\s*(\d+)', nutrition_text, re.IGNORECASE)
            if calories_match:
                nutrition['calories'] = calories_match.group(1)

            # Fat (with g unit)
            fat_patterns = [
                r'(?:total\s+)?fat:?\s*(\d+)(?:\.\d+)?\s*g',
                r'(?:fat|total fat)(?:\(g\))?:?\s*(\d+)',
                r'(\d+)(?:\.\d+)?\s*g\s+(?:fat|total fat)'
            ]
            for pattern in fat_patterns:
                fat_match = re.search(pattern, nutrition_text, re.IGNORECASE)
                if fat_match:
                    nutrition['fat'] = fat_match.group(1)
                    break

            # Carbohydrates (with g unit)
            carb_patterns = [
                r'(?:carb|carbs|carbohydrates?):?\s*(\d+)(?:\.\d+)?\s*g',
                r'(?:carb|carbs|carbohydrates?)(?:\(g\))?:?\s*(\d+)',
                r'(\d+)(?:\.\d+)?\s*g\s+(?:carb|carbs|carbohydrates?)'
            ]
            for pattern in carb_patterns:
                carbs_match = re.search(pattern, nutrition_text, re.IGNORECASE)
                if carbs_match:
                    nutrition['carbs'] = carbs_match.group(1)
                    break

            # Protein (with g unit)
            protein_patterns = [
                r'protein:?\s*(\d+)(?:\.\d+)?\s*g',
                r'protein(?:\(g\))?:?\s*(\d+)',
                r'(\d+)(?:\.\d+)?\s*g\s+protein'
            ]
            for pattern in protein_patterns:
                protein_match = re.search(pattern, nutrition_text, re.IGNORECASE)
                if protein_match:
                    nutrition['protein'] = protein_match.group(1)
                    break

            # Additional nutrition info
            sugar_match = re.search(r'sugar:?\s*(\d+)(?:\.\d+)?\s*g', nutrition_text, re.IGNORECASE)
            if sugar_match:
                nutrition['sugar'] = sugar_match.group(1)

            fiber_match = re.search(r'fiber:?\s*(\d+)(?:\.\d+)?\s*g', nutrition_text, re.IGNORECASE)
            if fiber_match:
                nutrition['fiber'] = fiber_match.group(1)

            sodium_match = re.search(r'sodium:?\s*(\d+)(?:\.\d+)?\s*mg', nutrition_text, re.IGNORECASE)
            if sodium_match:
                nutrition['sodium'] = sodium_match.group(1)

        # If nutrition data is still empty, try JSON-LD
        if not nutrition:
            try:
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    try:
                        data = json.loads(script.string)

                        # Handle different JSON-LD structures
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe' and item.get('nutrition'):
                                    nutrition_data = item['nutrition']
                                    if nutrition_data.get('calories'):
                                        nutrition['calories'] = self._extract_numeric_value(nutrition_data['calories'])
                                    if nutrition_data.get('fatContent'):
                                        nutrition['fat'] = self._extract_numeric_value(nutrition_data['fatContent'])
                                    if nutrition_data.get('carbohydrateContent'):
                                        nutrition['carbs'] = self._extract_numeric_value(nutrition_data['carbohydrateContent'])
                                    if nutrition_data.get('proteinContent'):
                                        nutrition['protein'] = self._extract_numeric_value(nutrition_data['proteinContent'])
                                    if nutrition_data.get('sugarContent'):
                                        nutrition['sugar'] = self._extract_numeric_value(nutrition_data['sugarContent'])
                                    if nutrition_data.get('fiberContent'):
                                        nutrition['fiber'] = self._extract_numeric_value(nutrition_data['fiberContent'])
                                    if nutrition_data.get('sodiumContent'):
                                        nutrition['sodium'] = self._extract_numeric_value(nutrition_data['sodiumContent'])
                                    break
                        elif isinstance(data, dict) and data.get('@type') == 'Recipe' and data.get('nutrition'):
                            nutrition_data = data['nutrition']
                            if nutrition_data.get('calories'):
                                nutrition['calories'] = self._extract_numeric_value(nutrition_data['calories'])
                            if nutrition_data.get('fatContent'):
                                nutrition['fat'] = self._extract_numeric_value(nutrition_data['fatContent'])
                            if nutrition_data.get('carbohydrateContent'):
                                nutrition['carbs'] = self._extract_numeric_value(nutrition_data['carbohydrateContent'])
                            if nutrition_data.get('proteinContent'):
                                nutrition['protein'] = self._extract_numeric_value(nutrition_data['proteinContent'])
                            if nutrition_data.get('sugarContent'):
                                nutrition['sugar'] = self._extract_numeric_value(nutrition_data['sugarContent'])
                            if nutrition_data.get('fiberContent'):
                                nutrition['fiber'] = self._extract_numeric_value(nutrition_data['fiberContent'])
                            if nutrition_data.get('sodiumContent'):
                                nutrition['sodium'] = self._extract_numeric_value(nutrition_data['sodiumContent'])
                    except:
                        continue
            except:
                pass

        return nutrition

    def _extract_numeric_value(self, value):
        """Extract numeric value from string with unit"""
        if isinstance(value, (int, float)):
            return str(value)

        if not value:
            return None

        # Extract number from string like "150 calories" or "10g"
        match = re.search(r'(\d+(?:\.\d+)?)', str(value))
        if match:
            return match.group(1)

        return None
    
    def _extract_tasty_tags(self, container, soup, ingredients, instructions, categories):
        """Extract tags from various sources"""
        tags = []
        
        # Add categories as tags
        if categories:
            tags.extend([cat.lower() for cat in categories])
        
        # Look for meta keywords
        keywords_meta = soup.find('meta', {'name': 'keywords'})
        if keywords_meta and keywords_meta.get('content'):
            keywords = keywords_meta['content'].split(',')
            tags.extend([k.strip().lower() for k in keywords if k.strip()])
        
        # Look for tag elements on the page
        tag_selectors = [
            '.recipe-tag', '.tag', '.post-tag', 
            'a[rel="tag"]', '.entry-tags a', '.tags a',
            '.tagcloud a', '.tag-links a'
        ]
        
        for selector in tag_selectors:
            tag_elements = soup.select(selector)
            for elem in tag_elements:
                tag_text = elem.text.strip()
                if tag_text and len(tag_text) < 50:
                    tags.append(tag_text.lower())
        
        # Look for Tasty Recipes specific tags
        keywords_section = container.select_one('.tasty-recipes-keywords')
        if keywords_section:
            keywords_text = keywords_section.get_text().strip()
            if keywords_text:
                # Remove "Keywords:" prefix if present
                keywords_text = re.sub(r'^keywords?:?\s*', '', keywords_text, flags=re.IGNORECASE)
                # Split by comma or space
                keywords = re.split(r'[,\s]+', keywords_text)
                tags.extend([k.strip().lower() for k in keywords if k.strip()])
        
        # Generate tags from content analysis
        combined_text = ' '.join(ingredients + instructions).lower()
        
        # Diet-related tags
        diet_terms = {
            'vegetarian': ['vegetarian', 'veggie', 'meatless'],
            'vegan': ['vegan', 'plant-based'],
            'gluten-free': ['gluten-free', 'gluten free', 'celiac'],
            'dairy-free': ['dairy-free', 'dairy free', 'lactose-free'],
            'keto': ['keto', 'ketogenic', 'low-carb'],
            'paleo': ['paleo', 'caveman'],
            'whole30': ['whole30', 'whole 30'],
            'low-fat': ['low-fat', 'low fat', 'light'],
            'sugar-free': ['sugar-free', 'sugar free', 'no sugar']
        }
        
        for tag, terms in diet_terms.items():
            if any(term in combined_text for term in terms):
                tags.append(tag)
        
        # Meal type tags
        meal_types = ['breakfast', 'brunch', 'lunch', 'dinner', 'dessert', 'appetizer', 'snack', 'beverage']
        for meal in meal_types:
            if meal in combined_text:
                tags.append(meal)
        
        # Cooking method tags
        cooking_methods = [
            'baked', 'grilled', 'fried', 'roasted', 'steamed', 'sauteed',
            'slow cooker', 'instant pot', 'air fryer', 'pressure cooker',
            'no-bake', 'one-pot', 'sheet pan'
        ]
        for method in cooking_methods:
            if method in combined_text:
                tags.append(method)
        
        # Season/holiday tags
        seasonal_terms = {
            'summer': ['summer', 'bbq', 'picnic', 'beach'],
            'fall': ['fall', 'autumn', 'thanksgiving', 'pumpkin'],
            'winter': ['winter', 'christmas', 'holiday', 'warm', 'comfort'],
            'spring': ['spring', 'easter', 'fresh']
        }
        
        for season, terms in seasonal_terms.items():
            if any(term in combined_text for term in terms):
                tags.append(season)
        
        # Remove duplicates and clean
        tags = list(set([tag.strip().lower() for tag in tags if tag and len(tag) > 2]))
        
        return tags
    
    def _determine_complexity(self, ingredients, instructions):
        """Determine recipe complexity based on ingredients and instructions"""
        # Count ingredients and steps
        ingredient_count = len(ingredients)
        step_count = len(instructions)
        
        # Calculate average instruction length
        instruction_lengths = [len(step.split()) for step in instructions]
        avg_instruction_length = sum(instruction_lengths) / len(instructions) if instructions else 0
        
        # Check for complex techniques
        complex_techniques = [
            'sous vide', 'temper', 'caramelize', 'flambe', 'reduce', 'deglaze',
            'emulsify', 'fold', 'proof', 'ferment', 'render', 'braise',
            'blanch', 'poach', 'overnight'
        ]
        
        has_complex_technique = False
        for step in instructions:
            if any(technique in step.lower() for technique in complex_techniques):
                has_complex_technique = True
                break
        
        # Determine complexity
        if ingredient_count <= 5 and step_count <= 5 and avg_instruction_length < 15 and not has_complex_technique:
            return 'easy'
        elif ingredient_count >= 12 or step_count >= 10 or avg_instruction_length > 30 or has_complex_technique:
            return 'complex'
        else:
            return 'medium'
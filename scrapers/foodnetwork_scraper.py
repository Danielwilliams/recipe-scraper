import requests
import time
import logging
import re
import json
import random
import os
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper

# Configure logging
logger = logging.getLogger(__name__)

class FoodNetworkScraper:
    """Scraper for Food Network recipes with multiple fallback methods"""
    
    def __init__(self):
        """Initialize the Food Network scraper with enhanced browser simulation"""
        logger.info("Initializing Food Network Scraper")
        
        # Expanded User-Agent pool
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0',
        ]
        
        # Base headers
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Referer': 'https://www.foodnetwork.com/',
        }
        
        self.base_url = "https://www.foodnetwork.com"
        self.recipe_list_url = "https://www.foodnetwork.com/recipes/recipes-a-z"
        
        # Attempt counter and max retries
        self.attempt_counter = 0
        self.max_attempts = 3
        
        # Cache directory
        self.cache_dir = os.path.join('data', 'recipe_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cloudscraper with session persistence
        self.cloud_scraper = cloudscraper.create_scraper()
        self.session_cookies = {}
    
    def _get_headers(self):
        """Generate fresh headers with a random User-Agent per request"""
        headers = self.base_headers.copy()
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers
    
    def scrape(self, limit=50):
        """Scrape recipes from Food Network"""
        logger.info(f"Starting Food Network scraping with limit: {limit}")
        recipes = []
        
        methods = [
            self._scrape_from_static_links,
            self._scrape_normal
        ]
        
        for method in methods:
            if len(recipes) < limit:
                try:
                    logger.info(f"Attempting to scrape with method: {method.__name__}")
                    new_recipes = method(limit - len(recipes))
                    if new_recipes:
                        recipes.extend(new_recipes)
                        logger.info(f"Method {method.__name__} added {len(new_recipes)} recipes")
                except Exception as e:
                    logger.error(f"Error with method {method.__name__}: {str(e)}")
        
        logger.info(f"Total Food Network recipes scraped: {len(recipes)}")
        return recipes[:limit]
    
    def _scrape_normal(self, limit):
        """Standard scraping method with cloudscraper"""
        recipes = []
        letters = list("abcdefghijklmnopqrstuvwxyz123")
        recipes_per_letter = max(2, limit // len(letters))
        
        for letter in letters:
            if len(recipes) >= limit:
                break
                
            try:
                letter_url = f"{self.recipe_list_url}/{letter}"
                logger.info(f"Scraping recipes starting with '{letter}': {letter_url}")
                
                recipe_links = self._get_recipe_links(letter_url, recipes_per_letter)
                logger.info(f"Found {len(recipe_links)} recipes for letter '{letter}'")
                
                letter_count = 0
                for url in recipe_links:
                    if len(recipes) >= limit or letter_count >= recipes_per_letter:
                        break
                        
                    try:
                        full_url = urljoin(self.base_url, url)
                        logger.info(f"Scraping recipe: {full_url}")
                        
                        time.sleep(random.uniform(8, 15))  # Increased delay
                        recipe_info = self._process_recipe_url(full_url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            letter_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                time.sleep(random.uniform(10, 20))  # Increased delay between letters
                
            except Exception as e:
                logger.error(f"Error processing letter '{letter}': {str(e)}")
        
        return recipes
    
    def _get_recipe_links(self, letter_url, limit):
        """Get recipe links from a letter page with retries"""
        recipe_links = []
        
        for attempt in range(self.max_attempts):
            try:
                logger.info(f"Accessing letter page (attempt {attempt + 1}): {letter_url}")
                time.sleep(random.uniform(8, 15))
                
                response = self.cloud_scraper.get(letter_url, headers=self._get_headers(), cookies=self.session_cookies, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to access letter page: {letter_url}, Status: {response.status_code}")
                    with open(f"foodnetwork_error_response_{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    if response.status_code == 403 and attempt < self.max_attempts - 1:
                        logger.info(f"Retrying after {5 * (attempt + 1)} seconds...")
                        time.sleep(5 * (attempt + 1))
                        continue
                    return recipe_links
                
                # Update session cookies
                self.session_cookies.update(response.cookies.get_dict())
                
                soup = BeautifulSoup(response.text, 'lxml')
                link_elements = soup.select('.m-PromoList__a-ListItem a')
                logger.info(f"Found {len(link_elements)} raw links on page")
                
                for link in link_elements:
                    href = link.get('href')
                    if href:
                        if href.startswith('//'):
                            href = f"https:{href}"
                        elif not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        if '/recipes/' in href:
                            recipe_links.append(href)
                            if len(recipe_links) >= limit:
                                break
                
                logger.info(f"After filtering, found {len(recipe_links)} recipe links")
                return recipe_links
            
            except Exception as e:
                logger.error(f"Error getting recipe links from {letter_url} (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_attempts - 1:
                    time.sleep(5 * (attempt + 1))
        
        logger.error(f"All {self.max_attempts} attempts failed for {letter_url}")
        return recipe_links

    def _scrape_from_static_links(self, limit):
        """Scrape recipes from links stored in external files"""
        recipes = []
        static_links = []
        
        links_file = os.path.join('data', 'foodnetwork_links.json')
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                static_links = json.load(f)
                logger.info(f"Loaded {len(static_links)} links from JSON file")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load links from JSON file: {str(e)}")
            return recipes
        
        static_links = static_links[:limit]
        logger.info(f"Processing {len(static_links)} static recipe links")
        
        for url in static_links:
            try:
                logger.info(f"Static scraping - Processing recipe: {url}")
                time.sleep(random.uniform(8, 15))  # Increased delay
                recipe_info = self._process_recipe_url(url)
                if recipe_info:
                    recipes.append(recipe_info)
                    logger.info(f"Static scraping - Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
            except Exception as e:
                logger.error(f"Static scraping - Error processing recipe {url}: {str(e)}")
        
        return recipes
    
    def _process_recipe_url(self, url):
        """Process a recipe URL with multiple fallback methods"""
        recipe_id = self._extract_recipe_id(url)
        
        if recipe_id:
            cache_file = os.path.join(self.cache_dir, f"{recipe_id}.html")
            if os.path.exists(cache_file):
                try:
                    logger.info(f"Using cached HTML for recipe: {url}")
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    return self._extract_recipe_info(html_content, url)
                except Exception as e:
                    logger.error(f"Error using cached HTML for {url}: {str(e)}")
        
        for attempt in range(self.max_attempts):
            try:
                logger.info(f"Fetching recipe HTML via HTTP (attempt {attempt + 1}): {url}")
                time.sleep(random.uniform(8, 15))
                
                response = self.cloud_scraper.get(url, headers=self._get_headers(), cookies=self.session_cookies, timeout=30)
                if response.status_code == 200:
                    if recipe_id:
                        cache_file = os.path.join(self.cache_dir, f"{recipe_id}.html")
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        logger.info(f"Saved recipe HTML to cache: {cache_file}")
                    self.session_cookies.update(response.cookies.get_dict())
                    return self._extract_recipe_info(response.text, url)
                else:
                    logger.error(f"Failed to fetch recipe: {url}, Status: {response.status_code}")
                    if response.status_code == 403 and attempt < self.max_attempts - 1:
                        time.sleep(5 * (attempt + 1))
                        continue
            
            except Exception as e:
                logger.error(f"Error fetching recipe {url} (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_attempts - 1:
                    time.sleep(5 * (attempt + 1))
        
        logger.error(f"All methods failed for recipe: {url}")
        return None
    
    def _extract_recipe_id(self, url):
        """Extract recipe ID from URL"""
        match = re.search(r'/recipes/.*?/([^/]+?)(?:-recipe)?-(\d+)$', url)
        if match:
            return f"{match.group(1)}-{match.group(2)}"
        match = re.search(r'/recipes/.*?/([^/]+?)$', url)
        if match:
            return match.group(1)
        return None
    
    def _extract_recipe_info(self, html_content, url):
        """Extract structured recipe information from HTML"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract title
            title_elem = soup.select_one('h1.o-AssetTitle__a-Headline, h1.recipe-title')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients
            ingredients = []
            ingredient_elements = soup.select('.o-Ingredients__a-Ingredient--CheckboxLabel, .ingredients-item-name')
            for elem in ingredient_elements:
                ingredient_text = elem.text.strip()
                if ingredient_text and not ingredient_text.startswith('Deselect All'):
                    ingredients.append(ingredient_text)
            
            section_headers = soup.select('.o-Ingredients__a-SubHeadline, .recipe-subsection-title')
            for header in section_headers:
                ingredients.append(header.text.strip())
            
            # Extract instructions
            instructions = []
            instruction_elements = soup.select('.o-Method__m-Step, .recipe-directions__list--item')
            for elem in instruction_elements:
                instruction_text = elem.text.strip()
                if instruction_text:
                    instructions.append(instruction_text)
            
            instruction_headers = soup.select('.o-Method__a-SubHeadline, .recipe-subsection-title')
            for header in instruction_headers:
                instructions.append(header.text.strip())
            
            if not instructions:
                instruction_paragraphs = soup.select('.o-Method__m-Body p, .recipe-directions__list p')
                for p in instruction_paragraphs:
                    p_text = p.text.strip()
                    if p_text and len(p_text) > 10:
                        instructions.append(p_text)
            
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.info(f"Skipping recipe {url} - not enough data extracted")
                return None
            
            # Extract complexity (Level)
            complexity = None
            level_elem = soup.select_one('.o-RecipeInfo__a-Description, .recipe-level')
            if level_elem:
                level_text = level_elem.text.strip()
                if 'Level:' in level_text:
                    complexity = level_text.split('Level:')[-1].strip().lower()
                    if complexity not in ['easy', 'medium', 'complex']:
                        complexity = 'medium'
            
            if not complexity:
                num_ingredients = len(ingredients)
                num_steps = len(instructions)
                if num_ingredients <= 5 and num_steps <= 3:
                    complexity = 'easy'
                elif num_ingredients >= 12 or num_steps >= 8:
                    complexity = 'complex'
                else:
                    complexity = 'medium'
            
            # Extract metadata (prep time, cook time, total time, servings)
            metadata = {}
            time_elements = soup.select('.o-RecipeInfo__m-Time .o-RecipeInfo__a-Description')
            for elem in time_elements:
                label = elem.find_previous_sibling('dt')
                if label:
                    label_text = label.text.strip().lower()
                    value_text = elem.text.strip()
                    time_match = re.search(r'(\d+)\s*(?:hr|hour|min|minute)s?', value_text, re.IGNORECASE)
                    if time_match:
                        time_value = int(time_match.group(1))
                        unit = time_match.group(2).lower()
                        if 'hr' in unit or 'hour' in unit:
                            time_value *= 60
                        if 'prep' in label_text:
                            metadata['prep_time'] = time_value
                        elif 'cook' in label_text:
                            metadata['cook_time'] = time_value
                        elif 'total' in label_text:
                            metadata['total_time'] = time_value
            
            servings_elem = soup.select_one('.o-RecipeInfo__a-Description--Yield, .recipe-yield')
            if servings_elem:
                servings_text = servings_elem.text.strip()
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Extract image URL
            image_url = None
            
            # Try Open Graph meta tag
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                image_url = og_image.get('content')
            
            # Try primary image classes
            if not image_url:
                img_tag = soup.find('img', {'class': 'o-AssetImage__a-Image'}) or \
                          soup.find('img', {'class': 'recipe-lead-image'}) or \
                          soup.find('img', {'class': 'primary-image'})
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
            
            # Fallback to any image with recipe-related alt text
            if not image_url:
                img_tag = soup.find('img', {'data-src': True, 'alt': lambda x: x and 'recipe' in x.lower()})
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
            
            # Extract tags
            tags = []
            
            # Look for tags/keywords in meta tags
            keywords_meta = soup.find('meta', {'name': 'keywords'})
            if keywords_meta and keywords_meta.get('content'):
                keywords = keywords_meta['content'].split(',')
                tags.extend([k.strip() for k in keywords if k.strip()])
            
            # Look for category/tag elements
            tag_elements = soup.select('.o-Tags__a-Tag, .tag-item, .recipe-tag, a[href*="/tags/"], a[href*="/recipes/"]')
            for elem in tag_elements:
                tag_text = elem.text.strip()
                if tag_text and len(tag_text) < 50:  # Reasonable tag length
                    tags.append(tag_text)
            
            # Extract from breadcrumbs
            breadcrumb_elements = soup.select('.breadcrumb__link, .o-Breadcrumbs__a-Link')
            for crumb in breadcrumb_elements:
                crumb_text = crumb.text.strip()
                if crumb_text and crumb_text.lower() not in ['home', 'recipes', 'food network']:
                    tags.append(crumb_text)
            
            # Generate tags based on content analysis
            combined_text = (title + ' ' + ' '.join(ingredients) + ' ' + ' '.join(instructions)).lower()
            
            # Diet-related tags
            diet_terms = {
                'vegetarian': ['vegetarian', 'veggie'],
                'vegan': ['vegan'],
                'gluten-free': ['gluten-free', 'gluten free'],
                'dairy-free': ['dairy-free', 'dairy free'],
                'keto': ['keto', 'ketogenic'],
                'paleo': ['paleo'],
                'low-carb': ['low-carb', 'low carb'],
                'healthy': ['healthy', 'nutritious']
            }
            
            for tag, terms in diet_terms.items():
                if any(term in combined_text for term in terms):
                    tags.append(tag)
            
            # Meal type tags
            meal_types = ['breakfast', 'lunch', 'dinner', 'dessert', 'appetizer', 'snack', 'brunch']
            for meal in meal_types:
                if meal in combined_text:
                    tags.append(meal)
            
            # Cooking method tags
            cooking_methods = ['grilled', 'baked', 'fried', 'roasted', 'slow cooker', 'instant pot', 'air fryer']
            for method in cooking_methods:
                if method in combined_text:
                    tags.append(method)
            
            # Remove duplicates and clean up
            tags = list(set([tag.lower().strip() for tag in tags if tag]))
            
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'Food Network',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'metadata': metadata,
                'image_url': image_url,  # Add image URL field
                'tags': tags,  # Add tags field
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = FoodNetworkScraper()
    recipes = scraper.scrape(limit=5)
    print(f"Scraped {len(recipes)} recipes")
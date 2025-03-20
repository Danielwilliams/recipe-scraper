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
        
        # User-Agent rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
        ]
        
        # Sophisticated headers to mimic a real browser
        self.headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',  # Do Not Track
            'Referer': 'https://www.foodnetwork.com/',
        }
        
        # Cookies for better browser simulation
        self.cookies = {
            'OptanonAlertBoxClosed': '2023-01-01T12:00:00.000Z',
            'OptanonConsent': 'isIABGlobal=false&datestamp=Tue+Mar+19+2024+12:00:00+GMT-0400',
        }
        
        self.base_url = "https://www.foodnetwork.com"
        self.recipe_list_url = "https://www.foodnetwork.com/recipes/recipes-a-z"
        
        # Attempt counter for retries
        self.attempt_counter = 0
        self.max_attempts = 3
        
        # Cache directory for storing recipe HTML
        self.cache_dir = os.path.join('data', 'recipe_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize cloudscraper
        self.cloud_scraper = cloudscraper.create_scraper()
    
    def scrape(self, limit=50):
        """
        Scrape recipes from Food Network
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting Food Network scraping with limit: {limit}")
        recipes = []
        
        # Try different scraping methods in order of preference
        methods = [
            self._scrape_from_static_links,  # Prioritize static links in CI
            self._scrape_normal              # Then normal scraping with cloudscraper
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
        
        # Distribute limit across alphabet letters
        recipes_per_letter = max(2, limit // len(letters))
        
        for letter in letters:
            if len(recipes) >= limit:
                break
                
            try:
                letter_url = f"{self.recipe_list_url}/{letter}"
                logger.info(f"Scraping recipes starting with '{letter}': {letter_url}")
                
                recipe_links = self._get_recipe_links(letter_url, recipes_per_letter)
                logger.info(f"Found {len(recipe_links)} recipes for letter '{letter}'")
                
                # Process recipe links
                letter_count = 0
                for url in recipe_links:
                    if len(recipes) >= limit or letter_count >= recipes_per_letter:
                        break
                        
                    try:
                        full_url = urljoin(self.base_url, url)
                        logger.info(f"Scraping recipe: {full_url}")
                        
                        time.sleep(random.uniform(5, 10))
                        recipe_info = self._process_recipe_url(full_url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            letter_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                time.sleep(random.uniform(5, 10))
                
            except Exception as e:
                logger.error(f"Error processing letter '{letter}': {str(e)}")
        
        return recipes
    
    def _get_recipe_links(self, letter_url, limit):
        """
        Get recipe links from a letter page with retries
        
        Args:
            letter_url (str): URL of the letter page
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        
        for attempt in range(self.max_attempts):
            try:
                logger.info(f"Accessing letter page (attempt {attempt + 1}): {letter_url}")
                time.sleep(random.uniform(5, 10))
                
                response = self.cloud_scraper.get(letter_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to access letter page: {letter_url}, Status: {response.status_code}")
                    with open(f"foodnetwork_error_response_{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    if response.status_code == 403 and attempt < self.max_attempts - 1:
                        logger.info(f"Retrying after {5 * (attempt + 1)} seconds...")
                        time.sleep(5 * (attempt + 1))
                        continue
                    return recipe_links
                
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
                recipe_info = self._process_recipe_url(url)
                if recipe_info:
                    recipes.append(recipe_info)
                    logger.info(f"Static scraping - Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
            except Exception as e:
                logger.error(f"Static scraping - Error processing recipe {url}: {str(e)}")
        
        return recipes
    
    def _process_recipe_url(self, url):
        """
        Process a recipe URL with multiple fallback methods
        
        Args:
            url (str): Recipe URL
            
        Returns:
            dict: Recipe information or None if all methods fail
        """
        recipe_id = self._extract_recipe_id(url)
        
        # Check for cached HTML file
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
        
        # Try direct HTTP request with cloudscraper
        for attempt in range(self.max_attempts):
            try:
                logger.info(f"Fetching recipe HTML via HTTP (attempt {attempt + 1}): {url}")
                time.sleep(random.uniform(5, 10))
                
                response = self.cloud_scraper.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    if recipe_id:
                        cache_file = os.path.join(self.cache_dir, f"{recipe_id}.html")
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        logger.info(f"Saved recipe HTML to cache: {cache_file}")
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
                   # Standardize complexity values
                   if complexity not in ['easy', 'medium', 'complex']:
                       complexity = 'medium'  # Default if unrecognized
           
           # If complexity not found, infer it
           if not complexity:
               num_ingredients = len(ingredients)
               num_steps = len(instructions)
               if num_ingredients <= 5 and num_steps <= 3:
                   complexity = 'easy'
               elif num_ingredients >= 12 or num_steps >= 8:
                   complexity = 'complex'
               else:
                   complexity = 'medium'
           
           recipe = {
               'title': title,
               'ingredients': ingredients,
               'instructions': instructions,
               'source': 'Food Network',
               'source_url': url,
               'date_scraped': datetime.now().isoformat(),
               'complexity': complexity,  # Add complexity field
           }
           
           return recipe
           
       except Exception as e:
           logger.error(f"Error extracting recipe info from {url}: {str(e)}")
           return None
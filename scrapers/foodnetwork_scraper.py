# scrapers/foodnetwork_scraper.py
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
logger = logging.getLogger(__name__)

class FoodNetworkScraper:
    """Scraper for Food Network recipes"""
    
    def __init__(self):
        """Initialize the Food Network scraper with enhanced browser simulation"""
        logger.info("Initializing Food Network Scraper")
        
        # More sophisticated headers to appear like a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.foodnetwork.com/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        # Add cookies for better browser simulation
        self.cookies = {
            'OptanonAlertBoxClosed': '2023-01-01T12:00:00.000Z',
            'OptanonConsent': 'isIABGlobal=false&datestamp=Tue+Mar+19+2024+12:00:00+GMT-0400',
        }
        
        self.base_url = "https://www.foodnetwork.com"
        self.recipe_list_url = "https://www.foodnetwork.com/recipes/recipes-a-z"
        
        # Attempt counter for retries
        self.attempt_counter = 0
        self.max_attempts = 3
    
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
            self._scrape_normal,
            self._scrape_with_selenium,
            self._scrape_from_static_links
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
        return recipes[:limit]  # Ensure we don't exceed the limit
    
    def _scrape_normal(self, limit):
        """Standard scraping method"""
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
                        
                        # Add random delay to appear more human-like
                        time.sleep(random.uniform(2, 4))
                        
                        recipe_response = requests.get(
                            full_url, 
                            headers=self.headers, 
                            cookies=self.cookies,
                            timeout=30
                        )
                        
                        if recipe_response.status_code != 200:
                            logger.error(f"Error accessing recipe URL: {full_url}, Status: {recipe_response.status_code}")
                            continue
                        
                        recipe_info = self._extract_recipe_info(recipe_response.text, full_url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            letter_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                # Be polite between letters
                time.sleep(random.uniform(4, 7))
                
            except Exception as e:
                logger.error(f"Error processing letter '{letter}': {str(e)}")
        
        return recipes
    
    def _get_recipe_links(self, letter_url, limit):
        """
        Get recipe links from a letter page
        
        Args:
            letter_url (str): URL of the letter page
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        
        try:
            logger.info(f"Accessing letter page with enhanced headers: {letter_url}")
            
            # Add a random delay to simulate human browsing
            time.sleep(random.uniform(2, 5))
            
            response = requests.get(
                letter_url, 
                headers=self.headers, 
                cookies=self.cookies,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to access letter page: {letter_url}, Status: {response.status_code}")
                
                # Save the response for debugging
                with open(f"foodnetwork_error_response.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                
                return recipe_links
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Store the HTML for debugging if needed
            with open(f"foodnetwork_debug_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)
                
            # Find all recipe links on the page
            link_elements = soup.select('.m-PromoList__a-ListItem a')
            logger.info(f"Found {len(link_elements)} raw links on page")
            
            for link in link_elements:
                href = link.get('href')
                if href:
                    # Handle relative URLs
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
            logger.error(f"Error getting recipe links from {letter_url}: {str(e)}")
            return recipe_links

def _scrape_with_selenium(self, limit):
        """Scrape using Selenium for better browser simulation"""
        recipes = []
        letters = list("abcdefghijklmnopqrstuvwxyz123")
        
        try:
            # Import Selenium libraries
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            
            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")
            
            # Initialize the driver
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            
            # Distribute limit across alphabet letters
            recipes_per_letter = max(2, limit // len(letters))
            
            for letter in letters[:5]:  # Limit to first 5 letters for speed
                if len(recipes) >= limit:
                    break
                    
                try:
                    letter_url = f"{self.recipe_list_url}/{letter}"
                    logger.info(f"Selenium - Scraping recipes starting with '{letter}': {letter_url}")
                    
                    # Visit the page
                    driver.get(letter_url)
                    
                    # Wait for the recipe list to load
                    time.sleep(5)  # Give the page time to fully load
                    
                    try:
                        # Wait for the list to be present
                        recipe_elements = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".m-PromoList__a-ListItem a"))
                        )
                        
                        # Extract links
                        recipe_links = []
                        for element in recipe_elements:
                            href = element.get_attribute("href")
                            if href and '/recipes/' in href:
                                recipe_links.append(href)
                                if len(recipe_links) >= recipes_per_letter:
                                    break
                        
                        logger.info(f"Selenium - Found {len(recipe_links)} recipes for letter '{letter}'")
                        
                        # Process recipe links
                        letter_count = 0
                        for url in recipe_links:
                            if len(recipes) >= limit or letter_count >= recipes_per_letter:
                                break
                                
                            try:
                                logger.info(f"Selenium - Scraping recipe: {url}")
                                
                                # Load the recipe page
                                driver.get(url)
                                time.sleep(random.uniform(3, 5))
                                
                                # Get the page source
                                page_source = driver.page_source
                                
                                # Extract recipe info
                                recipe_info = self._extract_recipe_info(page_source, url)
                                if recipe_info:
                                    recipes.append(recipe_info)
                                    letter_count += 1
                                    logger.info(f"Selenium - Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                                
                            except Exception as e:
                                logger.error(f"Selenium - Error scraping recipe {url}: {str(e)}")
                        
                    except Exception as e:
                        logger.error(f"Selenium - Error finding recipe elements: {str(e)}")
                    
                    # Be polite between letters
                    time.sleep(random.uniform(4, 7))
                    
                except Exception as e:
                    logger.error(f"Selenium - Error processing letter '{letter}': {str(e)}")
            
            driver.quit()
            
        except ImportError:
            logger.error("Selenium not installed. Please install selenium and webdriver-manager packages.")
        except Exception as e:
            logger.error(f"Selenium setup error: {str(e)}")
        
        return recipes
    
    def _scrape_from_static_links(self, limit):
        """Scrape recipes from links stored in external files"""
        recipes = []
        static_links = []
        
        # Try to load links from a JSON file first (most efficient)
        try:
            with open('data/foodnetwork_links.json', 'r', encoding='utf-8') as f:
                static_links = json.load(f)
                logger.info(f"Loaded {len(static_links)} links from JSON file")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load links from JSON file: {str(e)}")
            
            # Try to load from HTML file as fallback
            try:
                with open('data/foodnetwork_recipe_links.html', 'r', encoding='utf-8') as f:
                    html_content = f.read()
                    
                soup = BeautifulSoup(html_content, 'lxml')
                link_elements = soup.select('.m-PromoList__a-ListItem a')
                
                for link in link_elements:
                    href = link.get('href')
                    if href:
                        # Handle relative URLs
                        if href.startswith('//'):
                            href = f"https:{href}"
                        elif not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                            
                        static_links.append(href)
                
                logger.info(f"Loaded {len(static_links)} links from HTML file")
                
                # Optionally save these links to a JSON file for future use
                try:
                    os.makedirs('data', exist_ok=True)
                    with open('data/foodnetwork_links.json', 'w', encoding='utf-8') as f:
                        json.dump(static_links, f, indent=2)
                    logger.info("Saved extracted links to JSON file for future use")
                except Exception as json_e:
                    logger.warning(f"Failed to save links to JSON: {str(json_e)}")
                    
            except FileNotFoundError:
                logger.warning("No static links file found. Creating sample file structure.")
                
                # Create directory and sample file structure for future use
                os.makedirs('data', exist_ok=True)
                
                # Create a simple text file with instructions
                with open('data/README.txt', 'w', encoding='utf-8') as f:
                    f.write("""
                    Food Network Links Files:
                    
                    1. foodnetwork_links.json - JSON array of recipe URLs
                       Format: ["https://www.foodnetwork.com/recipes/example1", "https://www.foodnetwork.com/recipes/example2"]
                    
                    2. foodnetwork_recipe_links.html - HTML file containing links in Food Network format
                       Format: 
                       <ul class="m-PromoList o-Capsule__m-PromoList">
                         <li class="m-PromoList__a-ListItem"><a href="//www.foodnetwork.com/recipes/example">Example Recipe</a></li>
                       </ul>
                    
                    Place either of these files in this directory to enable scraping from static links.
                    """)
                
                # Use a minimal set of example links as fallback
                static_links = [
                    "https://www.foodnetwork.com/recipes/food-network-kitchen/basic-vanilla-cake-recipe-2043654",
                    "https://www.foodnetwork.com/recipes/ina-garten/roast-chicken-recipe-1940592"
                ]
        
        # Limit the number of links to process
        static_links = static_links[:limit]
        logger.info(f"Processing {len(static_links)} static recipe links")
        
        # Process recipe links
        for url in static_links:
            try:
                logger.info(f"Static scraping - Processing recipe: {url}")
                
                # Add random delay to appear more human-like
                time.sleep(random.uniform(2, 4))
                
                recipe_response = requests.get(
                    url, 
                    headers=self.headers, 
                    cookies=self.cookies,
                    timeout=30
                )
                
                if recipe_response.status_code != 200:
                    logger.error(f"Static scraping - Error accessing URL: {url}, Status: {recipe_response.status_code}")
                    continue
                
                recipe_info = self._extract_recipe_info(recipe_response.text, url)
                if recipe_info:
                    recipes.append(recipe_info)
                    logger.info(f"Static scraping - Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                
            except Exception as e:
                logger.error(f"Static scraping - Error processing recipe {url}: {str(e)}")
        
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
            
            # Extract instructions
            instructions = []
            instruction_elements = soup.select('.o-Method__m-Step, .recipe-directions__list--item')
            for elem in instruction_elements:
                instruction_text = elem.text.strip()
                if instruction_text:
                    instructions.append(instruction_text)
            
            # If no structured instructions found, try paragraphs
            if not instructions:
                instruction_paragraphs = soup.select('.o-Method__m-Body p, .recipe-directions__list p')
                for p in instruction_paragraphs:
                    p_text = p.text.strip()
                    if p_text and len(p_text) > 10:  # Filter out short text
                        instructions.append(p_text)
            
            # Extract metadata
            metadata = {}
            
            # Level
            level_elem = soup.select_one('.o-RecipeInfo__a-Description, .recipe-level')
            if level_elem and 'Level:' in soup.text:
                complexity = level_elem.text.strip().lower()
                metadata['complexity'] = complexity
            else:
                # Infer complexity based on number of ingredients and steps
                metadata['complexity'] = self._infer_complexity(len(ingredients), len(instructions))
            
            # Time
            time_elements = soup.select('.o-RecipeInfo__m-Time li, .recipe-time-yield__cooking-time')
            for elem in time_elements:
                time_text = elem.text.strip()
                if 'Total:' in time_text or 'Total Time:' in time_text:
                    total_match = re.search(r'Total:?\s*([\d\s]+(?:hr|min))', time_text)
                    if total_match:
                        total_time = self._parse_time(total_match.group(1))
                        metadata['total_time'] = total_time
                
                if 'Active:' in time_text or 'Prep:' in time_text:
                    prep_match = re.search(r'(?:Active|Prep):?\s*([\d\s]+(?:hr|min))', time_text)
                    if prep_match:
                        prep_time = self._parse_time(prep_match.group(1))
                        metadata['prep_time'] = prep_time
                
                if 'Cook:' in time_text:
                    cook_match = re.search(r'Cook:?\s*([\d\s]+(?:hr|min))', time_text)
                    if cook_match:
                        cook_time = self._parse_time(cook_match.group(1))
                        metadata['cook_time'] = cook_time
            
            # Yield/Servings
            yield_elem = soup.select_one('.o-RecipeInfo__a-Description:not(:has(*:contains("Level"))), .recipe-yield')
            if yield_elem:
                servings_text = yield_elem.text.strip()
                # Extract numbers from the yield text
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Extract nutrition info
            nutrition = self._extract_nutrition(soup)
            
            # Extract image URL
            image_elem = soup.select_one('.m-MediaBlock__a-Image, .recipe-lead-image img')
            image_url = image_elem.get('src') if image_elem else None
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.info(f"Skipping recipe {url} - not enough data extracted")
                return None
            
            # Generate tags based on title and ingredients
            tags = self._generate_tags(title, ingredients, instructions)
            
            # Create author section
            author_elem = soup.select_one('.o-Attribution__m-Author, .author-name')
            author = author_elem.text.strip() if author_elem else "Food Network Kitchen"
            
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'Food Network',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': metadata.get('complexity', 'medium'),
                'tags': tags,
                'metadata': metadata,
                'nutrition': nutrition,
                'image_url': image_url,
                'author': author,
                'raw_content': html_content[:5000]  # First 5000 chars to save space
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            return None
    
    def _parse_time(self, time_str):
        """
        Parse time strings like "1 hr 20 min" into minutes
        
        Args:
            time_str (str): Time string
            
        Returns:
            int: Time in minutes
        """
        if not time_str:
            return None
        
        total_minutes = 0
        
        # Extract hours
        hr_match = re.search(r'(\d+)\s*hr', time_str)
        if hr_match:
            total_minutes += int(hr_match.group(1)) * 60
        
        # Extract minutes
        min_match = re.search(r'(\d+)\s*min', time_str)
        if min_match:
            total_minutes += int(min_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
    def _extract_nutrition(self, soup):
        """
        Extract nutrition information
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Nutrition information
        """
        nutrition = {}
        
        try:
            # Find nutrition elements
            nutrition_elements = soup.select('.m-NutritionTable__a-Content dt, .m-NutritionTable__a-Content dd, .nutrition-info-item')
            
            current_key = None
            for i, elem in enumerate(nutrition_elements):
                if i % 2 == 0:  # Even indices are keys (dt elements)
                    current_key = elem.text.strip().lower().replace(' ', '_')
                else:  # Odd indices are values (dd elements)
                    value_text = elem.text.strip()
                    
                    # Extract numeric part
                    numeric_match = re.search(r'(\d+(?:\.\d+)?)', value_text)
                    if numeric_match and current_key:
                        # Convert to appropriate type
                        value = float(numeric_match.group(1))
                        
                        # Store in nutrition dictionary with standardized keys
                        if 'calorie' in current_key:
                            nutrition['calories'] = value
                        elif 'fat' in current_key and 'saturated' not in current_key:
                            nutrition['fat'] = value
                        elif 'saturated' in current_key:
                            nutrition['saturated_fat'] = value
                        elif 'carbohydrate' in current_key:
                            nutrition['carbs'] = value
                        elif 'fiber' in current_key:
                            nutrition['fiber'] = value
                        elif 'sugar' in current_key:
                            nutrition['sugar'] = value
                        elif 'protein' in current_key:
                            nutrition['protein'] = value
                        elif 'cholesterol' in current_key:
                            nutrition['cholesterol'] = value
                        elif 'sodium' in current_key:
                            nutrition['sodium'] = value
            
            # Alternative nutrition section format
            if not nutrition:
                nutrition_text = soup.select_one('.nutrition-info')
                if nutrition_text:
                    calories_match = re.search(r'Calories:\s*(\d+)', nutrition_text.text)
                    if calories_match:
                        nutrition['calories'] = float(calories_match.group(1))
                    
                    fat_match = re.search(r'Fat:\s*(\d+)g', nutrition_text.text)
                    if fat_match:
                        nutrition['fat'] = float(fat_match.group(1))
                    
                    carb_match = re.search(r'Carbohydrate:\s*(\d+)g', nutrition_text.text)
                    if carb_match:
                        nutrition['carbs'] = float(carb_match.group(1))
                    
                    protein_match = re.search(r'Protein:\s*(\d+)g', nutrition_text.text)
                    if protein_match:
                        nutrition['protein'] = float(protein_match.group(1))
            
            return nutrition if nutrition else None
            
        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            return None
    
    def _infer_complexity(self, num_ingredients, num_steps):
        """
        Infer recipe complexity based on ingredients and steps count
        
        Args:
            num_ingredients (int): Number of ingredients
            num_steps (int): Number of instructions steps
            
        Returns:
            str: Complexity level (easy, medium, complex)
        """
        if num_ingredients <= 5 and num_steps <= 3:
            return 'easy'
        elif num_ingredients >= 12 or num_steps >= 8:
            return 'complex'
        else:
            return 'medium'
    
    def _generate_tags(self, title, ingredients, instructions):
        """
        Generate tags based on recipe content
        
        Args:
            title (str): Recipe title
            ingredients (list): List of ingredients
            instructions (list): List of instructions
            
        Returns:
            list: Generated tags
        """
        tags = []
        combined_text = (title + ' ' + ' '.join(ingredients) + ' ' + ' '.join(instructions)).lower()
        
        # Diet tags
        diet_terms = [
            'vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'keto', 
            'paleo', 'low-carb', 'low-fat', 'sugar-free', 'whole30'
        ]
        
        for term in diet_terms:
            if term in combined_text:
                tags.append(term)
        
        # Meal type tags
        meal_types = [
            'breakfast', 'lunch', 'dinner', 'dessert', 'snack', 'appetizer',
            'side dish', 'salad', 'soup', 'main course', 'drink'
        ]
        
        for meal in meal_types:
            if meal in combined_text:
                tags.append(meal)
        
        # Cuisine tags
        cuisines = [
            'italian', 'mexican', 'chinese', 'indian', 'french', 'japanese',
            'thai', 'mediterranean', 'greek', 'spanish', 'american', 'southern'
        ]
        
        for cuisine in cuisines:
            if cuisine in combined_text:
                tags.append(cuisine)
        
        return list(set(tags))  # Remove duplicates
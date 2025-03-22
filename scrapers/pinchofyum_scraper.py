import requests
import time
import logging
import re
import json
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import traceback

# Import database connector to save recipes
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pinchofyum_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class PinchOfYumScraper:
    """Scraper for Pinch of Yum recipes"""
    
    def __init__(self):
        """Initialize the Pinch of Yum scraper with headers and category URLs"""
        logger.info("Initializing Pinch of Yum Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # List of category URLs to scrape
        self.category_urls = [
            "https://pinchofyum.com/recipes/breakfast",
            "https://pinchofyum.com/recipes/lunch",
            "https://pinchofyum.com/recipes/dinner",
            "https://pinchofyum.com/recipes/appetizer",
            "https://pinchofyum.com/recipes/snack",
            "https://pinchofyum.com/recipes/dessert"
        ]
        
        logger.info(f"Initialized with {len(self.category_urls)} category URLs")

    def scrape(self, limit=50):
        """
        Scrape recipes from Pinch of Yum
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting Pinch of Yum scraping with limit: {limit}")
        recipes = []
        recipes_per_category = max(3, limit // len(self.category_urls))  # Distribute limit across categories
        
        # Loop through each category URL
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
                break
                
            try:
                logger.info(f"Scraping category page: {category_url}")
                
                # Get recipe links from category page
                recipe_links = self._get_recipe_links(category_url, recipes_per_category)
                logger.info(f"Found {len(recipe_links)} recipe links in {category_url}")
                
                # Process only up to recipes_per_category for this category
                category_count = 0
                for url in recipe_links:
                    if len(recipes) >= limit or category_count >= recipes_per_category:
                        logger.info(f"Reached limit for category {category_url}")
                        break
                        
                    try:
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
                        time.sleep(random.uniform(2, 4))
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                        logger.error(traceback.format_exc())
                
                # Be polite between categories
                time.sleep(random.uniform(3, 5))
                
            except Exception as e:
                logger.error(f"Error scraping category page {category_url}: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"Total recipes scraped: {len(recipes)}")
        return recipes

    def _get_recipe_links(self, category_url, limit):
        """
        Get recipe links from a category page
        
        Args:
            category_url (str): URL of the category page
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        page = 1
        max_pages = 5  # Limit to 5 pages per category
        
        while len(recipe_links) < limit and page <= max_pages:
            try:
                page_url = f"{category_url}/page/{page}" if page > 1 else category_url
                logger.info(f"Fetching page {page}: {page_url}")
                
                response = requests.get(page_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to access page: {page_url}, Status: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Try multiple selector patterns to find recipe links
                link_selectors = [
                    'article.post .post-header a',               # Try header links
                    'article.post a.post-image',                 # Try image links
                    'article.post a.post-thumbnail',             # Try thumbnail links
                    '.archive-post a[href*="pinchofyum.com"]',   # Generic archive links
                    '.content-area article a[href*="/recipe/"]',  # Links containing "recipe"
                    '.site-content a[href*="pinchofyum.com"]'    # Any site content links
                ]
                
                found_links = False
                for selector in link_selectors:
                    links = soup.select(selector)
                    logger.info(f"Found {len(links)} links with selector '{selector}'")
                    
                    if links:
                        found_links = True
                        for link in links:
                            href = link.get('href')
                            if href and 'pinchofyum.com' in href:
                                if href not in recipe_links:
                                    recipe_links.append(href)
                                    if len(recipe_links) >= limit:
                                        break
                
                # If none of our selectors worked, try a more generic approach
                if not found_links:
                    # Get all links on the page and filter for those that look like recipes
                    all_links = soup.find_all('a', href=True)
                    for link in all_links:
                        href = link.get('href')
                        if href and 'pinchofyum.com' in href and ('/recipe/' in href or '/recipes/' in href):
                            if href not in recipe_links:
                                recipe_links.append(href)
                                if len(recipe_links) >= limit:
                                    break
                
                # If we found no links or less than expected and this isn't the last page, continue to next page
                if len(links) < 10 and page > 1:
                    break
                
                page += 1
                
                # Be polite
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error fetching recipes from page {page}: {str(e)}")
                logger.error(traceback.format_exc())
                break
        
        logger.info(f"Found {len(recipe_links)} recipe links in {category_url}")
        return recipe_links

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
            
            # Find Tasty Recipes container
            tasty_recipes_div = soup.select_one('div[id^="tasty-recipes-"]')
            if not tasty_recipes_div:
                logger.warning(f"No Tasty Recipes div found in {url}")
                return None
            
            # Extract recipe ID
            recipe_id = tasty_recipes_div.get('data-tr-id', '')
            
            # Extract title
            title_elem = tasty_recipes_div.select_one('.tasty-recipes-title')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract image URL
            image_url = None
            image_elem = tasty_recipes_div.select_one('.tasty-recipes-image img')
            if image_elem:
                image_url = image_elem.get('src')
            
            # Extract prep time, cook time, total time
            metadata = {}
            prep_time_elem = tasty_recipes_div.select_one('.tasty-recipes-prep-time')
            if prep_time_elem:
                metadata['prep_time'] = self._parse_time_text(prep_time_elem.text.strip())
            
            cook_time_elem = tasty_recipes_div.select_one('.tasty-recipes-cook-time')
            if cook_time_elem:
                metadata['cook_time'] = self._parse_time_text(cook_time_elem.text.strip())
                
            total_time_elem = tasty_recipes_div.select_one('.tasty-recipes-total-time')
            if total_time_elem:
                metadata['total_time'] = self._parse_time_text(total_time_elem.text.strip())
            
            # Extract yield/servings
            yield_elem = tasty_recipes_div.select_one('.tasty-recipes-yield')
            if yield_elem:
                yield_text = yield_elem.text.strip()
                servings_match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+))?', yield_text)
                if servings_match:
                    servings = servings_match.group(2) or servings_match.group(1)
                    metadata['servings'] = int(servings)
            
            # Extract ingredients
            ingredients = []
            ingredient_elems = tasty_recipes_div.select('.tasty-recipes-ingredients li')
            for elem in ingredient_elems:
                ingredient_text = elem.get_text(strip=True)
                if ingredient_text:
                    ingredients.append(ingredient_text)
            
            # Extract instructions
            instructions = []
            instruction_elems = tasty_recipes_div.select('.tasty-recipes-instructions li')
            for elem in instruction_elems:
                # Remove image tags from instructions
                for img in elem.select('img'):
                    img.decompose()
                
                instruction_text = elem.get_text(strip=True)
                if instruction_text:
                    instructions.append(instruction_text)
            
            # Extract notes
            notes = []
            notes_body = tasty_recipes_div.select_one('.tasty-recipes-notes-body')
            if notes_body:
                for p in notes_body.select('p'):
                    note_text = p.get_text(strip=True)
                    if note_text:
                        notes.append(note_text)
            
            # Extract nutrition information
            nutrition = self._extract_nutrition(tasty_recipes_div)
            
            # Extract categories and tags
            categories = []
            category_elem = tasty_recipes_div.select_one('.tasty-recipes-category')
            if category_elem:
                categories.append(category_elem.text.strip())
            
            cuisine_elem = tasty_recipes_div.select_one('.tasty-recipes-cuisine')
            if cuisine_elem:
                categories.append(cuisine_elem.text.strip())
            
            # Extract keywords/tags
            tags = []
            keywords_elem = tasty_recipes_div.select_one('.tasty-recipes-keywords')
            if keywords_elem:
                keywords_text = keywords_elem.get_text(strip=True)
                if 'Keywords:' in keywords_text:
                    keywords_list = keywords_text.split('Keywords:')[1].strip()
                    tags = [tag.strip() for tag in keywords_list.split(',')]
            
            # Determine complexity based on number of ingredients and steps
            complexity = "easy"
            if len(ingredients) >= 10 or len(instructions) >= 7:
                complexity = "complex"
            elif len(ingredients) >= 6 or len(instructions) >= 4:
                complexity = "medium"
            
            # Create recipe object
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'Pinch of Yum',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'categories': categories,
                'cuisine': cuisine_elem.text.strip() if cuisine_elem else None,
                'tags': tags,
                'metadata': metadata,
                'nutrition': nutrition,
                'image_url': image_url,
                'notes': notes,
                'raw_content': html_content[:5000]  # First 5000 chars
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _parse_time_text(self, time_text):
        """
        Parse time text like "30 minutes" or "1 hour 15 minutes" into minutes
        
        Args:
            time_text (str): Time text to parse
            
        Returns:
            int: Time in minutes or None
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
    
    def _extract_nutrition(self, recipe_div):
        """
        Extract nutrition information from the recipe
        
        Args:
            recipe_div (BeautifulSoup element): Recipe container div
            
        Returns:
            dict: Nutrition information
        """
        try:
            nutrition_data = {}
            
            # Find the nutrition iframe or section
            nutrition_iframe = recipe_div.select_one('iframe[id^="nutrifox-label-"]')
            if not nutrition_iframe:
                return nutrition_data
            
            # Look for common nutrition items in the page
            nutrition_text = recipe_div.get_text()
            
            # Extract calories
            calorie_match = re.search(r'Calories:?\s*(\d+)', nutrition_text)
            if calorie_match:
                nutrition_data['calories'] = int(calorie_match.group(1))
            
            # Extract fat
            fat_match = re.search(r'Fat:?\s*(\d+)g', nutrition_text)
            if fat_match:
                nutrition_data['fat'] = int(fat_match.group(1))
            
            # Extract carbs
            carbs_match = re.search(r'Carbohydrates?:?\s*(\d+)g', nutrition_text)
            if carbs_match:
                nutrition_data['carbs'] = int(carbs_match.group(1))
            
            # Extract protein
            protein_match = re.search(r'Protein:?\s*(\d+)g', nutrition_text)
            if protein_match:
                nutrition_data['protein'] = int(protein_match.group(1))
            
            # Extract fiber
            fiber_match = re.search(r'Fiber:?\s*(\d+)g', nutrition_text)
            if fiber_match:
                nutrition_data['fiber'] = int(fiber_match.group(1))
            
            # Extract sugar
            sugar_match = re.search(r'Sugar:?\s*(\d+)g', nutrition_text)
            if sugar_match:
                nutrition_data['sugar'] = int(sugar_match.group(1))
            
            # Extract sodium
            sodium_match = re.search(r'Sodium:?\s*(\d+)mg', nutrition_text)
            if sodium_match:
                nutrition_data['sodium'] = int(sodium_match.group(1))
            
            return nutrition_data
            
        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            return {}
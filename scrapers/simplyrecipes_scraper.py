# scrapers/

import requests
import time
import logging
import re
import random
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import traceback

# Import database connection to save recipes
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simplyrecipes_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class SimplyRecipesScraper:
    """Scraper for SimplyRecipes.com website"""
    
    def __init__(self):
        """Initialize the SimplyRecipes scraper"""
        logger.info("Initializing SimplyRecipes Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # Base category URLs to start scraping from
        self.category_urls = [
            "https://www.simplyrecipes.com/dinner-recipes-5091433",
            "https://www.simplyrecipes.com/breakfast-recipes-5091541",
            "https://www.simplyrecipes.com/lunch-recipes-5091263",
            "https://www.simplyrecipes.com/dessert-recipes-5091513",
            "https://www.simplyrecipes.com/snacks-and-appetizer-recipes-5090762",
            "https://www.simplyrecipes.com/holiday-and-seasonal-recipes-5091321",
            "https://www.simplyrecipes.com/recipes-by-ingredients-5091192",
            "https://www.simplyrecipes.com/recipes-by-method-5091235",
            "https://www.simplyrecipes.com/recipes-by-diet-5091259",
            "https://www.simplyrecipes.com/recipes-by-time-and-ease-5090817",
            "https://www.simplyrecipes.com/world-cuisine-recipes-5090811"
        ]
        
        logger.info(f"Initialized with {len(self.category_urls)} category URLs")
    
    def scrape(self, limit=1100):
        """
        Scrape recipes from SimplyRecipes
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting SimplyRecipes scraping with limit: {limit}")
        recipes = []
        
        # Distribute limit across categories
        recipes_per_category = max(3, limit // len(self.category_urls))
        
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
                break
                
            try:
                logger.info(f"Exploring category page: {category_url}")
                
                # Find recipe links from this category
                recipe_links = self._find_recipe_links(category_url)
                logger.info(f"Found {len(recipe_links)} recipe links in category {category_url}")
                
                # Add some randomness to link selection to diversify scraping
                random.shuffle(recipe_links)
                
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
                logger.error(f"Error exploring category page {category_url}: {str(e)}")
                logger.error(traceback.format_exc())
        
        logger.info(f"Total SimplyRecipes recipes scraped: {len(recipes)}")
        return recipes
    
    def _find_recipe_links(self, category_url, depth=0, max_depth=2):
        """
        Find recipe links within a category page
        
        Args:
            category_url (str): URL of the category page
            depth (int): Current recursion depth
            max_depth (int): Maximum recursion depth for subcategories
            
        Returns:
            list: List of recipe links
        """
        if depth > max_depth:
            return []
            
        try:
            logger.info(f"Finding recipe links at {category_url} (depth: {depth})")
            
            response = requests.get(category_url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to access URL: {category_url}, Status: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Recipe links set
            recipe_links = set()
            
            # Try to find recipe links with various selectors
            selectors = [
                '.card__title-link',
                'a.comp.card__title-link',
                '.comp.card a',
                'a[href*="/recipes/"]',
                'a[href*="-recipe-"]'
            ]
            
            base_url = "https://www.simplyrecipes.com"
            
            for selector in selectors:
                links = soup.select(selector)
                
                for link in links:
                    href = link.get('href')
                    if not href:
                        continue
                        
                    # Normalize URL
                    if not href.startswith('http'):
                        href = urljoin(base_url, href)
                    
                    # Filter for recipe pages vs. category pages
                    # Recipe pages typically have a distinct pattern
                    if ('simplyrecipes.com' in href and
                        not href.endswith('-recipes-') and
                        not '/recipes-by-' in href and
                        not '-recipes-5' in href):
                        
                        recipe_links.add(href)
            
            # Find subcategory links if not at max depth
            if depth < max_depth:
                subcategory_links = set()
                subcategory_selectors = [
                    '.taxonomy-nodes a',
                    'a[href*="-recipes-"]',
                    '.link-list__link'
                ]
                
                for selector in subcategory_selectors:
                    links = soup.select(selector)
                    
                    for link in links:
                        href = link.get('href')
                        if not href:
                            continue
                            
                        # Normalize URL
                        if not href.startswith('http'):
                            href = urljoin(base_url, href)
                        
                        # Add to subcategories if it looks like a category
                        if ('simplyrecipes.com' in href and
                            ('-recipes-' in href or '/recipes-by-' in href) and
                            href != category_url):
                            
                            subcategory_links.add(href)
                
                # Process subcategories (limited number to avoid too many requests)
                subcategory_limit = 3
                for i, subcat_url in enumerate(list(subcategory_links)[:subcategory_limit]):
                    logger.info(f"Processing subcategory {i+1}/{min(subcategory_limit, len(subcategory_links))}: {subcat_url}")
                    # Recursive call to find links in subcategory
                    subcat_recipe_links = self._find_recipe_links(subcat_url, depth + 1, max_depth)
                    recipe_links.update(subcat_recipe_links)
                    
                    # Politeness delay between subcategory processing
                    time.sleep(random.uniform(1, 2))
            
            return list(recipe_links)
            
        except Exception as e:
            logger.error(f"Error finding recipe links in {category_url}: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
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
            # Extract title
            title_elem = soup.select_one('h1.article-heading, h2.recipe-block__header')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients
            ingredients = []
            ingredient_elems = soup.select('.structured-ingredients__list-item')
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
            instruction_blocks = soup.select('.structured-project__steps .mntl-sc-block-group--LI')
            for block in instruction_blocks:
                # Get step heading
                step_heading = block.select_one('.mntl-sc-block-subheading')
                heading_text = step_heading.text.strip() if step_heading else ""
                
                # Get step paragraphs
                step_paragraphs = block.select('p.mntl-sc-block-html')
                for p in step_paragraphs:
                    paragraph_text = p.text.strip()
                    if paragraph_text:
                        if heading_text:
                            instructions.append(f"{heading_text} {paragraph_text}")
                            heading_text = ""  # Only include heading with first paragraph
                        else:
                            instructions.append(paragraph_text)
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.info(f"Skipping recipe {url} - not enough data extracted")
                return None
            
            # Extract metadata
            metadata = {}
            
            # Prep time
            prep_time_elem = soup.select_one('.prep-time .meta-text__data')
            if prep_time_elem:
                metadata['prep_time'] = self._parse_time_text(prep_time_elem.text.strip())
            
            # Cook time
            cook_time_elem = soup.select_one('.cook-time .meta-text__data')
            if cook_time_elem:
                metadata['cook_time'] = self._parse_time_text(cook_time_elem.text.strip())
            
            # Total time
            total_time_elem = soup.select_one('.total-time .meta-text__data')
            if total_time_elem:
                metadata['total_time'] = self._parse_time_text(total_time_elem.text.strip())
            
            # Servings
            servings_elem = soup.select_one('.recipe-serving .meta-text__data')
            if servings_elem:
                servings_text = servings_elem.text.strip()
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Extract nutrition information
            nutrition = {}
            
            # Basic nutrition
            calories_elem = soup.select_one('.nutrition-info__table--row:nth-child(1) .nutrition-info__table--cell')
            if calories_elem:
                try:
                    nutrition['calories'] = float(re.sub(r'[^\d.]', '', calories_elem.text.strip()))
                except (ValueError, TypeError):
                    pass
            
            fat_elem = soup.select_one('.nutrition-info__table--row:nth-child(2) .nutrition-info__table--cell')
            if fat_elem:
                try:
                    nutrition['fat'] = float(re.sub(r'[^\d.]', '', fat_elem.text.strip()))
                except (ValueError, TypeError):
                    pass
            
            carbs_elem = soup.select_one('.nutrition-info__table--row:nth-child(3) .nutrition-info__table--cell')
            if carbs_elem:
                try:
                    nutrition['carbs'] = float(re.sub(r'[^\d.]', '', carbs_elem.text.strip()))
                except (ValueError, TypeError):
                    pass
            
            protein_elem = soup.select_one('.nutrition-info__table--row:nth-child(4) .nutrition-info__table--cell')
            if protein_elem:
                try:
                    nutrition['protein'] = float(re.sub(r'[^\d.]', '', protein_elem.text.strip()))
                except (ValueError, TypeError):
                    pass
            
            # Extract image URL
            image_url = None
            image_elem = soup.select_one('meta[property="og:image"]')
            if image_elem:
                image_url = image_elem.get('content')
            
            if not image_url:
                image_elem = soup.select_one('.primary-image__image, .mntl-primary-image img')
                if image_elem:
                    image_url = image_elem.get('src') or image_elem.get('data-src')
            
            # Extract tags
            tags = []
            tag_elems = soup.select('.tag-nav__link')
            for elem in tag_elems:
                tag_text = elem.text.strip()
                if tag_text:
                    tags.append(tag_text)
            
            # Determine complexity based on number of ingredients and steps
            complexity = "easy"
            if len(ingredients) >= 10 or len(instructions) >= 7:
                complexity = "complex"
            elif len(ingredients) >= 6 or len(instructions) >= 4:
                complexity = "medium"
            
            # Build the recipe object
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'SimplyRecipes',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'metadata': metadata,
                'nutrition': nutrition,
                'tags': tags,
                'image_url': image_url,
                'raw_content': html_content[:5000]  # First 5000 chars
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _parse_time_text(self, time_text):
        """
        Parse time text like "30 mins" or "1 hr 15 mins" into minutes
        
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
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
        Get recipe links from a category page with improved filtering
        
        Args:
            category_url (str): URL of the category page
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        page = 1
        max_pages = 5  # Limit to 5 pages per category
        base_url = "https://pinchofyum.com"
        
        while len(recipe_links) < limit and page <= max_pages:
            try:
                # Construct page URL properly
                if page > 1:
                    # Check if URL already ends with slash
                    if category_url.endswith('/'):
                        page_url = f"{category_url}page/{page}"
                    else:
                        page_url = f"{category_url}/page/{page}"
                else:
                    page_url = category_url
                    
                logger.info(f"Fetching page {page}: {page_url}")
                
                response = requests.get(page_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to access page: {page_url}, Status: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Check if we're on a valid archive/category page
                is_archive_page = bool(soup.select('.archive-post') or 
                                      soup.select('.category-posts') or
                                      soup.select('body.archive'))
                
                if not is_archive_page:
                    logger.warning(f"Page doesn't appear to be an archive/category page: {page_url}")
                    # If we're on the first page and it's not an archive, it may be a single recipe
                    # Don't try pagination in that case
                    if page == 1:
                        # Maybe the URL itself is a recipe page
                        if '/recipe/' in page_url or ('/recipes/' in page_url and page_url.count('/') > 4):
                            recipe_links.append(page_url)
                    break
                
                # Find recipe links using a variety of selectors
                found_links = False
                
                # Try multiple selector patterns that are specific to recipe posts
                post_containers = soup.select('article.post, div.archive-post, div.category-posts .post')
                
                for container in post_containers:
                    # Look for the main link in this post container
                    main_link = None
                    
                    # Try title link first
                    title_link = container.select_one('h2.entry-title a, h3.entry-title a, .post-header a, .post-title a')
                    if title_link and title_link.get('href'):
                        main_link = title_link.get('href')
                    
                    # If no title link, try image link
                    if not main_link:
                        image_link = container.select_one('a.post-image, a.post-thumbnail, .post-image a, .post-thumbnail a')
                        if image_link and image_link.get('href'):
                            main_link = image_link.get('href')
                    
                    # Last resort: any link in the container
                    if not main_link:
                        any_link = container.select_one('a[href*="pinchofyum.com"]')
                        if any_link and any_link.get('href'):
                            main_link = any_link.get('href')
                    
                    # Process the link if found
                    if main_link:
                        found_links = True
                        
                        # Normalize URL
                        if not main_link.startswith('http'):
                            main_link = urljoin(base_url, main_link)
                        
                        # Only add actual recipe pages, not category pages or pagination
                        if (main_link not in recipe_links and 
                            'pinchofyum.com' in main_link and 
                            '/page/' not in main_link and
                            '/category/' not in main_link and
                            not main_link.endswith('/recipes/') and
                            not main_link.endswith('/recipe/')):
                            
                            # Further verify this looks like a recipe page
                            if ('/recipe/' in main_link or 
                                (main_link.count('/') >= 4 and not main_link.endswith('/'))):
                                recipe_links.append(main_link)
                                if len(recipe_links) >= limit:
                                    break
                
                # If we didn't find any valid links with our structured approach,
                # fall back to a more aggressive approach
                if not found_links:
                    # Get all links on the page and filter for those that look like recipes
                    all_links = soup.find_all('a', href=True)
                    for link in all_links:
                        href = link.get('href')
                        if (href and 
                            'pinchofyum.com' in href and 
                            '/page/' not in href and
                            href not in recipe_links and
                            ('/recipe/' in href or (href.count('/') >= 4 and 'recipes' in href))):
                            
                            recipe_links.append(href)
                            if len(recipe_links) >= limit:
                                break
                
                # If we found no links or less than expected and this isn't the last page, continue to next page
                if not found_links and page > 1:
                    break
                
                page += 1
                
                # Be polite
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error fetching recipes from page {page}: {str(e)}")
                logger.error(traceback.format_exc())
                break
        
        # One final filter to remove any non-recipe pages
        filtered_links = []
        for link in recipe_links:
            if (('/recipe/' in link or '/recipes/' in link) and 
                '/page/' not in link and 
                not link.endswith('/recipes/') and
                not link.endswith('/recipe/')):
                filtered_links.append(link)
        
        logger.info(f"Found {len(filtered_links)} recipe links in {category_url}")
        return filtered_links

    def _extract_recipe_info(self, html_content, url):
        """
        Extract structured recipe information from HTML with improved robustness
        
        Args:
            html_content (str): HTML content of the recipe page
            url (str): URL of the recipe
            
        Returns:
            dict: Extracted recipe information
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Check if this is actually a recipe page
            if '/recipes/page/' in url or '/recipe/page/' in url:
                logger.warning(f"URL appears to be a pagination page, not a recipe: {url}")
                return None
            
            # Multiple ways to identify a recipe
            tasty_recipes_div = None
            
            # Try standard Tasty Recipes container
            tasty_recipes_div = soup.select_one('div[id^="tasty-recipes-"]')
            
            # If not found, try newer/different container patterns
            if not tasty_recipes_div:
                tasty_recipes_div = soup.select_one('.tasty-recipes, .tasty-recipe, .wprm-recipe-container, .recipe-content')
            
            # If still not found, look for any recipe container indicators
            if not tasty_recipes_div:
                # Look for recipe JSON-LD
                recipe_json_ld = None
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Recipe':
                            recipe_json_ld = data
                            break
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                    recipe_json_ld = item
                                    break
                    except:
                        continue
                
                # If we found JSON-LD but no container, use the main content
                if recipe_json_ld:
                    tasty_recipes_div = soup.select_one('main, .content, .post-content, article')
                    logger.info(f"Using fallback content container with JSON-LD data for {url}")
                else:
                    # Last resort: look for common recipe indicators in page content
                    recipe_indicators = soup.select('h2, h3, h4')
                    for indicator in recipe_indicators:
                        text = indicator.get_text().lower()
                        if 'ingredients' in text or 'instructions' in text or 'directions' in text:
                            # Found a likely recipe page
                            tasty_recipes_div = soup.select_one('main, .content, .post-content, article')
                            logger.info(f"Using fallback content container with recipe indicators for {url}")
                            break
            
            if not tasty_recipes_div:
                logger.warning(f"No recipe container found in {url}")
                return None
            
            # Extract title - first try recipe container, then page title
            title = None
            title_elem = tasty_recipes_div.select_one('.tasty-recipes-title, .wprm-recipe-name, h1, .entry-title')
            if title_elem:
                title = title_elem.text.strip()
            
            if not title:
                title_elem = soup.select_one('h1, .entry-title, title')
                if title_elem:
                    title = title_elem.text.strip()
                    # Clean up title if from page title
                    title = title.split('|')[0].split('-')[0].strip()
            
            if not title:
                title = "Untitled Recipe"
            
            # Extract image URL - try multiple approaches
            image_url = None
            
            # Try recipe container image
            image_elem = tasty_recipes_div.select_one('.tasty-recipes-image img, .wprm-recipe-image img')
            if image_elem:
                image_url = image_elem.get('src') or image_elem.get('data-src')
            
            # Try page featured image
            if not image_url:
                image_elem = soup.select_one('.post-thumbnail img, .featured-image img')
                if image_elem:
                    image_url = image_elem.get('src') or image_elem.get('data-src')
            
            # Try OpenGraph image
            if not image_url:
                og_image = soup.select_one('meta[property="og:image"]')
                if og_image:
                    image_url = og_image.get('content')
            
            # Extract prep time, cook time, total time - try multiple approaches
            metadata = {}
            
            # Try structured time metadata
            time_map = {
                'prep_time': ['.tasty-recipes-prep-time', '.wprm-recipe-prep-time-container', '.prep-time'],
                'cook_time': ['.tasty-recipes-cook-time', '.wprm-recipe-cook-time-container', '.cook-time'],
                'total_time': ['.tasty-recipes-total-time', '.wprm-recipe-total-time-container', '.total-time']
            }
            
            for meta_key, selectors in time_map.items():
                for selector in selectors:
                    time_elem = tasty_recipes_div.select_one(selector)
                    if time_elem:
                        metadata[meta_key] = self._parse_time_text(time_elem.text.strip())
                        break
            
            # Extract yield/servings - try multiple approaches
            servings_selectors = [
                '.tasty-recipes-yield', 
                '.wprm-recipe-servings-container',
                '.yield',
                '.servings'
            ]
            
            for selector in servings_selectors:
                yield_elem = tasty_recipes_div.select_one(selector)
                if yield_elem:
                    yield_text = yield_elem.text.strip()
                    servings_match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+))?', yield_text)
                    if servings_match:
                        servings = servings_match.group(2) or servings_match.group(1)
                        metadata['servings'] = int(servings)
                        break
            
            # Extract ingredients - try multiple approaches
            ingredients = []
            
            # Try structured ingredient lists
            ingredient_selectors = [
                '.tasty-recipes-ingredients li',
                '.wprm-recipe-ingredient',
                '.ingredients-list li',
                'div:has(> h3:contains("Ingredients")) li',
                'div:has(> h2:contains("Ingredients")) li'
            ]
            
            for selector in ingredient_selectors:
                ingredient_elems = tasty_recipes_div.select(selector)
                if ingredient_elems:
                    for elem in ingredient_elems:
                        ingredient_text = elem.get_text(strip=True)
                        if ingredient_text and ingredient_text not in ingredients:
                            ingredients.append(ingredient_text)
                    
                    if ingredients:  # Break once we've found ingredients
                        break
            
            # If still no ingredients, look harder
            if not ingredients:
                # Find headers that might indicate ingredients
                headers = tasty_recipes_div.select('h2, h3, h4, h5')
                for header in headers:
                    if 'ingredient' in header.get_text().lower():
                        # Look at the next unordered list or paragraphs
                        ingredient_list = header.find_next('ul')
                        if ingredient_list:
                            for li in ingredient_list.select('li'):
                                text = li.get_text(strip=True)
                                if text:
                                    ingredients.append(text)
                        
                        if not ingredients:
                            # Try paragraphs instead
                            next_p = header.find_next('p')
                            while next_p and not next_p.name in ['h2', 'h3', 'h4', 'h5']:
                                text = next_p.get_text(strip=True)
                                if text:
                                    ingredients.append(text)
                                next_p = next_p.find_next()
                        
                        break
            
            # Extract instructions - try multiple approaches
            instructions = []
            
            # Try structured instruction lists
            instruction_selectors = [
                '.tasty-recipes-instructions li',
                '.wprm-recipe-instruction',
                '.instructions-list li',
                'div:has(> h3:contains("Instructions")) li',
                'div:has(> h2:contains("Instructions")) li',
                'div:has(> h3:contains("Directions")) li',
                'div:has(> h2:contains("Directions")) li'
            ]
            
            for selector in instruction_selectors:
                instruction_elems = tasty_recipes_div.select(selector)
                if instruction_elems:
                    for elem in instruction_elems:
                        # Remove image tags from instructions
                        for img in elem.select('img'):
                            img.decompose()
                        
                        instruction_text = elem.get_text(strip=True)
                        if instruction_text and instruction_text not in instructions:
                            instructions.append(instruction_text)
                    
                    if instructions:  # Break once we've found instructions
                        break
            
            # If still no instructions, look harder
            if not instructions:
                # Find headers that might indicate instructions
                headers = tasty_recipes_div.select('h2, h3, h4, h5')
                for header in headers:
                    header_text = header.get_text().lower()
                    if 'instruction' in header_text or 'direction' in header_text or 'method' in header_text:
                        # Look at the next unordered list or paragraphs
                        instruction_list = header.find_next('ol')
                        if instruction_list:
                            for li in instruction_list.select('li'):
                                text = li.get_text(strip=True)
                                if text:
                                    instructions.append(text)
                        
                        if not instructions:
                            # Try paragraphs instead
                            next_p = header.find_next('p')
                            while next_p and not next_p.name in ['h2', 'h3', 'h4', 'h5']:
                                text = next_p.get_text(strip=True)
                                if text:
                                    instructions.append(text)
                                next_p = next_p.find_next()
                        
                        break
            
            # Extract notes
            notes = []
            notes_selectors = [
                '.tasty-recipes-notes-body p',
                '.wprm-recipe-notes p',
                'div:has(> h3:contains("Notes")) p'
            ]
            
            for selector in notes_selectors:
                notes_elems = tasty_recipes_div.select(selector)
                if notes_elems:
                    for elem in notes_elems:
                        note_text = elem.get_text(strip=True)
                        if note_text:
                            notes.append(note_text)
                    
                    if notes:  # Break once we've found notes
                        break
            
            # Extract nutrition information - enhanced to handle multiple formats
            nutrition = self._extract_nutrition(tasty_recipes_div, soup)
            
            # Extract categories and tags - try multiple approaches
            categories = []
            
            # Try structured categories
            category_selectors = [
                '.tasty-recipes-category',
                '.wprm-recipe-category',
                '.recipe-category'
            ]
            
            for selector in category_selectors:
                category_elem = tasty_recipes_div.select_one(selector)
                if category_elem:
                    category_text = category_elem.get_text(strip=True)
                    if category_text:
                        # Clean up and split categories
                        if 'Category:' in category_text:
                            category_text = category_text.split('Category:')[1]
                        
                        categories.extend([c.strip() for c in category_text.split(',')])
                        break
            
            # Try to find cuisine
            cuisine = None
            cuisine_selectors = [
                '.tasty-recipes-cuisine',
                '.wprm-recipe-cuisine',
                '.recipe-cuisine'
            ]
            
            for selector in cuisine_selectors:
                cuisine_elem = tasty_recipes_div.select_one(selector)
                if cuisine_elem:
                    cuisine_text = cuisine_elem.get_text(strip=True)
                    if cuisine_text:
                        # Clean up cuisine
                        if 'Cuisine:' in cuisine_text:
                            cuisine_text = cuisine_text.split('Cuisine:')[1]
                        
                        cuisine = cuisine_text.strip()
                        break
            
            # Extract keywords/tags
            tags = []
            keywords_selectors = [
                '.tasty-recipes-keywords',
                '.wprm-recipe-keyword',
                '.recipe-tags',
                'meta[name="keywords"]'
            ]
            
            for selector in keywords_selectors:
                try:
                    if selector.startswith('meta'):
                        # Handle meta tag
                        keywords_elem = soup.select_one(selector)
                        if keywords_elem:
                            keywords_text = keywords_elem.get('content', '')
                    else:
                        # Handle normal element
                        keywords_elem = tasty_recipes_div.select_one(selector)
                        if keywords_elem:
                            keywords_text = keywords_elem.get_text(strip=True)
                        else:
                            continue
                    
                    if keywords_text:
                        # Clean up and split keywords
                        if 'Keywords:' in keywords_text:
                            keywords_text = keywords_text.split('Keywords:')[1]
                        
                        if ',' in keywords_text:
                            tags.extend([tag.strip() for tag in keywords_text.split(',')])
                        else:
                            tags.extend([tag.strip() for tag in keywords_text.split(' ')])
                        
                        break
                except:
                    continue
            
            # Also add categories to tags
            for category in categories:
                if category not in tags:
                    tags.append(category)
            
            # Add cuisine to tags if not already included
            if cuisine and cuisine not in tags:
                tags.append(cuisine)
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.warning(f"Recipe missing sufficient ingredients ({len(ingredients)}) or instructions ({len(instructions)}) in {url}")
                return None
            
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
                'cuisine': cuisine,
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
    
    def _extract_nutrition(self, recipe_div, soup=None):
        """
        Extract nutrition information from the recipe with improved robustness
        
        Args:
            recipe_div (BeautifulSoup element): Recipe container div
            soup (BeautifulSoup, optional): Full page soup object for fallbacks
            
        Returns:
            dict: Nutrition information
        """
        try:
            nutrition_data = {}
            
            # Try JSON-LD first
            if soup:
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'Recipe' and 'nutrition' in data:
                            nutrition = data['nutrition']
                            for key, value in nutrition.items():
                                if key.startswith('@'):
                                    continue
                                
                                # Clean up key
                                clean_key = key.replace('Content', '').lower()
                                
                                # Clean up value (extract number)
                                if isinstance(value, str):
                                    match = re.search(r'(\d+(\.\d+)?)', value)
                                    if match:
                                        nutrition_data[clean_key] = float(match.group(1))
                            
                            if nutrition_data:
                                return nutrition_data
                    except:
                        continue
            
            # Try structured nutrition blocks
            nutrition_selectors = [
                '.tasty-recipes-nutrition-label',
                '.wprm-nutrition-label',
                '.nutrition-label',
                '.nutrition-facts'
            ]
            
            nutrition_div = None
            for selector in nutrition_selectors:
                nutrition_div = recipe_div.select_one(selector)
                if nutrition_div:
                    break
            
            if nutrition_div:
                # Extract key nutrition info
                nutrient_map = {
                    'calories': [r'Calories:?\s*(\d+)', r'calories', r'energy'],
                    'fat': [r'Fat:?\s*(\d+)g', r'fat'],
                    'carbs': [r'Carbohydrates?:?\s*(\d+)g', r'carbs?'],
                    'protein': [r'Protein:?\s*(\d+)g', r'protein'],
                    'fiber': [r'Fiber:?\s*(\d+)g', r'fiber'],
                    'sugar': [r'Sugar:?\s*(\d+)g', r'sugars?'],
                    'sodium': [r'Sodium:?\s*(\d+)mg', r'sodium'],
                    'cholesterol': [r'Cholesterol:?\s*(\d+)mg', r'cholesterol']
                }
                
                nutrition_text = nutrition_div.get_text()
                
                for nutrient, patterns in nutrient_map.items():
                    for pattern in patterns:
                        # Look for structured patterns first
                        match = re.search(pattern, nutrition_text, re.IGNORECASE)
                        if match and match.groups():
                            try:
                                nutrition_data[nutrient] = float(match.group(1))
                                break
                            except (ValueError, IndexError):
                                pass
                        
                        # If structured pattern fails, try to find values next to labels
                        if not nutrition_data.get(nutrient):
                            label_elems = nutrition_div.select_one('th, td, span, div:contains("' + pattern + '")')
                            if label_elems:
                                next_elem = label_elems.find_next('td, span, div')
                                if next_elem:
                                    value_text = next_elem.get_text(strip=True)
                                    value_match = re.search(r'(\d+(\.\d+)?)', value_text)
                                    if value_match:
                                        nutrition_data[nutrient] = float(value_match.group(1))
                                        break
            
            # If Nutrifox is used, we might find it in an iframe or data attribute
            if not nutrition_data:
                nutrition_iframe = recipe_div.select_one('iframe[id^="nutrifox-label-"], [data-nutrifox-id]')
                if nutrition_iframe:
                    # Since we can't directly access iframe content, try to extract from page text
                    nutrifox_id = nutrition_iframe.get('data-nutrifox-id') or nutrition_iframe.get('id', '').replace('nutrifox-label-', '')
                    
                    if nutrifox_id:
                        logger.info(f"Found Nutrifox nutrition with ID: {nutrifox_id}")
                        
                        # Look for key nutrition values in the page
                        page_text = recipe_div.get_text()
                        
                        # Extract calories
                        calorie_match = re.search(r'Calories:?\s*(\d+)', page_text)
                        if calorie_match:
                            nutrition_data['calories'] = float(calorie_match.group(1))
                        
                        # Extract fat
                        fat_match = re.search(r'Fat:?\s*(\d+)g', page_text)
                        if fat_match:
                            nutrition_data['fat'] = float(fat_match.group(1))
                        
                        # Extract carbs
                        carbs_match = re.search(r'Carbohydrates?:?\s*(\d+)g', page_text)
                        if carbs_match:
                            nutrition_data['carbs'] = float(carbs_match.group(1))
                        
                        # Extract protein
                        protein_match = re.search(r'Protein:?\s*(\d+)g', page_text)
                        if protein_match:
                            nutrition_data['protein'] = float(protein_match.group(1))
            
            return nutrition_data
            
        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            logger.error(traceback.format_exc())
            return {}
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
    """Enhanced scraper for Pinch of Yum recipes"""
    
    def __init__(self):
        """Initialize the Pinch of Yum scraper with headers and category URLs"""
        logger.info("Initializing Pinch of Yum Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://pinchofyum.com/'
        }
        
        # Direct recipe links - these are the main recipe landing pages
        self.recipe_list_pages = [
            "https://pinchofyum.com/recipes",
            "https://pinchofyum.com/all-recipes"
        ]
        
        # Category URLs for different recipe types
        self.category_urls = [
            "https://pinchofyum.com/recipes/breakfast",
            "https://pinchofyum.com/recipes/lunch",
            "https://pinchofyum.com/recipes/dinner",
            "https://pinchofyum.com/recipes/appetizer",
            "https://pinchofyum.com/recipes/snack",
            "https://pinchofyum.com/recipes/dessert",
            "https://pinchofyum.com/recipes/drinks",
            "https://pinchofyum.com/recipes/instant-pot",
            "https://pinchofyum.com/recipes/crockpot",
            "https://pinchofyum.com/recipes/vegetarian",
            "https://pinchofyum.com/recipes/vegan",
            "https://pinchofyum.com/recipes/gluten-free",
            "https://pinchofyum.com/recipes/dairy-free",
            "https://pinchofyum.com/recipes/soup",
            "https://pinchofyum.com/recipes/salad"
        ]
        
        # Cache of seen recipe links to avoid duplicates
        self.seen_recipe_links = set()
        
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
        
        # First, try to get recipes from the full recipe list pages
        for list_page in self.recipe_list_pages:
            if len(recipes) >= limit:
                break
                
            try:
                logger.info(f"Fetching recipes from main list page: {list_page}")
                recipe_links = self._get_recipe_links_from_page(list_page, limit - len(recipes))
                
                for url in recipe_links:
                    if len(recipes) >= limit:
                        break
                        
                    recipe_info = self._scrape_recipe(url)
                    if recipe_info:
                        recipes.append(recipe_info)
                        
                # If we found a good number of recipes, stop here
                if len(recipes) >= limit * 0.5:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing main list page {list_page}: {str(e)}")
                logger.error(traceback.format_exc())
        
        # If we still need more recipes, try category pages
        if len(recipes) < limit:
            # Shuffle categories to get a variety
            random.shuffle(self.category_urls)
            
            # Calculate recipes needed per category
            remaining = limit - len(recipes)
            recipes_per_category = max(3, remaining // len(self.category_urls))
            
            for category_url in self.category_urls:
                if len(recipes) >= limit:
                    break
                    
                try:
                    logger.info(f"Scraping category page: {category_url}")
                    recipes_needed = min(recipes_per_category, limit - len(recipes))
                    
                    # Get recipe links from this category
                    recipe_links = self._get_recipe_links_from_category(category_url, recipes_needed)
                    logger.info(f"Found {len(recipe_links)} recipe links in {category_url}")
                    
                    # Process recipe links
                    category_count = 0
                    for url in recipe_links:
                        if len(recipes) >= limit or category_count >= recipes_needed:
                            logger.info(f"Reached limit for category {category_url}")
                            break
                            
                        recipe_info = self._scrape_recipe(url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            category_count += 1
                    
                    # Be polite between categories
                    time.sleep(random.uniform(3, 5))
                    
                except Exception as e:
                    logger.error(f"Error processing category {category_url}: {str(e)}")
                    logger.error(traceback.format_exc())
        
        logger.info(f"Total Pinch of Yum recipes scraped: {len(recipes)}")
        return recipes
    
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
            
            # Skip URLs that don't look like recipe pages
            if self._is_non_recipe_url(url):
                logger.info(f"Skipping non-recipe URL: {url}")
                return None
            
            # Get the page content
            response = requests.get(url, headers=self.headers, timeout=30)
            
            # Check for valid response
            if response.status_code != 200:
                logger.error(f"Error accessing recipe URL: {url} - Status: {response.status_code}")
                return None
            
            # Extract recipe info
            recipe_info = self._extract_recipe_info(response.text, url)
            
            # Add some delay between requests
            time.sleep(random.uniform(2, 4))
            
            return recipe_info
            
        except Exception as e:
            logger.error(f"Error scraping recipe {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _is_non_recipe_url(self, url):
        """
        Check if URL is likely not a recipe page
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL is likely not a recipe page
        """
        # Check for typical non-recipe sections
        non_recipe_patterns = [
            '/about', '/contact', '/terms', '/privacy', '/faq', 
            '/page/', '/category/', '/tag/', '/author/',
            'comment-', '#comment', '#respond', 'pinchofyum.com/page/',
            'pinchofyum.com/category/', '/wp-', '.com/blog/'
        ]
        
        for pattern in non_recipe_patterns:
            if pattern in url:
                return True
        
        # Check for recipe directory URLs
        if url.rstrip('/') in [u.rstrip('/') for u in self.category_urls]:
            return True
        
        # Check for recipe list pages
        if url.rstrip('/') in [u.rstrip('/') for u in self.recipe_list_pages]:
            return True
        
        return False
    
    def _get_recipe_links_from_page(self, page_url, limit=1100):
        """
        Get recipe links from any page
        
        Args:
            page_url (str): URL of the page
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        
        try:
            logger.info(f"Fetching recipe links from: {page_url}")
            
            # Get the page content
            response = requests.get(page_url, headers=self.headers, timeout=30)
            
            # Check for valid response
            if response.status_code != 200:
                logger.error(f"Error accessing page: {page_url} - Status: {response.status_code}")
                return recipe_links
            
            # Parse the page
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all links on the page
            links = soup.find_all('a', href=True)
            
            # Base URL for relative links
            base_url = "https://pinchofyum.com"
            
            # Process links
            for link in links:
                href = link.get('href')
                
                # Skip if no href
                if not href:
                    continue
                
                # Make absolute URL
                if not href.startswith(('http://', 'https://')):
                    href = urljoin(base_url, href)
                
                # Skip if not from pinchofyum.com
                if 'pinchofyum.com' not in href:
                    continue
                
                # Skip non-recipe URLs
                if self._is_non_recipe_url(href):
                    continue
                
                # Skip if already seen
                if href in self.seen_recipe_links:
                    continue
                
                # Look for recipe indicators in URL
                recipe_indicators = [
                    '/recipe/', 
                    '/-recipe', 
                    'pinchofyum.com/recipes/'
                ]
                
                # Skip if no recipe indicators - unless in deeper folders
                if not any(indicator in href for indicator in recipe_indicators):
                    # Check if deep enough to likely be a recipe
                    path = urlparse(href).path
                    path_parts = [p for p in path.split('/') if p]
                    
                    # Most recipe URLs have at least one folder after domain
                    if len(path_parts) < 1:
                        continue
                
                # Add to recipe links
                recipe_links.append(href)
                self.seen_recipe_links.add(href)
                
                # Stop if reached limit
                if len(recipe_links) >= limit:
                    break
            
            logger.info(f"Found {len(recipe_links)} recipe links on page {page_url}")
            return recipe_links
            
        except Exception as e:
            logger.error(f"Error getting recipe links from {page_url}: {str(e)}")
            logger.error(traceback.format_exc())
            return recipe_links
    
    def _get_recipe_links_from_category(self, category_url, limit=50):
        """
        Get recipe links from a category page with pagination
        
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
                # Construct page URL
                if page > 1:
                    # Check if URL ends with slash
                    if category_url.endswith('/'):
                        page_url = f"{category_url}page/{page}/"
                    else:
                        page_url = f"{category_url}/page/{page}/"
                else:
                    page_url = category_url
                
                logger.info(f"Fetching page {page}: {page_url}")
                
                # Get links from this page
                new_links = self._get_recipe_links_from_page(page_url, limit - len(recipe_links))
                
                # Add new links to our list
                for link in new_links:
                    if link not in recipe_links:
                        recipe_links.append(link)
                
                # Move to next page if we found links and need more
                if new_links and len(recipe_links) < limit:
                    page += 1
                    # Be polite
                    time.sleep(random.uniform(1, 2))
                else:
                    # Stop if no links found
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching recipe links from page {page}: {str(e)}")
                logger.error(traceback.format_exc())
                break
        
        logger.info(f"Found total {len(recipe_links)} recipe links in category {category_url}")
        return recipe_links
    
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
            
            # First, verify this is a recipe page
            if not self._verify_recipe_page(soup, url):
                logger.warning(f"Not a valid recipe page: {url}")
                return None
            
            # Multiple ways to identify recipe content
            recipe_container = self._find_recipe_container(soup)
            
            if not recipe_container:
                logger.warning(f"No recipe container found in {url}")
                return None
            
            # Extract recipe details
            title = self._extract_title(soup, recipe_container)
            image_url = self._extract_image_url(soup, recipe_container)
            ingredients = self._extract_ingredients(soup, recipe_container)
            instructions = self._extract_instructions(soup, recipe_container)
            
            # Skip if we couldn't extract required data
            if not title or len(ingredients) < 2 or len(instructions) < 2:
                logger.warning(f"Missing essential recipe data for {url}: title={bool(title)}, ingredients={len(ingredients)}, instructions={len(instructions)}")
                return None
            
            # Extract additional data
            metadata = self._extract_metadata(soup, recipe_container)
            notes = self._extract_notes(soup, recipe_container)
            nutrition = self._extract_nutrition(soup)
            categories, tags, cuisine = self._extract_categories_and_tags(soup, recipe_container)
            
            # Determine complexity
            complexity = self._determine_complexity(ingredients, instructions)
            
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
                'notes': notes
            }
            
            logger.info(f"Successfully scraped recipe: {title}")
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _verify_recipe_page(self, soup, url):
        """
        Verify this is actually a recipe page
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): URL of the page
            
        Returns:
            bool: True if this is a recipe page
        """
        # Check for recipe JSON-LD
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    return True
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            return True
            except:
                pass
        
        # Check for common recipe indicators
        recipe_indicators = [
            'div[id^="tasty-recipes"]', 
            '.tasty-recipes',
            '.wprm-recipe-container',
            '.recipe-container',
            'h2:-soup-contains("Ingredients")',
            'h3:-soup-contains("Ingredients")'
        ]
        
        for indicator in recipe_indicators:
            try:
                if soup.select(indicator):
                    return True
            except:
                pass
        
        # Look for recipe keyword
        try:
            meta_keywords = soup.find('meta', {'name': 'keywords'})
            if meta_keywords:
                keywords = meta_keywords.get('content', '').lower()
                if 'recipe' in keywords:
                    return True
        except:
            pass
        
        # Look for recipe title pattern
        title_elem = soup.find('title')
        if title_elem:
            title_text = title_elem.get_text().lower()
            if 'recipe' in title_text or 'how to make' in title_text:
                return True
        
        return False
    
    def _find_recipe_container(self, soup):
        """
        Find the main recipe container in the HTML
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            BeautifulSoup element: Recipe container or None
        """
        # Try multiple container selectors in order of specificity
        container_selectors = [
            'div[id^="tasty-recipes-"]',  # Tasty Recipes plugin
            '.tasty-recipes',
            '.tasty-recipe',
            '.wprm-recipe-container',  # WP Recipe Maker
            '.recipe-content',
            'article.post',
            'main article',
            '.entry-content',
            '.post-content'
        ]
        
        for selector in container_selectors:
            try:
                container = soup.select_one(selector)
                if container:
                    return container
            except:
                pass
        
        # If no container found, try the main content
        return soup.select_one('main, article, .content')
    
    def _extract_title(self, soup, container):
        """
        Extract recipe title
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            str: Recipe title
        """
        # Try container title first
        title_selectors = [
            '.tasty-recipes-title',
            '.wprm-recipe-name',
            'h1.entry-title',
            'h1',
            '.post-title',
            '.recipe-title'
        ]
        
        for selector in title_selectors:
            try:
                title_elem = container.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    if title:
                        return title
            except:
                pass
        
        # Try page title
        try:
            title_elem = soup.select_one('title')
            if title_elem:
                title = title_elem.get_text().strip()
                # Clean up title
                if ' - ' in title:
                    title = title.split(' - ')[0].strip()
                elif ' | ' in title:
                    title = title.split(' | ')[0].strip()
                return title
        except:
            pass
        
        # Try JSON-LD
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Recipe' and data.get('name'):
                    return data['name']
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe' and item.get('name'):
                            return item['name']
        except:
            pass
        
        return None
    
    def _extract_image_url(self, soup, container):
        """
        Extract recipe image URL
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            str: Image URL or None
        """
        # Try recipe container image
        image_selectors = [
            '.tasty-recipes-image img',
            '.wprm-recipe-image img',
            '.recipe-image img',
            '.post-thumbnail img',
            '.featured-image img',
            '.entry-content img'
        ]
        
        for selector in image_selectors:
            try:
                img = container.select_one(selector)
                if img:
                    image_url = img.get('src') or img.get('data-src')
                    if image_url:
                        return image_url
            except:
                pass
        
        # Try OpenGraph image
        try:
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image:
                return og_image.get('content')
        except:
            pass
        
        # Try JSON-LD
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Recipe' and data.get('image'):
                    image_data = data['image']
                    if isinstance(image_data, str):
                        return image_data
                    elif isinstance(image_data, dict) and image_data.get('url'):
                        return image_data['url']
                    elif isinstance(image_data, list) and len(image_data) > 0:
                        if isinstance(image_data[0], str):
                            return image_data[0]
                        elif isinstance(image_data[0], dict) and image_data[0].get('url'):
                            return image_data[0]['url']
        except:
            pass
        
        return None
    
    def _extract_ingredients(self, soup, container):
        """
        Extract recipe ingredients
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            list: Ingredients
        """
        ingredients = []
        
        # Try multiple ingredient selectors
        ingredient_selectors = [
            '.tasty-recipes-ingredients li',
            '.tasty-recipes-ingredients-body li',
            '.wprm-recipe-ingredient',
            '.recipe-ingredients li',
            'div:-soup-contains("Ingredients") + ul li',
            'h2:-soup-contains("Ingredients") + ul li',
            'h3:-soup-contains("Ingredients") + ul li',
            'h4:-soup-contains("Ingredients") + ul li'
        ]
        
        for selector in ingredient_selectors:
            try:
                ing_elems = container.select(selector)
                if ing_elems:
                    for elem in ing_elems:
                        text = elem.get_text().strip()
                        if text and not any(bad in text.lower() for bad in ['for the', 'instructions']):
                            ingredients.append(text)
                    
                    if ingredients:
                        break
            except:
                pass
        
        # Try JSON-LD if no ingredients found
        if not ingredients:
            try:
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Recipe' and data.get('recipeIngredient'):
                        return data['recipeIngredient']
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe' and item.get('recipeIngredient'):
                                return item['recipeIngredient']
            except:
                pass
        
        # Try harder if still no ingredients
        if not ingredients:
            try:
                # Look for ingredient headings
                headers = container.select('h2, h3, h4, h5')
                for header in headers:
                    if 'ingredient' in header.get_text().lower():
                        # Try to find the ingredient list after this header
                        ing_list = header.find_next('ul')
                        if ing_list:
                            for li in ing_list.select('li'):
                                text = li.get_text().strip()
                                if text:
                                    ingredients.append(text)
                        break
            except:
                pass
        
        return ingredients
    
    def _extract_instructions(self, soup, container):
        """
        Extract recipe instructions
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            list: Instructions
        """
        instructions = []
        
        # Try multiple instruction selectors
        instruction_selectors = [
            '.tasty-recipes-instructions li',
            '.tasty-recipes-instructions-body li',
            '.wprm-recipe-instruction',
            '.recipe-instructions li',
            'div:-soup-contains("Instructions") + ol li',
            'h2:-soup-contains("Instructions") + ol li',
            'h3:-soup-contains("Instructions") + ol li',
            'h4:-soup-contains("Instructions") + ol li',
            'div:-soup-contains("Directions") + ol li',
            'h2:-soup-contains("Directions") + ol li',
            'h3:-soup-contains("Directions") + ol li',
            'h4:-soup-contains("Directions") + ol li'
        ]
        
        for selector in instruction_selectors:
            try:
                inst_elems = container.select(selector)
                if inst_elems:
                    for elem in inst_elems:
                        # Remove image tags
                        for img in elem.select('img'):
                            img.decompose()
                        
                        text = elem.get_text().strip()
                        if text:
                            instructions.append(text)
                    
                    if instructions:
                        break
            except:
                pass
        
        # Try JSON-LD if no instructions found
        if not instructions:
            try:
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Recipe' and data.get('recipeInstructions'):
                        inst_data = data['recipeInstructions']
                        if isinstance(inst_data, list):
                            for item in inst_data:
                                if isinstance(item, str):
                                    instructions.append(item)
                                elif isinstance(item, dict) and item.get('text'):
                                    instructions.append(item['text'])
                        else:
                            instructions.append(str(inst_data))
                        return instructions
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe' and item.get('recipeInstructions'):
                                inst_data = item['recipeInstructions']
                                if isinstance(inst_data, list):
                                    for sub_item in inst_data:
                                        if isinstance(sub_item, str):
                                            instructions.append(sub_item)
                                        elif isinstance(sub_item, dict) and sub_item.get('text'):
                                            instructions.append(sub_item['text'])
                                else:
                                    instructions.append(str(inst_data))
                                return instructions
            except:
                pass
        
        # Try harder if still no instructions
        if not instructions:
            try:
                # Look for instruction headings
                headers = container.select('h2, h3, h4, h5')
                for header in headers:
                    header_text = header.get_text().lower()
                    if 'instruction' in header_text or 'direction' in header_text:
                        # Try to find the instruction list after this header
                        inst_list = header.find_next('ol')
                        if inst_list:
                            for li in inst_list.select('li'):
                                text = li.get_text().strip()
                                if text:
                                    instructions.append(text)
                        
                        # If no ordered list, try paragraphs
                        if not instructions:
                            p = header.find_next('p')
                            step_num = 1
                            while p and not p.name in ['h2', 'h3', 'h4', 'h5']:
                                text = p.get_text().strip()
                                if text:
                                    # Try to detect if this is a step
                                    if text.startswith(f"{step_num}.") or len(text) > 20:
                                        instructions.append(text)
                                        step_num += 1
                                p = p.find_next()
                        
                        break
            except:
                pass
        
        return instructions
    
    def _extract_metadata(self, soup, container):
        """
        Extract recipe metadata (prep time, cook time, etc.)
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            dict: Metadata
        """
        metadata = {}
        
        # Try to extract times from HTML
        time_map = {
            'prep_time': ['.tasty-recipes-prep-time', '.wprm-recipe-prep-time-container', '.prep-time'],
            'cook_time': ['.tasty-recipes-cook-time', '.wprm-recipe-cook-time-container', '.cook-time'],
            'total_time': ['.tasty-recipes-total-time', '.wprm-recipe-total-time-container', '.total-time']
        }
        
        for meta_key, selectors in time_map.items():
            for selector in selectors:
                try:
                    elem = container.select_one(selector)
                    if elem:
                        time_text = elem.get_text().strip()
                        minutes = self._parse_time_text(time_text)
                        if minutes:
                            metadata[meta_key] = minutes
                            break
                except:
                    pass
        
        # Try to extract servings
        serving_selectors = [
            '.tasty-recipes-yield',
            '.wprm-recipe-servings',
            '.recipe-yield',
            '.servings'
        ]
        
        for selector in serving_selectors:
            try:
                elem = container.select_one(selector)
                if elem:
                    yield_text = elem.get_text().strip()
                    servings_match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+))?', yield_text)
                    if servings_match:
                        servings = servings_match.group(2) or servings_match.group(1)
                        metadata['servings'] = int(servings)
                        break
            except:
                pass
        
        # Try JSON-LD if metadata is incomplete
        if not metadata or len(metadata) < 3:
            try:
                for script in soup.find_all('script', {'type': 'application/ld+json'}):
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Recipe':
                        # Extract times
                        for time_type, json_key in [
                            ('prep_time', 'prepTime'),
                            ('cook_time', 'cookTime'),
                            ('total_time', 'totalTime')
                        ]:
                            if json_key in data and not metadata.get(time_type):
                                minutes = self._parse_iso_duration(data[json_key])
                                if minutes:
                                    metadata[time_type] = minutes
                        
                        # Extract servings
                        if 'recipeYield' in data and not metadata.get('servings'):
                            yield_data = data['recipeYield']
                            if isinstance(yield_data, list):
                                yield_text = yield_data[0] if yield_data else ""
                            else:
                                yield_text = str(yield_data)
                            
                            servings_match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+))?', yield_text)
                            if servings_match:
                                servings = servings_match.group(2) or servings_match.group(1)
                                metadata['servings'] = int(servings)
                    
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                # Extract times
                                for time_type, json_key in [
                                    ('prep_time', 'prepTime'),
                                    ('cook_time', 'cookTime'),
                                    ('total_time', 'totalTime')
                                ]:
                                    if json_key in item and not metadata.get(time_type):
                                        minutes = self._parse_iso_duration(item[json_key])
                                        if minutes:
                                            metadata[time_type] = minutes
                                
                                # Extract servings
                                if 'recipeYield' in item and not metadata.get('servings'):
                                    yield_data = item['recipeYield']
                                    if isinstance(yield_data, list):
                                        yield_text = yield_data[0] if yield_data else ""
                                    else:
                                        yield_text = str(yield_data)
                                    
                                    servings_match = re.search(r'(\d+)(?:\s*[-–]\s*(\d+))?', yield_text)
                                    if servings_match:
                                        servings = servings_match.group(2) or servings_match.group(1)
                                        metadata['servings'] = int(servings)
            except:
                pass
        
        return metadata
    
    def _extract_notes(self, soup, container):
        """
        Extract recipe notes
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            list: Notes
        """
        notes = []
        
        # Try multiple note selectors
        note_selectors = [
            '.tasty-recipes-notes-body p',
            '.wprm-recipe-notes p',
            '.recipe-notes p',
            'div:-soup-contains("Notes") p'
        ]
        
        for selector in note_selectors:
            try:
                note_elems = container.select(selector)
                if note_elems:
                    for elem in note_elems:
                        text = elem.get_text().strip()
                        if text and not text.startswith('NOTES'):
                            notes.append(text)
                    
                    if notes:
                        break
            except:
                pass
        
        # Try harder if no notes found
        if not notes:
            try:
                # Look for notes heading
                headers = container.select('h2, h3, h4, h5')
                for header in headers:
                    if 'note' in header.get_text().lower():
                        # Get paragraphs after this header
                        p = header.find_next('p')
                        while p and not p.name in ['h2', 'h3', 'h4', 'h5']:
                            text = p.get_text().strip()
                            if text:
                                notes.append(text)
                            p = p.find_next()
                        break
            except:
                pass
        
        return notes
    
    def _extract_nutrition(self, soup):
        """
        Extract nutrition information
        
        Args:
            soup (BeautifulSoup): Full page soup
            
        Returns:
            dict: Nutrition information
        """
        nutrition_data = {}
        
        # Try JSON-LD first for most accurate data
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Recipe' and 'nutrition' in data:
                    nutrition = data['nutrition']
                    
                    # Extract key nutrition values
                    nutrient_map = {
                        'calories': 'calories',
                        'fat': 'fatContent',
                        'carbs': 'carbohydrateContent',
                        'protein': 'proteinContent',
                        'fiber': 'fiberContent',
                        'sugar': 'sugarContent',
                        'sodium': 'sodiumContent',
                        'cholesterol': 'cholesterolContent'
                    }
                    
                    for target_key, json_key in nutrient_map.items():
                        if json_key in nutrition:
                            value = nutrition[json_key]
                            if isinstance(value, str):
                                # Extract number from string like "240 calories"
                                match = re.search(r'(\d+(\.\d+)?)', value)
                                if match:
                                    nutrition_data[target_key] = float(match.group(1))
                            elif isinstance(value, (int, float)):
                                nutrition_data[target_key] = float(value)
                    
                    if nutrition_data:
                        return nutrition_data
                
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe' and 'nutrition' in item:
                            nutrition = item['nutrition']
                            
                            # Extract key nutrition values
                            nutrient_map = {
                                'calories': 'calories',
                                'fat': 'fatContent',
                                'carbs': 'carbohydrateContent',
                                'protein': 'proteinContent',
                                'fiber': 'fiberContent',
                                'sugar': 'sugarContent',
                                'sodium': 'sodiumContent',
                                'cholesterol': 'cholesterolContent'
                            }
                            
                            for target_key, json_key in nutrient_map.items():
                                if json_key in nutrition:
                                    value = nutrition[json_key]
                                    if isinstance(value, str):
                                        # Extract number from string like "240 calories"
                                        match = re.search(r'(\d+(\.\d+)?)', value)
                                        if match:
                                            nutrition_data[target_key] = float(match.group(1))
                                    elif isinstance(value, (int, float)):
                                        nutrition_data[target_key] = float(value)
                            
                            if nutrition_data:
                                return nutrition_data
        except:
            pass
        
        # Try finding nutrition from HTML
        try:
            # Look for Nutrifox iframe
            nutrifox_iframe = soup.select_one('iframe[id^="nutrifox-label-"]')
            if nutrifox_iframe:
                # Nutrifox data is usually near the iframe
                nearby_text = ''
                
                # Try to get parent container
                parent = nutrifox_iframe.parent
                if parent:
                    nearby_text = parent.get_text()
                
                # Extract key nutrition info using regex
                nutrient_patterns = {
                    'calories': r'Calories:?\s*(\d+)',
                    'fat': r'Fat:?\s*(\d+)g',
                    'carbs': r'Carbohydrates?:?\s*(\d+)g',
                    'protein': r'Protein:?\s*(\d+)g',
                    'fiber': r'Fiber:?\s*(\d+)g',
                    'sugar': r'Sugar:?\s*(\d+)g',
                    'sodium': r'Sodium:?\s*(\d+)mg',
                    'cholesterol': r'Cholesterol:?\s*(\d+)mg'
                }
                
                for nutrient, pattern in nutrient_patterns.items():
                    match = re.search(pattern, nearby_text, re.IGNORECASE)
                    if match:
                        nutrition_data[nutrient] = float(match.group(1))
        except:
            pass
        
        # Try looking for structured nutrition info
        if not nutrition_data:
            try:
                nutrition_section = soup.select_one('.nutrition-label, .wprm-nutrition-label, .tasty-recipes-nutrition')
                if nutrition_section:
                    nutrition_text = nutrition_section.get_text()
                    
                    # Extract key nutrition info using regex
                    nutrient_patterns = {
                        'calories': r'Calories:?\s*(\d+)',
                        'fat': r'Fat:?\s*(\d+)g',
                        'carbs': r'Carbohydrates?:?\s*(\d+)g',
                        'protein': r'Protein:?\s*(\d+)g',
                        'fiber': r'Fiber:?\s*(\d+)g',
                        'sugar': r'Sugar:?\s*(\d+)g',
                        'sodium': r'Sodium:?\s*(\d+)mg',
                        'cholesterol': r'Cholesterol:?\s*(\d+)mg'
                    }
                    
                    for nutrient, pattern in nutrient_patterns.items():
                        match = re.search(pattern, nutrition_text, re.IGNORECASE)
                        if match:
                            nutrition_data[nutrient] = float(match.group(1))
            except:
                pass
        
        return nutrition_data
    
    def _extract_categories_and_tags(self, soup, container):
        """
        Extract recipe categories, tags, and cuisine
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            tuple: (categories, tags, cuisine)
        """
        categories = []
        tags = []
        cuisine = None
        
        # Try to extract categories
        category_selectors = [
            '.tasty-recipes-category',
            '.wprm-recipe-category',
            '.recipe-category',
            '.category-links a'
        ]
        
        for selector in category_selectors:
            try:
                elems = container.select(selector)
                if not elems:
                    elems = soup.select(selector)
                
                if elems:
                    for elem in elems:
                        text = elem.get_text().strip()
                        if text:
                            if 'Category:' in text:
                                text = text.split('Category:')[1].strip()
                            if ',' in text:
                                for cat in text.split(','):
                                    cat = cat.strip()
                                    if cat and cat not in categories:
                                        categories.append(cat)
                            else:
                                if text not in categories:
                                    categories.append(text)
            except:
                pass
        
        # Try to extract cuisine
        cuisine_selectors = [
            '.tasty-recipes-cuisine',
            '.wprm-recipe-cuisine',
            '.recipe-cuisine'
        ]
        
        for selector in cuisine_selectors:
            try:
                elem = container.select_one(selector)
                if elem:
                    text = elem.get_text().strip()
                    if text:
                        if 'Cuisine:' in text:
                            text = text.split('Cuisine:')[1].strip()
                        cuisine = text
                        break
            except:
                pass
        
        # Try to extract keywords/tags
        tag_selectors = [
            '.tasty-recipes-keywords',
            '.wprm-recipe-keyword',
            '.recipe-tags',
            '.tags a'
        ]
        
        for selector in tag_selectors:
            try:
                elems = container.select(selector)
                if not elems:
                    elems = soup.select(selector)
                
                if elems:
                    for elem in elems:
                        text = elem.get_text().strip()
                        if text:
                            if 'Keywords:' in text:
                                text = text.split('Keywords:')[1].strip()
                            if ',' in text:
                                for tag in text.split(','):
                                    tag = tag.strip()
                                    if tag and tag not in tags:
                                        tags.append(tag)
                            else:
                                if text not in tags:
                                    tags.append(text)
            except:
                pass
        
        # Try JSON-LD for more data
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    # Extract categories
                    if 'recipeCategory' in data:
                        cat_data = data['recipeCategory']
                        if isinstance(cat_data, list):
                            for cat in cat_data:
                                if cat and cat not in categories:
                                    categories.append(cat)
                        elif cat_data and cat_data not in categories:
                            categories.append(cat_data)
                    
                    # Extract cuisine
                    if not cuisine and 'recipeCuisine' in data:
                        cuisine_data = data['recipeCuisine']
                        if isinstance(cuisine_data, list):
                            cuisine = cuisine_data[0] if cuisine_data else None
                        else:
                            cuisine = cuisine_data
                    
                    # Extract keywords
                    if 'keywords' in data:
                        keyword_data = data['keywords']
                        if isinstance(keyword_data, str):
                            for keyword in keyword_data.split(','):
                                keyword = keyword.strip()
                                if keyword and keyword not in tags:
                                    tags.append(keyword)
                        elif isinstance(keyword_data, list):
                            for keyword in keyword_data:
                                if keyword and keyword not in tags:
                                    tags.append(keyword)
                
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            # Extract categories
                            if 'recipeCategory' in item:
                                cat_data = item['recipeCategory']
                                if isinstance(cat_data, list):
                                    for cat in cat_data:
                                        if cat and cat not in categories:
                                            categories.append(cat)
                                elif cat_data and cat_data not in categories:
                                    categories.append(cat_data)
                            
                            # Extract cuisine
                            if not cuisine and 'recipeCuisine' in item:
                                cuisine_data = item['recipeCuisine']
                                if isinstance(cuisine_data, list):
                                    cuisine = cuisine_data[0] if cuisine_data else None
                                else:
                                    cuisine = cuisine_data
                            
                            # Extract keywords
                            if 'keywords' in item:
                                keyword_data = item['keywords']
                                if isinstance(keyword_data, str):
                                    for keyword in keyword_data.split(','):
                                        keyword = keyword.strip()
                                        if keyword and keyword not in tags:
                                            tags.append(keyword)
                                elif isinstance(keyword_data, list):
                                    for keyword in keyword_data:
                                        if keyword and keyword not in tags:
                                            tags.append(keyword)
        except:
            pass
        
        # Add categories to tags if missing
        for category in categories:
            if category not in tags:
                tags.append(category)
        
        # Add cuisine to tags if missing
        if cuisine and cuisine not in tags:
            tags.append(cuisine)
        
        return categories, tags, cuisine
    
    def _determine_complexity(self, ingredients, instructions):
        """
        Determine recipe complexity based on ingredients and instructions
        
        Args:
            ingredients (list): Recipe ingredients
            instructions (list): Recipe instructions
            
        Returns:
            str: Complexity level (easy, medium, complex)
        """
        # Count ingredients and steps
        num_ingredients = len(ingredients)
        num_steps = len(instructions)
        
        # Calculate average instruction length
        avg_instruction_length = sum(len(step) for step in instructions) / num_steps if num_steps > 0 else 0
        
        # Look for complex techniques
        complex_techniques = [
            'sous vide', 'ferment', 'proofing', 'proving', 'knead', 'fold', 'whip',
            'temper', 'caramelize', 'reduce', 'deglaze', 'sear', 'braise', 'blanch'
        ]
        
        instruction_text = ' '.join(instructions).lower()
        has_complex_technique = any(technique in instruction_text for technique in complex_techniques)
        
        # Determine complexity
        if (num_ingredients <= 5 and num_steps <= 3 and avg_instruction_length < 100
                and not has_complex_technique):
            return 'easy'
        elif (num_ingredients >= 12 or num_steps >= 8 or avg_instruction_length > 200
                or has_complex_technique):
            return 'complex'
        else:
            return 'medium'
    
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
        
        # Look for hours with various formats
        hr_patterns = [
            r'(\d+)\s*(?:hour|hr)s?',
            r'(\d+)\s*h\b'
        ]
        
        for pattern in hr_patterns:
            hr_match = re.search(pattern, time_text, re.IGNORECASE)
            if hr_match:
                total_minutes += int(hr_match.group(1)) * 60
                break
        
        # Look for minutes with various formats
        min_patterns = [
            r'(\d+)\s*(?:minute|min)s?',
            r'(\d+)\s*m\b'
        ]
        
        for pattern in min_patterns:
            min_match = re.search(pattern, time_text, re.IGNORECASE)
            if min_match:
                total_minutes += int(min_match.group(1))
                break
        
        return total_minutes if total_minutes > 0 else None
    
    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration string (e.g. PT1H30M) to minutes
        
        Args:
            iso_duration (str): ISO duration string
            
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
        except:
            return None
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
        
        # Direct recipe list pages - these are the main recipe landing pages
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

    def _find_recipe_links_from_carousel(self, html_content):
        """Extract recipe links from carousel elements in the HTML"""
        soup = BeautifulSoup(html_content, 'lxml')
        recipe_links = []
        
        # Look for carousel items or article elements containing recipes
        carousel_items = soup.select('.carousel-cell article a, .flickity-slider article a')
        
        base_url = "https://pinchofyum.com"
        
        for item in carousel_items:
            href = item.get('href')
            if href:
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(base_url, href)
                
                # Skip if not from pinchofyum.com
                if 'pinchofyum.com' not in href:
                    continue
                    
                # Skip category pages
                if self._is_category_url(href) or self._is_non_recipe_url(href):
                    continue
                    
                # Skip if already seen
                if href in self.seen_recipe_links:
                    continue
                    
                recipe_links.append(href)
                self.seen_recipe_links.add(href)
        
        return recipe_links

    def scrape(self, limit=50):
        """
        Scrape recipes from Pinch of Yum with improved category handling
        
        Args:
            limit (int): Maximum number of recipes to scrape
                
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting Pinch of Yum scraping with limit: {limit}")
        recipes = []
        processed_urls = set()
        
        # First, try to get recipes from the main recipe list pages
        for list_page in self.recipe_list_pages:
            if len(recipes) >= limit:
                break
                
            try:
                logger.info(f"Fetching recipes from main list page: {list_page}")
                recipe_links = self._get_recipe_links_from_page(list_page, limit - len(recipes))
                
                for url in recipe_links:
                    if len(recipes) >= limit:
                        break
                        
                    if url in processed_urls:
                        continue
                        
                    processed_urls.add(url)
                    recipe_info = self._scrape_recipe(url)
                    if recipe_info:
                        recipes.append(recipe_info)
            except Exception as e:
                logger.error(f"Error processing main list page {list_page}: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Process category URLs - first scrape the category pages for links
        category_recipe_links = []
        
        if len(recipes) < limit:
            # Shuffle categories to get a variety
            random.shuffle(self.category_urls)
            
            for category_url in self.category_urls:
                if len(category_recipe_links) >= (limit - len(recipes)) * 2:  # Get extra links in case some fail
                    break
                    
                try:
                    # Crawl the category page for recipe links
                    category_links = self._crawl_category_page(category_url, 20)
                    category_recipe_links.extend(category_links)
                    
                    # Check for subcategories that might need crawling
                    response = requests.get(category_url, headers=self.headers, timeout=30)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'lxml')
                        subcategory_links = []
                        
                        # Find potential subcategory links
                        for link in soup.find_all('a', href=True):
                            href = link.get('href')
                            if href and 'pinchofyum.com/recipes/' in href and href != category_url:
                                if self._is_category_url(href) and href not in self.category_urls:
                                    subcategory_links.append(href)
                        
                        # Limit subcategories to crawl
                        subcategory_links = subcategory_links[:3]
                        
                        # Crawl subcategories
                        for subcategory_url in subcategory_links:
                            subcategory_links = self._crawl_category_page(subcategory_url, 10)
                            category_recipe_links.extend(subcategory_links)
                    
                    # Be polite between categories
                    time.sleep(random.uniform(2, 3))
                    
                except Exception as e:
                    logger.error(f"Error processing category {category_url}: {str(e)}")
                    logger.error(traceback.format_exc())
        
        # Remove duplicates and already processed URLs
        category_recipe_links = [url for url in category_recipe_links if url not in processed_urls]
        random.shuffle(category_recipe_links)  # Randomize for variety
        
        # Process the recipes found in categories
        for url in category_recipe_links:
            if len(recipes) >= limit:
                break
                
            processed_urls.add(url)
            recipe_info = self._scrape_recipe(url)
            if recipe_info:
                recipes.append(recipe_info)
        
        logger.info(f"Total Pinch of Yum recipes scraped: {len(recipes)}")
        return recipes

    def _is_non_recipe_url(self, url):
        """
        Check if URL is likely not a recipe page but a category or index page
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL is likely not a recipe page
        """
        # Parse the URL
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        path_parts = path.split('/')
        
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
        
        # Check for recipe directory URLs - these need special handling
        if url.rstrip('/') in [u.rstrip('/') for u in self.category_urls]:
            return True
        
        # Check for recipe list pages
        if url.rstrip('/') in [u.rstrip('/') for u in self.recipe_list_pages]:
            return True
        
        # Check for category-style recipe pages (recipes/X where X is a category)
        if path.startswith('recipes/') and len(path_parts) == 2:
            # This is a recipe category like /recipes/pasta, not an individual recipe
            return True
        
        # Check for recipe tags
        recipe_tags = [
            'pasta', 'vegan', 'vegetarian', 'chicken', 'beef', 'pork', 'seafood',
            'breakfast', 'lunch', 'dinner', 'dessert', 'snack', 'appetizer',
            'salad', 'soup', 'stew', 'slow-cooker', 'instant-pot', 'bowl',
            'casserole', 'cake', 'cookies', 'drink', 'taco', 'pizza',
            'healthy', 'quick', 'easy', 'gluten-free', 'kid-friendly', 'popular'
        ]
        
        # If the URL pattern is /recipes/tag and tag is in our known recipe tags list
        if (path.startswith('recipes/') and len(path_parts) == 2 and 
                path_parts[1].lower() in recipe_tags):
            return True
        
        return False

    def _is_category_url(self, url):
        """
        Check if a URL is a category page that should be crawled for recipe links
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL is a category page
        """
        # Parse the URL
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        path_parts = path.split('/')
        
        # Check if this is a known category page
        if url.rstrip('/') in [u.rstrip('/') for u in self.category_urls]:
            return True
        
        # Check if this is a recipe category page
        if path.startswith('recipes/') and len(path_parts) == 2:
            return True
        
        # Check for other category indicators
        category_indicators = [
            '/category/', 
            '/tag/',
            '/recipes/popular',
            '/recipes/seasonal',
            '/collections/'
        ]
        
        for indicator in category_indicators:
            if indicator in url:
                return True
        
        return False
    
    def _scrape_recipe(self, url):
        """
        Scrape a single recipe URL, with special handling for category pages
        
        Args:
            url (str): Recipe URL
            
        Returns:
            dict: Recipe information or None if failed
        """
        try:
            logger.info(f"Scraping recipe: {url}")
            
            # Check if this is a category page
            if self._is_category_url(url):
                logger.info(f"Found category page: {url} - will extract recipe links instead")
                return None  # Skip this URL for direct recipe processing
            
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
    
    def _crawl_category_page(self, url, limit=20):
        """
        Crawl a category page for recipe links
        
        Args:
            url (str): Category page URL
            limit (int): Maximum number of links to find
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        try:
            logger.info(f"Crawling category page: {url}")
            
            # Get the page content
            response = requests.get(url, headers=self.headers, timeout=30)
            
            # Check for valid response
            if response.status_code != 200:
                logger.error(f"Error accessing category URL: {url} - Status: {response.status_code}")
                return recipe_links
            
            # First try to extract from carousel elements
            carousel_links = self._find_recipe_links_from_carousel(response.text)
            recipe_links.extend(carousel_links)
            logger.info(f"Found {len(carousel_links)} recipe links from carousel on {url}")
            
            # Parse the page to find additional links
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all article links that might be recipes
            article_links = soup.select('article.post a[href], .post-item a[href], .recipe-card a[href]')
            
            # Base URL for relative links
            base_url = "https://pinchofyum.com"
            
            # Process article links
            for link in article_links:
                href = link.get('href')
                
                # Skip if no href
                if not href:
                    continue
                
                # Make absolute URL
                if not href.startswith('http'):
                    href = urljoin(base_url, href)
                
                # Skip if not from pinchofyum.com
                if 'pinchofyum.com' not in href:
                    continue
                
                # Skip if it's a category or non-recipe URL
                if self._is_category_url(href) or self._is_non_recipe_url(href):
                    continue
                
                # Skip if already seen
                if href in self.seen_recipe_links:
                    continue
                
                recipe_links.append(href)
                self.seen_recipe_links.add(href)
                
                # Stop if reached limit
                if len(recipe_links) >= limit:
                    break
            
            logger.info(f"Found {len(recipe_links)} recipe links on category page {url}")
            return recipe_links
            
        except Exception as e:
            logger.error(f"Error crawling category page {url}: {str(e)}")
            logger.error(traceback.format_exc())
            return recipe_links
    
    def _get_recipe_links_from_page(self, page_url, limit=50):
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
                
                # Check if it's a recipe page vs a category page
                if not self._is_category_url(href):
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

    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes
        
        Args:
            iso_duration (str): ISO 8601 duration string (e.g., 'PT15M')
            
        Returns:
            int: Duration in minutes or None if parsing fails
        """
        if not iso_duration:
            return None
        
        try:
            # Handle PT1H30M format (ISO 8601 duration)
            hours_match = re.search(r'PT(?:(\d+)H)?', iso_duration)
            minutes_match = re.search(r'PT(?:[^M]*?)(\d+)M', iso_duration)
            
            hours = int(hours_match.group(1)) if hours_match and hours_match.group(1) else 0
            minutes = int(minutes_match.group(1)) if minutes_match and minutes_match.group(1) else 0
            
            total_minutes = hours * 60 + minutes
            return total_minutes if total_minutes > 0 else None
        except Exception as e:
            logger.error(f"Error parsing ISO duration {iso_duration}: {str(e)}")
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
                                    for step in inst_data:
                                        if isinstance(step, str):
                                            instructions.append(step)
                                        elif isinstance(step, dict) and step.get('text'):
                                            instructions.append(step['text'])
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
                    if 'instruction' in header.get_text().lower() or 'direction' in header.get_text().lower():
                        # Try to find the instruction list after this header
                        inst_list = header.find_next('ol') or header.find_next('ul')
                        if inst_list:
                            for li in inst_list.select('li'):
                                text = li.get_text().strip()
                                if text:
                                    instructions.append(text)
                        break
            except:
                pass
        
        return instructions
    
    def _extract_metadata(self, soup, container):
        """
        Extract recipe metadata like prep time, cook time, etc.
        
        Args:
            soup (BeautifulSoup): Full page soup
            container (BeautifulSoup element): Recipe container
            
        Returns:
            dict: Metadata
        """
        metadata = {
            'prep_time': None,
            'cook_time': None,
            'total_time': None,
            'servings': None,
            'yield': None,
            'author': None,
            'published_date': None
        }
        
        # Try JSON-LD first (most reliable)
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                recipe_data = None
                
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    recipe_data = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            recipe_data = item
                            break
                
                if recipe_data:
                    # Extract time information - convert ISO durations to minutes
                    if recipe_data.get('prepTime'):
                        metadata['prep_time'] = self._parse_iso_duration(recipe_data['prepTime'])
                    if recipe_data.get('cookTime'):
                        metadata['cook_time'] = self._parse_iso_duration(recipe_data['cookTime'])
                    if recipe_data.get('totalTime'):
                        metadata['total_time'] = self._parse_iso_duration(recipe_data['totalTime'])
                          
                    # Extract servings
                    if recipe_data.get('recipeYield'):
                        yield_info = recipe_data['recipeYield']
                        if isinstance(yield_info, list) and len(yield_info) > 0:
                            metadata['yield'] = yield_info[0]
                        else:
                            metadata['yield'] = str(yield_info)
                        
                        # Try to extract servings from yield
                        servings_match = re.search(r'(\d+)\s*servings', str(yield_info), re.IGNORECASE)
                        if servings_match:
                            metadata['servings'] = int(servings_match.group(1))
                    
                    # Extract author
                    if recipe_data.get('author'):
                        author_info = recipe_data['author']
                        if isinstance(author_info, dict) and author_info.get('name'):
                            metadata['author'] = author_info['name']
                        elif isinstance(author_info, list) and len(author_info) > 0:
                            if isinstance(author_info[0], dict) and author_info[0].get('name'):
                                metadata['author'] = author_info[0]['name']
                            else:
                                metadata['author'] = str(author_info[0])
                        else:
                            metadata['author'] = str(author_info)
                    
                    # Extract date
                    if recipe_data.get('datePublished'):
                        metadata['published_date'] = recipe_data['datePublished']
                    
                    break
        except:
            pass
        
        # Try HTML elements for missing data
        if not metadata['prep_time']:
            try:
                prep_time_selectors = [
                    '.tasty-recipes-prep-time',
                    '.wprm-recipe-prep-time-container',
                    'span:-soup-contains("Prep Time:")',
                    'div:-soup-contains("Prep Time:")'
                ]
                
                for selector in prep_time_selectors:
                    elem = container.select_one(selector)
                    if elem:
                        # Clean up the time text
                        time_text = elem.get_text().strip()
                        time_match = re.search(r'(\d+)\s*(min|hour|minute)', time_text, re.IGNORECASE)
                        if time_match:
                            value = time_match.group(1)
                            unit = time_match.group(2).lower()
                            if 'hour' in unit:
                                metadata['prep_time'] = f'PT{value}H'
                            else:
                                metadata['prep_time'] = f'PT{value}M'
                        break
            except:
                pass
        
        if not metadata['cook_time']:
            try:
                cook_time_selectors = [
                    '.tasty-recipes-cook-time',
                    '.wprm-recipe-cook-time-container',
                    'span:-soup-contains("Cook Time:")',
                    'div:-soup-contains("Cook Time:")'
                ]
                
                for selector in cook_time_selectors:
                    elem = container.select_one(selector)
                    if elem:
                        # Clean up the time text
                        time_text = elem.get_text().strip()
                        time_match = re.search(r'(\d+)\s*(min|hour|minute)', time_text, re.IGNORECASE)
                        if time_match:
                            value = time_match.group(1)
                            unit = time_match.group(2).lower()
                            if 'hour' in unit:
                                metadata['cook_time'] = f'PT{value}H'
                            else:
                                metadata['cook_time'] = f'PT{value}M'
                        break
            except:
                pass
        
        if not metadata['servings']:
            try:
                servings_selectors = [
                    '.tasty-recipes-yield',
                    '.wprm-recipe-servings',
                    'span:-soup-contains("Servings:")',
                    'div:-soup-contains("Servings:")',
                    'span:-soup-contains("Yield:")',
                    'div:-soup-contains("Yield:")'
                ]
                
                for selector in servings_selectors:
                    elem = container.select_one(selector)
                    if elem:
                        # Clean up the text
                        text = elem.get_text().strip()
                        servings_match = re.search(r'(\d+)\s*servings', text, re.IGNORECASE)
                        if servings_match:
                            metadata['servings'] = int(servings_match.group(1))
                            if not metadata['yield']:
                                metadata['yield'] = text
                        else:
                            if not metadata['yield']:
                                metadata['yield'] = text
                        break
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
        
        # Try common note selectors
        note_selectors = [
            '.tasty-recipes-notes',
            '.wprm-recipe-notes',
            '.recipe-notes',
            'div:-soup-contains("Notes")',
            'h2:-soup-contains("Notes") + div',
            'h3:-soup-contains("Notes") + div',
            'h4:-soup-contains("Notes") + div',
            'h2:-soup-contains("Tips") + div',
            'h3:-soup-contains("Tips") + div',
            'h4:-soup-contains("Tips") + div'
        ]
        
        for selector in note_selectors:
            try:
                note_elem = container.select_one(selector)
                if note_elem:
                    # Clean up note text
                    for element in note_elem.select('h1, h2, h3, h4, h5, h6'):
                        # Remove headings from notes
                        if 'note' in element.get_text().lower() or 'tip' in element.get_text().lower():
                            element.decompose()
                    
                    # Check for list items
                    list_items = note_elem.select('li')
                    if list_items:
                        for li in list_items:
                            text = li.get_text().strip()
                            if text:
                                notes.append(text)
                    else:
                        # Get paragraph text
                        paragraphs = note_elem.select('p') or [note_elem]
                        for p in paragraphs:
                            text = p.get_text().strip()
                            if text:
                                notes.append(text)
                    
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
        nutrition = {}
        
        # Try JSON-LD first
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                recipe_data = None
                
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    recipe_data = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            recipe_data = item
                            break
                
                if recipe_data and recipe_data.get('nutrition'):
                    nutrition_data = recipe_data['nutrition']
                    
                    # Extract common nutrition fields
                    nutrition_fields = [
                        'calories', 'carbohydrateContent', 'proteinContent', 
                        'fatContent', 'saturatedFatContent', 'sodiumContent',
                        'fiberContent', 'sugarContent', 'cholesterolContent'
                    ]
                    
                    for field in nutrition_fields:
                        if nutrition_data.get(field):
                            nutrition[field] = nutrition_data[field]
                    
                    break
        except:
            pass
        
        # If no structured nutrition info, try HTML
        if not nutrition:
            try:
                nutrition_selectors = [
                    '.tasty-recipes-nutrition',
                    '.wprm-recipe-nutrition-container',
                    'div:-soup-contains("Nutrition Information")',
                    'div:-soup-contains("Nutrition Facts")'
                ]
                
                for selector in nutrition_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        # Extract full text
                        nutrition_text = elem.get_text().strip()
                        
                        # Try to extract common values
                        calories_match = re.search(r'calories:?\s*(\d+)', nutrition_text, re.IGNORECASE)
                        if calories_match:
                            nutrition['calories'] = calories_match.group(1)
                        
                        fat_match = re.search(r'fat:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                        if fat_match:
                            nutrition['fatContent'] = f"{fat_match.group(1)}g"
                        
                        carbs_match = re.search(r'carbohydrates:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                        if carbs_match:
                            nutrition['carbohydrateContent'] = f"{carbs_match.group(1)}g"
                        
                        protein_match = re.search(r'protein:?\s*(\d+)g', nutrition_text, re.IGNORECASE)
                        if protein_match:
                            nutrition['proteinContent'] = f"{protein_match.group(1)}g"
                        
                        break
            except:
                pass
        
        return nutrition
    
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
        
        # Try JSON-LD first
        try:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                data = json.loads(script.string)
                recipe_data = None
                
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    recipe_data = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Recipe':
                            recipe_data = item
                            break
                
                if recipe_data:
                    # Extract category
                    if recipe_data.get('recipeCategory'):
                        cat_data = recipe_data['recipeCategory']
                        if isinstance(cat_data, list):
                            categories.extend(cat_data)
                        else:
                            categories.append(cat_data)
                    
                    # Extract cuisine
                    if recipe_data.get('recipeCuisine'):
                        cuisine_data = recipe_data['recipeCuisine']
                        if isinstance(cuisine_data, list) and len(cuisine_data) > 0:
                            cuisine = cuisine_data[0]
                        else:
                            cuisine = str(cuisine_data)
                    
                    # Extract keywords/tags
                    if recipe_data.get('keywords'):
                        keyword_data = recipe_data['keywords']
                        if isinstance(keyword_data, list):
                            tags.extend(keyword_data)
                        elif isinstance(keyword_data, str):
                            # Split comma-separated tags
                            for tag in keyword_data.split(','):
                                clean_tag = tag.strip()
                                if clean_tag:
                                    tags.append(clean_tag)
                    
                    break
        except:
            pass
        
        # Try HTML for tags/categories
        if not categories or not tags:
            try:
                # Look for category and tag links
                for link in soup.select('a[href*="/category/"], a[href*="/tag/"]'):
                    text = link.get_text().strip()
                    
                    if not text:
                        continue
                    
                    href = link.get('href', '')
                    
                    if '/category/' in href and text not in categories:
                        categories.append(text)
                    elif '/tag/' in href and text not in tags:
                        tags.append(text)
            except:
                pass
        
        # If we have no cuisine but have categories, try to extract it
        if not cuisine and categories:
            cuisine_keywords = [
                'italian', 'mexican', 'chinese', 'indian', 'french', 'japanese',
                'thai', 'greek', 'spanish', 'lebanese', 'moroccan', 'turkish',
                'korean', 'vietnamese', 'american', 'cajun', 'mediterranean',
                'middle eastern', 'german', 'british', 'irish', 'swedish'
            ]
            
            for category in categories:
                if category.lower() in cuisine_keywords:
                    cuisine = category
                    break
        
        return categories, tags, cuisine
    
    def _determine_complexity(self, ingredients, instructions):
        """
        Determine recipe complexity
        
        Args:
            ingredients (list): Recipe ingredients
            instructions (list): Recipe instructions
            
        Returns:
            str: Complexity level (Easy, Medium, Hard)
        """
        # Count ingredients and steps
        ingredient_count = len(ingredients)
        step_count = len(instructions)
        
        # Calculate average instruction length
        instruction_lengths = [len(step.split()) for step in instructions]
        avg_instruction_length = sum(instruction_lengths) / len(instructions) if instructions else 0
        
        # Check for complex techniques
        complex_techniques = [
            'sous vide', 'temper', 'caramelize', 'flambe', 'reduce', 'deglaze',
            'emulsify', 'fold', 'proof', 'ferment', 'render', 'braise', 'broil',
            'blanch', 'poach', 'sear', 'simmer', 'marinate overnight', 'chill for',
            'refrigerate for', 'freeze for', 'rest for', 'proof for'
        ]
        
        has_complex_technique = False
        for step in instructions:
            if any(technique in step.lower() for technique in complex_techniques):
                has_complex_technique = True
                break
        
        # Determine complexity
        if ingredient_count <= 5 and step_count <= 5 and avg_instruction_length < 15 and not has_complex_technique:
            return 'Easy'
        elif ingredient_count >= 12 or step_count >= 10 or avg_instruction_length > 30 or has_complex_technique:
            return 'Hard'
        else:
            return 'Medium'

# For testing
if __name__ == "__main__":
    scraper = PinchOfYumScraper()
    recipes = scraper.scrape(limit=10)
    print(f"Scraped {len(recipes)} recipes")
    for i, recipe in enumerate(recipes):
        print(f"\nRecipe {i+1}: {recipe['title']}")
        print(f"Complexity: {recipe['complexity']}")
        print(f"Source: {recipe['source_url']}")
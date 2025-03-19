# scrapers/eatingwell_scraper.py
import requests
import time
import logging
import re
import random
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Configure more detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('eatingwell_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class EatingWellScraper:
    def __init__(self):
        """
        Initialize the EatingWell scraper with headers and category URLs
        """
        logger.info("Initializing EatingWell Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        # List of ALL category URLs to scrape
        self.category_urls = [
            # Meal Types and Courses
            "https://www.eatingwell.com/recipes/18041/appetizer/",
            "https://www.eatingwell.com/recipes/18042/soup/",
            "https://www.eatingwell.com/recipes/17981/salad/",
            "https://www.eatingwell.com/recipes/17986/side-dishes/",
            "https://www.eatingwell.com/recipes/17965/main-dishes/",
            "https://www.eatingwell.com/recipes/17968/mealtimes/",
            "https://www.eatingwell.com/recipes/17949/drinks/",
            "https://www.eatingwell.com/recipes/18044/desserts/",
            "https://www.eatingwell.com/recipes/17915/bread/",
            "https://www.eatingwell.com/recipes/17956/sauces-condiments/",
            
            # Dietary Restrictions and Diets
            "https://www.eatingwell.com/recipes/22824/dietary-restrictions/",
            "https://www.eatingwell.com/recipes/22825/nutrient-focused-diets/",
            "https://www.eatingwell.com/recipes/18024/lifestyle-diets/",
            "https://www.eatingwell.com/category/4283/vegetarian-diet-center/",
            "https://www.eatingwell.com/category/4280/vegan-diet-center/",
            "https://www.eatingwell.com/category/4251/gluten-free-diet-center/",
            "https://www.eatingwell.com/category/4247/dairy-free-diet-center/",
            "https://www.eatingwell.com/recipes/18045/weight-loss-diet/",
            "https://www.eatingwell.com/category/4267/low-carb-diet-center/",
            "https://www.eatingwell.com/category/4262/high-fiber-diet-center/",
            "https://www.eatingwell.com/category/4271/low-sodium-diet-center/",
            
            # Health and Nutrition
            "https://www.eatingwell.com/recipes/18043/ingredients/",
            "https://www.eatingwell.com/high-protein-diet-8660073",
            "https://www.eatingwell.com/gut-health-diet-8660054",
            "https://www.eatingwell.com/recipes/22823/health-condition/",
            "https://www.eatingwell.com/category/4248/diabetes-diet-center/",
            "https://www.eatingwell.com/category/4274/mediterranean-diet-center/",
            "https://www.eatingwell.com/category/4243/anti-inflammatory-diet-center/",
            "https://www.eatingwell.com/category/4256/heart-healthy-diet-center/",
            "https://www.eatingwell.com/category/4259/high-blood-pressure-diet-center/",
            "https://www.eatingwell.com/category/4268/cholesterol-diet-center/",
            "https://www.eatingwell.com/category/4277/pregnancy-diet-center/",
            "https://www.eatingwell.com/category/4254/healthy-aging-diet-center/",
            
            # Lifestyle and Special Categories
            "https://www.eatingwell.com/recipes/17979/cuisines-regions/",
            "https://www.eatingwell.com/recipes/17985/seasonal/",
            "https://www.eatingwell.com/recipes/17959/holidays-occasions/",
            "https://www.eatingwell.com/recipes/18012/low-calorie/",
            "https://www.eatingwell.com/recipes/17942/cooking-methods-styles/",
            "https://www.eatingwell.com/category/4333/family-heritage-cooking/",
            "https://www.eatingwell.com/recipes/18049/healthy-kids/",
            "https://www.eatingwell.com/category/4326/veganize-it/",
            "https://www.eatingwell.com/category/4241/popular-diet-program-reviews/"
        ]
        
        logger.info(f"Initialized with {len(self.category_urls)} category URLs")

    def _find_nested_recipe_links(self, url):
        """
        Find all recipe links within a collection or category page
        
        Args:
            url (str): URL of the collection page
            
        Returns:
            list: Unique recipe links found on the page
        """
        logger.info(f"Finding nested recipe links for URL: {url}")
        
        try:
            # Log request details
            logger.debug(f"Sending GET request to {url}")
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error accessing URL: {url} - Status code: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Comprehensive set of selectors to find recipe links
            link_selectors = [
                # Collection page specific selectors
                'a.comp.mntl-card-list-items',
                'a.card__titleLink',
                'a.mntl-card-list-items__link',
                
                # More generic selectors
                '.mntl-card-list-items .card__title a',
                '.card__content a',
                '.card__title a',
                'a[href*="/recipe/"]',
                'a[href*="-recipe-"]',
                'a[href*="/recipes/"]',
                'a[href*=".html"]'
            ]
            
            recipe_links = set()
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            for selector in link_selectors:
                links = soup.select(selector)
                logger.debug(f"Selector {selector}: found {len(links)} potential links")
                
                for link in links:
                    href = link.get('href')
                    if not href:
                        continue
                    
                    # Normalize the URL
                    if not href.startswith('http'):
                        # Handle relative URLs
                        if href.startswith('//'):
                            href = f"https:{href}"
                        else:
                            href = urljoin(base_url, href)
                    
                    # Filter for EatingWell recipe links
                    if ('eatingwell.com' in href and 
                        ('-recipe-' in href.lower() or 
                         any(keyword in href for keyword in ['/recipe/', '/recipes/', '.html']))):
                        # Further filter to avoid tag or category pages
                        if not any(bad_path in href for bad_path in [
                            '/recipes/', '/categories/', '/tags/', '/diet-centers/'
                        ]):
                            recipe_links.add(href)
            
            logger.info(f"Found {len(recipe_links)} unique recipe links on {url}")
            return list(recipe_links)
        
        except requests.RequestException as e:
            logger.error(f"Network error finding recipe links in {url}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error finding recipe links in {url}: {str(e)}")
            return []

    def scrape(self, limit=50):
        """
        Scrape recipes from EatingWell
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting EatingWell scraping with limit: {limit}")
        recipes = []
        recipes_per_category = max(3, limit // len(self.category_urls))  # Distribute limit across categories
        
        # Comprehensive set of recipe-finding strategies
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
                break
                
            try:
                logger.info(f"Exploring category page: {category_url}")
                
                # First, find nested recipe links from this page
                recipe_links = self._find_nested_recipe_links(category_url)
                
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
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                # Be polite between categories
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error exploring category page {category_url}: {str(e)}")
        
        logger.info(f"Total recipes scraped: {len(recipes)}")
        return recipes

# Update for EatingWellScraper - Better Image Extraction

def _extract_recipe_info(self, html_content, url):
    """Extract structured recipe information from HTML"""
    soup = BeautifulSoup(html_content, 'lxml')
    
    try:
        # Extract title
        title_elem = soup.select_one('h1.article-heading')
        title = title_elem.text.strip() if title_elem else "Untitled Recipe"
        
        # Extract ingredients
        ingredients = []
        ingredient_items = soup.select('.mm-recipes-structured-ingredients__list-item')
        
        for item in ingredient_items:
            quantity = item.select_one('[data-ingredient-quantity="true"]')
            unit = item.select_one('[data-ingredient-unit="true"]')
            name = item.select_one('[data-ingredient-name="true"]')
            
            ingredient_text = ""
            if quantity:
                ingredient_text += quantity.text.strip() + " "
            if unit:
                ingredient_text += unit.text.strip() + " "
            if name:
                ingredient_text += name.text.strip()
            
            if ingredient_text.strip():
                ingredients.append(ingredient_text.strip())
        
        # Extract instructions
        instructions = []
        instruction_items = soup.select('.mm-recipes-steps .mntl-sc-block-group--LI p')
        
        for item in instruction_items:
            step = item.text.strip()
            if step:
                instructions.append(step)
        
        # Extract metadata
        metadata = {}
        
        # Time details
        time_details = soup.select('.mm-recipes-details__item')
        for detail in time_details:
            label_elem = detail.select_one('.mm-recipes-details__label')
            value_elem = detail.select_one('.mm-recipes-details__value')
            
            if label_elem and value_elem:
                label = label_elem.text.strip().lower()
                value = value_elem.text.strip()
                
                time_match = re.search(r'(\d+)\s*(mins?|hrs?)?', value, re.IGNORECASE)
                if time_match:
                    time_value = int(time_match.group(1))
                    time_unit = time_match.group(2) or 'mins'
                    
                    if 'hr' in time_unit.lower():
                        time_value *= 60
                    
                    if 'prep time' in label:
                        metadata['prep_time'] = time_value
                    elif 'cook time' in label:
                        metadata['cook_time'] = time_value
                    elif 'total time' in label:
                        metadata['total_time'] = time_value
                
                # Servings
                if 'servings' in label:
                    servings_match = re.search(r'(\d+)', value)
                    if servings_match:
                        metadata['servings'] = int(servings_match.group(1))
        
        # Extract nutrition information
        nutrition_data = self._extract_nutrition(soup)
        
        # Extract nutrition profiles
        nutrition_profiles = []
        profile_container = soup.select_one('.mm-recipes-details__nutrition-profile')
        if profile_container:
            profile_elems = profile_container.select('.mm-recipes-details__nutrition-profile-item')
            for profile in profile_elems:
                profile_text = profile.text.strip()
                if profile_text:
                    nutrition_profiles.append(profile_text)
            
            logger.info(f"Extracted nutrition profiles: {nutrition_profiles}")
        
        # Determine complexity
        complexity = "easy"
        if len(ingredients) >= 10 or len(instructions) >= 7:
            complexity = "complex"
        elif len(ingredients) >= 6 or len(instructions) >= 4:
            complexity = "medium"
        
        # Breadcrumb for category/cuisine
        categories = []
        breadcrumbs = soup.select('.mntl-breadcrumbs__link')
        for crumb in breadcrumbs:
            crumb_text = crumb.text.strip()
            if crumb_text and crumb_text.lower() not in ['home', 'recipes']:
                categories.append(crumb_text)
        
        # Infer cuisine
        cuisine = None
        for crumb in categories:
            known_cuisines = ['Italian', 'Mexican', 'Chinese','Indian', 
                            'Japanese', 'Thai', 'French', 'Greek', 
                            'Mediterranean', 'Spanish', 'Korean', 'Vietnamese']
            if crumb in known_cuisines:
                cuisine = crumb
                break
        
        # Generate tags
        tags = []
        tags.extend(nutrition_profiles)
        tags.append(complexity + ' recipe')
        
        # UPDATED: Enhanced image URL extraction with multiple fallbacks
        image_url = None
        
        # Try primary image
        image_elem = soup.select_one('.primary-image__image')
        if image_elem:
            image_url = image_elem.get('src')
        
        # Try universal image
        if not image_url:
            image_elem = soup.select_one('.universal-image__image')
            if image_elem:
                image_url = image_elem.get('src') or image_elem.get('data-src')
        
        # Try figure image
        if not image_url:
            image_elem = soup.select_one('figure.primary-media img')
            if image_elem:
                image_url = image_elem.get('src') or image_elem.get('data-src')
        
        # Try structured data
        if not image_url:
            for script in soup.find_all('script', {'type': 'application/ld+json'}):
                try:
                    json_data = json.loads(script.string)
                    if isinstance(json_data, dict) and '@type' in json_data and json_data['@type'] == 'Recipe':
                        if 'image' in json_data:
                            image_data = json_data['image']
                            if isinstance(image_data, list):
                                image_url = image_data[0] if image_data else None
                            else:
                                image_url = image_data
                            break
                except:
                    continue
        
        # Try OG image as final fallback
        if not image_url:
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                image_url = og_image.get('content')
        
        # Construct recipe dictionary
        recipe = {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions,
            'source': 'EatingWell',
            'source_url': url,
            'date_scraped': datetime.now().isoformat(),
            'complexity': complexity,
            'categories': categories,
            'cuisine': cuisine,
            'tags': tags,
            'metadata': metadata,
            'nutrition': nutrition_data,
            'image_url': image_url,
            'nutrition_profiles': nutrition_profiles,
            'raw_content': html_content[:5000]  # Store first 5000 chars
        }
        
        return recipe
        
    except Exception as e:
        logger.error(f"Error extracting recipe from {url}: {str(e)}")
        return None

    def _extract_nutrition(self, soup):
        """Extract detailed nutrition information from the page"""
        try:
            # Find the nutrition callout section
            nutrition_callout = soup.select_one('.mntl-sc-block-universal-callout__body')
            
            if not nutrition_callout:
                return None
            
            # Extract nutrition text
            nutrition_text = nutrition_callout.get_text(strip=True)
            
            # Parse the nutrition information
            nutrition_data = {
                'calories': None,
                'fat': None,
                'saturated_fat': None,
                'cholesterol': None,
                'carbs': None,
                'total_sugars': None,
                'added_sugars': None,
                'protein': None,
                'fiber': None,
                'sodium': None,
                'potassium': None
            }
            
            # Extract values using regex
            nutrition_mapping = {
                'calories': r'Calories\s*(\d+)',
                'fat': r'Fat\s*(\d+)g',
                'saturated_fat': r'Saturated Fat\s*(\d+)g',
                'cholesterol': r'Cholesterol\s*(\d+)mg',
                'carbs': r'Carbohydrates\s*(\d+)g',
                'total_sugars': r'Total Sugars\s*(\d+)g',
                'added_sugars': r'Added Sugars\s*(\d+)g',
                'protein': r'Protein\s*(\d+)g',
                'fiber': r'Fiber\s*(\d+)g',
                'sodium': r'Sodium\s*(\d+)mg',
                'potassium': r'Potassium\s*(\d+)mg'
            }
            
            for key, pattern in nutrition_mapping.items():
                match = re.search(pattern, nutrition_text, re.IGNORECASE)
                if match:
                    # Convert to float, defaulting to None if conversion fails
                    try:
                        nutrition_data[key] = float(match.group(1))
                    except (ValueError, TypeError):
                        nutrition_data[key] = None
            
            return nutrition_data
        
        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            return None

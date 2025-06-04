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

class EnhancedSimplyRecipesScraper:
    """Enhanced scraper for Simply Recipes website"""
    
    def __init__(self):
        """Initialize the Simply Recipes scraper with headers and category URLs"""
        logger.info("Initializing Enhanced Simply Recipes Scraper")
        
        self.site_name = "SimplyRecipes"
        self.base_url = "https://www.simplyrecipes.com"
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://www.simplyrecipes.com/'
        }
        
        # Category URLs to scrape
        self.category_urls = [
            "https://www.simplyrecipes.com/recipes-by-ingredients-5091192",
            "https://www.simplyrecipes.com/recipes-by-method-5091235",
            "https://www.simplyrecipes.com/recipes-by-diet-5091259",
            "https://www.simplyrecipes.com/recipes-by-time-and-ease-5090817",
            "https://www.simplyrecipes.com/dinner-recipes-5091433",
            "https://www.simplyrecipes.com/breakfast-recipes-5091541",
            "https://www.simplyrecipes.com/lunch-recipes-5091263",
            "https://www.simplyrecipes.com/dessert-recipes-5091513",
            "https://www.simplyrecipes.com/snacks-and-appetizer-recipes-5090762",
            "https://www.simplyrecipes.com/holiday-and-seasonal-recipes-5091321"
        ]
        
        # Cache of seen recipe links to avoid duplicates
        self.seen_recipe_links = set()
        
        logger.info(f"Initialized with {len(self.category_urls)} category URLs")

    def scrape(self, limit=50):
        """
        Scrape recipes from Simply Recipes
        
        Args:
            limit (int): Maximum number of recipes to scrape
                
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting Simply Recipes scraping with limit: {limit}")
        recipes = []
        processed_urls = set()
        
        # Distribute limit across categories
        recipes_per_category = max(3, limit // len(self.category_urls))
        
        # Shuffle categories for variety
        random.shuffle(self.category_urls)
        
        for category_url in self.category_urls:
            if len(recipes) >= limit:
                break
                
            try:
                logger.info(f"Processing category: {category_url}")
                
                # Find recipe links from this category
                recipe_links = self._find_recipe_links(category_url, recipes_per_category)
                
                # Process recipe links
                for url in recipe_links:
                    if url in processed_urls or len(recipes) >= limit:
                        continue
                        
                    processed_urls.add(url)
                    
                    # Scrape the recipe
                    recipe_info = self._scrape_recipe(url)
                    if recipe_info:
                        recipes.append(recipe_info)
                        logger.info(f"Successfully scraped recipe: {recipe_info['title']}")
                    
                    # Be polite - don't hammer the server
                    time.sleep(random.uniform(2, 4))
                
                # Be extra polite between categories
                time.sleep(random.uniform(3, 5))
                
            except Exception as e:
                logger.error(f"Error processing category {category_url}: {str(e)}")
                logger.error(f"Error details: {e}", exc_info=True)
        
        logger.info(f"Total Simply Recipes recipes scraped: {len(recipes)}")
        return recipes
    
    def _find_recipe_links(self, category_url, limit):
        """
        Find recipe links within a category page
        
        Args:
            category_url (str): Category page URL
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        
        try:
            logger.info(f"Finding recipe links at {category_url}")
            
            # Get the page content
            response = requests.get(category_url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error accessing category URL: {category_url} - Status: {response.status_code}")
                return recipe_links
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try to find recipe links with various selectors
            link_selectors = [
                '.card__title-link',
                'a.comp.card__title-link',
                '.comp.card a',
                'a[href*="/recipes/"]',
                'a[href*="-recipe-"]',
                '.link-list__link',
                '.taxonomy-nodes a'
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
                
                # Skip if not from simplyrecipes.com
                if 'simplyrecipes.com' not in href:
                    continue
                
                # Skip category pages and non-recipe pages
                if self._is_category_or_listing(href):
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
            logger.error(f"Error finding recipe links from {category_url}: {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)
        
        return recipe_links
    
    def _is_category_or_listing(self, url):
        """
        Check if URL is a category or listing page
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if URL is a category or listing page
        """
        # Parse URL
        parsed_url = urlparse(url)
        path = parsed_url.path.strip('/')
        
        # Category patterns
        category_patterns = [
            '-recipes-5', 
            '/recipes-by-', 
            '/category/', 
            '/recipes/'
        ]
        
        # Check if URL matches any category pattern
        return any(pattern in url for pattern in category_patterns)
    
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
        Extract structured recipe information from HTML
        
        Args:
            html_content (str): HTML content of the recipe page
            url (str): URL of the recipe
            
        Returns:
            dict: Extracted recipe information
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Check if this is a recipe page by looking for recipe block
            recipe_block = soup.select_one('#recipe-block_1-0, .recipe-block, .structured-ingredients__list, .mntl-structured-ingredients, [data-module="recipe"]')
            
            if not recipe_block:
                logger.warning(f"No recipe block found in {url}")
                return None
            
            # Extract recipe details
            title = self._extract_title(soup)
            ingredients = self._extract_ingredients(soup)
            instructions = self._extract_instructions(soup)
            
            # Skip if we couldn't extract required data
            if not title or not ingredients or not instructions:
                logger.warning(f"Missing essential recipe data for {url}")
                return None
            
            # Extract additional data
            metadata = self._extract_metadata(soup)
            notes = self._extract_notes(soup)
            image_url = self._extract_image(soup)
            categories, tags, cuisine = self._extract_categories_and_tags(soup)
            nutrition = self._extract_nutrition(soup)
            
            # Determine complexity based on ingredients and instructions
            complexity = self._determine_complexity(ingredients, instructions)
            
            # Create recipe object
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': self.site_name,
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'metadata': metadata,
                'notes': notes,
                'categories': categories,
                'cuisine': cuisine,
                'tags': tags,
                'nutrition': nutrition,
                'image_url': image_url
            }
            
            logger.info(f"Successfully extracted recipe: {title}")
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            logger.error(f"Error details: {e}", exc_info=True)
            return None
    
    def _extract_title(self, soup):
        """
        Extract recipe title
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            str: Recipe title
        """
        # Try multiple selectors for title
        title_selectors = [
            '.recipe-block__header',
            'h1.article-heading',
            'h1.heading__title',
            'h1'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                return title_elem.get_text().strip()
        
        # Try JSON-LD as fallback
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
    
    def _extract_ingredients(self, soup):
        """
        Extract recipe ingredients
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: Ingredients
        """
        ingredients = []
        
        # First try structured ingredients list
        ingredient_selectors = [
            '.structured-ingredients__list-item',
            '.mntl-structured-ingredients__list-item',
            '.ingredients-list li',
            '.ingredients li',
            '[data-ingredient-name]',
            '.recipe-ingredients li'
        ]
        
        for selector in ingredient_selectors:
            ingredient_items = soup.select(selector)
            if ingredient_items:
                for item in ingredient_items:
                    # Check if item has structured data
                    quantity_elem = item.select_one('[data-ingredient-quantity="true"]')
                    unit_elem = item.select_one('[data-ingredient-unit="true"]')
                    name_elem = item.select_one('[data-ingredient-name="true"]')
                    
                    if quantity_elem or unit_elem or name_elem:
                        # Extract structured ingredient
                        ingredient_text = ""
                        
                        if quantity_elem:
                            ingredient_text += quantity_elem.get_text().strip() + " "
                        
                        if unit_elem:
                            ingredient_text += unit_elem.get_text().strip() + " "
                        
                        if name_elem:
                            ingredient_text += name_elem.get_text().strip()
                        
                        if ingredient_text.strip():
                            ingredients.append(ingredient_text.strip())
                    else:
                        # Extract regular ingredient text
                        text = item.get_text().strip()
                        if text:
                            ingredients.append(text)
                
                break
        
        # If no structured ingredients found, try JSON-LD
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
        
        # Fallback to general ingredient sections
        if not ingredients:
            ingredient_sections = soup.select('.recipe-ingredients, .ingredients, .ingredient-list')
            for section in ingredient_sections:
                for li in section.select('li'):
                    text = li.get_text().strip()
                    if text:
                        ingredients.append(text)
        
        return ingredients
    
    def _extract_instructions(self, soup):
        """
        Extract recipe instructions
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: Instructions
        """
        instructions = []
        
        # Try structured steps
        step_selectors = [
            '.structured-project__steps .mntl-sc-block-group--LI',
            '.recipe-directions__list--item',
            '.recipe-method li',
            '.instructions li',
            '.recipe-instructions li'
        ]
        
        for selector in step_selectors:
            step_items = soup.select(selector)
            if step_items:
                for item in step_items:
                    # Get step heading if present
                    step_heading = item.select_one('.mntl-sc-block-subheading')
                    heading_text = step_heading.get_text().strip() if step_heading else ""
                    
                    # Get step paragraphs
                    step_paragraphs = item.select('p.mntl-sc-block-html, p')
                    for p in step_paragraphs:
                        paragraph_text = p.get_text().strip()
                        if paragraph_text:
                            if heading_text:
                                instructions.append(f"{heading_text} {paragraph_text}")
                                heading_text = ""  # Only include heading with first paragraph
                            else:
                                instructions.append(paragraph_text)
                
                break
        
        # If no structured steps found, try JSON-LD
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
        
        # Fallback to general instruction sections
        if not instructions:
            instruction_sections = soup.select('.recipe-instructions, .instructions, .method')
            for section in instruction_sections:
                for li in section.select('li'):
                    text = li.get_text().strip()
                    if text:
                        instructions.append(text)
        
        return instructions
    
    def _extract_metadata(self, soup):
        """
        Extract recipe metadata (prep time, cook time, etc.)
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Metadata
        """
        metadata = {
            'prep_time': None,
            'cook_time': None,
            'total_time': None,
            'servings': None,
            'yield': None
        }
        
        # First try project meta container
        project_meta = soup.select_one('.project-meta, .recipe-block__meta')
        
        if project_meta:
            # Prep time
            prep_time_elem = project_meta.select_one('.prep-time .meta-text__data')
            if prep_time_elem:
                metadata['prep_time'] = self._parse_time(prep_time_elem.get_text().strip())
            
            # Cook time
            cook_time_elem = project_meta.select_one('.cook-time .meta-text__data')
            if cook_time_elem:
                metadata['cook_time'] = self._parse_time(cook_time_elem.get_text().strip())
            
            # Total time
            total_time_elem = project_meta.select_one('.total-time .meta-text__data')
            if total_time_elem:
                metadata['total_time'] = self._parse_time(total_time_elem.get_text().strip())
            
            # Servings
            servings_elem = project_meta.select_one('.recipe-serving .meta-text__data')
            if servings_elem:
                servings_text = servings_elem.get_text().strip()
                metadata['yield'] = servings_text
                
                # Try to extract servings number
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
        
        # If not found, try JSON-LD
        if not metadata['prep_time'] or not metadata['cook_time'] or not metadata['total_time'] or not metadata['servings']:
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
                        # Prep time
                        if not metadata['prep_time'] and recipe_data.get('prepTime'):
                            metadata['prep_time'] = self._parse_iso_duration(recipe_data['prepTime'])
                        
                        # Cook time
                        if not metadata['cook_time'] and recipe_data.get('cookTime'):
                            metadata['cook_time'] = self._parse_iso_duration(recipe_data['cookTime'])
                        
                        # Total time
                        if not metadata['total_time'] and recipe_data.get('totalTime'):
                            metadata['total_time'] = self._parse_iso_duration(recipe_data['totalTime'])
                        
                        # Servings
                        if not metadata['servings'] and recipe_data.get('recipeYield'):
                            yield_info = recipe_data['recipeYield']
                            
                            if not metadata['yield']:
                                if isinstance(yield_info, list) and len(yield_info) > 0:
                                    metadata['yield'] = yield_info[0]
                                else:
                                    metadata['yield'] = str(yield_info)
                            
                            # Try to extract servings from yield
                            servings_match = re.search(r'(\d+)', str(yield_info))
                            if servings_match:
                                metadata['servings'] = int(servings_match.group(1))
            except:
                pass
        
        return metadata
    
    def _parse_time(self, time_text):
        """
        Parse time text to minutes
        
        Args:
            time_text (str): Time text (e.g., "30 mins", "1 hr 15 mins")
            
        Returns:
            int: Time in minutes
        """
        if not time_text:
            return None
        
        total_minutes = 0
        
        # Look for hours
        hours_match = re.search(r'(\d+)\s*(?:hours?|hrs?)', time_text, re.IGNORECASE)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        
        # Look for minutes
        mins_match = re.search(r'(\d+)\s*(?:minutes?|mins?)', time_text, re.IGNORECASE)
        if mins_match:
            total_minutes += int(mins_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes
        
        Args:
            iso_duration (str): ISO duration string (e.g., "PT30M", "PT1H30M")
            
        Returns:
            int: Duration in minutes
        """
        if not iso_duration:
            return None
        
        total_minutes = 0
        
        # Parse hours
        hours_match = re.search(r'PT(\d+)H', iso_duration)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        
        # Parse minutes
        mins_match = re.search(r'PT(?:\d+H)?(\d+)M', iso_duration)
        if mins_match:
            total_minutes += int(mins_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
    def _extract_notes(self, soup):
        """
        Extract recipe notes
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: Notes
        """
        notes = []
        
        # Try recipe block note
        note_elem = soup.select_one('.recipe-block__note-text')
        if note_elem:
            for p in note_elem.select('p'):
                text = p.get_text().strip()
                if text:
                    notes.append(text)
            
            if not notes:
                text = note_elem.get_text().strip()
                if text:
                    notes.append(text)
        
        # Try other note elements
        if not notes:
            tip_elems = soup.select('.recipe-tips, .tips, .recipe-notes, .notes')
            for elem in tip_elems:
                for p in elem.select('p'):
                    text = p.get_text().strip()
                    if text:
                        notes.append(text)
                
                for li in elem.select('li'):
                    text = li.get_text().strip()
                    if text:
                        notes.append(text)
        
        return notes
    
    def _extract_image(self, soup):
        """
        Extract recipe image URL
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            str: Image URL
        """
        # Try Open Graph image
        og_img = soup.select_one('meta[property="og:image"]')
        if og_img:
            return og_img.get('content', '')
        
        # Try primary image
        primary_img = soup.select_one('.primary-image__image')
        if primary_img:
            return primary_img.get('src', '') or primary_img.get('data-src', '')
        
        # Try other image selectors
        img_selectors = [
            '.mntl-primary-image img',
            '.recipe-block__image img',
            '.recipe-image img',
            '.featured-image img'
        ]
        
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                return img.get('src', '') or img.get('data-src', '')
        
        # Try JSON-LD
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
                
                if recipe_data and recipe_data.get('image'):
                    image_data = recipe_data['image']
                    
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
    
    def _extract_categories_and_tags(self, soup):
        """
        Extract recipe categories, tags, and cuisine
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            tuple: (categories, tags, cuisine)
        """
        categories = []
        tags = []
        cuisine = None
        
        # Try to find tags/categories from breadcrumbs or taxonomy
        breadcrumbs = soup.select('.breadcrumbs__link, .taxonomy-breadcrumbs a')
        for crumb in breadcrumbs:
            text = crumb.get_text().strip()
            if text and text not in ['Home', 'Recipes']:
                categories.append(text)
        
        # Try to find tags from taxonomy links
        tag_links = soup.select('.recipe-tags a, .recipe-keywords a, .tag-nav__link')
        for link in tag_links:
            text = link.get_text().strip()
            if text:
                tags.append(text)
        
        # Try JSON-LD
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
                    # Extract cuisine
                    if recipe_data.get('recipeCuisine'):
                        cuisine_data = recipe_data['recipeCuisine']
                        
                        if isinstance(cuisine_data, list) and len(cuisine_data) > 0:
                            cuisine = cuisine_data[0]
                        else:
                            cuisine = str(cuisine_data)
                    
                    # Extract categories
                    if recipe_data.get('recipeCategory'):
                        category_data = recipe_data['recipeCategory']
                        
                        if isinstance(category_data, list):
                            for cat in category_data:
                                if cat not in categories:
                                    categories.append(cat)
                        elif category_data not in categories:
                            categories.append(category_data)
                    
                    # Extract keywords
                    if recipe_data.get('keywords'):
                        keyword_data = recipe_data['keywords']
                        
                        if isinstance(keyword_data, list):
                            for kw in keyword_data:
                                if kw not in tags:
                                    tags.append(kw)
                        elif isinstance(keyword_data, str):
                            for kw in keyword_data.split(','):
                                kw = kw.strip()
                                if kw and kw not in tags:
                                    tags.append(kw)
        except:
            pass
        
        # If no cuisine but we have categories, try to extract cuisine from categories
        if not cuisine and categories:
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
        
        return categories, tags, cuisine
    
    def _extract_nutrition(self, soup):
        """
        Extract nutrition information
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Nutrition information
        """
        nutrition = {}
        
        # Try nutrition info container
        nutrition_table = soup.select_one('.nutrition-info__table, .nutrition-info')
        if nutrition_table:
            # Basic nutrition
            calories_elem = nutrition_table.select_one('.nutrition-info__table--row:nth-child(1) .nutrition-info__table--cell')
            if calories_elem:
                try:
                    nutrition['calories'] = float(re.sub(r'[^\d.]', '', calories_elem.get_text().strip()))
                except:
                    pass
            
            fat_elem = nutrition_table.select_one('.nutrition-info__table--row:nth-child(2) .nutrition-info__table--cell')
            if fat_elem:
                try:
                    nutrition['fat'] = float(re.sub(r'[^\d.]', '', fat_elem.get_text().strip()))
                except:
                    pass
            
            carbs_elem = nutrition_table.select_one('.nutrition-info__table--row:nth-child(3) .nutrition-info__table--cell')
            if carbs_elem:
                try:
                    nutrition['carbs'] = float(re.sub(r'[^\d.]', '', carbs_elem.get_text().strip()))
                except:
                    pass
            
            protein_elem = nutrition_table.select_one('.nutrition-info__table--row:nth-child(4) .nutrition-info__table--cell')
            if protein_elem:
                try:
                    nutrition['protein'] = float(re.sub(r'[^\d.]', '', protein_elem.get_text().strip()))
                except:
                    pass
        
        # If not found, try JSON-LD
        if not nutrition:
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
                        
                        if nutrition_data.get('calories'):
                            nutrition['calories'] = self._extract_numeric_value(nutrition_data['calories'])
                        
                        if nutrition_data.get('fatContent'):
                            nutrition['fat'] = self._extract_numeric_value(nutrition_data['fatContent'])
                        
                        if nutrition_data.get('carbohydrateContent'):
                            nutrition['carbs'] = self._extract_numeric_value(nutrition_data['carbohydrateContent'])
                        
                        if nutrition_data.get('proteinContent'):
                            nutrition['protein'] = self._extract_numeric_value(nutrition_data['proteinContent'])
            except:
                pass
        
        return nutrition
    
    def _extract_numeric_value(self, value):
        """
        Extract numeric value from string
        
        Args:
            value (str): String with numeric value (e.g., "150 cal", "10g")
            
        Returns:
            float: Numeric value
        """
        if isinstance(value, (int, float)):
            return float(value)
        
        match = re.search(r'(\d+(?:\.\d+)?)', str(value))
        if match:
            return float(match.group(1))
        
        return None
    
    def _determine_complexity(self, ingredients, instructions):
        """
        Determine recipe complexity based on ingredients and instructions
        
        Args:
            ingredients (list): Recipe ingredients
            instructions (list): Recipe instructions
            
        Returns:
            str: Complexity ("easy", "medium", or "complex")
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

if __name__ == "__main__":
    # Test the scraper with a specific URL
    scraper = EnhancedSimplyRecipesScraper()
    test_url = "https://www.simplyrecipes.com/cassava-cake-recipe-6832078"
    recipe = scraper._scrape_recipe(test_url)
    
    if recipe:
        print(f"Recipe: {recipe['title']}")
        print(f"Ingredients count: {len(recipe['ingredients'])}")
        print("Sample ingredients:")
        for i, ingredient in enumerate(recipe['ingredients'][:5]):
            print(f"  {i+1}. {ingredient}")
        
        print(f"Instructions count: {len(recipe['instructions'])}")
        print("Sample instructions:")
        for i, instruction in enumerate(recipe['instructions'][:3]):
            print(f"  {i+1}. {instruction}")
        
        print(f"Prep time: {recipe['metadata'].get('prep_time')} minutes")
        print(f"Cook time: {recipe['metadata'].get('cook_time')} minutes")
        print(f"Total time: {recipe['metadata'].get('total_time')} minutes")
        print(f"Servings: {recipe['metadata'].get('servings')}")
    else:
        print("Failed to scrape recipe")
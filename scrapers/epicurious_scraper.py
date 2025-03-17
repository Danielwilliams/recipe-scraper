# scrapers/epicurious_scraper.py
import requests
import time
import logging
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logger = logging.getLogger(__name__)

class EpicuriousScraper:
    """Scraper for Epicurious recipes"""
    
    def __init__(self):
        """Initialize the Epicurious scraper"""
        logger.info("Initializing Epicurious Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        self.base_url = "https://www.epicurious.com"
        self.categories = [
            "/recipes-menus/recipes",
            "/recipes-menus/collections/dinner",
            "/recipes-menus/collections/chicken",
            "/recipes-menus/collections/quick-simple",
            "/recipes-menus/collections/vegetarian",
            "/recipes-menus/collections/healthy"
        ]
    
    def scrape(self, limit=50):
        """
        Scrape recipes from Epicurious
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting Epicurious scraping with limit: {limit}")
        recipes = []
        
        # Distribute limit across categories
        recipes_per_category = max(5, limit // len(self.categories))
        
        for category in self.categories:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
                break
                
            try:
                category_url = urljoin(self.base_url, category)
                logger.info(f"Scraping category: {category_url}")
                
                recipe_links = self._get_recipe_links(category_url, recipes_per_category)
                logger.info(f"Found {len(recipe_links)} recipes in category {category}")
                
                # Process recipe links
                category_count = 0
                for url in recipe_links:
                    if len(recipes) >= limit or category_count >= recipes_per_category:
                        break
                        
                    try:
                        full_url = urljoin(self.base_url, url)
                        
                        # Skip if we've already scraped this URL
                        if any(r.get('source_url') == full_url for r in recipes):
                            continue
                            
                        logger.info(f"Scraping recipe: {full_url}")
                        
                        recipe_response = requests.get(full_url, headers=self.headers, timeout=30)
                        if recipe_response.status_code != 200:
                            logger.error(f"Error accessing URL: {full_url}, Status: {recipe_response.status_code}")
                            continue
                        
                        recipe_info = self._extract_recipe_info(recipe_response.text, full_url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            category_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                        
                        # Be polite - don't hammer the server
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                # Be polite between categories
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error processing category '{category}': {str(e)}")
        
        logger.info(f"Total Epicurious recipes scraped: {len(recipes)}")
        return recipes
    
    def _get_recipe_links(self, category_url, limit):
        """
        Get recipe links from a category page
        
        Args:
            category_url (str): URL of the category
            limit (int): Maximum number of links to return
            
        Returns:
            list: Recipe links
        """
        recipe_links = []
        page = 1
        max_pages = 3  # Limit to 3 pages per category
        
        while len(recipe_links) < limit and page <= max_pages:
            try:
                page_url = f"{category_url}?page={page}"
                logger.info(f"Fetching page {page}: {page_url}")
                
                response = requests.get(page_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    logger.error(f"Failed to access page: {page_url}, Status: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find recipe links
                links = soup.select('a.components-card-recipe')
                
                if not links:
                    # Try alternative selectors
                    links = soup.select('.recipe-content-card a')
                
                if not links:
                    logger.warning(f"No recipe links found on page {page_url}")
                    break
                
                for link in links:
                    href = link.get('href')
                    if href and '/recipes/' in href:
                        recipe_links.append(href)
                        if len(recipe_links) >= limit:
                            break
                
                page += 1
                
                # Be polite
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error fetching recipes from page {page}: {str(e)}")
                break
        
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
            
            # Try to extract from structured data first
            recipe_data = self._extract_from_json_ld(soup)
            
            if recipe_data:
                return recipe_data
            
            # Fallback to HTML parsing if JSON-LD extraction failed
            logger.info(f"JSON-LD extraction failed, falling back to HTML parsing for {url}")
            
            # Extract title
            title_elem = soup.select_one('h1')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients
            ingredients = []
            ingredient_sections = soup.select('.ingredients-section')
            for section in ingredient_sections:
                ingredient_items = section.select('.ingredient')
                for item in ingredient_items:
                    ingredient_text = item.text.strip()
                    if ingredient_text:
                        ingredients.append(ingredient_text)
            
            # Extract instructions
            instructions = []
            instruction_sections = soup.select('.preparation-section, .preparation-steps')
            for section in instruction_sections:
                steps = section.select('.preparation-step')
                for step in steps:
                    step_text = step.text.strip()
                    if step_text:
                        instructions.append(step_text)
            
            # If no structured steps, try other selectors
            if not instructions:
                instruction_paragraphs = soup.select('.instructions p, .preparation-steps p')
                for p in instruction_paragraphs:
                    p_text = p.text.strip()
                    if p_text and len(p_text) > 10:  # Filter out short text
                        instructions.append(p_text)
            
            # Extract metadata
            metadata = {}
            
            # Cook time and prep time
            time_section = soup.select_one('.recipe-meta-item-body')
            if time_section:
                time_text = time_section.text.strip()
                time_minutes = self._parse_time_text(time_text)
                if time_minutes:
                    metadata['total_time'] = time_minutes
            
            # Rating info
            rating_elem = soup.select_one('.rating')
            if rating_elem:
                rating_text = rating_elem.text.strip()
                rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
                if rating_match:
                    metadata['rating'] = float(rating_match.group(1))
            
            # Number of ratings
            reviews_elem = soup.select_one('.reviews-count')
            if reviews_elem:
                reviews_text = reviews_elem.text.strip()
                reviews_match = re.search(r'(\d+)', reviews_text)
                if reviews_match:
                    metadata['reviews_count'] = int(reviews_match.group(1))
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.info(f"Skipping recipe {url} - not enough data extracted")
                return None
            
            # Determine complexity based on number of ingredients and steps
            if len(ingredients) <= 5 and len(instructions) <= 3:
                complexity = 'easy'
            elif len(ingredients) >= 12 or len(instructions) >= 8:
                complexity = 'complex'
            else:
                complexity = 'medium'
            
            # Extract image
            image_elem = soup.select_one('.recipe-image img, .photo-wrap img')
            image_url = image_elem.get('src') if image_elem else None
            
            # Generate tags based on title and ingredients
            tags = self._generate_tags(title, ingredients, instructions)
            
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'Epicurious',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'tags': tags,
                'metadata': metadata,
                'image_url': image_url,
                'raw_content': html_content[:5000]  # First 5000 chars
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe info from {url}: {str(e)}")
            return None
    
    def _extract_from_json_ld(self, soup):
        """
        Extract recipe data from JSON-LD
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            dict: Extracted recipe information or None
        """
        try:
            # Find JSON-LD script tag
            script_tag = soup.find('script', {'type': 'application/ld+json'})
            if not script_tag:
                return None
            
            # Parse JSON
            json_data = json.loads(script_tag.string)
            
            # Handle array format
            if isinstance(json_data, list):
                recipe_data = next((item for item in json_data if item.get('@type') == 'Recipe'), None)
            else:
                recipe_data = json_data if json_data.get('@type') == 'Recipe' else None
            
            if not recipe_data:
                return None
            
            # Extract recipe information
            title = recipe_data.get('name', 'Untitled Recipe')
            
            # Extract ingredients
            ingredients = recipe_data.get('recipeIngredient', [])
            
            # Extract instructions
            instructions = []
            instruction_data = recipe_data.get('recipeInstructions', [])
            
            if isinstance(instruction_data, list):
                for step in instruction_data:
                    if isinstance(step, dict) and 'text' in step:
                        instructions.append(step.get('text', ''))
                    elif isinstance(step, str):
                        instructions.append(step)
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                return None
            
            # Extract metadata
            metadata = {}
            
            # Cook time
            if 'cookTime' in recipe_data:
                cook_time = recipe_data['cookTime']
                minutes = self._parse_iso_duration(cook_time)
                if minutes:
                    metadata['cook_time'] = minutes
            
            # Prep time
            if 'prepTime' in recipe_data:
                prep_time = recipe_data['prepTime']
                minutes = self._parse_iso_duration(prep_time)
                if minutes:
                    metadata['prep_time'] = minutes
            
            # Total time
            if 'totalTime' in recipe_data:
                total_time = recipe_data['totalTime']
                minutes = self._parse_iso_duration(total_time)
                if minutes:
                    metadata['total_time'] = minutes
            
            # Yield/Servings
            if 'recipeYield' in recipe_data:
                yield_info = recipe_data['recipeYield']
                if isinstance(yield_info, list):
                    yield_info = yield_info[0] if yield_info else None
                
                if yield_info:
                    # Try to extract number
                    servings_match = re.search(r'(\d+)', str(yield_info))
                    if servings_match:
                        metadata['servings'] = int(servings_match.group(1))
                    else:
                        metadata['yield'] = yield_info
            
            # Rating
            if 'aggregateRating' in recipe_data:
                rating_data = recipe_data['aggregateRating']
                if 'ratingValue' in rating_data:
                    metadata['rating'] = float(rating_data['ratingValue'])
                if 'reviewCount' in rating_data:
                    metadata['reviews_count'] = int(rating_data['reviewCount'])
            
            # Nutrition
            nutrition = {}
            if 'nutrition' in recipe_data:
                nutrition_data = recipe_data['nutrition']
                for key, value in nutrition_data.items():
                    if key != '@type':
                        # Extract numeric value
                        numeric_match = re.search(r'(\d+(?:\.\d+)?)', str(value))
                        if numeric_match:
                            nutrition[key.replace('Content', '').lower()] = float(numeric_match.group(1))
            
            # Categories and keywords
            categories = []
            if 'recipeCategory' in recipe_data:
                categories.extend(recipe_data['recipeCategory'] if isinstance(recipe_data['recipeCategory'], list) else [recipe_data['recipeCategory']])
            
            # Cuisine
            cuisine = None
            if 'recipeCuisine' in recipe_data:
                cuisine_data = recipe_data['recipeCuisine']
                cuisine = cuisine_data[0] if isinstance(cuisine_data, list) and cuisine_data else cuisine_data
            
            # Tags
            tags = []
            if 'keywords' in recipe_data:
                keywords = recipe_data['keywords']
                if isinstance(keywords, str):
                    tags = [k.strip() for k in keywords.split(',')]
                elif isinstance(keywords, list):
                    tags = keywords
            
            # Add categories to tags
            tags.extend(categories)
            
            # Add cuisine to tags if present
            if cuisine:
                tags.append(cuisine.lower())
            
            # Determine complexity based on ingredients and steps
            if len(ingredients) <= 5 and len(instructions) <= 3:
                complexity = 'easy'
            elif len(ingredients) >= 12 or len(instructions) >= 8:
                complexity = 'complex'
            else:
                complexity = 'medium'
            
            # Extract image URL
            image_url = None
            if 'image' in recipe_data:
                image_data = recipe_data['image']
                if isinstance(image_data, list):
                    image_url = image_data[0] if image_data else None
                elif isinstance(image_data, dict) and 'url' in image_data:
                    image_url = image_data['url']
                else:
                    image_url = image_data
            
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'Epicurious',
                'source_url': recipe_data.get('url', ''),
                'date_scraped': datetime.now().isoformat(),
                'complexity': complexity,
                'tags': list(set(tags)),  # Remove duplicates
                'metadata': metadata,
                'nutrition': nutrition,
                'cuisine': cuisine,
                'image_url': image_url,
                'raw_content': json.dumps(recipe_data)[:5000]  # First 5000 chars
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting JSON-LD data: {str(e)}")
            return None
    
    def _parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes
        
        Args:
            iso_duration (str): ISO 8601 duration string (e.g., 'PT1H30M')
            
        Returns:
            int: Duration in minutes
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
        except Exception:
            return None
    
    def _parse_time_text(self, time_text):
        """
        Parse time text into minutes
        
        Args:
            time_text (str): Time text (e.g., '1 hour 30 minutes')
            
        Returns:
            int: Time in minutes
        """
        if not time_text:
            return None
            
        total_minutes = 0
        
        # Look for hours
        hours_match = re.search(r'(\d+)\s*(?:hour|hr)', time_text, re.IGNORECASE)
        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        
        # Look for minutes
        minutes_match = re.search(r'(\d+)\s*(?:minute|min)', time_text, re.IGNORECASE)
        if minutes_match:
            total_minutes += int(minutes_match.group(1))
        
        return total_minutes if total_minutes > 0 else None
    
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

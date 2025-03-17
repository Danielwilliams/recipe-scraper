# scrapers/foodnetwork_scraper.py
import requests
import time
import logging
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Configure logging
logger = logging.getLogger(__name__)

class FoodNetworkScraper:
    """Scraper for Food Network recipes"""
    
    def __init__(self):
        """Initialize the Food Network scraper"""
        logger.info("Initializing Food Network Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        self.base_url = "https://www.foodnetwork.com"
        self.recipe_list_url = "https://www.foodnetwork.com/recipes/recipes-a-z"
    
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
        letters = list("abcdefghijklmnopqrstuvwxyz123")
        
        # Distribute limit across alphabet letters
        recipes_per_letter = max(2, limit // len(letters))
        
        for letter in letters:
            if len(recipes) >= limit:
                logger.info(f"Reached total recipe limit of {limit}")
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
                        
                        recipe_response = requests.get(full_url, headers=self.headers, timeout=30)
                        if recipe_response.status_code != 200:
                            logger.error(f"Error accessing recipe URL: {full_url}, Status: {recipe_response.status_code}")
                            continue
                        
                        recipe_info = self._extract_recipe_info(recipe_response.text, full_url)
                        if recipe_info:
                            recipes.append(recipe_info)
                            letter_count += 1
                            logger.info(f"Successfully scraped recipe: {recipe_info.get('title', 'Unknown')}")
                        
                        # Be polite - don't hammer the server
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                # Be polite between letters
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error processing letter '{letter}': {str(e)}")
        
        logger.info(f"Total Food Network recipes scraped: {len(recipes)}")
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
            response = requests.get(letter_url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                logger.error(f"Failed to access letter page: {letter_url}, Status: {response.status_code}")
                return recipe_links
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find all recipe links on the page
            link_elements = soup.select('.m-PromoList__a-ListItem a')
            
            for link in link_elements:
                href = link.get('href')
                if href and '/recipes/' in href:
                    recipe_links.append(href)
                    if len(recipe_links) >= limit:
                        break
            
            return recipe_links
            
        except Exception as e:
            logger.error(f"Error getting recipe links from {letter_url}: {str(e)}")
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
            
            # Extract title
            title_elem = soup.select_one('h1.o-AssetTitle__a-Headline')
            title = title_elem.text.strip() if title_elem else "Untitled Recipe"
            
            # Extract ingredients
            ingredients = []
            ingredient_elements = soup.select('.o-Ingredients__a-Ingredient--CheckboxLabel')
            for elem in ingredient_elements:
                ingredient_text = elem.text.strip()
                if ingredient_text and not ingredient_text.startswith('Deselect All'):
                    ingredients.append(ingredient_text)
            
            # Extract instructions
            instructions = []
            instruction_elements = soup.select('.o-Method__m-Step')
            for elem in instruction_elements:
                instruction_text = elem.text.strip()
                if instruction_text:
                    instructions.append(instruction_text)
            
            # Extract metadata
            metadata = {}
            
            # Level
            level_elem = soup.select_one('.o-RecipeInfo__a-Description')
            if level_elem and 'Level:' in soup.text:
                complexity = level_elem.text.strip().lower()
                metadata['complexity'] = complexity
            else:
                # Infer complexity based on number of ingredients and steps
                metadata['complexity'] = self._infer_complexity(len(ingredients), len(instructions))
            
            # Time
            time_elements = soup.select('.o-RecipeInfo__m-Time li')
            for elem in time_elements:
                time_text = elem.text.strip()
                if 'Total:' in time_text:
                    total_match = re.search(r'Total:\s*([\d\s]+(?:hr|min))', time_text)
                    if total_match:
                        total_time = self._parse_time(total_match.group(1))
                        metadata['total_time'] = total_time
                
                if 'Active:' in time_text:
                    prep_match = re.search(r'Active:\s*([\d\s]+(?:hr|min))', time_text)
                    if prep_match:
                        prep_time = self._parse_time(prep_match.group(1))
                        metadata['prep_time'] = prep_time
            
            # Yield/Servings
            yield_elem = soup.select_one('.o-RecipeInfo__a-Description:not(:has(*:contains("Level")))')
            if yield_elem:
                servings_text = yield_elem.text.strip()
                # Extract numbers from the yield text
                servings_match = re.search(r'(\d+)', servings_text)
                if servings_match:
                    metadata['servings'] = int(servings_match.group(1))
            
            # Extract nutrition info
            nutrition = self._extract_nutrition(soup)
            
            # Extract image URL
            image_elem = soup.select_one('.m-MediaBlock__a-Image')
            image_url = image_elem.get('src') if image_elem else None
            
            # Skip if we couldn't extract minimal recipe data
            if len(ingredients) < 2 or len(instructions) < 2:
                logger.info(f"Skipping recipe {url} - not enough data extracted")
                return None
            
            # Generate tags based on title and ingredients
            tags = self._generate_tags(title, ingredients, instructions)
            
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
            nutrition_elements = soup.select('.m-NutritionTable__a-Content dt, .m-NutritionTable__a-Content dd')
            
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

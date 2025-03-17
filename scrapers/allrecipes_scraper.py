import requests
import time
import logging
import re
import json
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class AllRecipesScraper:
    def __init__(self):
        self.base_url = "https://www.allrecipes.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        }
    
    def scrape(self, limit=50):
        """Scrape recipes from AllRecipes"""
        recipes = []
        
        # Start with a category page
        category_url = f"{self.base_url}/recipes/dinner/"
        logger.info(f"Scraping category page: {category_url}")
        
        try:
            response = requests.get(category_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Find recipe cards
            recipe_cards = soup.select('.mntl-card-list-items')
            
            for card in recipe_cards[:limit]:
                try:
                    # Find the link to the recipe
                    link_elem = card.select_one('a')
                    if not link_elem or not link_elem.get('href'):
                        continue
                    
                    recipe_url = link_elem['href']
                    if not recipe_url.startswith('http'):
                        recipe_url = self.base_url + recipe_url
                    
                    logger.info(f"Scraping recipe: {recipe_url}")
                    
                    # Get the recipe page
                    recipe_response = requests.get(recipe_url, headers=self.headers, timeout=30)
                    recipe_response.raise_for_status()
                    
                    # Extract recipe information
                    recipe_info = self._extract_recipe_info(recipe_response.text, recipe_url)
                    if recipe_info:
                        recipes.append(recipe_info)
                        logger.info(f"Successfully scraped recipe: {recipe_info['title']}")
                    
                    # Be polite - don't hammer the server
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error scraping recipe: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error scraping category page: {str(e)}")
        
        logger.info(f"Total recipes scraped: {len(recipes)}")
        return recipes
    
    def _extract_recipe_info(self, html_content, url):
        """Extract structured recipe information from HTML"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        try:
            # Look for recipe data in JSON-LD
            script_tag = soup.find('script', {'type': 'application/ld+json'})
            if not script_tag:
                logger.warning("No JSON-LD data found")
                return None
            
            try:
                json_data = json.loads(script_tag.string)
                
                # Sometimes the data is in an array
                if isinstance(json_data, list):
                    recipe_data = next((item for item in json_data if item.get('@type') == 'Recipe'), None)
                else:
                    recipe_data = json_data if json_data.get('@type') == 'Recipe' else None
                
                if not recipe_data:
                    logger.warning("No recipe data found in JSON-LD")
                    return None
                
                # Extract basic recipe information
                title = recipe_data.get('name', 'Untitled Recipe')
                
                # Extract ingredients
                ingredients = recipe_data.get('recipeIngredient', [])
                
                # Extract instructions
                instructions = []
                instruction_data = recipe_data.get('recipeInstructions', [])
                
                if isinstance(instruction_data, list):
                    for step in instruction_data:
                        if isinstance(step, dict) and 'text' in step:
                            instructions.append(step['text'])
                        elif isinstance(step, str):
                            instructions.append(step)
                
                # Extract metadata
                metadata = {}
                
                # Prep time
                if 'prepTime' in recipe_data:
                    prep_time = recipe_data['prepTime']
                    # Convert ISO duration to minutes
                    minutes = self._parse_iso_duration(prep_time)
                    if minutes:
                        metadata['prep_time'] = minutes
                
                # Cook time
                if 'cookTime' in recipe_data:
                    cook_time = recipe_data['cookTime']
                    # Convert ISO duration to minutes
                    minutes = self._parse_iso_duration(cook_time)
                    if minutes:
                        metadata['cook_time'] = minutes
                
                # Total time
                if 'totalTime' in recipe_data:
                    total_time = recipe_data['totalTime']
                    # Convert ISO duration to minutes
                    minutes = self._parse_iso_duration(total_time)
                    if minutes:
                        metadata['total_time'] = minutes
                
                # Servings
                if 'recipeYield' in recipe_data:
                    servings = recipe_data['recipeYield']
                    if isinstance(servings, list):
                        servings = servings[0]
                    # Try to extract number
                    servings_match = re.search(r'(\d+)', str(servings))
                    if servings_match:
                        metadata['servings'] = int(servings_match.group(1))
                
                # Categories and keywords
                categories = []
                if 'recipeCategory' in recipe_data:
                    categories.extend(recipe_data['recipeCategory'] if isinstance(recipe_data['recipeCategory'], list) else [recipe_data['recipeCategory']])
                
                if 'recipeCuisine' in recipe_data:
                    cuisine = recipe_data['recipeCuisine']
                    if isinstance(cuisine, list):
                        cuisine = cuisine[0] if cuisine else None
                    metadata['cuisine'] = cuisine
                
                tags = []
                if 'keywords' in recipe_data:
                    keywords = recipe_data['keywords']
                    if isinstance(keywords, str):
                        tags = [k.strip() for k in keywords.split(',')]
                    elif isinstance(keywords, list):
                        tags = keywords
                
                # Determine complexity based on number of ingredients and steps
                complexity = "easy"
                if len(ingredients) >= 10 or len(instructions) >= 7:
                    complexity = "complex"
                elif len(ingredients) >= 6 or len(instructions) >= 4:
                    complexity = "medium"
                
                return {
                    'title': title,
                    'ingredients': ingredients,
                    'instructions': instructions,
                    'source': 'AllRecipes',
                    'source_url': url,
                    'date_scraped': datetime.now().isoformat(),
                    'complexity': complexity,
                    'tags': tags,
                    'categories': categories,
                    'metadata': metadata,
                    'raw_content': html_content
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON-LD: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting recipe info: {str(e)}")
            return None
    
    def _parse_iso_duration(self, iso_duration):
        """Parse ISO 8601 duration to minutes"""
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
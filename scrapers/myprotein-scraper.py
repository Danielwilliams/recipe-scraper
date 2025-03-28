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
        logging.FileHandler('myprotein_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

class MyProteinScraper:
    """Scraper for MyProtein.com recipes - integrates with recipe_scraper project"""
    
    def __init__(self):
        """Initialize the MyProtein recipe scraper"""
        logger.info("Initializing MyProtein Recipe Scraper")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://www.myprotein.com/'
        }
        
        # Base URL for recipes
        self.base_url = "https://www.myprotein.com/thezone/recipe/"
        
        # Cache of seen recipe links to avoid duplicates
        self.seen_recipe_links = set()
        
        logger.info("Initialized scraper for MyProtein recipes")

    def scrape(self, limit=50):
        """
        Scrape recipes from MyProtein
        
        Args:
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: Scraped recipes
        """
        logger.info(f"Starting MyProtein recipe scraping with limit: {limit}")
        recipes = []
        page_number = 1
        
        while len(recipes) < limit:
            if page_number == 1:
                page_url = self.base_url
            else:
                page_url = f"{self.base_url}page/{page_number}/"
                
            logger.info(f"Scraping recipe list page: {page_url}")
            
            try:
                # Get the recipe list page
                response = requests.get(page_url, headers=self.headers, timeout=30)
                
                if response.status_code != 200:
                    logger.error(f"Failed to access recipe list page: {page_url}, Status: {response.status_code}")
                    break
                
                # Parse the page
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find all recipe links on the page
                recipe_links = self._extract_recipe_links(soup, page_url)
                logger.info(f"Found {len(recipe_links)} recipe links on page {page_number}")
                
                if not recipe_links:
                    logger.info(f"No more recipe links found on page {page_number}")
                    break
                
                # Process each recipe link
                for url in recipe_links:
                    if len(recipes) >= limit:
                        logger.info(f"Reached limit of {limit} recipes")
                        break
                    
                    try:
                        logger.info(f"Scraping recipe: {url}")
                        recipe_info = self._scrape_recipe(url)
                        
                        if recipe_info:
                            recipes.append(recipe_info)
                            logger.info(f"Successfully scraped recipe: {recipe_info['title']}")
                        
                        # Be polite - don't hammer the server
                        time.sleep(random.uniform(1, 3))
                        
                    except Exception as e:
                        logger.error(f"Error scraping recipe {url}: {str(e)}")
                
                # Check if there's a next page
                next_page = self._check_next_page(soup)
                if not next_page:
                    logger.info("No more pages available")
                    break
                
                page_number += 1
                
                # Be polite between pages
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"Error processing page {page_number}: {str(e)}")
                break
        
        logger.info(f"Total MyProtein recipes scraped: {len(recipes)}")
        return recipes

    def _extract_recipe_links(self, soup, page_url):
        """
        Extract recipe links from a recipe list page
        
        Args:
            soup (BeautifulSoup): Parsed HTML of recipe list page
            page_url (str): URL of the current page
            
        Returns:
            list: List of recipe links
        """
        recipe_links = []
        
        # Find all post preview containers
        post_previews = soup.select('.post-preview')
        
        for preview in post_previews:
            # Find the heading and extract the link
            heading = preview.select_one('h2')
            if heading:
                link_elem = heading.find_parent('a')
                if link_elem and 'href' in link_elem.attrs:
                    href = link_elem['href']
                    
                    # Skip if already seen
                    if href in self.seen_recipe_links:
                        continue
                    
                    # Skip external links or non-recipe pages
                    if 'myprotein.com/thezone/recipe/' in href:
                        recipe_links.append(href)
                        self.seen_recipe_links.add(href)
        
        return recipe_links

    def _check_next_page(self, soup):
        """
        Check if there's a next page available
        
        Args:
            soup (BeautifulSoup): Parsed HTML of current page
            
        Returns:
            bool: True if next page exists, False otherwise
        """
        # Look for pagination links
        pagination = soup.select_one('.join')
        if pagination:
            next_link = pagination.select_one('a.btn')
            if next_link and '»' in next_link.text:
                return True
        
        return False

    def _scrape_recipe(self, url):
        """
        Scrape a single recipe page
        
        Args:
            url (str): URL of the recipe
            
        Returns:
            dict: Recipe information or None if failed
        """
        try:
            # Get the recipe page
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Failed to access recipe page: {url}, Status: {response.status_code}")
                return None
            
            # Parse the page
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract recipe details
            title = self._extract_title(soup)
            if not title:
                logger.warning(f"Could not extract title from {url}")
                return None
            
            image_url = self._extract_image_url(soup)
            ingredients = self._extract_ingredients(soup)
            instructions = self._extract_instructions(soup)
            
            # Skip if we couldn't extract essential recipe info
            if not ingredients or not instructions:
                logger.warning(f"Missing essential recipe data for {url}")
                return None
            
            # Extract additional information
            servings = self._extract_servings(soup)
            prep_time = self._extract_prep_time(soup)
            cook_time = self._extract_cook_time(soup)
            nutrition = self._extract_nutrition(soup)
            author = self._extract_author(soup)
            date_published = self._extract_date(soup)
            
            # Determine recipe complexity
            complexity = self._determine_complexity(ingredients, instructions)
            
            # Calculate total time if available
            total_time = None
            if prep_time is not None and cook_time is not None:
                total_time = prep_time + cook_time
                
            # Create recipe object matching the expected schema in the project
            recipe = {
                'title': title,
                'ingredients': ingredients,
                'instructions': instructions,
                'source': 'MyProtein',
                'source_url': url,
                'date_scraped': datetime.now().isoformat(),
                'date_processed': datetime.now().isoformat(),
                'complexity': complexity,
                'prep_time': prep_time,
                'cook_time': cook_time,
                'total_time': total_time,
                'servings': servings,
                'cuisine': None,  # MyProtein doesn't explicitly categorize by cuisine
                'image_url': image_url,
                'raw_content': '',  # We're not storing the raw HTML
                'metadata': {
                    'author': author,
                    'date_published': date_published,
                    'nutrition': nutrition
                },
                'tags': self._extract_tags(soup)  # Extract any recipe tags
            }
            
            return recipe
            
        except Exception as e:
            logger.error(f"Error extracting recipe from {url}: {str(e)}")
            return None

    def _extract_title(self, soup):
        """Extract recipe title"""
        title_elem = soup.select_one('h1.text-3xl, h2.text-2xl.font-bold')
        return title_elem.text.strip() if title_elem else None

    def _extract_image_url(self, soup):
        """Extract recipe image URL"""
        image_elem = soup.select_one('.container.mx-auto.article img')
        return image_elem.get('src') if image_elem else None

    def _extract_ingredients(self, soup):
        """Extract recipe ingredients"""
        ingredients = []
        
        # Find the ingredients section
        ingredients_section = soup.find('h2', text='Ingredients')
        if ingredients_section:
            # Get the next ul element
            ingredients_list = ingredients_section.find_next('ul')
            if ingredients_list:
                for li in ingredients_list.find_all('li'):
                    ingredients.append(li.text.strip())
        
        return ingredients

    def _extract_instructions(self, soup):
        """Extract recipe instructions"""
        instructions = []
        
        # Find the instructions section
        instructions_section = soup.find('h2', text='Instructions')
        if instructions_section:
            # Get the next ol element
            instructions_list = instructions_section.find_next('ol')
            if instructions_list:
                for li in instructions_list.find_all('li'):
                    instructions.append(li.text.strip())
        
        return instructions

    def _extract_servings(self, soup):
        """Extract number of servings"""
        servings_text = soup.find(string=re.compile('Servings:'))
        if servings_text:
            match = re.search(r'Servings:\s*(\d+)', servings_text)
            if match:
                return int(match.group(1))
        return None

    def _extract_prep_time(self, soup):
        """Extract preparation time in minutes"""
        prep_time_text = soup.find(string=re.compile('Prep time:'))
        if prep_time_text:
            match = re.search(r'Prep time:\s*(\d+)', prep_time_text)
            if match:
                return int(match.group(1))
        return None

    def _extract_cook_time(self, soup):
        """Extract cooking time in minutes"""
        cook_time_text = soup.find(string=re.compile('Cook time:'))
        if cook_time_text:
            match = re.search(r'Cook time:\s*(\d+)', cook_time_text)
            if match:
                return int(match.group(1))
        return None

    def _extract_nutrition(self, soup):
        """Extract nutrition information"""
        nutrition = {}
        
        # Find the nutrition table
        nutrition_table = soup.select_one('table.max-w-\\[600px\\]')
        if nutrition_table:
            rows = nutrition_table.select('tr')
            for row in rows:
                cells = row.select('td')
                if len(cells) == 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    try:
                        nutrition[key] = float(value)
                    except (ValueError, TypeError):
                        nutrition[key] = value
        
        return nutrition

    def _extract_author(self, soup):
        """Extract recipe author"""
        author_link = soup.select_one('.uppercase a.underline')
        if author_link:
            # Extract the author name from text like "By Author Name"
            author_text = author_link.text.strip()
            if author_text.startswith('By '):
                return author_text[3:].strip()
            return author_text
        return None

    def _extract_date(self, soup):
        """Extract publication date"""
        date_span = soup.select_one('.space-x-6 .opacity-60')
        if date_span:
            date_text = date_span.text.strip()
            try:
                # Convert to ISO format
                date_obj = datetime.strptime(date_text, '%m/%d/%Y')
                return date_obj.isoformat()
            except ValueError:
                return date_text
        return None

    def _extract_tags(self, soup):
        """
        Extract recipe tags
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            
        Returns:
            list: Recipe tags
        """
        tags = []
        
        # Look for category links or tags in the article
        tag_links = soup.select('a.uppercase.underline')
        for tag in tag_links:
            tag_text = tag.text.strip().lower()
            if tag_text and tag_text not in tags:
                tags.append(tag_text)
                
        # Also check for any dietary indicators (common on MyProtein)
        dietary_indicators = ['vegan', 'vegetarian', 'gluten-free', 'dairy-free', 
                             'high-protein', 'low-carb', 'keto', 'low-fat']
        
        article_text = soup.select_one('.container.mx-auto.article')
        if article_text:
            article_text = article_text.get_text().lower()
            for indicator in dietary_indicators:
                if indicator in article_text:
                    tags.append(indicator)
        
        return list(set(tags))  # Remove duplicates
    
    def _determine_complexity(self, ingredients, instructions):
        """
        Determine recipe complexity based on ingredients and instructions
        
        Args:
            ingredients (list): List of ingredients
            instructions (list): List of instructions
            
        Returns:
            str: 'easy', 'medium', or 'complex'
        """
        # Count ingredients and steps
        ingredient_count = len(ingredients)
        step_count = len(instructions)
        
        # Calculate total instruction complexity
        total_words = sum(len(step.split()) for step in instructions)
        avg_words_per_step = total_words / step_count if step_count > 0 else 0
        
        # Determine complexity
        if ingredient_count <= 7 and step_count <= 5 and avg_words_per_step < 20:
            return 'easy'
        elif ingredient_count >= 15 or step_count >= 10 or avg_words_per_step > 30:
            return 'complex'
        else:
            return 'medium'

    def save_recipe(self, recipe):
        """
        Save a recipe to the database
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            int: Recipe ID if successful, None otherwise
        """
        from database.recipe_storage import RecipeStorage
        
        try:
            storage = RecipeStorage()
            recipe_id = storage.save_recipe(recipe)
            return recipe_id
        except Exception as e:
            logger.error(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
    def save_recipes_to_json(self, recipes, filename="myprotein_recipes.json"):
        """
        Save scraped recipes to a JSON file
        
        Args:
            recipes (list): List of recipe dictionaries
            filename (str): Output JSON filename
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(recipes, f, ensure_ascii=False, indent=4)
            logger.info(f"Successfully saved {len(recipes)} recipes to {filename}")
        except Exception as e:
            logger.error(f"Error saving recipes to JSON: {str(e)}")
            
    def save_recipes_to_db(self, recipes):
        """
        Save scraped recipes to the database
        
        Args:
            recipes (list): List of recipe dictionaries
            
        Returns:
            tuple: (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0
        
        for recipe in recipes:
            try:
                result = self.save_recipe(recipe)
                if result:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(f"Error saving recipe: {str(e)}")
                logger.error(traceback.format_exc())
                failure_count += 1
                
        return (success_count, failure_count)

# Example usage
if __name__ == "__main__":
    # When running as standalone script
    try:
        from database.db_connector import create_tables_if_not_exist
        
        # Ensure database tables exist
        create_tables_if_not_exist()
        
        # Create scraper and run
        scraper = MyProteinScraper()
        recipes = scraper.scrape(limit=10)
        
        # Save to JSON file (for backup)
        scraper.save_recipes_to_json(recipes)
        
        # Save to database
        success, failure = scraper.save_recipes_to_db(recipes)
        logger.info(f"Saved to database: {success} successful, {failure} failed")
        
        print(f"Scraped {len(recipes)} recipes")
    except ImportError:
        # If database modules not available, just save to JSON
        scraper = MyProteinScraper()
        recipes = scraper.scrape(limit=10)
        scraper.save_recipes_to_json(recipes)
        print(f"Scraped {len(recipes)} recipes (saved to JSON only)")
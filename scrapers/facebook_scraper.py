# scrapers/facebook_scraper.py
import logging
import requests
import re
import json
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class FacebookScraper:
    """
    Scraper for public Facebook pages with recipes
    Note: This uses the Facebook Graph API which requires an access token
    """
    
    def __init__(self, access_token=None):
        """
        Initialize the Facebook scraper
        
        Args:
            access_token (str): Facebook Graph API access token
        """
        self.access_token = access_token
        if not self.access_token:
            raise ValueError("Facebook access token is required")
        
        self.api_version = "v18.0"  # Use the latest stable version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    def scrape(self, page_ids=None, limit=50):
        """
        Scrape recipes from Facebook pages
        
        Args:
            page_ids (list): List of Facebook page IDs or handles
            limit (int): Maximum number of recipes to scrape per page
            
        Returns:
            list: List of scraped recipe dictionaries
        """
        if not page_ids:
            logger.warning("No Facebook page IDs provided")
            return []

        recipes = []
        
        for page_id in page_ids:
            try:
                logger.info(f"Scraping recipes from Facebook page: {page_id}")
                page_recipes = self._scrape_page(page_id, limit)
                recipes.extend(page_recipes)
                
                # Be polite to the API
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scraping Facebook page {page_id}: {str(e)}")
        
        return recipes
    
    def _scrape_page(self, page_id, limit):
        """
        Scrape recipes from a single Facebook page
        
        Args:
            page_id (str): Facebook page ID or handle
            limit (int): Maximum number of recipes to scrape
            
        Returns:
            list: List of recipe dictionaries
        """
        recipes = []
        next_url = None
        
        try:
            # Get basic page info first to confirm it exists
            page_info_url = f"{self.base_url}/{page_id}?fields=name,id&access_token={self.access_token}"
            response = requests.get(page_info_url)
            
            if not response.ok:
                logger.error(f"Could not access page {page_id}: {response.status_code} {response.text}")
                return recipes
            
            page_info = response.json()
            logger.info(f"Scraping page: {page_info.get('name', page_id)}")
            
            # Get posts from the page
            posts_url = f"{self.base_url}/{page_id}/posts?fields=message,created_time,permalink_url,full_picture&limit=100&access_token={self.access_token}"
            
            while len(recipes) < limit and posts_url:
                response = requests.get(posts_url)
                
                if not response.ok:
                    logger.error(f"Error fetching posts: {response.status_code} {response.text}")
                    break
                
                posts_data = response.json()
                
                if 'data' not in posts_data or not posts_data['data']:
                    logger.info("No more posts found")
                    break
                
                for post in posts_data['data']:
                    if 'message' not in post:
                        continue
                    
                    # Check if this post contains a recipe
                    if self._is_recipe(post):
                        recipe_info = self._extract_recipe_info(post)
                        if recipe_info:
                            recipes.append(recipe_info)
                            logger.info(f"Found recipe: {recipe_info['title']}")
                            
                            if len(recipes) >= limit:
                                break
                
                # Check for next page of results
                if 'paging' in posts_data and 'next' in posts_data['paging']:
                    posts_url = posts_data['paging']['next']
                    # Be polite to the API
                    time.sleep(1)
                else:
                    posts_url = None
            
            return recipes
            
        except Exception as e:
            logger.error(f"Error scraping page {page_id}: {str(e)}")
            return recipes
    
    def _is_recipe(self, post):
        """
        Determine if a Facebook post contains a recipe
        
        Args:
            post (dict): Facebook post data
            
        Returns:
            bool: True if post likely contains a recipe
        """
        if 'message' not in post:
            return False
        
        message = post['message'].lower()
        
        # Check for recipe indicators
        recipe_keywords = [
            'recipe', 'ingredients', 'instructions', 'directions',
            'cook', 'bake', 'mix', 'stir', 'preheat', 'whisk',
            'serving', 'serves', 'prep time', 'cook time'
        ]
        
        # Common recipe patterns
        recipe_patterns = [
            r'ingredients:',
            r'directions:',
            r'instructions:',
            r'\d+\s*(?:cup|cups|tablespoon|tablespoons|tbsp|teaspoon|teaspoons|tsp|oz|ounce|ounces|lb|pound|pounds|g|gram|grams|kg|kilogram|kilograms)',
            r'^\d+\.\s+',  # Numbered steps
            r'preheat (?:oven|grill) to \d+'
        ]
        
        # Check for keywords
        if any(keyword in message for keyword in recipe_keywords):
            return True
        
        # Check for patterns
        if any(re.search(pattern, message, re.IGNORECASE | re.MULTILINE) for pattern in recipe_patterns):
            return True
        
        return False
    
    def _extract_recipe_info(self, post):
        """
        Extract structured recipe information from a Facebook post
        
        Args:
            post (dict): Facebook post data
            
        Returns:
            dict: Structured recipe information
        """
        if 'message' not in post:
            return None
        
        message = post['message']
        
        # Try to extract a title
        title_match = re.search(r'^([^\n\.]+)', message)
        title = title_match.group(1).strip() if title_match else "Untitled Recipe"
        
        # Clean up title
        if len(title) > 100:  # Likely not a proper title if too long
            title = title[:97] + "..."
        
        # Extract ingredients section
        ingredients = []
        ingredients_section = None
        
        # Try different patterns for ingredients section
        patterns = [
            r'(?:ingredients|you\'ll need)[:\n]+\s*(.*?)(?:(?:instructions|directions|steps|method|preparation)[:\n]|$)',
            r'(?:what you\'ll need)[:\n]+\s*(.*?)(?:(?:instructions|directions|steps|method|preparation)[:\n]|$)',
            r'(?:you will need)[:\n]+\s*(.*?)(?:(?:instructions|directions|steps|method|preparation)[:\n]|$)'
        ]
        
        for pattern in patterns:
            ingredients_match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if ingredients_match:
                ingredients_section = ingredients_match.group(1)
                break
        
        if ingredients_section:
            # Split by common ingredient delimiters
            lines = re.split(r'[\n•\-]+', ingredients_section)
            ingredients = [line.strip() for line in lines if line.strip()]
        
        # Extract instructions section
        instructions = []
        instructions_section = None
        
        # Try different patterns for instructions section
        patterns = [
            r'(?:instructions|directions|steps|method|preparation)[:\n]+\s*(.*?)(?:(?:notes|enjoy|serve|yield|nutrition|makes)[:\n]|$)',
            r'(?:how to make it)[:\n]+\s*(.*?)(?:(?:notes|enjoy|serve|yield|nutrition|makes)[:\n]|$)',
            r'(?:method)[:\n]+\s*(.*?)(?:(?:notes|enjoy|serve|yield|nutrition|makes)[:\n]|$)'
        ]
        
        for pattern in patterns:
            instructions_match = re.search(pattern, message, re.IGNORECASE | re.DOTALL)
            if instructions_match:
                instructions_section = instructions_match.group(1)
                break
        
        if instructions_section:
            # Try to split by numbered steps first
            step_matches = re.findall(r'(?:\d+\.\s*|\n-\s*)([^\n\d\.]+)', instructions_section)
            
            if step_matches:
                instructions = [step.strip() for step in step_matches if step.strip()]
            else:
                # Fall back to splitting by newlines
                lines = instructions_section.split('\n')
                instructions = [line.strip() for line in lines if line.strip()]
        
        # Extract metadata
        metadata = {}
        
        # Prep time
        prep_time_match = re.search(r'(?:prep time|preparation)[:\s]+(\d+)[\s-]*(minutes?|mins?|hours?|hrs?)', 
                                 message, re.IGNORECASE)
        if prep_time_match:
            time_value = int(prep_time_match.group(1))
            time_unit = prep_time_match.group(2).lower()
            
            if 'hour' in time_unit:
                time_value *= 60  # Convert to minutes
                
            metadata['prep_time'] = time_value
        
        # Cook time
        cook_time_match = re.search(r'(?:cook time|baking time)[:\s]+(\d+)[\s-]*(minutes?|mins?|hours?|hrs?)', 
                                 message, re.IGNORECASE)
        if cook_time_match:
            time_value = int(cook_time_match.group(1))
            time_unit = cook_time_match.group(2).lower()
            
            if 'hour' in time_unit:
                time_value *= 60  # Convert to minutes
                
            metadata['cook_time'] = time_value
        
        # Servings
        servings_match = re.search(r'(?:serves|servings|yield)[:\s]+(\d+)', message, re.IGNORECASE)
        if servings_match:
            metadata['servings'] = int(servings_match.group(1))
        
        # Skip if we couldn't extract minimal recipe data
        if len(ingredients) < 2 or len(instructions) < 2:
            logger.info(f"Skipping post - not enough recipe data extracted: {title}")
            return None
        
        # Determine complexity based on number of ingredients and steps
        complexity = "easy"
        if len(ingredients) >= 10 or len(instructions) >= 7:
            complexity = "complex"
        elif len(ingredients) >= 6 or len(instructions) >= 4:
            complexity = "medium"
        
        # Look for cuisine hints
        cuisine = None
        cuisine_keywords = {
            'italian': ['italian', 'pasta', 'pizza', 'risotto'],
            'mexican': ['mexican', 'taco', 'burrito', 'enchilada', 'quesadilla'],
            'chinese': ['chinese', 'stir fry', 'wok', 'dumpling'],
            'indian': ['indian', 'curry', 'masala', 'tikka'],
            'thai': ['thai', 'pad thai', 'curry'],
            'japanese': ['japanese', 'sushi', 'ramen', 'udon'],
            'french': ['french', 'croissant', 'baguette'],
            'mediterranean': ['mediterranean', 'greek', 'hummus', 'falafel']
        }
        
        for cuisine_name, keywords in cuisine_keywords.items():
            if any(keyword in message.lower() for keyword in keywords):
                cuisine = cuisine_name
                break
        
        # Extract possible tags
        tags = []
        tag_candidates = ['vegetarian', 'vegan', 'gluten-free', 'keto', 'low-carb', 
                          'dairy-free', 'quick', 'easy', 'dessert', 'breakfast', 
                          'lunch', 'dinner', 'snack', 'healthy', 'baking']
        
        for tag in tag_candidates:
            if tag in message.lower():
                tags.append(tag)
        
        # Add complexity as a tag
        tags.append(complexity)
        
        # Build the recipe object
        recipe = {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions,
            'source': 'Facebook',
            'source_url': post.get('permalink_url', ''),
            'date_scraped': datetime.now().isoformat(),
            'complexity': complexity,
            'raw_content': message[:5000],  # Limit raw content size
            'metadata': metadata,
            'cuisine': cuisine,
            'tags': tags,
            'image_url': post.get('full_picture', None)
        }
        
        return recipe
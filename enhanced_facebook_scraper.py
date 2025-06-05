#!/usr/bin/env python3
"""
Enhanced Facebook Scraper with URL Extraction and Database Integration

This script:
1. Extracts Facebook URLs from the FB URLs.txt HTML content
2. Checks if recipes already exist in the database by title and source
3. Updates source_url and downloads images for existing recipes if missing
4. Creates new recipes with proper URLs and images if they don't exist
"""

import os
import re
import json
import logging
import sys
from datetime import datetime
from urllib.parse import urlparse, urljoin

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import requests
    from bs4 import BeautifulSoup
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from database.db_connector import get_db_connection
    from database.recipe_storage import RecipeStorage
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Please install required packages from requirements.txt")
    DEPENDENCIES_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_facebook_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced_facebook_scraper")

# Headers to appear more like a regular browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

class EnhancedFacebookScraper:
    """Enhanced Facebook scraper with database integration and image downloading"""
    
    def __init__(self, output_dir="recipe_images"):
        self.recipe_storage = RecipeStorage()
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
    
    def extract_facebook_urls(self, html_content):
        """Extract Facebook post URLs from HTML content"""
        urls = []
        
        # Pattern to match Facebook post URLs
        url_patterns = [
            r'href="(https://www\.facebook\.com/groups/[\w]+/permalink/[\w]+/)"',
            r'href="(https://www\.facebook\.com/groups/[\w]+/posts/[\w]+/)"',
            r'href="(https://www\.facebook\.com/permalink\.php\?story_fbid=[^"]+)"',
            r'href="(/groups/[\w]+/permalink/[\w]+/)"',
            r'href="(/groups/[\w]+/posts/[\w]+/)"',
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, html_content)
            for match in matches:
                # Convert relative URLs to absolute
                if match.startswith('/'):
                    url = f"https://www.facebook.com{match}"
                else:
                    url = match
                
                if url not in urls:
                    urls.append(url)
        
        logger.info(f"Extracted {len(urls)} Facebook URLs")
        return urls
    
    def extract_recipe_from_html(self, html_content, source_url):
        """Extract recipe information from Facebook HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try to find recipe text in various elements
        recipe_text = ""
        
        # Look for recipe content in common Facebook post elements
        selectors = [
            '[data-testid="post_message"]',
            '.userContent',
            '.text_exposed_root',
            '[role="article"] span',
            'div[data-ad-preview="message"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if len(text) > len(recipe_text):
                    recipe_text = text
        
        # If no specific selectors work, try getting all text
        if not recipe_text:
            recipe_text = soup.get_text()
        
        if not recipe_text:
            logger.warning(f"No text content found for {source_url}")
            return None
        
        # Check if this looks like a recipe
        if not self._is_recipe_content(recipe_text):
            logger.info(f"Content doesn't appear to be a recipe: {source_url}")
            return None
        
        # Extract recipe components
        recipe_info = self._extract_recipe_info(recipe_text, source_url)
        
        # Try to extract image URL
        image_url = self._extract_image_url(soup, source_url)
        if image_url:
            recipe_info['image_url'] = image_url
        
        return recipe_info
    
    def _is_recipe_content(self, text):
        """Check if text content appears to be a recipe"""
        text_lower = text.lower()
        
        # Recipe indicators
        recipe_keywords = [
            'ingredients', 'instructions', 'directions', 'recipe',
            'cook', 'bake', 'mix', 'stir', 'preheat', 'whisk',
            'serving', 'serves', 'prep time', 'cook time', 'minutes'
        ]
        
        # Recipe patterns
        recipe_patterns = [
            r'\d+\s*(?:cup|cups|tablespoon|tablespoons|tbsp|teaspoon|teaspoons|tsp|oz|ounce|ounces)',
            r'preheat.*oven.*\d+',
            r'cook.*time.*\d+.*min',
            r'prep.*time.*\d+.*min'
        ]
        
        # Check keywords
        keyword_count = sum(1 for keyword in recipe_keywords if keyword in text_lower)
        
        # Check patterns
        pattern_matches = sum(1 for pattern in recipe_patterns if re.search(pattern, text_lower))
        
        # Consider it a recipe if we have multiple indicators
        return keyword_count >= 2 or pattern_matches >= 1
    
    def _extract_recipe_info(self, text, source_url):
        """Extract structured recipe information from text"""
        # Extract title (first line or sentence)
        title_match = re.search(r'^([^\n\.!]{10,100})', text.strip())
        title = title_match.group(1).strip() if title_match else "Facebook Recipe"
        
        # Clean up title
        title = re.sub(r'[🍽️🔥🍋🧀🥘🌟✨🎉]+', '', title).strip()
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Extract ingredients
        ingredients = self._extract_ingredients(text)
        
        # Extract instructions
        instructions = self._extract_instructions(text)
        
        # Extract metadata
        metadata = self._extract_metadata(text)
        
        # Determine complexity
        complexity = "easy"
        if len(ingredients) >= 10 or len(instructions) >= 7:
            complexity = "complex"
        elif len(ingredients) >= 6 or len(instructions) >= 4:
            complexity = "medium"
        
        # Extract tags
        tags = self._extract_tags(text, complexity)
        
        # Build recipe object
        recipe = {
            'title': title,
            'source': 'Facebook',
            'source_url': source_url,
            'ingredients': ingredients,
            'instructions': instructions,
            'date_scraped': datetime.now().isoformat(),
            'complexity': complexity,
            'raw_content': text[:5000],  # Limit size
            'metadata': metadata,
            'tags': tags,
            'cuisine': self._extract_cuisine(text)
        }
        
        return recipe
    
    def _extract_ingredients(self, text):
        """Extract ingredients from text"""
        ingredients = []
        
        # Try to find ingredients section
        ingredients_section = None
        patterns = [
            r'(?:ingredients|you\'ll need)[:\n]+\s*(.*?)(?:(?:instructions|directions|steps|method)[:\n]|$)',
            r'(?:what you\'ll need)[:\n]+\s*(.*?)(?:(?:instructions|directions|steps|method)[:\n]|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                ingredients_section = match.group(1)
                break
        
        if ingredients_section:
            # Split by common delimiters
            lines = re.split(r'[\n•\-*]+', ingredients_section)
            ingredients = [line.strip() for line in lines if line.strip()]
        else:
            # Try to extract ingredient-like lines
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                # Look for measurement patterns
                if re.search(r'\d+\s*(?:cup|cups|tbsp|tsp|oz|lb|g|kg)', line, re.IGNORECASE):
                    ingredients.append(line)
        
        return ingredients[:20]  # Limit to reasonable number
    
    def _extract_instructions(self, text):
        """Extract instructions from text"""
        instructions = []
        
        # Try to find instructions section
        instructions_section = None
        patterns = [
            r'(?:instructions|directions|steps|method)[:\n]+\s*(.*?)(?:(?:notes|enjoy|serve)[:\n]|$)',
            r'(?:how to make)[:\n]+\s*(.*?)(?:(?:notes|enjoy|serve)[:\n]|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                instructions_section = match.group(1)
                break
        
        if instructions_section:
            # Try numbered steps first
            numbered_steps = re.findall(r'(?:\d+[\.\)]\s*)(.*?)(?=\d+[\.\)]|$)', instructions_section, re.DOTALL)
            if numbered_steps:
                instructions = [step.strip() for step in numbered_steps if step.strip()]
            else:
                # Split by sentences or lines
                sentences = re.split(r'[\.!]\s+', instructions_section)
                instructions = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        return instructions[:15]  # Limit to reasonable number
    
    def _extract_metadata(self, text):
        """Extract metadata like prep time, cook time, servings"""
        metadata = {}
        
        # Prep time
        prep_match = re.search(r'(?:prep.*time)[:\s]*(\d+)[\s-]*(?:min|minute)', text, re.IGNORECASE)
        if prep_match:
            metadata['prep_time'] = int(prep_match.group(1))
        
        # Cook time
        cook_match = re.search(r'(?:cook.*time|bake.*time)[:\s]*(\d+)[\s-]*(?:min|minute)', text, re.IGNORECASE)
        if cook_match:
            metadata['cook_time'] = int(cook_match.group(1))
        
        # Servings
        serving_match = re.search(r'(?:serves|servings|yield)[:\s]*(\d+)', text, re.IGNORECASE)
        if serving_match:
            metadata['servings'] = int(serving_match.group(1))
        
        return metadata
    
    def _extract_tags(self, text, complexity):
        """Extract tags from text"""
        tags = [complexity]
        
        tag_candidates = [
            'vegetarian', 'vegan', 'gluten-free', 'keto', 'low-carb',
            'dairy-free', 'quick', 'easy', 'dessert', 'breakfast',
            'lunch', 'dinner', 'snack', 'healthy', 'baking'
        ]
        
        text_lower = text.lower()
        for tag in tag_candidates:
            if tag in text_lower:
                tags.append(tag)
        
        return tags
    
    def _extract_cuisine(self, text):
        """Extract cuisine type from text"""
        cuisine_keywords = {
            'italian': ['italian', 'pasta', 'pizza', 'risotto'],
            'mexican': ['mexican', 'taco', 'burrito', 'enchilada'],
            'chinese': ['chinese', 'stir fry', 'wok'],
            'indian': ['indian', 'curry', 'masala'],
            'thai': ['thai', 'pad thai'],
            'french': ['french', 'croissant'],
            'mediterranean': ['mediterranean', 'greek', 'hummus']
        }
        
        text_lower = text.lower()
        for cuisine, keywords in cuisine_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return cuisine
        
        return None
    
    def _extract_image_url(self, soup, source_url):
        """Extract image URL from HTML"""
        image_url = None
        
        # Try various methods to find images
        # Method 1: img tags with src
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src')
            if src and 'scontent' in src and any(ext in src for ext in ['.jpg', '.jpeg', '.png']):
                image_url = src
                break
        
        if image_url:
            # Make sure URL is absolute
            image_url = urljoin(source_url, image_url)
        
        return image_url
    
    def check_recipe_exists(self, title, source='Facebook'):
        """Check if recipe already exists in database"""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, source_url, image_url 
                    FROM scraped_recipes 
                    WHERE title = %s AND source = %s
                    LIMIT 1
                """, (title, source))
                
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error checking recipe existence: {str(e)}")
            return None
        finally:
            conn.close()
    
    def update_recipe_source_url(self, recipe_id, source_url, image_url=None):
        """Update source URL and optionally image URL for existing recipe"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                if image_url:
                    cursor.execute("""
                        UPDATE scraped_recipes 
                        SET source_url = %s, image_url = %s, date_processed = %s
                        WHERE id = %s
                    """, (source_url, image_url, datetime.now(), recipe_id))
                else:
                    cursor.execute("""
                        UPDATE scraped_recipes 
                        SET source_url = %s, date_processed = %s
                        WHERE id = %s
                    """, (source_url, datetime.now(), recipe_id))
                
                conn.commit()
                logger.info(f"Updated recipe {recipe_id} with new source URL")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating recipe {recipe_id}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def download_image(self, image_url, recipe_id, recipe_title):
        """Download image and save locally"""
        try:
            response = requests.get(image_url, headers=HEADERS, timeout=15, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not return an image: {content_type}")
                return None
            
            # Create filename
            extension = '.jpg'
            if '.png' in image_url:
                extension = '.png'
            elif '.jpeg' in image_url:
                extension = '.jpeg'
            
            safe_title = re.sub(r'[<>:"/\\|?*]', '', recipe_title)[:50]
            filename = f"{recipe_id}_{safe_title}{extension}"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save image
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded image: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading image from {image_url}: {str(e)}")
            return None
    
    def scrape_facebook_urls(self, fb_urls_file, limit=50, force_update=False):
        """Main method to scrape Facebook URLs and process recipes"""
        # Read the HTML content
        with open(fb_urls_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract URLs
        urls = self.extract_facebook_urls(html_content)
        
        if not urls:
            logger.warning("No Facebook URLs found in the file")
            return
        
        # Limit the number of URLs to process
        urls_to_process = urls[:limit]
        logger.info(f"Processing {len(urls_to_process)} of {len(urls)} Facebook URLs (limit: {limit})")
        
        # Process each URL
        processed = 0
        created = 0
        updated = 0
        errors = 0
        
        for url in urls_to_process:
            try:
                logger.info(f"Processing URL: {url}")
                
                # Extract recipe from the same HTML content since we already have it
                recipe_info = self.extract_recipe_from_html(html_content, url)
                
                if not recipe_info:
                    logger.info(f"No recipe found at {url}")
                    continue
                
                # Check if recipe exists
                existing = self.check_recipe_exists(recipe_info['title'])
                
                if existing:
                    # Recipe exists - check if we need to update it
                    recipe_id = existing['id']
                    needs_update = force_update
                    
                    # Update source URL if missing, different, or force update
                    if force_update or not existing['source_url'] or existing['source_url'] != url:
                        needs_update = True
                        logger.info(f"Will update source URL for existing recipe: {recipe_info['title']}")
                    
                    # Download image if missing or force update
                    image_downloaded = False
                    if (force_update or not existing['image_url']) and recipe_info.get('image_url'):
                        image_path = self.download_image(
                            recipe_info['image_url'], 
                            recipe_id, 
                            recipe_info['title']
                        )
                        if image_path:
                            image_downloaded = True
                    
                    if needs_update:
                        self.update_recipe_source_url(
                            recipe_id, 
                            url, 
                            recipe_info.get('image_url') if image_downloaded else None
                        )
                        updated += 1
                    else:
                        logger.info(f"Recipe already up to date: {recipe_info['title']}")
                else:
                    # New recipe - save it
                    # Download image if available
                    if recipe_info.get('image_url'):
                        image_path = self.download_image(
                            recipe_info['image_url'], 
                            'new', 
                            recipe_info['title']
                        )
                    
                    recipe_id = self.recipe_storage.save_recipe(recipe_info)
                    if recipe_id:
                        created += 1
                        logger.info(f"Created new recipe: {recipe_info['title']} (ID: {recipe_id})")
                    else:
                        errors += 1
                
                processed += 1
                
            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}")
                errors += 1
        
        # Summary
        logger.info(f"\nProcessing complete!")
        logger.info(f"URLs processed: {processed}")
        logger.info(f"New recipes created: {created}")
        logger.info(f"Existing recipes updated: {updated}")
        logger.info(f"Errors: {errors}")

def main():
    """Main function"""
    import argparse
    
    if not DEPENDENCIES_AVAILABLE:
        print("Cannot run scraper due to missing dependencies")
        return
    
    parser = argparse.ArgumentParser(description="Process Facebook URLs and update database")
    parser.add_argument("--file", default="data/FB_URLs.txt", help="Path to FB URLs file")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of URLs to process")
    parser.add_argument("--force-update", action="store_true", help="Force update existing recipes")
    parser.add_argument("--output-dir", default="recipe_images", help="Directory to save images")
    
    args = parser.parse_args()
    
    # Check for file in multiple possible locations
    possible_paths = [
        args.file,
        "FB URLs.txt",
        "data/FB URLs.txt",  # With space
        "data/FB_URLs.txt",  # With underscore
        "/mnt/e/recipe-scraper/FB URLs.txt"
    ]
    
    fb_urls_file = None
    for path in possible_paths:
        if os.path.exists(path):
            fb_urls_file = path
            break
    
    if not fb_urls_file:
        logger.error(f"FB URLs file not found in any of these locations: {possible_paths}")
        print("Please upload your FB URLs file to: data/FB_URLs.txt")
        return
    
    logger.info(f"Using FB URLs file: {fb_urls_file}")
    
    scraper = EnhancedFacebookScraper(output_dir=args.output_dir)
    scraper.scrape_facebook_urls(fb_urls_file, limit=args.limit, force_update=args.force_update)

if __name__ == "__main__":
    main()
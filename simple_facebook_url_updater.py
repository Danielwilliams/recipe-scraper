#!/usr/bin/env python3
"""
Simple Facebook URL Updater

This script takes a simpler approach:
1. Extracts recipe titles and URLs from the FB HTML file
2. Matches titles to existing recipes in the database
3. Updates the source_url for matching recipes
"""

import os
import re
import logging
import sys
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from database.db_connector import get_db_connection
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    DEPENDENCIES_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_facebook_url_updater.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("simple_facebook_url_updater")

class SimpleFacebookUrlUpdater:
    """Simple approach to update Facebook source URLs"""
    
    def extract_title_url_pairs(self, html_content):
        """Extract title-URL pairs from Facebook HTML"""
        pairs = []
        
        # Pattern to find Facebook URLs
        url_pattern = r'href="(https://www\.facebook\.com/groups/[^"]+/(?:permalink|posts)/[^"]+/)"'
        urls = re.findall(url_pattern, html_content)
        
        logger.info(f"Found {len(urls)} Facebook URLs")
        
        # For each URL, try to find associated recipe title
        for url in urls:
            # Look for recipe titles near this URL in the HTML
            title = self.find_title_near_url(html_content, url)
            if title:
                pairs.append((title, url))
                logger.debug(f"Found pair: '{title}' -> {url}")
        
        logger.info(f"Extracted {len(pairs)} title-URL pairs")
        return pairs
    
    def find_title_near_url(self, html_content, url):
        """Find recipe title near a URL in the HTML"""
        # Find the position of the URL in the content
        url_pos = html_content.find(url)
        if url_pos == -1:
            return None
        
        # Look in a window around the URL for recipe titles
        window_size = 2000  # Characters before and after URL
        start = max(0, url_pos - window_size)
        end = min(len(html_content), url_pos + window_size)
        window = html_content[start:end]
        
        # Look for recipe title patterns
        title_patterns = [
            r'<span[^>]*>([^<]{20,100}(?:Recipe|Chicken|Pasta|Soup|Salad|Cake|Cookies|Bread)[^<]{0,50})</span>',
            r'>([A-Z][^<]{15,80}(?:Recipe|Chicken|Pasta|Soup|Salad|Cake|Cookies|Bread)[^<]{0,40})<',
            r'title="([^"]{20,100})"',
            r'aria-label="([^"]{20,100})"'
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, window, re.IGNORECASE)
            for match in matches:
                # Clean up the title
                title = self.clean_title(match)
                if title and self.is_likely_recipe_title(title):
                    return title
        
        return None
    
    def clean_title(self, title):
        """Clean up extracted title"""
        # Remove HTML entities
        title = re.sub(r'&[a-zA-Z0-9#]+;', ' ', title)
        
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove emojis and special characters
        title = re.sub(r'[🍽️🔥🍋🧀🥘🌟✨🎉💯❤️👌🤤😋]+', '', title).strip()
        
        # Remove common prefixes/suffixes
        title = re.sub(r'^(Recipe:|Recipe\s+)', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+(Recipe)$', '', title, flags=re.IGNORECASE)
        
        return title[:100] if len(title) <= 100 else None
    
    def is_likely_recipe_title(self, title):
        """Check if title looks like a recipe"""
        if not title or len(title) < 10:
            return False
        
        # Skip titles that are clearly not recipes
        skip_patterns = [
            r'^\d+$',  # Just numbers
            r'^[A-Z\s]+$',  # All caps (probably UI text)
            r'Click here|See more|Show more|Read more',
            r'Facebook|Group|Post|Comment|Share|Like'
        ]
        
        for pattern in skip_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return False
        
        # Look for recipe indicators
        recipe_words = [
            'recipe', 'chicken', 'pasta', 'soup', 'salad', 'cake', 'cookies', 
            'bread', 'pie', 'casserole', 'stir fry', 'curry', 'sandwich',
            'pizza', 'burger', 'taco', 'burrito', 'rice', 'noodle'
        ]
        
        title_lower = title.lower()
        return any(word in title_lower for word in recipe_words)
    
    def find_matching_recipes(self, title_url_pairs):
        """Find matching recipes in database"""
        if not title_url_pairs:
            return []
        
        conn = get_db_connection()
        matches = []
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                for title, url in title_url_pairs:
                    # Try exact match first
                    cursor.execute("""
                        SELECT id, title, source_url 
                        FROM scraped_recipes 
                        WHERE title = %s AND source = 'Facebook'
                        LIMIT 1
                    """, (title,))
                    
                    result = cursor.fetchone()
                    if result:
                        matches.append({
                            'recipe_id': result['id'],
                            'db_title': result['title'],
                            'current_url': result['source_url'],
                            'new_url': url,
                            'match_type': 'exact'
                        })
                        continue
                    
                    # Try fuzzy match (similar titles)
                    cursor.execute("""
                        SELECT id, title, source_url 
                        FROM scraped_recipes 
                        WHERE source = 'Facebook' 
                        AND (
                            title ILIKE %s OR 
                            title ILIKE %s OR
                            %s ILIKE title
                        )
                        LIMIT 1
                    """, (f'%{title}%', f'{title}%', f'%{title}%'))
                    
                    result = cursor.fetchone()
                    if result:
                        matches.append({
                            'recipe_id': result['id'],
                            'db_title': result['title'],
                            'current_url': result['source_url'],
                            'new_url': url,
                            'match_type': 'fuzzy'
                        })
        
        except Exception as e:
            logger.error(f"Error finding matching recipes: {str(e)}")
        finally:
            conn.close()
        
        logger.info(f"Found {len(matches)} matching recipes")
        return matches
    
    def update_recipe_urls(self, matches, force_update=False):
        """Update source URLs for matching recipes"""
        if not matches:
            return
        
        conn = get_db_connection()
        updated_count = 0
        
        try:
            with conn.cursor() as cursor:
                for match in matches:
                    recipe_id = match['recipe_id']
                    current_url = match['current_url']
                    new_url = match['new_url']
                    match_type = match['match_type']
                    
                    # Update if no current URL or force update
                    if not current_url or force_update or current_url != new_url:
                        cursor.execute("""
                            UPDATE scraped_recipes 
                            SET source_url = %s, date_processed = %s
                            WHERE id = %s
                        """, (new_url, datetime.now(), recipe_id))
                        
                        updated_count += 1
                        logger.info(f"Updated recipe {recipe_id} ({match_type} match): '{match['db_title']}' -> {new_url}")
                    else:
                        logger.info(f"Recipe {recipe_id} already has correct URL: '{match['db_title']}'")
            
            conn.commit()
            logger.info(f"Successfully updated {updated_count} recipes")
        
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating recipe URLs: {str(e)}")
        finally:
            conn.close()
    
    def process_facebook_urls(self, fb_urls_file, force_update=False):
        """Main processing function"""
        logger.info(f"Processing Facebook URLs from: {fb_urls_file}")
        
        # Read HTML content
        with open(fb_urls_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        logger.info(f"Read HTML file: {len(html_content)} characters")
        
        # Extract title-URL pairs
        title_url_pairs = self.extract_title_url_pairs(html_content)
        
        if not title_url_pairs:
            logger.warning("No title-URL pairs found")
            return
        
        # Find matching recipes in database
        matches = self.find_matching_recipes(title_url_pairs)
        
        if not matches:
            logger.warning("No matching recipes found in database")
            return
        
        # Update URLs
        self.update_recipe_urls(matches, force_update)
        
        # Summary
        logger.info(f"Processing summary:")
        logger.info(f"- Title-URL pairs extracted: {len(title_url_pairs)}")
        logger.info(f"- Database matches found: {len(matches)}")
        logger.info(f"- URLs updated: {len([m for m in matches if not m['current_url'] or force_update])}")

def main():
    """Main function"""
    import argparse
    
    if not DEPENDENCIES_AVAILABLE:
        print("Cannot run updater due to missing dependencies")
        return
    
    parser = argparse.ArgumentParser(description="Update Facebook source URLs for existing recipes")
    parser.add_argument("--file", default="data/FB URLs.txt", help="Path to FB URLs file")
    parser.add_argument("--force-update", action="store_true", help="Force update existing URLs")
    
    args = parser.parse_args()
    
    # Check for file in multiple possible locations
    possible_paths = [
        args.file,
        "FB URLs.txt",
        "data/FB URLs.txt",
        "data/FB_URLs.txt",
        "/mnt/e/recipe-scraper/FB URLs.txt"
    ]
    
    fb_urls_file = None
    for path in possible_paths:
        if os.path.exists(path):
            fb_urls_file = path
            break
    
    if not fb_urls_file:
        logger.error(f"FB URLs file not found in any of these locations: {possible_paths}")
        print("Please upload your FB URLs file to: data/FB URLs.txt")
        return
    
    logger.info(f"Using FB URLs file: {fb_urls_file}")
    
    updater = SimpleFacebookUrlUpdater()
    updater.process_facebook_urls(fb_urls_file, args.force_update)

if __name__ == "__main__":
    main()
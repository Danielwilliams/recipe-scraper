#!/usr/bin/env python3
"""
Recipe Image Updater - Direct Web Scraping Approach

This script updates missing image URLs for recipes by directly scraping the source URLs
regardless of the source website. It uses a generic approach to find the largest/most prominent
image on the recipe page.

Usage:
    python update_recipe_images.py [--limit N]
"""

import os
import sys
import argparse
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import random
from psycopg2.extras import RealDictCursor
from database.db_connector import get_db_connection
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_updates.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_image_updater")

# User agents for rotating
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def get_random_user_agent():
    """Get a random user agent from the list"""
    return random.choice(USER_AGENTS)

def get_recipes_missing_images(limit=None):
    """Get recipes that don't have an image URL"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT id, title, source, source_url
                FROM scraped_recipes
                WHERE (image_url IS NULL OR image_url = '')
                  AND source_url IS NOT NULL
                  AND source_url != ''
                ORDER BY id
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            recipes = cursor.fetchall()
            
            logger.info(f"Found {len(recipes)} recipes missing images")
            return recipes
    except Exception as e:
        logger.error(f"Error getting recipes: {str(e)}")
        return []
    finally:
        conn.close()

def find_largest_image(soup, base_url):
    """Find the largest image in the page that's likely to be the recipe image"""
    images = soup.find_all('img')
    
    # Filter out small icons, tracking pixels, etc.
    valid_images = []
    for img in images:
        # Skip images without src
        if not img.get('src'):
            continue
            
        # Skip tiny images and svg icons
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                w, h = int(width), int(height)
                if w < 200 or h < 200:  # Skip small images
                    continue
            except ValueError:
                pass  # Couldn't parse dimensions, keep the image
                
        # Skip common icon patterns
        src = img.get('src', '')
        if any(pattern in src.lower() for pattern in ['icon', 'logo', 'avatar', 'banner', 'ad-']):
            continue
            
        # Make relative URLs absolute
        img_url = urljoin(base_url, img.get('src'))
        valid_images.append({
            'url': img_url,
            'width': img.get('width'),
            'height': img.get('height'),
            'alt': img.get('alt', ''),
            'img': img
        })
    
    # No valid images found
    if not valid_images:
        return None
        
    # Try to find the recipe image by:
    # 1. Images with recipe-related alt text
    for img in valid_images:
        alt_text = img.get('alt', '').lower()
        if alt_text and any(term in alt_text for term in ['recipe', 'dish', 'food', 'meal']):
            return img['url']
    
    # 2. Find images that are near recipe-related content
    for img in valid_images:
        parent = img['img'].parent
        if parent:
            parent_text = parent.get_text().lower()
            if any(term in parent_text for term in ['recipe', 'ingredients', 'instructions', 'cook']):
                return img['url']
    
    # 3. Just use the largest image that's likely in the content area
    content_areas = soup.select('article, main, .content, .post, .recipe')
    if content_areas:
        # Look for images in content areas
        for area in content_areas:
            area_images = area.find_all('img')
            if area_images:
                for img in area_images:
                    if img.get('src'):
                        return urljoin(base_url, img.get('src'))
    
    # 4. Fall back to the first valid image
    return valid_images[0]['url']

def find_structured_data_image(soup):
    """Extract image URL from structured data (JSON-LD or microdata)"""
    # Try JSON-LD first
    json_ld = soup.find('script', {'type': 'application/ld+json'})
    if json_ld:
        try:
            import json
            data = json.loads(json_ld.string)
            
            # Handle array of structured data
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') in ['Recipe', 'Article', 'WebPage']:
                        if item.get('image'):
                            if isinstance(item['image'], dict) and item['image'].get('url'):
                                return item['image']['url']
                            elif isinstance(item['image'], str):
                                return item['image']
                            elif isinstance(item['image'], list) and len(item['image']) > 0:
                                if isinstance(item['image'][0], str):
                                    return item['image'][0]
                                elif isinstance(item['image'][0], dict) and item['image'][0].get('url'):
                                    return item['image'][0]['url']
            
            # Handle single structured data object
            elif isinstance(data, dict):
                if data.get('@type') in ['Recipe', 'Article', 'WebPage']:
                    if data.get('image'):
                        if isinstance(data['image'], dict) and data['image'].get('url'):
                            return data['image']['url']
                        elif isinstance(data['image'], str):
                            return data['image']
                        elif isinstance(data['image'], list) and len(data['image']) > 0:
                            if isinstance(data['image'][0], str):
                                return data['image'][0]
                            elif isinstance(data['image'][0], dict) and data['image'][0].get('url'):
                                return data['image'][0]['url']
        except Exception as e:
            logger.warning(f"Error parsing JSON-LD: {str(e)}")
    
    # Try OpenGraph (og:image)
    og_image = soup.find('meta', {'property': 'og:image'})
    if og_image and og_image.get('content'):
        return og_image.get('content')
    
    # Try Twitter Card
    twitter_image = soup.find('meta', {'name': 'twitter:image'})
    if twitter_image and twitter_image.get('content'):
        return twitter_image.get('content')
    
    return None

def scrape_image_url(recipe):
    """Scrape the recipe page to find the main image"""
    url = recipe['source_url']
    
    try:
        # Prepare headers with random user agent
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Request the page
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to access URL: {url}, Status: {response.status_code}")
            return None
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # First try to find image in structured data
        image_url = find_structured_data_image(soup)
        
        # If not found, look for the largest/most prominent image
        if not image_url:
            image_url = find_largest_image(soup, url)
        
        if image_url:
            logger.info(f"Found image for '{recipe['title']}': {image_url}")
            return image_url
        else:
            logger.warning(f"Could not find any suitable image for '{recipe['title']}'")
            return None
            
    except Exception as e:
        logger.error(f"Error scraping image for '{recipe['title']}': {str(e)}")
        return None

def update_recipe_image(recipe_id, image_url):
    """Update the image URL for a recipe in the database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE scraped_recipes
                SET image_url = %s
                WHERE id = %s
            """, (image_url, recipe_id))
            
            conn.commit()
            logger.info(f"Updated image for recipe ID {recipe_id}")
            return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating recipe {recipe_id}: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Update missing recipe images using direct web scraping")
    parser.add_argument("--limit", type=int, help="Limit the number of recipes to process")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests in seconds (default: 2.0)")
    args = parser.parse_args()
    
    # Get recipes missing images
    recipes = get_recipes_missing_images(args.limit)
    
    if not recipes:
        logger.info("No recipes missing images found")
        return
        
    # Process each recipe
    total = len(recipes)
    success_count = 0
    failed_count = 0
    
    for i, recipe in enumerate(recipes):
        logger.info(f"Processing recipe {i+1}/{total}: {recipe['title']} ({recipe['source']})")
        
        try:
            # Find image URL
            image_url = scrape_image_url(recipe)
            
            if image_url:
                # Update the database
                if update_recipe_image(recipe['id'], image_url):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
                
            # Be polite to the servers
            time.sleep(args.delay)
            
        except Exception as e:
            logger.error(f"Error processing recipe {recipe['id']}: {str(e)}")
            failed_count += 1
    
    # Output summary
    logger.info(f"Update complete. Total: {total}, Success: {success_count}, Failed: {failed_count}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Download Recipe Images from Source URLs

This script fetches recipes from the database, visits their source URLs,
extracts the main recipe image, and saves it locally with the recipe name as filename.

Usage:
    python download_recipe_images.py [--limit N] [--output-dir DIR] [--recipe-ids ID1,ID2,...]
"""

import os
import sys
import re
import logging
import argparse
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
from database.db_connector import get_db_connection
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("download_images.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_image_downloader")

# Headers to appear more like a regular browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def sanitize_filename(filename):
    """Sanitize filename to be filesystem-safe"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    filename = re.sub(r'\s+', ' ', filename)
    # Trim to reasonable length
    filename = filename[:100]
    return filename.strip()

def get_recipes(limit=None, recipe_ids=None):
    """Get recipes with source URLs from database"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            if recipe_ids:
                # Get specific recipes by ID
                query = """
                    SELECT id, title, source_url, image_url
                    FROM scraped_recipes
                    WHERE id = ANY(%s)
                    AND source_url IS NOT NULL
                    ORDER BY id
                """
                cursor.execute(query, (recipe_ids,))
            else:
                # Get all recipes with source URLs
                query = """
                    SELECT id, title, source_url, image_url
                    FROM scraped_recipes
                    WHERE source_url IS NOT NULL
                    ORDER BY id
                """
                if limit:
                    query += f" LIMIT {limit}"
                cursor.execute(query)
            
            recipes = cursor.fetchall()
            logger.info(f"Found {len(recipes)} recipes to process")
            return recipes
    except Exception as e:
        logger.error(f"Error getting recipes: {str(e)}")
        return []
    finally:
        conn.close()

def extract_image_from_url(url):
    """Extract the main recipe image from a recipe URL"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try various methods to find the recipe image
        image_url = None
        
        # Method 1: Look for Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image['content']
            logger.debug(f"Found OG image: {image_url}")
        
        # Method 2: Look for Twitter card image
        if not image_url:
            twitter_image = soup.find('meta', {'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                logger.debug(f"Found Twitter image: {image_url}")
        
        # Method 3: Look for structured data (JSON-LD)
        if not image_url:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Check for Recipe schema
                        if data.get('@type') == 'Recipe' and data.get('image'):
                            if isinstance(data['image'], str):
                                image_url = data['image']
                            elif isinstance(data['image'], dict) and data['image'].get('url'):
                                image_url = data['image']['url']
                            elif isinstance(data['image'], list) and data['image']:
                                image_url = data['image'][0] if isinstance(data['image'][0], str) else data['image'][0].get('url')
                            if image_url:
                                logger.debug(f"Found JSON-LD image: {image_url}")
                                break
                except:
                    pass
        
        # Method 4: Look for recipe-specific image classes/IDs
        if not image_url:
            # Common recipe image selectors
            selectors = [
                'img.recipe-image',
                'img.recipe-photo',
                'img[itemprop="image"]',
                '.recipe-header img',
                '.recipe-image img',
                '.recipe-hero img',
                'figure.recipe-image img',
                'div.recipe-image img'
            ]
            
            for selector in selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    image_url = img['src']
                    logger.debug(f"Found image with selector '{selector}': {image_url}")
                    break
        
        # Make sure URL is absolute
        if image_url:
            image_url = urljoin(url, image_url)
            
        return image_url
        
    except Exception as e:
        logger.error(f"Error extracting image from {url}: {str(e)}")
        return None

def download_image(image_url, filepath):
    """Download an image from URL and save to filepath"""
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=15, stream=True)
        response.raise_for_status()
        
        # Check if it's actually an image
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"URL does not return an image: {content_type}")
            return False
        
        # Save the image
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded image to: {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading image from {image_url}: {str(e)}")
        return False

def update_recipe_image_url(recipe_id, image_url):
    """Update the image_url field in the database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE scraped_recipes
                SET image_url = %s
                WHERE id = %s
            """, (image_url, recipe_id))
            conn.commit()
            logger.info(f"Updated image_url for recipe ID {recipe_id}")
            return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating recipe {recipe_id}: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Download recipe images from source URLs")
    parser.add_argument("--limit", type=int, help="Limit the number of recipes to process")
    parser.add_argument("--output-dir", default="recipe_images", help="Directory to save images")
    parser.add_argument("--recipe-ids", help="Comma-separated list of specific recipe IDs to process")
    parser.add_argument("--update-db", action="store_true", help="Update database with downloaded image URLs")
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Parse recipe IDs if provided
    recipe_ids = None
    if args.recipe_ids:
        recipe_ids = [int(id.strip()) for id in args.recipe_ids.split(',')]
    
    # Get recipes to process
    recipes = get_recipes(args.limit, recipe_ids)
    
    if not recipes:
        logger.info("No recipes found to process")
        return
    
    # Process each recipe
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for recipe in recipes:
        recipe_id = recipe['id']
        title = recipe['title']
        source_url = recipe['source_url']
        existing_image_url = recipe.get('image_url')
        
        logger.info(f"\nProcessing recipe {recipe_id}: {title}")
        
        # Skip if already has an image URL and we're not forcing
        if existing_image_url:
            logger.info(f"Recipe already has image URL: {existing_image_url}")
            skip_count += 1
            continue
        
        # Extract image URL from source
        logger.info(f"Fetching from: {source_url}")
        image_url = extract_image_from_url(source_url)
        
        if not image_url:
            logger.warning(f"Could not find image for recipe {recipe_id}")
            fail_count += 1
            continue
        
        # Prepare filename
        safe_title = sanitize_filename(title)
        extension = os.path.splitext(urlparse(image_url).path)[1] or '.jpg'
        filename = f"{recipe_id}_{safe_title}{extension}"
        filepath = os.path.join(args.output_dir, filename)
        
        # Download the image
        if download_image(image_url, filepath):
            success_count += 1
            
            # Update database if requested
            if args.update_db:
                update_recipe_image_url(recipe_id, image_url)
        else:
            fail_count += 1
    
    # Summary
    logger.info(f"\nProcessing complete!")
    logger.info(f"Successful downloads: {success_count}")
    logger.info(f"Skipped (already have images): {skip_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Images saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
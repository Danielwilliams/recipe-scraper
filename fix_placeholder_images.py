#!/usr/bin/env python3
"""
Fix Placeholder SVG Image URLs

This script identifies and updates recipes in the database that have placeholder
SVG data URLs (like 'data:image/svg+xml...') as their image URLs. It attempts to
find proper images for these recipes using various methods.

Usage:
    python fix_placeholder_images.py [--limit N] [--dry-run]
"""

import os
import sys
import json
import logging
import argparse
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import config
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fix_placeholder_images.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("placeholder_image_fixer")

# Constants
PLACEHOLDER_PATTERNS = [
    'data:image/svg+xml',
    'data:image/svg',
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
    'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
]

FALLBACK_IMAGE_URL = "https://via.placeholder.com/500x500.png?text=No+Image+Available"

# Headers for web requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_recipes_with_placeholder_images(limit=None):
    """Get recipes that have placeholder SVG/data URLs as image URLs"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build query to find recipes with placeholder images
            placeholder_conditions = []
            for pattern in PLACEHOLDER_PATTERNS:
                placeholder_conditions.append(f"r.image_url LIKE '{pattern}%'")
            
            where_clause = f"({' OR '.join(placeholder_conditions)})"
            
            query = f"""
                SELECT r.id, r.title, r.source, r.source_url, r.image_url,
                       (SELECT string_agg(name, ', ') FROM 
                          (SELECT ri.name FROM recipe_ingredients ri 
                           WHERE ri.recipe_id = r.id 
                           ORDER BY ri.id 
                           LIMIT 3) AS top_ingredients
                       ) as main_ingredients
                FROM scraped_recipes r
                WHERE {where_clause}
                ORDER BY r.id
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            recipes = cursor.fetchall()
            
            logger.info(f"Found {len(recipes)} recipes with placeholder images")
            return recipes
    except Exception as e:
        logger.error(f"Error getting recipes: {str(e)}")
        return []
    finally:
        conn.close()

def extract_image_from_source_url(url):
    """Extract the main recipe image from a recipe's source URL"""
    if not url:
        return None
        
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
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe' and item.get('image'):
                                if isinstance(item['image'], str):
                                    image_url = item['image']
                                elif isinstance(item['image'], dict) and item['image'].get('url'):
                                    image_url = item['image']['url']
                                elif isinstance(item['image'], list) and item['image']:
                                    image_url = item['image'][0] if isinstance(item['image'][0], str) else item['image'][0].get('url')
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
                'div.recipe-image img',
                '.tasty-recipes-image img',
                '.wprm-recipe-image img'
            ]
            
            for selector in selectors:
                img = soup.select_one(selector)
                if img and img.get('src'):
                    image_url = img['src']
                    # Skip if it's another placeholder
                    if not any(pattern in image_url for pattern in PLACEHOLDER_PATTERNS):
                        logger.debug(f"Found image with selector '{selector}': {image_url}")
                        break
                    else:
                        image_url = None
        
        # Make sure URL is absolute and not a placeholder
        if image_url:
            image_url = urljoin(url, image_url)
            # Check if it's still a placeholder
            if any(pattern in image_url for pattern in PLACEHOLDER_PATTERNS):
                return None
            
        return image_url
        
    except Exception as e:
        logger.error(f"Error extracting image from {url}: {str(e)}")
        return None

def validate_image_url(image_url):
    """Validate that an image URL actually returns an image"""
    if not image_url:
        return False
        
    try:
        # Skip if it's a placeholder
        if any(pattern in image_url for pattern in PLACEHOLDER_PATTERNS):
            return False
            
        # Make a HEAD request to check content type
        response = requests.head(image_url, headers=HEADERS, timeout=5, allow_redirects=True)
        content_type = response.headers.get('content-type', '')
        
        # Check if it's an image
        return content_type.startswith('image/')
        
    except Exception as e:
        logger.debug(f"Error validating image URL {image_url}: {str(e)}")
        return False

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
            logger.info(f"Updated image for recipe ID {recipe_id} to: {image_url}")
            return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating recipe {recipe_id}: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Fix placeholder SVG image URLs in recipes")
    parser.add_argument("--limit", type=int, help="Limit the number of recipes to process")
    parser.add_argument("--dry-run", action="store_true", help="Run without updating the database")
    args = parser.parse_args()
    
    # Get recipes with placeholder images
    recipes = get_recipes_with_placeholder_images(args.limit)
    
    if not recipes:
        logger.info("No recipes with placeholder images found")
        return
        
    # Process each recipe
    total = len(recipes)
    success = 0
    failed = 0
    no_source = 0
    
    for i, recipe in enumerate(recipes):
        logger.info(f"\nProcessing recipe {i+1}/{total}: {recipe['title']} (ID: {recipe['id']})")
        logger.info(f"Current image URL: {recipe['image_url'][:100]}...")
        
        # Skip if no source URL
        if not recipe.get('source_url'):
            logger.warning("No source URL available for this recipe")
            no_source += 1
            continue
            
        try:
            # Try to extract image from source URL
            logger.info(f"Fetching from source: {recipe['source_url']}")
            new_image_url = extract_image_from_source_url(recipe['source_url'])
            
            if new_image_url:
                # Validate the image URL
                if validate_image_url(new_image_url):
                    logger.info(f"✅ Found valid image: {new_image_url}")
                    
                    # Update the database unless dry run
                    if not args.dry_run:
                        if update_recipe_image(recipe['id'], new_image_url):
                            success += 1
                        else:
                            failed += 1
                    else:
                        logger.info("(DRY RUN - not updating database)")
                        success += 1
                else:
                    logger.warning("Found image URL but it's not valid")
                    # Use fallback image
                    if not args.dry_run:
                        if update_recipe_image(recipe['id'], FALLBACK_IMAGE_URL):
                            success += 1
                        else:
                            failed += 1
                    else:
                        logger.info(f"(DRY RUN - would use fallback: {FALLBACK_IMAGE_URL})")
                        success += 1
            else:
                logger.warning("Could not find image from source")
                # Use fallback image
                if not args.dry_run:
                    if update_recipe_image(recipe['id'], FALLBACK_IMAGE_URL):
                        success += 1
                    else:
                        failed += 1
                else:
                    logger.info(f"(DRY RUN - would use fallback: {FALLBACK_IMAGE_URL})")
                    success += 1
                    
        except Exception as e:
            logger.error(f"Error processing recipe {recipe['id']}: {str(e)}")
            failed += 1
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    logger.info(f"Total recipes processed: {total}")
    logger.info(f"Successfully updated: {success}")
    logger.info(f"Failed to update: {failed}")
    logger.info(f"No source URL: {no_source}")
    
    if args.dry_run:
        logger.info("\n(This was a DRY RUN - no database changes were made)")

if __name__ == "__main__":
    main()
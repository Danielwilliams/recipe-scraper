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
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_updates.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_image_updater")

# Set to True to enable detailed debug info about image selection
DEBUG_IMAGE_SELECTION = os.environ.get('DEBUG_IMAGE_SELECTION', 'False').lower() == 'true'
if DEBUG_IMAGE_SELECTION and LOG_LEVEL != 'DEBUG':
    logger.setLevel(logging.DEBUG)
    logger.info("Debug image selection enabled")

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

def get_recipes_missing_images(limit=None, recipe_id=None):
    """
    Get recipes that don't have an image URL

    Args:
        limit (int, optional): Limit the number of recipes to return
        recipe_id (int, optional): If specified, only return this specific recipe

    Returns:
        list: Recipes missing images
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            if recipe_id:
                # If a specific recipe ID is requested, get it regardless of image status
                query = """
                    SELECT id, title, source, source_url
                    FROM scraped_recipes
                    WHERE id = %s AND source_url IS NOT NULL AND source_url != ''
                """
                cursor.execute(query, (recipe_id,))
            else:
                # Otherwise get recipes missing images
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

            if recipe_id:
                logger.info(f"Found recipe with ID {recipe_id}: {len(recipes) > 0}")
            else:
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
    excluded_count = 0

    for img in images:
        # Skip images without src
        if not img.get('src'):
            excluded_count += 1
            continue

        # Skip tiny images and svg icons
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                w, h = int(width), int(height)
                if w < 200 or h < 200:  # Skip small images
                    excluded_count += 1
                    continue
            except ValueError:
                pass  # Couldn't parse dimensions, keep the image for now

        # Make relative URLs absolute
        src = img.get('src', '')
        img_url = urljoin(base_url, src)

        # Check for logo/icon patterns in src, alt, class, and id attributes
        alt_text = img.get('alt', '').lower()
        img_class = ' '.join(img.get('class', [])).lower()
        img_id = img.get('id', '').lower()

        # List of patterns that suggest the image is a logo, icon, or advertisement
        logo_patterns = [
            'logo', 'icon', 'avatar', 'banner', 'ad-', 'advertisement',
            'sponsor', 'profile', 'badge', 'flag', 'social', 'facebook',
            'twitter', 'instagram', 'pinterest', 'mail', 'email', 'nav-',
            'header-', 'footer-', 'thumb', 'favicon', 'brand'
        ]

        # Check if any pattern appears in any attribute
        if any(pattern in src.lower() for pattern in logo_patterns) or \
           any(pattern in alt_text for pattern in logo_patterns) or \
           any(pattern in img_class for pattern in logo_patterns) or \
           any(pattern in img_id for pattern in logo_patterns):
            excluded_count += 1
            continue

        # Look for alt text that explicitly indicates it's a logo
        if alt_text and ('logo' in alt_text or 'site' in alt_text or 'brand' in alt_text):
            excluded_count += 1
            continue

        # Add to valid images
        valid_images.append({
            'url': img_url,
            'width': width,
            'height': height,
            'alt': alt_text,
            'class': img_class,
            'id': img_id,
            'img': img,
            'src': src
        })

    logger.debug(f"Found {len(valid_images)} valid images (excluded {excluded_count})")

    # No valid images found
    if not valid_images:
        return None

    # Score images based on multiple factors (higher score = more likely to be recipe image)
    scored_images = []
    for img in valid_images:
        score = 0

        # 1. Score based on alt text
        alt_text = img['alt']
        if alt_text:
            # Positive signals in alt text
            if any(term in alt_text for term in ['recipe', 'dish', 'food', 'meal', 'dinner', 'lunch', 'breakfast']):
                score += 5
            if any(term in alt_text for term in ['homemade', 'delicious', 'tasty', 'healthy', 'cooked']):
                score += 3

        # 2. Score based on context
        parent = img['img'].parent
        if parent:
            parent_text = parent.get_text().lower()
            if any(term in parent_text for term in ['recipe', 'ingredients', 'instructions', 'cook']):
                score += 4
            if any(term in parent_text for term in ['minutes', 'servings', 'yield', 'prep']):
                score += 3

        # 3. Score based on image file name
        if any(term in img['src'].lower() for term in ['recipe', 'dish', 'food', 'meal', '-final', 'hero']):
            score += 3

        # 4. Score based on position in content area
        content_areas = soup.select('article, main, .content, .post, .recipe, [itemprop="recipeInstructions"]')
        for area in content_areas:
            if img['img'] in area.find_all('img'):
                score += 4
                break

        # 5. Score based on image dimensions (larger is better)
        if img['width'] and img['height']:
            try:
                w, h = int(img['width']), int(img['height'])
                # Prefer landscape-oriented images with reasonable aspect ratio (typical for food photos)
                if 0.5 <= w/h <= 2.0:  # Aspect ratio between 1:2 and 2:1
                    score += 2
                # Prefer large images
                if w >= 400 and h >= 300:
                    score += 2
            except (ValueError, ZeroDivisionError):
                pass

        scored_images.append((score, img))

    # Sort images by score (highest first)
    scored_images.sort(reverse=True, key=lambda x: x[0])

    # Return the URL of the highest scored image
    if scored_images:
        best_image = scored_images[0][1]
        logger.debug(f"Selected best image with score {scored_images[0][0]}: {best_image['url']}")
        return best_image['url']

    # Fallback: if scoring didn't work, try the content area approach
    content_areas = soup.select('article, main, .content, .post, .recipe')
    if content_areas:
        for area in content_areas:
            area_images = area.find_all('img')
            if area_images:
                for img in area_images:
                    if img.get('src'):
                        img_url = urljoin(base_url, img.get('src'))
                        logger.debug(f"Fallback to content area image: {img_url}")
                        return img_url

    # Last resort: first valid image
    if valid_images:
        logger.debug(f"Fallback to first valid image: {valid_images[0]['url']}")
        return valid_images[0]['url']

    return None

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
    recipe_id = recipe['id']
    recipe_title = recipe['title']
    source = recipe['source']

    logger.info(f"Scraping image for recipe {recipe_id}: '{recipe_title}' from {source}")
    logger.debug(f"Source URL: {url}")

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
            'Cache-Control': 'no-cache',
        }

        # Request the page
        logger.debug(f"Requesting page: {url}")
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"Failed to access URL: {url}, Status: {response.status_code}")
            return None

        logger.debug(f"Successfully retrieved page, size: {len(response.text)} bytes")

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Log some basic page info for debugging
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            logger.debug(f"Page title: {title_tag.string.strip()}")

        # First try to find image in structured data (most reliable)
        logger.debug("Looking for image in structured data...")
        image_url = find_structured_data_image(soup)

        if image_url:
            logger.info(f"Found image in structured data for '{recipe_title}': {image_url}")
            return image_url

        # Try common recipe site image patterns
        logger.debug("Looking for image using common recipe site patterns...")

        # Check for schema.org recipe markup
        recipe_image = soup.select_one('[itemprop="image"], [property="og:image"], [name="twitter:image"]')
        if recipe_image and recipe_image.get('content'):
            image_url = recipe_image.get('content')
            logger.info(f"Found image using schema.org markup for '{recipe_title}': {image_url}")
            return urljoin(url, image_url)
        elif recipe_image and recipe_image.get('src'):
            image_url = recipe_image.get('src')
            logger.info(f"Found image using schema.org markup for '{recipe_title}': {image_url}")
            return urljoin(url, image_url)

        # Try recipe-specific containers that are common across sites
        for selector in ['.recipe-image', '.hero-photo', '.featured-image', '.post-thumbnail', '.entry-image', '.recipe-header-image']:
            container = soup.select_one(selector)
            if container:
                img = container.find('img')
                if img and img.get('src'):
                    image_url = img.get('src')
                    logger.info(f"Found image in container '{selector}' for '{recipe_title}': {image_url}")
                    return urljoin(url, image_url)

        # If not found, look for the largest/most prominent image
        logger.debug("Looking for largest/most prominent image...")
        image_url = find_largest_image(soup, url)

        if image_url:
            logger.info(f"Found image using image analysis for '{recipe_title}': {image_url}")
            return image_url
        else:
            logger.warning(f"Could not find any suitable image for '{recipe_title}'")
            return None

    except Exception as e:
        logger.error(f"Error scraping image for '{recipe_title}': {str(e)}")
        if DEBUG_IMAGE_SELECTION:
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
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
    parser.add_argument("--recipe-id", type=int, help="Update image for a specific recipe ID")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests in seconds (default: 2.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging for image selection")
    parser.add_argument("--force", action="store_true", help="Force update even if recipe already has an image")
    args = parser.parse_args()

    # Set debug mode if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        global DEBUG_IMAGE_SELECTION
        DEBUG_IMAGE_SELECTION = True
        logger.info("Debug mode enabled")

    # Get recipes missing images
    recipes = get_recipes_missing_images(args.limit, args.recipe_id)

    if not recipes:
        logger.info("No recipes found to update")
        return

    # Process each recipe
    total = len(recipes)
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for i, recipe in enumerate(recipes):
        logger.info(f"Processing recipe {i+1}/{total}: {recipe['title']} ({recipe['source']})")

        try:
            # Check if we should force update existing images
            if not args.force:
                # Check if recipe already has an image
                conn = get_db_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT image_url FROM scraped_recipes
                            WHERE id = %s AND image_url IS NOT NULL AND image_url != ''
                        """, (recipe['id'],))
                        existing_image = cursor.fetchone()
                        if existing_image:
                            logger.info(f"Recipe {recipe['id']} already has an image: {existing_image[0]}")
                            logger.info(f"Skipping (use --force to override)")
                            skipped_count += 1
                            continue
                finally:
                    conn.close()

            # Find image URL
            image_url = scrape_image_url(recipe)

            if image_url:
                # Update the database
                if update_recipe_image(recipe['id'], image_url):
                    success_count += 1
                    logger.info(f"✅ Successfully updated image for recipe {recipe['id']}")
                else:
                    failed_count += 1
                    logger.error(f"❌ Failed to update database for recipe {recipe['id']}")
            else:
                failed_count += 1
                logger.error(f"❌ Failed to find image for recipe {recipe['id']}")

            # Be polite to the servers
            if i < total - 1:  # Don't sleep after the last recipe
                logger.debug(f"Sleeping for {args.delay} seconds...")
                time.sleep(args.delay)

        except Exception as e:
            logger.error(f"Error processing recipe {recipe['id']}: {str(e)}")
            if DEBUG_IMAGE_SELECTION:
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
            failed_count += 1

    # Output summary
    logger.info("=" * 50)
    logger.info(f"Update complete:")
    logger.info(f"- Total recipes processed: {total}")
    logger.info(f"- Successfully updated: {success_count}")
    logger.info(f"- Failed to update: {failed_count}")
    logger.info(f"- Skipped (already had images): {skipped_count}")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
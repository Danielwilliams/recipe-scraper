#!/usr/bin/env python3
"""
Image Finder for Recipes

This script finds images for recipes that don't have an image URL.
It can either update recipes directly in the database or output a JSON file with 
recipe IDs and corresponding image URLs.

Usage:
    python find_recipe_images.py [--output-json filename.json] [--update-db] [--limit N]
"""

import os
import sys
import json
import logging
import argparse
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import config
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_finder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_image_finder")

# Constants
FALLBACK_IMAGE_URL = "https://via.placeholder.com/500x500.png?text=No+Image+Available"
UNSPLASH_API_KEY = os.environ.get('UNSPLASH_API_KEY')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY')

def get_recipes_missing_images(limit=None):
    """Get recipes that don't have an image URL"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Modified query to be compatible with more PostgreSQL versions
            query = """
                SELECT r.id, r.title, 
                       (SELECT string_agg(name, ', ') FROM 
                          (SELECT ri.name FROM recipe_ingredients ri 
                           WHERE ri.recipe_id = r.id 
                           ORDER BY ri.id 
                           LIMIT 3) AS top_ingredients
                       ) as main_ingredients
                FROM scraped_recipes r
                WHERE (r.image_url IS NULL OR r.image_url = '')
                ORDER BY r.id
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

def search_image_unsplash(query):
    """Search for an image using Unsplash API"""
    if not UNSPLASH_API_KEY:
        logger.warning("Unsplash API key not found")
        return None
        
    try:
        # Query the API
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": f"{query} food recipe",
            "per_page": 1,
            "orientation": "landscape",
            "content_filter": "high"
        }
        headers = {"Authorization": f"Client-ID {UNSPLASH_API_KEY}"}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if results and len(results) > 0:
                image_url = results[0].get("urls", {}).get("regular")
                if image_url:
                    return image_url
                    
        logger.warning(f"Failed to get image from Unsplash: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error searching Unsplash: {str(e)}")
        return None

def search_image_pexels(query):
    """Search for an image using Pexels API"""
    if not PEXELS_API_KEY:
        logger.warning("Pexels API key not found")
        return None
        
    try:
        # Query the API
        url = "https://api.pexels.com/v1/search"
        params = {
            "query": f"{query} food",
            "per_page": 1,
            "orientation": "landscape"
        }
        headers = {"Authorization": PEXELS_API_KEY}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", [])
            
            if photos and len(photos) > 0:
                image_url = photos[0].get("src", {}).get("large")
                if image_url:
                    return image_url
                    
        logger.warning(f"Failed to get image from Pexels: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error searching Pexels: {str(e)}")
        return None

def search_image(recipe):
    """Search for an image using available APIs"""
    title = recipe['title']
    main_ingredients = recipe.get('main_ingredients', '')
    
    # Check if we have any API keys
    if not UNSPLASH_API_KEY and not PEXELS_API_KEY:
        logger.warning("No image API keys available. Using fallback image.")
        return FALLBACK_IMAGE_URL
    
    # Prepare search query
    if main_ingredients:
        query = f"{title} {main_ingredients}"
    else:
        query = title
        
    # Try Unsplash first if key is available
    image_url = None
    if UNSPLASH_API_KEY:
        image_url = search_image_unsplash(query)
    
    # If Unsplash failed, try Pexels if key is available
    if not image_url and PEXELS_API_KEY:
        image_url = search_image_pexels(query)
        
    # If both failed or no keys available, use fallback
    if not image_url:
        image_url = FALLBACK_IMAGE_URL
        
    return image_url

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
    parser = argparse.ArgumentParser(description="Find images for recipes without image URLs")
    parser.add_argument("--output-json", help="Output file for JSON results")
    parser.add_argument("--update-db", action="store_true", help="Update the database with found images")
    parser.add_argument("--limit", type=int, help="Limit the number of recipes to process")
    args = parser.parse_args()
    
    # Validate arguments
    if not args.output_json and not args.update_db:
        logger.error("You must specify either --output-json or --update-db (or both)")
        sys.exit(1)
        
    # Get recipes missing images
    recipes = get_recipes_missing_images(args.limit)
    
    if not recipes:
        logger.info("No recipes missing images found")
        return
        
    # Find images for each recipe
    results = []
    total = len(recipes)
    success = 0
    
    for i, recipe in enumerate(recipes):
        logger.info(f"Processing recipe {i+1}/{total}: {recipe['title']}")
        
        try:
            # Find an image
            image_url = search_image(recipe)
            
            # Update the database if requested
            if args.update_db:
                if update_recipe_image(recipe['id'], image_url):
                    success += 1
                    
            # Add to results
            results.append({
                "id": recipe['id'],
                "title": recipe['title'],
                "image_url": image_url
            })
            
        except Exception as e:
            logger.error(f"Error processing recipe {recipe['id']}: {str(e)}")
            
    # Output summary
    logger.info(f"Processed {total} recipes, {success} updated successfully")
    
    # Save to JSON if requested
    if args.output_json:
        try:
            with open(args.output_json, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Saved results to {args.output_json}")
        except Exception as e:
            logger.error(f"Error saving to JSON: {str(e)}")

if __name__ == "__main__":
    main()
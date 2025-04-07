#!/usr/bin/env python3
"""
Import Tagged Recipes

This script imports recipes with tags from a JSON file into the Smart Meal Planner database.
It assumes the recipes already have tags generated using Claude.ai or Claude Console.

Usage:
    python import_tagged_recipes.py --input data/FB_Recipes_tagged.json [--dry-run]
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import config
from database.db_connector import get_db_connection

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("recipe_import.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_importer")

def load_recipes(filename):
    """Load recipes from JSON file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Check if file starts with a comma (invalid JSON)
            content = f.read()
            if content.strip().startswith(','):
                content = '[' + content + ']'
                recipes = json.loads(content)
            else:
                recipes = json.loads(content)
                
            # If recipes is not a list, wrap it in a list
            if not isinstance(recipes, list):
                recipes = [recipes]
                
        logger.info(f"Loaded {len(recipes)} recipes from {filename}")
        return recipes
    except Exception as e:
        logger.error(f"Error loading recipes from {filename}: {str(e)}")
        return []

def validate_recipe(recipe):
    """Validate recipe has all required fields"""
    required_fields = ['title', 'ingredients', 'instructions']
    for field in required_fields:
        if field not in recipe or not recipe[field]:
            logger.warning(f"Recipe missing required field: {field}")
            return False
    
    # Ensure tags exist
    if 'tags' not in recipe or not recipe['tags']:
        logger.warning(f"Recipe missing tags: {recipe.get('title', 'Unknown')}")
        return False
    
    # Add facebook tag if not present
    if 'facebook' not in recipe['tags']:
        recipe['tags'].append('facebook')
    
    return True

def import_recipe(recipe, dry_run=False):
    """Import recipe into database"""
    if not validate_recipe(recipe):
        return None
    
    if dry_run:
        logger.info(f"[DRY RUN] Would import: {recipe['title']}")
        return "dry-run-id"
    
    conn = get_db_connection()
    try:
        # Check if recipe already exists
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM scraped_recipes
                WHERE title = %s AND source = %s
                LIMIT 1
            """, (recipe['title'], recipe.get('source', 'Facebook')))
            
            existing = cursor.fetchone()
            if existing:
                logger.info(f"Recipe already exists: {recipe['title']}")
                return existing[0]
        
        # Prepare to insert the recipe
        title = recipe['title']
        source = recipe.get('source', 'Facebook')
        source_url = recipe.get('source_url', '')
        instructions = json.dumps(recipe.get('instructions', []))
        date_scraped = datetime.now()
        date_processed = datetime.now()
        complexity = recipe.get('complexity', 'medium')
        
        # Extract metadata
        metadata = recipe.get('metadata', {})
        prep_time = metadata.get('prep_time')
        cook_time = metadata.get('cook_time')
        total_time = metadata.get('total_time')
        servings = metadata.get('servings')
        cuisine = metadata.get('cuisine')
        
        # Other fields
        is_verified = True
        raw_content = recipe.get('raw_content', '')[:5000]  # Limit to 5000 chars
        image_url = recipe.get('image_url', '')
        
        with conn.cursor() as cursor:
            # Insert recipe
            cursor.execute("""
                INSERT INTO scraped_recipes (
                    title, source, source_url, instructions, date_scraped, date_processed,
                    complexity, prep_time, cook_time, total_time, servings, cuisine,
                    is_verified, raw_content, metadata, image_url
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """, (
                title, source, source_url, instructions, date_scraped, date_processed,
                complexity, prep_time, cook_time, total_time, servings, cuisine,
                is_verified, raw_content, json.dumps(metadata), image_url
            ))
            
            recipe_id = cursor.fetchone()[0]
            
            # Insert ingredients
            if 'ingredients' in recipe and recipe['ingredients']:
                for ing in recipe['ingredients']:
                    cursor.execute("""
                        INSERT INTO recipe_ingredients
                        (recipe_id, name, category)
                        VALUES (%s, %s, %s)
                    """, (
                        recipe_id,
                        str(ing)[:100],  # Truncate if too long
                        'unknown'
                    ))
            
            # Insert nutrition if available
            nutrition = recipe.get('nutrition', {})
            if nutrition:
                cursor.execute("""
                    INSERT INTO recipe_nutrition
                    (recipe_id, calories, protein, carbs, fat, fiber, sugar, sodium, is_calculated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    recipe_id,
                    nutrition.get('calories'),
                    nutrition.get('protein'),
                    nutrition.get('carbs'),
                    nutrition.get('fat'),
                    nutrition.get('fiber'),
                    nutrition.get('sugar'),
                    nutrition.get('sodium'),
                    True  # Mark as calculated
                ))
                
                # Add per-serving and per-meal nutrition to metadata if available
                if nutrition.get('per_serving') or nutrition.get('per_meal'):
                    nutrition_metadata = {
                        'nutrition_per_serving': nutrition.get('per_serving', {}),
                        'nutrition_per_meal': nutrition.get('per_meal', {})
                    }
                    
                    cursor.execute("""
                        UPDATE scraped_recipes
                        SET metadata = metadata || %s
                        WHERE id = %s
                    """, (
                        json.dumps(nutrition_metadata),
                        recipe_id
                    ))
            
            # Insert tags
            tags = recipe.get('tags', [])
            for tag in tags:
                if tag:  # Skip empty tags
                    cursor.execute("""
                        INSERT INTO recipe_tags
                        (recipe_id, tag)
                        VALUES (%s, %s)
                    """, (
                        recipe_id,
                        tag[:50]  # Truncate if too long
                    ))
            
            conn.commit()
            logger.info(f"Saved recipe '{recipe['title']}' with ID {recipe_id}")
            return recipe_id
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
        return None
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Import tagged recipes")
    parser.add_argument("--input", required=True, help="Input JSON file with tagged recipes")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually import, just validate")
    args = parser.parse_args()
    
    # Load recipes
    recipes = load_recipes(args.input)
    if not recipes:
        print("No recipes found to import")
        sys.exit(1)
    
    # Import recipes
    success_count = 0
    for i, recipe in enumerate(recipes):
        logger.info(f"Processing recipe {i+1}/{len(recipes)}: {recipe.get('title', 'Unknown')}")
        
        recipe_id = import_recipe(recipe, args.dry_run)
        if recipe_id:
            success_count += 1
    
    # Summary
    logger.info(f"Imported {success_count} out of {len(recipes)} recipes")
    print(f"Imported {success_count} out of {len(recipes)} recipes")

if __name__ == "__main__":
    main()
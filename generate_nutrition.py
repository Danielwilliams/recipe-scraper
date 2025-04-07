#!/usr/bin/env python3
"""
Nutrition Generator for Recipes

This script generates nutrition information for recipes that don't have it.
It uses the Edamam Nutrition API to estimate nutrition values based on ingredients.

Usage:
    python generate_nutrition.py [--output-json filename.json] [--update-db] [--limit N]
"""

import os
import sys
import json
import logging
import argparse
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nutrition_generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_nutrition_generator")

# Load environment variables
load_dotenv()

# Constants
DEFAULT_SERVING_SIZE = 4
EDAMAM_APP_ID = os.environ.get('EDAMAM_APP_ID')
EDAMAM_APP_KEY = os.environ.get('EDAMAM_APP_KEY')

def get_db_connection():
    """Create and return a database connection"""
    try:
        # First try using DATABASE_URL if available
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            conn = psycopg2.connect(database_url)
            return conn
        
        # Fall back to individual parameters
        conn = psycopg2.connect(
            dbname=os.environ.get('DB_NAME'),
            user=os.environ.get('DB_USER'),
            password=os.environ.get('DB_PASSWORD'),
            host=os.environ.get('DB_HOST'),
            port=os.environ.get('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

def get_recipes_missing_nutrition(limit=None):
    """Get recipes that don't have nutrition information"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT r.id, r.title, r.servings, 
                       json_agg(ri.name) as ingredients
                FROM scraped_recipes r
                LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
                LEFT JOIN recipe_nutrition rn ON r.id = rn.recipe_id
                WHERE rn.id IS NULL
                GROUP BY r.id, r.title, r.servings
                ORDER BY r.id
            """
            
            if limit:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            recipes = cursor.fetchall()
            
            logger.info(f"Found {len(recipes)} recipes missing nutrition info")
            return recipes
    except Exception as e:
        logger.error(f"Error getting recipes: {str(e)}")
        return []
    finally:
        conn.close()

def calculate_per_serving(nutrition, servings):
    """Calculate per serving nutrition values"""
    if not nutrition or not servings or servings <= 0:
        return {}
        
    per_serving = {}
    for key, value in nutrition.items():
        if value is not None:
            per_serving[key] = round(value / servings, 1)
            
    return per_serving

def calculate_per_meal(nutrition, recipe_type="main"):
    """Calculate per meal nutrition values based on recipe type"""
    if not nutrition:
        return {}
        
    per_meal = {}
    # For main dishes, per meal = per serving
    if recipe_type.lower() in ["main", "main dish", "entree"]:
        per_meal = nutrition.copy()
    # For side dishes, per meal = per serving * 0.5 (assuming 2 sides per meal)
    elif recipe_type.lower() in ["side", "side dish"]:
        for key, value in nutrition.items():
            if value is not None:
                per_meal[key] = round(value * 0.5, 1)
    # For desserts, per meal = per serving * 0.5
    elif recipe_type.lower() in ["dessert", "sweet"]:
        for key, value in nutrition.items():
            if value is not None:
                per_meal[key] = round(value * 0.5, 1)
    # For snacks, per meal = per serving * 0.25 (assuming 4 snacks = 1 meal)
    elif recipe_type.lower() in ["snack", "appetizer"]:
        for key, value in nutrition.items():
            if value is not None:
                per_meal[key] = round(value * 0.25, 1)
    # Default: same as per serving
    else:
        per_meal = nutrition.copy()
        
    return per_meal

def determine_recipe_type(recipe):
    """Determine the recipe type based on title and tags"""
    title = recipe['title'].lower()
    
    # Check title keywords
    if any(keyword in title for keyword in ["dessert", "cake", "cookie", "pie", "pudding"]):
        return "dessert"
    elif any(keyword in title for keyword in ["salad", "side", "vegetable"]):
        return "side"
    elif any(keyword in title for keyword in ["snack", "appetizer", "dip"]):
        return "snack"
    elif any(keyword in title for keyword in ["breakfast", "brunch", "morning"]):
        return "breakfast"
    
    # Default to main dish
    return "main"

def generate_nutrition_data(ingredients, servings):
    """Generate nutrition data using Edamam API"""
    if not EDAMAM_APP_ID or not EDAMAM_APP_KEY:
        logger.warning("Edamam API credentials not found, skipping nutrition calculation")
        return {}
        
    try:
        # Combine all ingredients into a single string
        ingredient_str = "\n".join(ingredients)
        
        # Query the API
        url = f"https://api.edamam.com/api/nutrition-data"
        params = {
            "app_id": EDAMAM_APP_ID,
            "app_key": EDAMAM_APP_KEY,
            "ingr": ingredient_str
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract the relevant nutrition data
            nutrients = data.get("totalNutrients", {})
            
            nutrition = {
                "calories": round(data.get("calories", 0)),
                "protein": round(nutrients.get("PROCNT", {}).get("quantity", 0), 1) if "PROCNT" in nutrients else None,
                "carbs": round(nutrients.get("CHOCDF", {}).get("quantity", 0), 1) if "CHOCDF" in nutrients else None,
                "fat": round(nutrients.get("FAT", {}).get("quantity", 0), 1) if "FAT" in nutrients else None,
                "fiber": round(nutrients.get("FIBTG", {}).get("quantity", 0), 1) if "FIBTG" in nutrients else None,
                "sugar": round(nutrients.get("SUGAR", {}).get("quantity", 0), 1) if "SUGAR" in nutrients else None,
                "sodium": round(nutrients.get("NA", {}).get("quantity", 0), 1) if "NA" in nutrients else None,
            }
            
            return nutrition
        else:
            logger.warning(f"Failed to get nutrition data: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error generating nutrition data: {str(e)}")
        return {}

def save_nutrition_to_db(recipe_id, nutrition, servings):
    """Save nutrition data to the database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Save main nutrition record
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
            
            # Calculate per serving
            servings_count = servings if servings else DEFAULT_SERVING_SIZE
            per_serving = calculate_per_serving(nutrition, servings_count)
            
            # Determine recipe type
            recipe_type = determine_recipe_type(recipe_id)
            
            # Calculate per meal
            per_meal = calculate_per_meal(per_serving, recipe_type)
            
            # Save per-serving and per-meal data in metadata
            cursor.execute("""
                UPDATE scraped_recipes
                SET metadata = metadata || %s
                WHERE id = %s
            """, (
                json.dumps({
                    'nutrition_per_serving': per_serving,
                    'nutrition_per_meal': per_meal
                }),
                recipe_id
            ))
            
            conn.commit()
            logger.info(f"Saved nutrition data for recipe ID {recipe_id}")
            return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving nutrition for recipe {recipe_id}: {str(e)}")
        return False
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Generate nutrition info for recipes")
    parser.add_argument("--output-json", help="Output file for JSON results")
    parser.add_argument("--update-db", action="store_true", help="Update the database with generated nutrition")
    parser.add_argument("--limit", type=int, help="Limit the number of recipes to process")
    args = parser.parse_args()
    
    # Validate arguments
    if not args.output_json and not args.update_db:
        logger.error("You must specify either --output-json or --update-db (or both)")
        sys.exit(1)
        
    # Get recipes missing nutrition
    recipes = get_recipes_missing_nutrition(args.limit)
    
    if not recipes:
        logger.info("No recipes missing nutrition info found")
        return
        
    # Process each recipe
    results = []
    total = len(recipes)
    success = 0
    
    for i, recipe in enumerate(recipes):
        logger.info(f"Processing recipe {i+1}/{total}: {recipe['title']}")
        
        try:
            # Get ingredients
            ingredients = recipe.get('ingredients', [])
            if not ingredients:
                logger.warning(f"Recipe {recipe['id']} has no ingredients, skipping")
                continue
                
            # Get servings
            servings = recipe.get('servings') or DEFAULT_SERVING_SIZE
            
            # Generate nutrition data
            nutrition = generate_nutrition_data(ingredients, servings)
            
            if not nutrition:
                logger.warning(f"Failed to generate nutrition for recipe {recipe['id']}")
                continue
                
            # Calculate per serving and per meal values
            nutrition['per_serving'] = calculate_per_serving(nutrition, servings)
            
            recipe_type = determine_recipe_type(recipe)
            nutrition['per_meal'] = calculate_per_meal(nutrition['per_serving'], recipe_type)
            
            # Update the database if requested
            if args.update_db:
                if save_nutrition_to_db(recipe['id'], nutrition, servings):
                    success += 1
                    
            # Add to results
            results.append({
                "id": recipe['id'],
                "title": recipe['title'],
                "nutrition": nutrition
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
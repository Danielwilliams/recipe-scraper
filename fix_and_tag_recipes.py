#!/usr/bin/env python3
"""
Fix and Tag Recipes

This script:
1. Fixes malformed JSON in FB_Recipes.json
2. Adds standardized tags to each recipe
3. Saves the fixed and tagged recipes to FB_Recipes_tagged.json

Usage:
    python fix_and_tag_recipes.py
"""

import os
import sys
import json
import re
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("recipe_fix.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recipe_fixer")

# Define standard tag categories
STANDARD_TAGS = {
    "meal_type": ["breakfast", "lunch", "dinner", "snack", "dessert", "appetizer", "side-dish"],
    "cuisine": ["italian", "mexican", "asian", "mediterranean", "american", "french", "indian", 
                "thai", "japanese", "chinese", "greek", "middle-eastern", "spanish"],
    "diet_type": ["vegetarian", "vegan", "gluten-free", "keto", "low-carb", "dairy-free", 
                 "paleo", "whole30"],
    "dish_type": ["soup", "salad", "sandwich", "pizza", "pasta", "stir-fry", "casserole", 
                 "stew", "curry", "bowl", "wrap", "burger", "taco", "pie", "bread", "cake", 
                 "cookie", "rice"],
    "main_ingredient": ["chicken", "beef", "pork", "fish", "seafood", "tofu", "lentils", 
                       "beans", "rice", "potato", "pasta", "vegetables", "mushroom"],
    "cooking_method": ["baked", "grilled", "fried", "slow-cooker", "instant-pot", "air-fryer", 
                      "steamed", "sauteed", "pressure-cooker", "one-pot", "sheet-pan"],
    "preparation_time": ["quick", "make-ahead", "meal-prep", "5-ingredients", "30-minute", "weeknight"],
    "complexity": ["easy", "medium", "complex"],
    "seasonal": ["spring", "summer", "fall", "winter", "holiday"],
    "occasion": ["party", "potluck", "family-friendly", "date-night", "weeknight", "weekend"]
}

# Ingredient lists for dietary classification
MEAT_INGREDIENTS = ["chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon", "tuna", 
                   "shrimp", "crab", "lobster", "bacon", "ham", "sausage", "meat", "steak"]
GLUTEN_INGREDIENTS = ["flour", "wheat", "barley", "rye", "pasta", "bread", "couscous", 
                     "soy sauce", "beer"]
HIGH_CARB_INGREDIENTS = ["sugar", "flour", "rice", "potato", "bread", "pasta", "corn", "oats"]
DAIRY_INGREDIENTS = ["milk", "cheese", "cream", "yogurt", "butter", "sour cream", "ice cream"]

def fix_json_file(input_file, output_file=None):
    """Fix malformed JSON file and return parsed recipes"""
    try:
        # Read the file content
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix common issues
        
        # 1. If it starts with a comma, add opening bracket
        if content.strip().startswith(','):
            content = '[' + content
        
        # 2. Look for unclosed arrays/objects
        # Simplest approach: count brackets and add missing ones
        open_braces = content.count('{')
        close_braces = content.count('}')
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        
        # Add missing closing braces/brackets
        if open_braces > close_braces:
            content += '}' * (open_braces - close_braces)
        if open_brackets > close_brackets:
            content += ']' * (open_brackets - close_brackets)
        
        # 3. If we added an opening bracket at the beginning, add closing bracket
        if content.strip().startswith('[') and not content.strip().endswith(']'):
            content += ']'
        
        # Try to parse the JSON
        try:
            recipes = json.loads(content)
            if not isinstance(recipes, list):
                recipes = [recipes]
            logger.info(f"Successfully parsed {len(recipes)} recipes")
            
            # If output file is provided, save the fixed JSON
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(recipes, f, indent=2)
                logger.info(f"Fixed JSON saved to {output_file}")
            
            return recipes
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            
            # More advanced fixing needed
            logger.info("Attempting more advanced fixing...")
            
            # Try to identify and fix specific recipe objects
            recipes = []
            
            # Split by recipe objects (looking for title fields)
            pattern = r'"title"\s*:\s*"[^"]+"\s*,'
            splits = re.split(pattern, content)
            
            if len(splits) > 1:
                # Reconstruct each recipe
                for i in range(1, len(splits)):
                    recipe_text = '{"title":' + splits[i]
                    # Try to find the end of this recipe
                    end_pos = recipe_text.find(',"title":')
                    if end_pos > -1:
                        recipe_text = recipe_text[:end_pos]
                    
                    # Try to parse this recipe
                    try:
                        recipe = json.loads(recipe_text)
                        recipes.append(recipe)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse recipe #{i}")
            
            # If we extracted any recipes this way
            if recipes:
                logger.info(f"Extracted {len(recipes)} recipes after advanced fixing")
                
                # If output file is provided, save the fixed JSON
                if output_file:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(recipes, f, indent=2)
                    logger.info(f"Fixed JSON saved to {output_file}")
                
                return recipes
            
            # If we still couldn't parse anything, return empty list
            logger.error("Could not fix JSON file")
            return []
            
    except Exception as e:
        logger.error(f"Error processing file {input_file}: {str(e)}")
        return []

def generate_tags(recipe):
    """Generate standardized tags for a recipe"""
    # If recipe already has tags, return them
    if 'tags' in recipe and recipe['tags'] and len(recipe['tags']) > 1:
        # Ensure 'facebook' tag is included
        tags = recipe['tags']
        if 'facebook' not in tags:
            tags.append('facebook')
        return tags
    
    # Start with basic tags
    tags = ['facebook']
    
    title = recipe.get('title', '').lower()
    ingredients = [ing.lower() for ing in recipe.get('ingredients', [])]
    instructions = ' '.join(recipe.get('instructions', [])).lower() if 'instructions' in recipe else ''
    cuisine = recipe.get('metadata', {}).get('cuisine', '').lower() if 'metadata' in recipe else ''
    raw_content = recipe.get('raw_content', '').lower() if 'raw_content' in recipe else ''
    
    # Add cuisine tag if available
    if cuisine:
        for std_cuisine in STANDARD_TAGS["cuisine"]:
            if std_cuisine in cuisine or std_cuisine.replace('-', ' ') in cuisine:
                tags.append(std_cuisine)
                break
    
    # Check for dietary tags
    ingredients_text = ' '.join(ingredients)
    
    # Vegetarian if no meat ingredients
    if not any(meat in ingredients_text for meat in MEAT_INGREDIENTS):
        tags.append("vegetarian")
        
        # Vegan if no dairy and no meat
        if not any(dairy in ingredients_text for dairy in DAIRY_INGREDIENTS):
            tags.append("vegan")
    
    # Gluten-free if no gluten ingredients
    if not any(gluten in ingredients_text for gluten in GLUTEN_INGREDIENTS):
        tags.append("gluten-free")
    
    # Low-carb if few high carb ingredients
    if sum(1 for carb in HIGH_CARB_INGREDIENTS if carb in ingredients_text) <= 1:
        tags.append("low-carb")
        
        # Keto if low-carb and high fat
        if any(fat in ingredients_text for fat in ["cream", "butter", "cheese", "avocado"]):
            tags.append("keto")
    
    # Meal type tags
    if any(term in title or term in raw_content for term in ["breakfast", "brunch", "morning"]):
        tags.append("breakfast")
    elif any(term in title or term in raw_content for term in ["dessert", "sweet", "cake", "cookie", "pie", "chocolate"]):
        tags.append("dessert")
    elif any(term in title or term in raw_content for term in ["appetizer", "dip", "snack", "bite"]):
        tags.append("appetizer")
        tags.append("snack")
    elif any(term in title or term in raw_content for term in ["salad", "side"]):
        tags.append("side-dish")
    else:
        # Default to lunch/dinner for main dishes
        tags.append("lunch")
        tags.append("dinner")
        tags.append("main-dish")
    
    # Add dish type tags
    for dish_type in STANDARD_TAGS["dish_type"]:
        if dish_type in title or dish_type in ingredients_text or dish_type in instructions:
            tags.append(dish_type)
    
    # Add main ingredient tags
    for ingredient in STANDARD_TAGS["main_ingredient"]:
        if ingredient in title or ingredient in ingredients_text:
            tags.append(ingredient)
    
    # Add cooking method tags
    for method in STANDARD_TAGS["cooking_method"]:
        if method in title or method in instructions or method in raw_content:
            tags.append(method)
    
    # Add preparation time tags
    prep_time = recipe.get('metadata', {}).get('prep_time', 0) if 'metadata' in recipe else 0
    total_time = recipe.get('metadata', {}).get('total_time', 0) if 'metadata' in recipe else 0
    
    if (prep_time and prep_time <= 15) or (total_time and total_time <= 30):
        tags.append("quick")
        tags.append("30-minute")
        tags.append("weeknight")
    
    if len(recipe.get('ingredients', [])) <= 5:
        tags.append("5-ingredients")
    
    # Add complexity tag
    complexity = recipe.get('complexity', '')
    if complexity and complexity not in tags:
        tags.append(complexity)
    
    # Flavor profile tags based on ingredients
    if any(spicy in ingredients_text for spicy in ["chili", "jalapeño", "cayenne", "sriracha", "spicy"]):
        tags.append("spicy")
    
    if any(sweet in ingredients_text for sweet in ["sugar", "honey", "maple", "sweet"]):
        tags.append("sweet")
    
    if any(garlicky in ingredients_text for garlicky in ["garlic"]):
        tags.append("garlicky")
    
    # Add occasion tags
    if "easy" in tags or "quick" in tags:
        tags.append("weeknight")
    
    if "casserole" in tags or "family" in raw_content:
        tags.append("family-friendly")
    
    # Remove duplicates and ensure all tags are lowercase
    return list(set([tag.lower() for tag in tags]))

def main():
    # Define input and output files
    input_file = os.path.join('data', 'FB_Recipes.json')
    fixed_file = os.path.join('data', 'FB_Recipes_fixed.json')
    output_file = os.path.join('data', 'FB_Recipes_tagged.json')
    
    # Create data directory if it doesn't exist
    Path(os.path.dirname(input_file)).mkdir(parents=True, exist_ok=True)
    
    # Fix the JSON file
    recipes = fix_json_file(input_file, fixed_file)
    
    if not recipes:
        print("No recipes were loaded. Please check the input file.")
        sys.exit(1)
    
    # Generate tags for each recipe
    for i, recipe in enumerate(recipes):
        print(f"Processing recipe {i+1}/{len(recipes)}: {recipe.get('title', 'Unknown')}")
        
        # Generate tags if needed
        if 'tags' not in recipe or not recipe['tags'] or len(recipe['tags']) <= 1:
            recipe['tags'] = generate_tags(recipe)
            print(f"  Generated tags: {', '.join(recipe['tags'])}")
        else:
            print(f"  Using existing tags: {', '.join(recipe['tags'])}")
    
    # Save tagged recipes
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, indent=2)
    
    print(f"Tagged {len(recipes)} recipes and saved to {output_file}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Repair JSON

This script:
1. Reads the possibly malformed FB_Recipes.json
2. Extracts recipe objects using regex patterns
3. Creates a properly formatted JSON file
"""

import os
import sys
import json
import re
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("json_repair")

def extract_recipes(file_path):
    """Extract recipes from a possibly malformed JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all recipe objects
        recipes = []
        
        # Look for recipe title patterns in the content
        title_pattern = r'"title"\s*:\s*"([^"]+)"'
        title_matches = list(re.finditer(title_pattern, content))
        
        for i, match in enumerate(title_matches):
            title = match.group(1)
            start_pos = match.start()
            
            # Find the end of this recipe (start of next one or end of file)
            end_pos = len(content)
            if i < len(title_matches) - 1:
                end_pos = title_matches[i+1].start() - 1
            
            # Extract the recipe text, adjusting the bounds
            # Go backwards to find opening brace
            brace_pos = content.rfind('{', 0, start_pos)
            if brace_pos >= 0:
                recipe_text = content[brace_pos:end_pos].strip()
                
                # Try to parse it as JSON
                try:
                    # Add missing closing braces if needed
                    open_braces = recipe_text.count('{')
                    close_braces = recipe_text.count('}')
                    if open_braces > close_braces:
                        recipe_text += '}' * (open_braces - close_braces)
                    
                    recipe = json.loads(recipe_text)
                    recipes.append(recipe)
                    logger.info(f"Extracted recipe: {title}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not parse recipe '{title}': {str(e)}")
                    
                    # Try a more flexible extraction
                    try:
                        # Extract individual fields
                        ingredients_match = re.search(r'"ingredients"\s*:\s*\[(.*?)\]', recipe_text, re.DOTALL)
                        instructions_match = re.search(r'"instructions"\s*:\s*\[(.*?)\]', recipe_text, re.DOTALL)
                        source_match = re.search(r'"source"\s*:\s*"(.*?)"', recipe_text)
                        complexity_match = re.search(r'"complexity"\s*:\s*"(.*?)"', recipe_text)
                        
                        # Extract image_url if available
                        image_url_match = re.search(r'"image_url"\s*:\s*"(.*?)"', recipe_text)
                        
                        # Create a new recipe object with available data
                        recipe = {
                            "title": title,
                            "ingredients": [],
                            "instructions": [],
                            "source": "Facebook",
                            "complexity": "medium"
                        }
                        
                        # Add ingredients if found
                        if ingredients_match:
                            ingredients_text = ingredients_match.group(1)
                            # Split by quotes and commas
                            ingredients = []
                            for ing in re.finditer(r'"([^"]+)"', ingredients_text):
                                ingredients.append(ing.group(1))
                            recipe["ingredients"] = ingredients
                        
                        # Add instructions if found
                        if instructions_match:
                            instructions_text = instructions_match.group(1)
                            # Split by quotes and commas
                            instructions = []
                            for instr in re.finditer(r'"([^"]+)"', instructions_text):
                                instructions.append(instr.group(1))
                            recipe["instructions"] = instructions
                        
                        # Add source if found
                        if source_match:
                            recipe["source"] = source_match.group(1)
                        
                        # Add complexity if found
                        if complexity_match:
                            recipe["complexity"] = complexity_match.group(1)
                            
                        # Add image URL if found
                        if image_url_match:
                            recipe["image_url"] = image_url_match.group(1)
                        
                        # Extract metadata if available
                        metadata_match = re.search(r'"metadata"\s*:\s*(\{.*?\})', recipe_text, re.DOTALL)
                        if metadata_match:
                            try:
                                metadata_text = metadata_match.group(1)
                                # Fix common issues in metadata JSON
                                metadata_text = re.sub(r',\s*\}', '}', metadata_text)
                                metadata = json.loads(metadata_text)
                                recipe["metadata"] = metadata
                            except:
                                recipe["metadata"] = {}
                        
                        # Extract nutrition if available
                        nutrition_match = re.search(r'"nutrition"\s*:\s*(\{.*?\})', recipe_text, re.DOTALL)
                        if nutrition_match:
                            try:
                                nutrition_text = nutrition_match.group(1)
                                # Fix common issues in nutrition JSON
                                nutrition_text = re.sub(r',\s*\}', '}', nutrition_text)
                                nutrition = json.loads(nutrition_text)
                                recipe["nutrition"] = nutrition
                            except:
                                recipe["nutrition"] = {}
                        
                        # Add tags if available
                        tags_match = re.search(r'"tags"\s*:\s*\[(.*?)\]', recipe_text, re.DOTALL)
                        if tags_match:
                            try:
                                tags_text = tags_match.group(1)
                                # Extract tags
                                tags = []
                                for tag in re.finditer(r'"([^"]+)"', tags_text):
                                    tags.append(tag.group(1))
                                recipe["tags"] = tags
                            except:
                                recipe["tags"] = ["facebook"]
                        else:
                            recipe["tags"] = ["facebook"]
                        
                        # Add the partially extracted recipe
                        recipes.append(recipe)
                        logger.info(f"Added partial recipe: {title}")
                    except Exception as partial_e:
                        logger.error(f"Failed to extract partial recipe '{title}': {str(partial_e)}")
        
        logger.info(f"Extracted {len(recipes)} recipes total")
        return recipes
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return []

def add_tags(recipes):
    """Add tags to recipes based on content"""
    # Standard tag categories
    meal_types = ["breakfast", "lunch", "dinner", "snack", "dessert", "appetizer", "side-dish"]
    cuisines = ["italian", "mexican", "asian", "mediterranean", "american", "french", "indian", 
                "thai", "japanese", "chinese", "greek", "middle-eastern", "spanish"]
    diet_types = ["vegetarian", "vegan", "gluten-free", "keto", "low-carb", "dairy-free", 
                "paleo", "whole30"]
    dish_types = ["soup", "salad", "sandwich", "pizza", "pasta", "stir-fry", "casserole", 
                "stew", "curry", "bowl", "wrap", "burger", "taco", "pie", "bread", "cake", 
                "cookie", "rice"]
    main_ingredients = ["chicken", "beef", "pork", "fish", "seafood", "tofu", "lentils", 
                      "beans", "rice", "potato", "pasta", "vegetables", "mushroom"]
    cooking_methods = ["baked", "grilled", "fried", "slow-cooker", "instant-pot", "air-fryer", 
                      "steamed", "sauteed", "pressure-cooker", "one-pot", "sheet-pan"]
    
    # Ingredients for dietary checks
    meat_items = ["chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon", "shrimp"]
    dairy_items = ["milk", "cheese", "cream", "yogurt", "butter"]
    gluten_items = ["flour", "wheat", "pasta", "bread"]
    
    for recipe in recipes:
        # Skip if recipe already has multiple tags
        if "tags" in recipe and len(recipe["tags"]) > 2:
            continue
        
        # Initialize tag list
        tags = ["facebook"]
        title = recipe.get("title", "").lower()
        
        # Check ingredients as a single string for easier pattern matching
        ingredients_text = " ".join(recipe.get("ingredients", [])).lower()
        
        # Add meal type tags
        if any(word in title for word in ["breakfast", "brunch", "morning"]):
            tags.append("breakfast")
        elif any(word in title for word in ["dessert", "cake", "cookie", "sweet", "pie"]):
            tags.append("dessert")
        elif any(word in title for word in ["appetizer", "snack", "dip"]):
            tags.append("appetizer")
            tags.append("snack")
        elif any(word in title for word in ["salad", "side"]):
            tags.append("side-dish")
        else:
            # Default to main dish
            tags.append("lunch")
            tags.append("dinner")
            tags.append("main-dish")
        
        # Add cuisine tags
        cuisine = recipe.get("metadata", {}).get("cuisine", "").lower()
        if cuisine:
            for c in cuisines:
                if c in cuisine:
                    tags.append(c)
                    break
        
        # Check for dietary restrictions
        if not any(meat in ingredients_text for meat in meat_items):
            tags.append("vegetarian")
            if not any(dairy in ingredients_text for dairy in dairy_items):
                tags.append("vegan")
        
        if not any(gluten in ingredients_text for gluten in gluten_items):
            tags.append("gluten-free")
        
        # Check for common dish types in title
        for dish in dish_types:
            if dish in title:
                tags.append(dish)
                break
        
        # Check for main ingredients
        for ingredient in main_ingredients:
            if ingredient in title or ingredient in ingredients_text:
                tags.append(ingredient)
                break
        
        # Check for cooking methods
        instructions_text = " ".join(recipe.get("instructions", [])).lower()
        for method in cooking_methods:
            if method in title or method in instructions_text:
                tags.append(method)
                break
        
        # Add complexity tag if available
        complexity = recipe.get("complexity", "").lower()
        if complexity in ["easy", "medium", "complex"]:
            tags.append(complexity)
        
        # Add family-friendly tag for casseroles and crowd-pleasers
        if "casserole" in title or "family" in title:
            tags.append("family-friendly")
        
        # Add weeknight tag for quick recipes
        prep_time = recipe.get("metadata", {}).get("prep_time", 0)
        total_time = recipe.get("metadata", {}).get("total_time", 0)
        if (prep_time and prep_time <= 15) or (total_time and total_time <= 30):
            tags.append("quick")
            tags.append("weeknight")
        
        # Remove duplicates
        recipe["tags"] = list(set(tags))
        
        logger.info(f"Added tags to {recipe['title']}: {recipe['tags']}")
    
    return recipes

def main():
    input_file = os.path.join('data', 'FB_Recipes.json')
    output_file = os.path.join('data', 'FB_Recipes_tagged.json')
    
    # Extract recipes from the file
    recipes = extract_recipes(input_file)
    
    if not recipes:
        print("No recipes extracted. Please check the input file.")
        sys.exit(1)
    
    # Add tags to recipes
    tagged_recipes = add_tags(recipes)
    
    # Save the tagged recipes
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tagged_recipes, f, indent=2)
    
    print(f"Saved {len(tagged_recipes)} tagged recipes to {output_file}")

if __name__ == "__main__":
    main()
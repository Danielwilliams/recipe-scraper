#!/usr/bin/env python3
import json
import re
import os
import sys
import requests
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import random
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

# Constants
DEFAULT_SERVING_SIZE = 4
FALLBACK_IMAGE_URL = "https://via.placeholder.com/500x500.png?text=No+Image+Available"
UNSPLASH_API_KEY = os.environ.get('UNSPLASH_API_KEY')
EDAMAM_APP_ID = os.environ.get('EDAMAM_APP_ID')
EDAMAM_APP_KEY = os.environ.get('EDAMAM_APP_KEY')

# Standard tags for recipe categorization
STANDARD_TAGS = {
    "meal_type": ["breakfast", "lunch", "dinner", "snack", "dessert"],
    "cuisine": ["italian", "mexican", "asian", "mediterranean", "american", 
               "french", "indian", "thai", "japanese", "chinese", "greek"],
    "diet_type": ["vegetarian", "vegan", "gluten-free", "keto", "low-carb", 
                 "dairy-free", "paleo", "whole30"],
    "dish_type": ["soup", "salad", "sandwich", "pizza", "pasta", "stir-fry", 
                 "casserole", "stew", "curry", "bowl", "wrap"],
    "main_ingredient": ["chicken", "beef", "pork", "fish", "tofu", "lentils", 
                       "beans", "rice", "potato", "pasta"],
    "cooking_method": ["baked", "grilled", "fried", "slow-cooker", "instant-pot", 
                      "air-fryer", "steamed", "sauteed", "pressure-cooker"],
    "preparation_time": ["quick", "make-ahead", "meal-prep", "5-ingredients"]
}

# Ingredient lists for dietary classification
MEAT_INGREDIENTS = ["chicken", "beef", "pork", "lamb", "turkey", "fish", "salmon", 
                    "tuna", "shrimp", "crab", "lobster", "bacon", "ham", "sausage", 
                    "meat", "steak", "ground beef", "ground turkey"]
GLUTEN_INGREDIENTS = ["flour", "wheat", "barley", "rye", "pasta", "bread", 
                      "couscous", "soy sauce", "beer"]
HIGH_CARB_INGREDIENTS = ["sugar", "flour", "rice", "potato", "bread", 
                         "pasta", "corn", "oats", "cereal", "honey", "maple syrup"]
DAIRY_INGREDIENTS = ["milk", "cheese", "cream", "yogurt", "butter", 
                     "sour cream", "ice cream", "whey", "casein"]

# Database connection is imported from database.db_connector

def alter_title_column_length():
    """Increase the length of the title column in the database if needed"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # First, check the current column type
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'scraped_recipes' AND column_name = 'title'
            """)
            column_info = cursor.fetchone()
            
            if column_info:
                logger.info(f"Current title column type: {column_info[1]} with max length: {column_info[2]}")
                
                # Only alter if needed
                if column_info[2] < 255:
                    logger.info("Altering title column to VARCHAR(255)...")
                    cursor.execute("ALTER TABLE scraped_recipes ALTER COLUMN title TYPE VARCHAR(255);")
                    conn.commit()
                    logger.info("Successfully increased title column length to 255 characters")
                else:
                    logger.info("Title column already has sufficient length")
            else:
                logger.warning("Could not find title column in scraped_recipes table")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error altering title column length: {str(e)}")
    finally:
        conn.close()

def get_ingredient_lists(recipe_text):
    """Extract ingredient lists from recipe text, handling grouped ingredients"""
    lines = recipe_text.strip().split('\n')
    ingredients = []
    in_ingredients = False
    ingredients_headers = ["ingredients", "ingredient list", "you will need", "what you need", "you'll need", "items needed"]
    current_section = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check for ingredients section
        if any(header in line.lower() for header in ingredients_headers):
            in_ingredients = True
            continue
            
        # Check for instructions or other section that would end ingredients
        if re.match(r'^(instructions|directions|steps|method|preparation|for serving|to serve)', line.lower()):
            in_ingredients = False
            continue
            
        # Check for ingredient subsections like "For the sauce:"
        if in_ingredients and re.match(r'^for the\s+|^for\s+', line.lower()):
            current_section = line
            continue
            
        # Process ingredients if we're in the ingredients section
        if in_ingredients and line:
            # Remove bullet points, asterisks, dashes, etc.
            cleaned_line = re.sub(r'^[•\-\*\⁃\\+⋅◦‣⦾⦿⁌⁍∙≡→→◆◇○●□■]\s*', '', line)
            
            # Handle numbered ingredients
            cleaned_line = re.sub(r'^\d+\.\s*', '', cleaned_line)
            
            # Add the subsection name if applicable
            if current_section and not line.startswith(' '):
                if not any(ing.startswith(f"{current_section} - ") for ing in ingredients):
                    ingredients.append(f"{current_section}")
            
            # Add the ingredient
            if cleaned_line:
                ingredients.append(cleaned_line)
                
    return ingredients

def get_instructions(recipe_text):
    """Extract instruction steps from recipe text"""
    lines = recipe_text.strip().split('\n')
    instructions = []
    in_instructions = False
    instruction_headers = ["instructions", "directions", "steps", "method", "preparation", "how to make"]
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check for instruction section headers
        if any(header in line.lower() for header in instruction_headers):
            in_instructions = True
            continue
            
        # Look for end of instructions section
        if in_instructions and any(header in line.lower() for header in ["notes", "tips", "serving suggestions", "nutrition"]):
            in_instructions = False
            continue
            
        # Process instructions
        if in_instructions and line:
            # Remove step numbers
            cleaned_line = re.sub(r'^\d+[\.\)]?\s*', '', line)
            
            # Remove bullet points, asterisks, etc.
            cleaned_line = re.sub(r'^[•\-\*\\+]\s*', '', cleaned_line)
            
            if cleaned_line:
                instructions.append(cleaned_line)
                
    return instructions

def extract_metadata(recipe_text):
    """Extract metadata like prep time, cook time, servings from recipe text"""
    metadata = {}
    
    # Find prep time
    prep_time_match = re.search(r'prep\s*time:?\s*(\d+)(?:\s*to\s*\d+)?\s*(?:min|minutes|hours|hrs)', recipe_text, re.IGNORECASE)
    if prep_time_match:
        metadata['prep_time'] = int(prep_time_match.group(1))
        
    # Find cook time
    cook_time_match = re.search(r'cook(?:ing)?\s*time:?\s*(\d+)(?:\s*to\s*\d+)?\s*(?:min|minutes|hours|hrs)', recipe_text, re.IGNORECASE)
    if cook_time_match:
        metadata['cook_time'] = int(cook_time_match.group(1))
        
    # Find total time
    total_time_match = re.search(r'total\s*time:?\s*(\d+)(?:\s*to\s*\d+)?\s*(?:min|minutes|hours|hrs)', recipe_text, re.IGNORECASE)
    if total_time_match:
        metadata['total_time'] = int(total_time_match.group(1))
        
    # If we have prep time and cook time but no total time, calculate it
    if 'prep_time' in metadata and 'cook_time' in metadata and 'total_time' not in metadata:
        metadata['total_time'] = metadata['prep_time'] + metadata['cook_time']
        
    # Find servings
    servings_match = re.search(r'(?:servings?|yields?|serves?)(?:\s*:)?\s*(\d+)(?:[^\d,](\d+))?\s*(?:servings|people|-|to|–|persons)', recipe_text, re.IGNORECASE)
    if servings_match:
        if servings_match.group(2):  # Range of servings, e.g., "Serves 4-6"
            # Use the average
            metadata['servings'] = (int(servings_match.group(1)) + int(servings_match.group(2))) // 2
        else:
            metadata['servings'] = int(servings_match.group(1))
    else:
        metadata['servings'] = DEFAULT_SERVING_SIZE
        
    # Find cuisine
    cuisine_match = re.search(r'cuisine:?\s*([a-zA-Z\s]+)', recipe_text, re.IGNORECASE)
    if cuisine_match:
        metadata['cuisine'] = cuisine_match.group(1).strip().lower()
        
    return metadata

def extract_nutrition(recipe_text):
    """Extract nutrition information from recipe text"""
    nutrition = {}
    
    # Find calories
    calories_match = re.search(r'calories:?\s*(\d+)(?:\s*kcal)?', recipe_text, re.IGNORECASE)
    if calories_match:
        nutrition['calories'] = int(calories_match.group(1))
        
    # Find protein
    protein_match = re.search(r'protein:?\s*(\d+\.?\d*)(?:\s*g)?', recipe_text, re.IGNORECASE)
    if protein_match:
        nutrition['protein'] = float(protein_match.group(1))
        
    # Find carbs
    carbs_match = re.search(r'carb(?:ohydrate)?s?:?\s*(\d+\.?\d*)(?:\s*g)?', recipe_text, re.IGNORECASE)
    if carbs_match:
        nutrition['carbs'] = float(carbs_match.group(1))
        
    # Find fat
    fat_match = re.search(r'fat:?\s*(\d+\.?\d*)(?:\s*g)?', recipe_text, re.IGNORECASE)
    if fat_match:
        nutrition['fat'] = float(fat_match.group(1))
        
    # Find fiber
    fiber_match = re.search(r'fiber:?\s*(\d+\.?\d*)(?:\s*g)?', recipe_text, re.IGNORECASE)
    if fiber_match:
        nutrition['fiber'] = float(fiber_match.group(1))
        
    # Find sugar
    sugar_match = re.search(r'sugar:?\s*(\d+\.?\d*)(?:\s*g)?', recipe_text, re.IGNORECASE)
    if sugar_match:
        nutrition['sugar'] = float(sugar_match.group(1))
        
    # Find sodium
    sodium_match = re.search(r'sodium:?\s*(\d+\.?\d*)(?:\s*mg)?', recipe_text, re.IGNORECASE)
    if sodium_match:
        nutrition['sodium'] = float(sodium_match.group(1))
        
    return nutrition

def calculate_per_serving_nutrition(nutrition, servings):
    """Calculate per serving nutrition values"""
    if not nutrition or not servings or servings <= 0:
        return {}
        
    per_serving = {}
    for key, value in nutrition.items():
        if value is not None:
            per_serving[key] = round(value / servings, 1)
            
    return per_serving

def calculate_per_meal_nutrition(nutrition, recipe_type="main"):
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
            
            # Add per serving calculations
            nutrition["per_serving"] = calculate_per_serving_nutrition(nutrition, servings)
            
            # Add per meal calculations (default to "main dish")
            nutrition["per_meal"] = calculate_per_meal_nutrition(nutrition["per_serving"], "main")
            
            return nutrition
        else:
            logger.warning(f"Failed to get nutrition data: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error generating nutrition data: {str(e)}")
        return {}

def extract_image_url(recipe_text):
    """Extract image URL from recipe text"""
    # Check for URLs in the text
    url_matches = re.finditer(r'https?://[^\s<>"\']+\.(jpg|jpeg|png|gif|webp)(?:\?[^\s<>"\']*)?', recipe_text, re.IGNORECASE)
    
    for match in url_matches:
        image_url = match.group(0)
        # Verify it's an image URL
        if re.search(r'\.(jpg|jpeg|png|gif|webp)(?:\?|$)', image_url, re.IGNORECASE):
            return image_url

    # Check for "Image:" or "Image Link:" prefixes
    image_line_match = re.search(r'image(?:\s+link)?:?\s*(https?://[^\s<>"\']+)', recipe_text, re.IGNORECASE)
    if image_line_match:
        return image_line_match.group(1)
        
    # No image URL found
    return None

def search_image(recipe_title, main_ingredients):
    """Search for an image using Unsplash API"""
    if not UNSPLASH_API_KEY:
        logger.warning("Unsplash API key not found, using placeholder image")
        return FALLBACK_IMAGE_URL
        
    try:
        # Prepare search query
        if main_ingredients and len(main_ingredients) > 0:
            top_ingredients = [ing.split(' ')[0] for ing in main_ingredients[:2]]
            query = f"{recipe_title} {' '.join(top_ingredients)} food"
        else:
            query = f"{recipe_title} food recipe"
            
        # Query the API
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 1,
            "orientation": "landscape"
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
        return FALLBACK_IMAGE_URL
    except Exception as e:
        logger.error(f"Error searching for image: {str(e)}")
        return FALLBACK_IMAGE_URL

def generate_tags(recipe_text, title, ingredients, cuisine=None):
    """Generate tags for the recipe"""
    tags = ["facebook"]  # Always add source tag
    
    # Extract hashtags
    hashtags = re.findall(r'#(\w+)', recipe_text)
    for tag in hashtags:
        clean_tag = tag.lower().strip()
        if clean_tag and clean_tag not in tags:
            tags.append(clean_tag)
            
    # Add cuisine tag if available
    if cuisine:
        cuisine_tag = cuisine.lower().strip()
        for std_cuisine in STANDARD_TAGS["cuisine"]:
            if std_cuisine in cuisine_tag:
                if std_cuisine not in tags:
                    tags.append(std_cuisine)
                break
                
    # Generate diet tags based on ingredients
    # Check for vegetarian - no meat ingredients
    if not any(meat in ' '.join(ingredients).lower() for meat in MEAT_INGREDIENTS):
        tags.append("vegetarian")
        
        # Check for vegan - no meat AND no dairy
        if not any(dairy in ' '.join(ingredients).lower() for dairy in DAIRY_INGREDIENTS):
            tags.append("vegan")
            
    # Check for gluten-free
    if not any(gluten in ' '.join(ingredients).lower() for gluten in GLUTEN_INGREDIENTS):
        tags.append("gluten-free")
        
    # Check for low-carb or keto
    if len([ing for ing in ingredients if any(carb in ing.lower() for carb in HIGH_CARB_INGREDIENTS)]) <= 2:
        tags.append("low-carb")
        
    # Add dish type tags
    for dish_type in STANDARD_TAGS["dish_type"]:
        if dish_type in title.lower() or dish_type in ' '.join(ingredients).lower():
            tags.append(dish_type)
            break
            
    # Detect meal type
    if "breakfast" in title.lower() or "breakfast" in recipe_text.lower():
        tags.append("breakfast")
    elif "dessert" in title.lower() or "sweet" in title.lower() or "cake" in title.lower() or "cookie" in title.lower():
        tags.append("dessert")
    elif "snack" in title.lower() or "appetizer" in title.lower():
        tags.append("snack")
    else:
        # Default to lunch/dinner
        tags.append("lunch")
        tags.append("dinner")
        
    # Add main ingredient tags
    for ingredient in STANDARD_TAGS["main_ingredient"]:
        if ingredient in title.lower() or any(ingredient in ing.lower() for ing in ingredients):
            tags.append(ingredient)
            break
            
    # Add cooking method tags
    for method in STANDARD_TAGS["cooking_method"]:
        if method in title.lower() or method in recipe_text.lower():
            tags.append(method)
            
    # Check for quick recipe
    if "quick" in title.lower() or "easy" in title.lower() or "simple" in title.lower():
        tags.append("quick")
        
    # Return unique tags
    return list(set(tags))

def determine_complexity(ingredients, instructions):
    """Determine recipe complexity based on ingredients count and instruction steps"""
    if len(ingredients) <= 5 and len(instructions) <= 5:
        return "easy"
    elif len(ingredients) >= 12 or len(instructions) >= 8:
        return "complex"
    else:
        return "medium"

def parse_recipe(recipe_text):
    """Parse a recipe from text into structured format"""
    lines = recipe_text.strip().split('\n')
    
    # Extract title from first line
    title = lines[0].strip() if lines else "Untitled Recipe"
    
    # Remove emojis and special characters
    title = re.sub(r'[^\x00-\x7F]+', '', title).strip()
    
    # Ensure title is under 95 characters
    if len(title) > 95:
        title = title[:95] + "..."
        
    # Extract ingredients
    ingredients = get_ingredient_lists(recipe_text)
    
    # Extract instructions
    instructions = get_instructions(recipe_text)
    
    # If we couldn't find instructions using section headers, try a simpler approach
    if not instructions:
        # Look for instruction markers
        instruction_markers = ["step 1", "1.", "first", "begin by", "start by"]
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if any(marker in line_lower for marker in instruction_markers):
                # Extract instructions from this point forward
                potential_instructions = []
                for instr_line in lines[i:]:
                    cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', instr_line.strip())
                    if cleaned_line and not cleaned_line.startswith("http") and not re.match(r'^-{3,}$', cleaned_line):
                        potential_instructions.append(cleaned_line)
                
                # If we found reasonable instructions, use them
                if len(potential_instructions) >= 2:
                    instructions = potential_instructions
                break
    
    # Extract metadata
    metadata = extract_metadata(recipe_text)
    
    # Extract nutrition information
    nutrition = extract_nutrition(recipe_text)
    
    # Calculate per-serving and per-meal nutrition if nutrition info exists
    if nutrition and metadata.get('servings'):
        nutrition['per_serving'] = calculate_per_serving_nutrition(nutrition, metadata.get('servings'))
        
        # Determine recipe type for per-meal calculation
        if "dessert" in title.lower() or "cake" in title.lower() or "cookie" in title.lower():
            recipe_type = "dessert"
        elif "side" in title.lower() or "salad" in title.lower():
            recipe_type = "side"
        elif "snack" in title.lower() or "appetizer" in title.lower():
            recipe_type = "snack"
        else:
            recipe_type = "main"
            
        nutrition['per_meal'] = calculate_per_meal_nutrition(nutrition['per_serving'], recipe_type)
    
    # If nutrition info wasn't found in the text, try to generate it
    if not nutrition and ingredients:
        try:
            nutrition = generate_nutrition_data(ingredients, metadata.get('servings', DEFAULT_SERVING_SIZE))
        except Exception as e:
            logger.error(f"Error generating nutrition data: {str(e)}")
    
    # Extract image URL
    image_url = extract_image_url(recipe_text)
    
    # If no image URL was found, search for one
    if not image_url:
        try:
            main_ingredients = ingredients[:3] if ingredients else []
            image_url = search_image(title, main_ingredients)
        except Exception as e:
            logger.error(f"Error searching for image: {str(e)}")
            image_url = FALLBACK_IMAGE_URL
    
    # Generate tags
    tags = generate_tags(recipe_text, title, ingredients, metadata.get('cuisine'))
    
    # Determine complexity
    complexity = determine_complexity(ingredients, instructions)
    
    # Construct the recipe object
    recipe = {
        'title': title,
        'ingredients': ingredients,
        'instructions': instructions,
        'source': 'Facebook',
        'source_url': '',
        'date_scraped': datetime.now().isoformat(),
        'complexity': complexity,
        'metadata': metadata,
        'nutrition': nutrition,
        'image_url': image_url,
        'tags': tags,
        'raw_content': recipe_text[:5000]  # Limit raw content to 5000 chars
    }
    
    return recipe

def save_recipe_to_database(recipe):
    """Save a recipe to the database"""
    conn = get_db_connection()
    try:
        title = recipe['title']
        logger.info(f"Saving recipe: '{title}' (Length: {len(title)} characters)")
        
        with conn.cursor() as cursor:
            # Check if recipe already exists
            cursor.execute("""
                SELECT id FROM scraped_recipes
                WHERE title = %s AND source = %s
                LIMIT 1
            """, (recipe['title'], recipe['source']))
            
            existing = cursor.fetchone()
            if existing:
                logger.info(f"Recipe already exists: {recipe['title']}")
                return existing[0]
            
            # Insert recipe
            try:
                cursor.execute("""
                    INSERT INTO scraped_recipes (
                        title, source, source_url, instructions, date_scraped, date_processed,
                        complexity, prep_time, cook_time, total_time, servings, cuisine,
                        is_verified, raw_content, metadata, image_url
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    recipe['title'],
                    recipe['source'],
                    recipe.get('source_url', ''),
                    json.dumps(recipe['instructions']),
                    datetime.now(),
                    datetime.now(),
                    recipe['complexity'],
                    recipe['metadata'].get('prep_time'),
                    recipe['metadata'].get('cook_time'),
                    recipe['metadata'].get('total_time'),
                    recipe['metadata'].get('servings'),
                    recipe['metadata'].get('cuisine'),
                    True,  # Facebook recipes are verified
                    recipe.get('raw_content', '')[:5000],  # Limit raw content size
                    json.dumps(recipe['metadata']),
                    recipe.get('image_url')
                ))
            except Exception as e:
                logger.error(f"ERROR on INSERT: {str(e)}")
                logger.error(f"Title value: '{recipe['title']}' (Length: {len(recipe['title'])})")
                # Try a simplified INSERT as a last resort
                cursor.execute("""
                    INSERT INTO scraped_recipes (
                        title, source, instructions
                    ) VALUES (
                        %s, %s, %s
                    ) RETURNING id
                """, (
                    recipe['title'][:95],  # Truncate title just to be safe
                    recipe['source'],
                    json.dumps(recipe['instructions'])
                ))
            
            recipe_id = cursor.fetchone()[0]
            
            # Insert ingredients
            if 'ingredients' in recipe and recipe['ingredients']:
                for ing in recipe['ingredients']:
                    # Simple insertion for string ingredients
                    cursor.execute("""
                        INSERT INTO recipe_ingredients
                        (recipe_id, name, category)
                        VALUES (%s, %s, %s)
                    """, (
                        recipe_id,
                        str(ing)[:100],  # Truncate ingredient name if too long
                        'unknown'
                    ))
            
            # Insert nutrition if available
            if recipe.get('nutrition'):
                nutrition = recipe['nutrition']
                # Handle both flat and nested nutrition structures
                calories = nutrition.get('calories')
                protein = nutrition.get('protein')
                carbs = nutrition.get('carbs')
                fat = nutrition.get('fat')
                fiber = nutrition.get('fiber')
                sugar = nutrition.get('sugar')
                sodium = nutrition.get('sodium')
                
                # If we have nested nutrition, store it in the metadata JSON
                if isinstance(nutrition.get('per_serving'), dict) or isinstance(nutrition.get('per_meal'), dict):
                    cursor.execute("""
                        UPDATE scraped_recipes
                        SET metadata = metadata || %s
                        WHERE id = %s
                    """, (
                        json.dumps({
                            'nutrition_per_serving': nutrition.get('per_serving', {}),
                            'nutrition_per_meal': nutrition.get('per_meal', {})
                        }),
                        recipe_id
                    ))
                
                # Insert the main nutrition record
                cursor.execute("""
                    INSERT INTO recipe_nutrition
                    (recipe_id, calories, protein, carbs, fat, fiber, sugar, sodium, is_calculated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    recipe_id,
                    calories,
                    protein,
                    carbs,
                    fat,
                    fiber,
                    sugar,
                    sodium,
                    True  # Mark as calculated values
                ))
            
            # Insert tags
            if 'tags' in recipe and recipe['tags']:
                for tag in recipe['tags']:
                    cursor.execute("""
                        INSERT INTO recipe_tags
                        (recipe_id, tag)
                        VALUES (%s, %s)
                    """, (
                        recipe_id,
                        tag[:50]  # Truncate tag if too long
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

def save_recipes_to_json(recipes, output_file):
    """Save recipes to a JSON file"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(recipes, f, indent=2)
        logger.info(f"Saved {len(recipes)} recipes to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving recipes to JSON: {str(e)}")
        return False

def split_recipes(content):
    """Split content into individual recipes"""
    # Common recipe separators
    separator_patterns = [
        r'-{10,}',  # At least 10 dashes
        r'_{10,}',  # At least 10 underscores
        r'\n\n\n+',  # Three or more newlines
        r'\d+\.\s*[A-Z][a-zA-Z\s]+\n',  # Numbered recipes like "1. Recipe Name"
        r'Recipe\s*\d+\s*:',  # "Recipe 1:" format
        r'https?://[^\s<>"\']+(?:\n\n)'  # URL followed by double newlines
    ]
    
    # Start with the whole content as a single recipe
    recipes = [content]
    
    # Try each separator pattern
    for pattern in separator_patterns:
        new_recipes = []
        for recipe_chunk in recipes:
            # Skip if it's too short to be a recipe
            if len(recipe_chunk.strip()) < 50:
                continue
                
            # Split by the current pattern
            splits = re.split(pattern, recipe_chunk)
            
            # If we found multiple parts, add them as separate recipes
            if len(splits) > 1:
                for split in splits:
                    if split.strip() and len(split.strip()) >= 50:
                        new_recipes.append(split.strip())
            else:
                new_recipes.append(recipe_chunk)
                
        # Update our recipe list
        if new_recipes:
            recipes = new_recipes
    
    # Filter out likely non-recipes (too short, etc.)
    valid_recipes = []
    for recipe in recipes:
        # Skip very short content
        if len(recipe.strip()) < 100:
            continue
            
        # Skip content without key recipe indicators
        if not any(term in recipe.lower() for term in ['ingredient', 'instruction', 'direction', 'cup', 'tablespoon', 'teaspoon']):
            continue
            
        valid_recipes.append(recipe.strip())
    
    return valid_recipes

def process_recipes_file(input_file, output_json=None, save_to_db=True):
    """Process a file containing multiple recipes"""
    try:
        logger.info(f"Reading file: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"File size: {len(content)} characters")
        
        # Split the content into individual recipes
        recipe_texts = split_recipes(content)
        
        logger.info(f"Found {len(recipe_texts)} potential recipes")
        
        # If we'll be saving to the database, ensure the title column is long enough
        if save_to_db:
            alter_title_column_length()
        
        # Process each recipe
        recipes = []
        for i, recipe_text in enumerate(recipe_texts):
            try:
                logger.info(f"\nProcessing recipe #{i+1}:")
                logger.info("-" * 40)
                logger.info(recipe_text[:100] + "..." if len(recipe_text) > 100 else recipe_text)
                logger.info("-" * 40)
                
                # Parse the recipe
                recipe = parse_recipe(recipe_text)
                
                # Save to database if requested
                if save_to_db:
                    recipe_id = save_recipe_to_database(recipe)
                    if recipe_id:
                        recipe['id'] = recipe_id
                
                # Add to our collection
                recipes.append(recipe)
                
            except Exception as e:
                logger.error(f"Error processing recipe: {str(e)}")
        
        logger.info(f"Successfully processed {len(recipes)} out of {len(recipe_texts)} recipes")
        
        # Save to JSON if an output file was specified
        if output_json:
            save_recipes_to_json(recipes, output_json)
            
        return recipes
        
    except Exception as e:
        logger.error(f"Error processing file {input_file}: {str(e)}")
        return []

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python enhanced_import_custom_recipes.py <input_file> [output_json] [--no-db-save]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    save_to_db = "--no-db-save" not in sys.argv
    
    recipes = process_recipes_file(input_file, output_json, save_to_db)
    logger.info(f"Processed {len(recipes)} recipes")

if __name__ == "__main__":
    main()
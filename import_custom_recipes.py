import json
import re
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection function
def get_db_connection():
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

def parse_custom_recipe(recipe_text):
    """Parse custom recipe text into structured format"""
    lines = recipe_text.strip().split('\n')
    
    # Extract title
    title = lines[0].strip()
    
    # Find ingredients and instructions sections
    ingredients = []
    instructions = []
    
    # Find nutrition info if available
    nutrition = {}
    metadata = {}
    
    # Default values
    image_url = None
    complexity = "medium"  # Default complexity
    source = "Custom"
    
    # Parse ingredients (lines before "Instruction:" or "Instructions:")
    instruction_index = -1
    for i, line in enumerate(lines[1:], 1):
        if re.search(r'instruction[s]?:', line.lower()):
            instruction_index = i
            break
        elif line.strip() and not line.startswith('--') and not line.startswith('http'):
            ingredients.append(line.strip())
    
    # Parse instructions (lines after "Instruction:" or "Instructions:")
    if instruction_index > 0:
        for line in lines[instruction_index+1:]:
            # Skip empty lines, image links, or separators
            if not line.strip() or line.startswith('--') or line.startswith('http') or re.search(r'key benefits:', line.lower()):
                continue
            # Check if line contains nutritional info
            if re.search(r'calories:', line.lower()):
                # Extract nutritional info
                calories_match = re.search(r'calories:\s*(\d+)', line.lower())
                if calories_match:
                    nutrition['calories'] = float(calories_match.group(1))
                
                protein_match = re.search(r'protein:\s*(\d+)g', line.lower())
                if protein_match:
                    nutrition['protein'] = float(protein_match.group(1))
                
                carbs_match = re.search(r'carbohydrates:\s*(\d+)g', line.lower())
                if carbs_match:
                    nutrition['carbs'] = float(carbs_match.group(1))
                
                fat_match = re.search(r'fat:\s*(\d+)g', line.lower())
                if fat_match:
                    nutrition['fat'] = float(fat_match.group(1))
                
                continue
            
            instructions.append(line.strip())
    
    # Extract image URL if present
    for line in lines:
        if line.startswith('http') and ('jpg' in line.lower() or 'png' in line.lower() or 'image' in line.lower()):
            image_url = line.strip()
            break
    
    # Determine complexity based on number of ingredients and steps
    if len(ingredients) <= 5 and len(instructions) <= 5:
        complexity = "easy"
    elif len(ingredients) >= 12 or len(instructions) >= 8:
        complexity = "complex"
    else:
        complexity = "medium"
    
    # Extract servings if available
    for line in lines:
        servings_match = re.search(r'makes\s+(\d+)\s+servings', line.lower()) or re.search(r'makes\s+(\d+)\s+portions', line.lower())
        if servings_match:
            metadata['servings'] = int(servings_match.group(1))
            break
    
    # Create the recipe object
    recipe = {
        'title': title,
        'ingredients': ingredients,
        'instructions': instructions,
        'source': source,
        'source_url': '',  # No source URL for custom recipes
        'date_scraped': datetime.now().isoformat(),
        'complexity': complexity,
        'metadata': metadata,
        'nutrition': nutrition,
        'image_url': image_url,
        'tags': ['custom'],  # Tag as custom recipe
        'raw_content': recipe_text[:5000]  # Limit raw content to 5000 chars
    }
    
    return recipe

def save_recipe(recipe):
    """Save a recipe to the database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if recipe already exists
            cursor.execute("""
                SELECT id FROM scraped_recipes
                WHERE title = %s AND source = %s
                LIMIT 1
            """, (recipe['title'], recipe['source']))
            
            existing = cursor.fetchone()
            if existing:
                print(f"Recipe already exists: {recipe['title']}")
                return existing[0]
            
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
                recipe.get('cuisine'),
                True,  # Custom recipes are verified
                recipe.get('raw_content', '')[:5000],  # Limit raw content size
                json.dumps(recipe['metadata']),
                recipe.get('image_url')
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
                        str(ing),
                        'unknown'
                    ))
            
            # Insert nutrition if available
            if recipe.get('nutrition'):
                nutrition = recipe['nutrition']
                cursor.execute("""
                    INSERT INTO recipe_nutrition
                    (recipe_id, calories, protein, carbs, fat, is_calculated)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    recipe_id,
                    nutrition.get('calories'),
                    nutrition.get('protein'),
                    nutrition.get('carbs'),
                    nutrition.get('fat'),
                    False  # Not calculated values
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
                        tag
                    ))
            
            conn.commit()
            print(f"Saved recipe '{recipe['title']}' with ID {recipe_id}")
            return recipe_id
                
    except Exception as e:
        conn.rollback()
        print(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
        return None
    finally:
        conn.close()

def process_custom_recipes_file(file_path):
    """Process a file containing multiple custom recipes"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split the file into individual recipes
        # Assuming recipes are separated by a line of dashes
        recipe_texts = re.split(r'-{10,}', content)
        
        saved_recipes = 0
        for recipe_text in recipe_texts:
            if not recipe_text.strip():
                continue
                
            try:
                recipe = parse_custom_recipe(recipe_text.strip())
                if recipe:
                    recipe_id = save_recipe(recipe)
                    if recipe_id:
                        saved_recipes += 1
            except Exception as e:
                print(f"Error processing recipe: {str(e)}")
        
        print(f"Successfully saved {saved_recipes} out of {len(recipe_texts)} recipes")
        
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")

if __name__ == "__main__":
    # Example usage
    file_path = "data/Custom_Recipes.txt"
    process_custom_recipes_file(file_path)
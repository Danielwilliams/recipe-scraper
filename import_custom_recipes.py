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

def alter_title_column_length():
    """Increase the length of the title column in the database"""
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
                print(f"Current title column type: {column_info[1]} with max length: {column_info[2]}")
                
                # Only alter if needed
                if column_info[2] < 255:
                    print("Altering title column to VARCHAR(255)...")
                    cursor.execute("ALTER TABLE scraped_recipes ALTER COLUMN title TYPE VARCHAR(255);")
                    conn.commit()
                    print("Successfully increased title column length to 255 characters")
                else:
                    print("Title column already has sufficient length")
            else:
                print("Could not find title column in scraped_recipes table")
    except Exception as e:
        conn.rollback()
        print(f"Error altering title column length: {str(e)}")
    finally:
        conn.close()

def parse_custom_recipe(recipe_text):
    """Parse custom recipe text into structured format"""
    lines = recipe_text.strip().split('\n')
    
    # Extract title and clean it
    title = lines[0].strip()
    
    # Remove emojis and special characters that might cause issues
    title = re.sub(r'[^\x00-\x7F]+', '', title)  # Remove non-ASCII characters
    
    # Debug output
    print(f"Original title: '{title}' ({len(title)} characters)")
    
    # Ensure the title is under 100 characters
    if len(title) > 95:
        title = title[:95] + "..."
        print(f"Truncated to: '{title}'")
    
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
    
    # Parse ingredients section
    in_ingredients = False
    in_instructions = False
    
    for i, line in enumerate(lines[1:], 1):
        line = line.strip()
        if not line:
            continue
            
        # Check for section headings
        if re.match(r'^INGREDIENTS', line, re.IGNORECASE):
            in_ingredients = True
            in_instructions = False
            continue
        elif re.match(r'^INSTRUCTIONS', line, re.IGNORECASE):
            in_ingredients = False
            in_instructions = True
            continue
        elif line.startswith('http') or line.startswith('Image Link:'):
            # This is likely an image URL
            url_match = re.search(r'https?://[^\s]+', line)
            if url_match:
                image_url = url_match.group(0)
            continue
            
        # Process based on current section
        if in_ingredients and line:
            ingredients.append(line)
        elif in_instructions and line:
            instructions.append(line)
        elif not in_ingredients and not in_instructions and i < 10 and not line.startswith('Image'):
            # If we haven't hit either section yet and we're in the beginning lines,
            # this might be part of the ingredients
            if line and not line.startswith('--'):
                ingredients.append(line)
    
    # If we didn't find explicit sections, try to infer them
    if not ingredients and not instructions:
        instruction_index = -1
        for i, line in enumerate(lines[1:], 1):
            if re.search(r'instruction[s]?:', line.lower()):
                instruction_index = i
                break
                
        if instruction_index > 0:
            # Get ingredients before instructions
            for i, line in enumerate(lines[1:instruction_index], 1):
                if line.strip() and not line.startswith('--') and not line.startswith('http'):
                    ingredients.append(line.strip())
                    
            # Get instructions after the instructions marker
            for line in lines[instruction_index+1:]:
                if not line.strip() or line.startswith('--') or line.startswith('http'):
                    continue
                if re.search(r'calories:', line.lower()):
                    # Extract nutritional info
                    calories_match = re.search(r'calories:\s*(\d+)', line.lower())
                    if calories_match:
                        nutrition['calories'] = float(calories_match.group(1))
                    continue
                    
                instructions.append(line.strip())
    
    # Determine complexity based on number of ingredients and steps
    if len(ingredients) <= 5 and len(instructions) <= 5:
        complexity = "easy"
    elif len(ingredients) >= 12 or len(instructions) >= 8:
        complexity = "complex"
    else:
        complexity = "medium"
    
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
        title = recipe['title']
        print(f"Attempting to save recipe with title: '{title}' (Length: {len(title)} characters)")
        
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
                    recipe.get('cuisine'),
                    True,  # Custom recipes are verified
                    recipe.get('raw_content', '')[:5000],  # Limit raw content size
                    json.dumps(recipe['metadata']),
                    recipe.get('image_url')
                ))
            except Exception as e:
                print(f"ERROR on INSERT: {str(e)}")
                print(f"Title value: '{recipe['title']}' (Length: {len(recipe['title'])})")
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
                        tag[:50]  # Truncate tag if too long
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
        print(f"Reading file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"File size: {len(content)} characters")
        
        # Split the file into individual recipes
        # Look for common recipe separators
        separator_patterns = [
            r'-{10,}',  # At least 10 dashes
            r'\d+\.\s*[A-Z][a-zA-Z\s]+\n',  # Numbered recipes like "1. Recipe Name"
            r'Recipe\s*\d+\s*:'  # "Recipe 1:" format
        ]
        
        all_recipes = [content]
        for pattern in separator_patterns:
            new_recipes = []
            for recipe_chunk in all_recipes:
                splits = re.split(pattern, recipe_chunk)
                if len(splits) > 1:
                    for i, split in enumerate(splits):
                        if i > 0:  # Add back the separator for everything except the first split
                            match = re.search(pattern, recipe_chunk)
                            if match:
                                new_recipes.append(match.group(0) + split)
                        else:
                            new_recipes.append(split)
                else:
                    new_recipes.append(recipe_chunk)
            all_recipes = new_recipes
        
        # Filter out empty recipes
        recipe_texts = [recipe for recipe in all_recipes if recipe.strip()]
        
        print(f"Found {len(recipe_texts)} potential recipes")
        
        # First try to alter the title column to handle longer titles
        alter_title_column_length()
        
        saved_recipes = 0
        for i, recipe_text in enumerate(recipe_texts):
            if not recipe_text.strip():
                continue
                
            print(f"\nProcessing recipe #{i+1}:")
            print("-" * 40)
            print(recipe_text[:100] + "..." if len(recipe_text) > 100 else recipe_text)
            print("-" * 40)
                
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
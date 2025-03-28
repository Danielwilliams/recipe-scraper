#!/usr/bin/env python3
import json
import os
import re
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create and return a database connection"""
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

def update_or_create_recipe_from_file(file_path):
    """Update existing recipes or create new ones from a text file"""
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            recipes_text = f.read()
            
        # Split the text into recipe sections by separator lines
        separator = "-" * 10
        recipes = re.split(separator, recipes_text)
        
        conn = get_db_connection()
        success_count = 0
        update_count = 0
        create_count = 0
        
        for recipe_text in recipes:
            if not recipe_text.strip():
                continue
                
            try:
                # Parse recipe details
                lines = recipe_text.strip().split('\n')
                if not lines:
                    continue
                    
                title = lines[0].strip()
                if not title:
                    continue
                
                # Extract image URL
                image_url = None
                instructions = []
                ingredients_section = False
                instruction_section = False
                ingredients_text = []
                
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith('Image Link:'):
                        image_url = line.replace('Image Link:', '').strip()
                    elif line.upper().startswith('INGREDIENTS') or line.startswith('INGREDIENT'):
                        ingredients_section = True
                        instruction_section = False
                    elif any(line.upper().startswith(s) for s in ['INSTRUCTION', 'DIRECTIONS', 'METHOD', 'STEPS']):
                        instruction_section = True
                        ingredients_section = False
                    elif instruction_section:
                        # Remove numbering from instructions if present
                        clean_line = re.sub(r'^\d+\.?\s*', '', line)
                        instructions.append(clean_line)
                    elif ingredients_section:
                        ingredients_text.append(line)
                
                complexity = 'medium'  # Default complexity
                
                # First check if recipe with this title exists
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id FROM scraped_recipes WHERE LOWER(title) = LOWER(%s)
                    """, (title,))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing recipe
                        recipe_id = existing['id']
                        print(f"Updating existing recipe: {title} (ID: {recipe_id})")
                        
                        update_fields = []
                        params = []
                        
                        if image_url:
                            update_fields.append("image_url = %s")
                            params.append(image_url)
                            
                        if instructions:
                            update_fields.append("instructions = %s")
                            params.append(json.dumps(instructions))
                        
                        if update_fields:
                            params.append(recipe_id)
                            cursor.execute(f"""
                                UPDATE scraped_recipes
                                SET {', '.join(update_fields)}
                                WHERE id = %s
                            """, params)
                            
                            # Now update ingredients if provided
                            if ingredients_text:
                                # First delete existing ingredients
                                cursor.execute("""
                                    DELETE FROM recipe_ingredients WHERE recipe_id = %s
                                """, (recipe_id,))
                                
                                # Add new ingredients
                                for ingredient in ingredients_text:
                                    # Skip headers or formatting lines
                                    if ingredient.isupper() or not ingredient.strip():
                                        continue
                                    cursor.execute("""
                                        INSERT INTO recipe_ingredients (recipe_id, name, category)
                                        VALUES (%s, %s, %s)
                                    """, (recipe_id, ingredient.strip(), 'general'))
                            
                            conn.commit()
                            print(f"Updated recipe: {title}")
                            update_count += 1
                            success_count += 1
                    else:
                        # Create new recipe
                        print(f"Creating new recipe: {title}")
                        
                        cursor.execute("""
                            INSERT INTO scraped_recipes
                            (title, image_url, source, complexity, instructions, date_scraped)
                            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                            RETURNING id
                        """, (
                            title,
                            image_url,
                            'custom',
                            complexity,
                            json.dumps(instructions) if instructions else None
                        ))
                        
                        new_id = cursor.fetchone()['id']
                        
                        # Add ingredients if provided
                        if ingredients_text:
                            for ingredient in ingredients_text:
                                # Skip headers or formatting lines
                                if ingredient.isupper() or not ingredient.strip():
                                    continue
                                cursor.execute("""
                                    INSERT INTO recipe_ingredients (recipe_id, name, category)
                                    VALUES (%s, %s, %s)
                                """, (new_id, ingredient.strip(), 'general'))
                        
                        conn.commit()
                        print(f"Created new recipe with ID: {new_id}")
                        create_count += 1
                        success_count += 1
            except Exception as e:
                print(f"Error processing recipe '{title if 'title' in locals() else 'unknown'}': {str(e)}")
                conn.rollback()
        
        print(f"Successfully processed {success_count} recipes")
        print(f"Updated: {update_count}, Created: {create_count}")
        return True
    except Exception as e:
        print(f"Error reading or processing recipes file: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Check if file path was provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = os.path.join('data', 'Custom_Recipes.txt')
    
    print(f"Updating recipes from: {file_path}")
    update_or_create_recipe_from_file(file_path)
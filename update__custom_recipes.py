import json
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import re
import sys

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

def list_recipes(limit=20, offset=0, search_term=None):
    """List recipes with optional search functionality"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT id, title, source, complexity, 
                    image_url, date_scraped::TEXT
                FROM scraped_recipes
            """
            
            params = []
            if search_term:
                query += " WHERE title ILIKE %s"
                params.append(f'%{search_term}%')
            
            query += " ORDER BY id DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            recipes = cursor.fetchall()
            
            print(f"Found {len(recipes)} recipes:")
            for i, recipe in enumerate(recipes):
                print(f"{i+1}. [ID: {recipe['id']}] {recipe['title']} ({recipe['source']})")
                print(f"   Image: {recipe['image_url'] or 'None'}")
                print(f"   Complexity: {recipe['complexity']}")
                print(f"   Scraped: {recipe['date_scraped']}")
                print("-" * 80)
            
            return recipes
    finally:
        conn.close()

def update_recipe_image(recipe_id, new_image_url):
    """Update the image URL for a specific recipe"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE scraped_recipes
                SET image_url = %s
                WHERE id = %s
                RETURNING title
            """, (new_image_url, recipe_id))
            
            result = cursor.fetchone()
            if result:
                conn.commit()
                print(f"Successfully updated image URL for recipe ID {recipe_id} ({result[0]})")
                return True
            else:
                print(f"Recipe ID {recipe_id} not found")
                return False
    except Exception as e:
        conn.rollback()
        print(f"Error updating image URL: {str(e)}")
        return False
    finally:
        conn.close()

def update_recipe_title(recipe_id, new_title):
    """Update the title for a specific recipe"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # First get the current title
            cursor.execute("SELECT title FROM scraped_recipes WHERE id = %s", (recipe_id,))
            result = cursor.fetchone()
            if not result:
                print(f"Recipe ID {recipe_id} not found")
                return False
            
            old_title = result[0]
            
            # Update the title
            cursor.execute("""
                UPDATE scraped_recipes
                SET title = %s
                WHERE id = %s
            """, (new_title, recipe_id))
            
            conn.commit()
            print(f"Successfully updated title for recipe ID {recipe_id}")
            print(f"Old title: {old_title}")
            print(f"New title: {new_title}")
            return True
    except Exception as e:
        conn.rollback()
        print(f"Error updating title: {str(e)}")
        return False
    finally:
        conn.close()

def update_recipe_complexity(recipe_id, new_complexity):
    """Update the complexity for a specific recipe"""
    if new_complexity not in ['easy', 'medium', 'complex']:
        print("Complexity must be one of: easy, medium, complex")
        return False
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE scraped_recipes
                SET complexity = %s
                WHERE id = %s
                RETURNING title
            """, (new_complexity, recipe_id))
            
            result = cursor.fetchone()
            if result:
                conn.commit()
                print(f"Successfully updated complexity to '{new_complexity}' for recipe ID {recipe_id} ({result[0]})")
                return True
            else:
                print(f"Recipe ID {recipe_id} not found")
                return False
    except Exception as e:
        conn.rollback()
        print(f"Error updating complexity: {str(e)}")
        return False
    finally:
        conn.close()

def update_recipe_ingredients(recipe_id):
    """Update ingredients for a specific recipe"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # First get the recipe details
            cursor.execute("""
                SELECT title FROM scraped_recipes WHERE id = %s
            """, (recipe_id,))
            
            recipe = cursor.fetchone()
            if not recipe:
                print(f"Recipe ID {recipe_id} not found")
                return False
            
            # Get current ingredients
            cursor.execute("""
                SELECT id, name, category FROM recipe_ingredients 
                WHERE recipe_id = %s
                ORDER BY id
            """, (recipe_id,))
            
            ingredients = cursor.fetchall()
            
            print(f"Current ingredients for: {recipe['title']}")
            for i, ing in enumerate(ingredients):
                print(f"{i+1}. [{ing['id']}] {ing['name']} (Category: {ing['category'] or 'None'})")
            
            print("\nOptions:")
            print("1. Add new ingredient")
            print("2. Update existing ingredient")
            print("3. Delete ingredient")
            print("4. Go back")
            
            choice = input("Enter your choice: ")
            
            if choice == '1':
                # Add new ingredient
                name = input("Enter ingredient name: ")
                category = input("Enter category (or leave blank): ") or 'unknown'
                
                cursor.execute("""
                    INSERT INTO recipe_ingredients (recipe_id, name, category)
                    VALUES (%s, %s, %s)
                """, (recipe_id, name, category))
                
                conn.commit()
                print(f"Added ingredient: {name}")
                return True
                
            elif choice == '2':
                # Update existing ingredient
                ing_id = input("Enter ingredient ID to update: ")
                
                # Verify ingredient exists and belongs to this recipe
                cursor.execute("""
                    SELECT id FROM recipe_ingredients 
                    WHERE id = %s AND recipe_id = %s
                """, (ing_id, recipe_id))
                
                if not cursor.fetchone():
                    print(f"Ingredient ID {ing_id} not found for this recipe")
                    return False
                
                name = input("Enter new name (or leave blank to keep current): ")
                category = input("Enter new category (or leave blank to keep current): ")
                
                update_query = "UPDATE recipe_ingredients SET "
                update_parts = []
                params = []
                
                if name:
                    update_parts.append("name = %s")
                    params.append(name)
                
                if category:
                    update_parts.append("category = %s")
                    params.append(category)
                
                if not update_parts:
                    print("No changes specified")
                    return False
                
                update_query += ", ".join(update_parts)
                update_query += " WHERE id = %s"
                params.append(ing_id)
                
                cursor.execute(update_query, params)
                conn.commit()
                print(f"Updated ingredient ID {ing_id}")
                return True
                
            elif choice == '3':
                # Delete ingredient
                ing_id = input("Enter ingredient ID to delete: ")
                
                # Verify ingredient exists and belongs to this recipe
                cursor.execute("""
                    SELECT id FROM recipe_ingredients 
                    WHERE id = %s AND recipe_id = %s
                """, (ing_id, recipe_id))
                
                if not cursor.fetchone():
                    print(f"Ingredient ID {ing_id} not found for this recipe")
                    return False
                
                confirm = input(f"Are you sure you want to delete ingredient ID {ing_id}? (y/n): ")
                if confirm.lower() != 'y':
                    print("Deletion cancelled")
                    return False
                
                cursor.execute("DELETE FROM recipe_ingredients WHERE id = %s", (ing_id,))
                conn.commit()
                print(f"Deleted ingredient ID {ing_id}")
                return True
                
            else:
                print("Returning to main menu")
                return False
    except Exception as e:
        conn.rollback()
        print(f"Error updating ingredients: {str(e)}")
        return False
    finally:
        conn.close()

def update_recipe_instructions(recipe_id):
    """Update instructions for a specific recipe"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get recipe details
            cursor.execute("""
                SELECT title, instructions FROM scraped_recipes WHERE id = %s
            """, (recipe_id,))
            
            recipe = cursor.fetchone()
            if not recipe:
                print(f"Recipe ID {recipe_id} not found")
                return False
            
            # Parse instructions
            instructions = []
            if recipe['instructions']:
                try:
                    instructions = json.loads(recipe['instructions'])
                except json.JSONDecodeError:
                    instructions = [recipe['instructions']]
            
            if not isinstance(instructions, list):
                instructions = [str(instructions)]
            
            print(f"Current instructions for: {recipe['title']}")
            for i, step in enumerate(instructions):
                print(f"Step {i+1}: {step}")
            
            print("\nOptions:")
            print("1. Edit all instructions")
            print("2. Add new instruction step")
            print("3. Update specific step")
            print("4. Delete step")
            print("5. Go back")
            
            choice = input("Enter your choice: ")
            
            if choice == '1':
                # Edit all instructions
                print("Enter new instructions (one step per line, enter blank line to finish):")
                new_instructions = []
                while True:
                    line = input()
                    if not line:
                        break
                    new_instructions.append(line)
                
                if not new_instructions:
                    print("No instructions entered")
                    return False
                
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET instructions = %s
                    WHERE id = %s
                """, (json.dumps(new_instructions), recipe_id))
                
                conn.commit()
                print(f"Updated all instructions for recipe ID {recipe_id}")
                return True
                
            elif choice == '2':
                # Add new step
                step = input("Enter new instruction step: ")
                if not step:
                    print("No step entered")
                    return False
                
                instructions.append(step)
                
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET instructions = %s
                    WHERE id = %s
                """, (json.dumps(instructions), recipe_id))
                
                conn.commit()
                print(f"Added new instruction step to recipe ID {recipe_id}")
                return True
                
            elif choice == '3':
                # Update specific step
                if not instructions:
                    print("No instructions to update")
                    return False
                
                step_num = int(input(f"Enter step number to update (1-{len(instructions)}): "))
                if step_num < 1 or step_num > len(instructions):
                    print(f"Invalid step number. Must be between 1 and {len(instructions)}")
                    return False
                
                new_step = input("Enter new step: ")
                if not new_step:
                    print("No step entered")
                    return False
                
                instructions[step_num-1] = new_step
                
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET instructions = %s
                    WHERE id = %s
                """, (json.dumps(instructions), recipe_id))
                
                conn.commit()
                print(f"Updated step {step_num} for recipe ID {recipe_id}")
                return True
                
            elif choice == '4':
                # Delete step
                if not instructions:
                    print("No instructions to delete")
                    return False
                
                step_num = int(input(f"Enter step number to delete (1-{len(instructions)}): "))
                if step_num < 1 or step_num > len(instructions):
                    print(f"Invalid step number. Must be between 1 and {len(instructions)}")
                    return False
                
                confirm = input(f"Are you sure you want to delete step {step_num}? (y/n): ")
                if confirm.lower() != 'y':
                    print("Deletion cancelled")
                    return False
                
                del instructions[step_num-1]
                
                cursor.execute("""
                    UPDATE scraped_recipes
                    SET instructions = %s
                    WHERE id = %s
                """, (json.dumps(instructions), recipe_id))
                
                conn.commit()
                print(f"Deleted step {step_num} for recipe ID {recipe_id}")
                return True
                
            else:
                print("Returning to main menu")
                return False
    except Exception as e:
        conn.rollback()
        print(f"Error updating instructions: {str(e)}")
        return False
    finally:
        conn.close()

def batch_update_image_urls(csv_file_path):
    """Update multiple image URLs from a CSV file (format: recipe_id,new_image_url)"""
    try:
        with open(csv_file_path, 'r') as f:
            lines = f.readlines()
        
        success_count = 0
        fail_count = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(',', 1)
            if len(parts) != 2:
                print(f"Invalid line format: {line}")
                fail_count += 1
                continue
            
            recipe_id, image_url = parts
            try:
                recipe_id = int(recipe_id)
            except ValueError:
                print(f"Invalid recipe ID: {recipe_id}")
                fail_count += 1
                continue
            
            if update_recipe_image(recipe_id, image_url):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"Batch update complete. Successful: {success_count}, Failed: {fail_count}")
        return success_count, fail_count
    except Exception as e:
        print(f"Error during batch update: {str(e)}")
        return 0, 0

def cleanup_recipe_duplicates():
    """Find and clean up duplicate recipes"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Find potential duplicates based on title similarity
            cursor.execute("""
                SELECT r1.id, r1.title, r2.id AS duplicate_id, r2.title AS duplicate_title
                FROM scraped_recipes r1
                JOIN scraped_recipes r2 ON r1.id < r2.id
                WHERE 
                    LOWER(r1.title) = LOWER(r2.title)
                    OR similarity(r1.title, r2.title) > 0.8
                ORDER BY r1.title
            """)
            
            duplicates = cursor.fetchall()
            
            if not duplicates:
                print("No potential duplicates found")
                return
            
            print(f"Found {len(duplicates)} potential duplicate pairs:")
            for i, dup in enumerate(duplicates):
                print(f"{i+1}. [ID: {dup['id']}] {dup['title']}")
                print(f"   Duplicate: [ID: {dup['duplicate_id']}] {dup['duplicate_title']}")
                print("-" * 80)
            
            while True:
                idx = input("Enter pair number to handle (or 'q' to quit): ")
                if idx.lower() == 'q':
                    break
                
                try:
                    idx = int(idx) - 1
                    if idx < 0 or idx >= len(duplicates):
                        print(f"Invalid index. Must be between 1 and {len(duplicates)}")
                        continue
                    
                    dup = duplicates[idx]
                    print(f"Selected pair:")
                    print(f"1. [ID: {dup['id']}] {dup['title']}")
                    print(f"2. [ID: {dup['duplicate_id']}] {dup['duplicate_title']}")
                    
                    action = input("Action (k=keep 1/d=keep 2/m=merge/s=skip): ")
                    
                    if action.lower() == 'k':
                        # Keep first, delete second
                        cursor.execute("DELETE FROM scraped_recipes WHERE id = %s", (dup['duplicate_id'],))
                        conn.commit()
                        print(f"Deleted duplicate [ID: {dup['duplicate_id']}] {dup['duplicate_title']}")
                    
                    elif action.lower() == 'd':
                        # Keep second, delete first
                        cursor.execute("DELETE FROM scraped_recipes WHERE id = %s", (dup['id'],))
                        conn.commit()
                        print(f"Deleted duplicate [ID: {dup['id']}] {dup['title']}")
                    
                    elif action.lower() == 'm':
                        # Merge the two recipes
                        print("Merging not implemented yet")
                        # This would be a complex operation requiring decisions about
                        # which fields to keep from which recipe
                    
                    else:
                        print("Skipping this pair")
                
                except Exception as e:
                    conn.rollback()
                    print(f"Error handling duplicates: {str(e)}")
    except Exception as e:
        print(f"Error finding duplicates: {str(e)}")
    finally:
        conn.close()

def main_menu():
    """Display main menu and handle user input"""
    while True:
        print("\n===== Recipe Database Management =====")
        print("1. List recipes")
        print("2. Search recipes")
        print("3. Update recipe image")
        print("4. Update recipe title")
        print("5. Update recipe complexity")
        print("6. Update recipe ingredients")
        print("7. Update recipe instructions")
        print("8. Batch update image URLs from CSV")
        print("9. Clean up duplicate recipes")
        print("q. Quit")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # List recipes
            limit = int(input("Enter number of recipes to display: ") or "20")
            offset = int(input("Enter offset (0 for beginning): ") or "0")
            list_recipes(limit, offset)
            
        elif choice == '2':
            # Search recipes
            search_term = input("Enter search term: ")
            if search_term:
                list_recipes(search_term=search_term)
            
        elif choice == '3':
            # Update recipe image
            recipe_id = int(input("Enter recipe ID: "))
            new_image_url = input("Enter new image URL: ")
            update_recipe_image(recipe_id, new_image_url)
            
        elif choice == '4':
            # Update recipe title
            recipe_id = int(input("Enter recipe ID: "))
            new_title = input("Enter new title: ")
            update_recipe_title(recipe_id, new_title)
            
        elif choice == '5':
            # Update recipe complexity
            recipe_id = int(input("Enter recipe ID: "))
            print("Complexity options: easy, medium, complex")
            new_complexity = input("Enter new complexity: ")
            update_recipe_complexity(recipe_id, new_complexity)
            
        elif choice == '6':
            # Update recipe ingredients
            recipe_id = int(input("Enter recipe ID: "))
            update_recipe_ingredients(recipe_id)
            
        elif choice == '7':
            # Update recipe instructions
            recipe_id = int(input("Enter recipe ID: "))
            update_recipe_instructions(recipe_id)
            
        elif choice == '8':
            # Batch update image URLs
            csv_file = input("Enter CSV file path: ")
            batch_update_image_urls(csv_file)
            
        elif choice == '9':
            # Clean up duplicate recipes
            cleanup_recipe_duplicates()
            
        elif choice.lower() == 'q':
            print("Exiting...")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main_menu()
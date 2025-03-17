# database/recipe_storage.py
import json
import logging
from datetime import datetime
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

class RecipeStorage:
    """Store processed recipes in the database"""
    
    def __init__(self, db_connector):
        self.db_connector = db_connector
    
    def save_recipe(self, processed_recipe):
        """
        Save a processed recipe to the database
        
        Args:
            processed_recipe (dict): Processed recipe data
            
        Returns:
            int: Recipe ID if successful, None otherwise
        """
        conn = self.db_connector.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Log metadata for debugging
                logger.info(f"Recipe metadata: {processed_recipe.get('metadata', {})}")
                
                # Extract metadata fields
                metadata = processed_recipe.get('metadata', {})
                prep_time = metadata.get('prep_time')
                cook_time = metadata.get('cook_time')
                total_time = metadata.get('total_time')
                servings = metadata.get('servings')
                
                # Log the times to ensure they're being passed correctly
                logger.info(f"Saving recipe '{processed_recipe['title']}' with prep_time={prep_time}, cook_time={cook_time}")
                
                # Insert recipe
                cursor.execute("""
                    INSERT INTO scraped_recipes (
                        title, source, source_url, instructions, date_scraped, date_processed,
                        complexity, prep_time, cook_time, total_time, servings, cuisine,
                        is_verified, raw_content, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    processed_recipe['title'],
                    processed_recipe['source'],
                    processed_recipe['source_url'],
                    json.dumps(processed_recipe['instructions']),
                    datetime.now(),
                    datetime.now(),
                    processed_recipe['complexity'],
                    prep_time,  # Using variable instead of nested dict access
                    cook_time,  # Using variable instead of nested dict access
                    total_time,  # Using variable instead of nested dict access
                    servings,    # Using variable instead of nested dict access
                    metadata.get('cuisine'),
                    False,  # Not verified initially
                    processed_recipe.get('raw_content', ''),
                    json.dumps(metadata)
                ))
                
                recipe_id = cursor.fetchone()[0]
                
                # Insert ingredients
                if 'ingredients' in processed_recipe and processed_recipe['ingredients']:
                    ingredient_data = []
                    for ing in processed_recipe['ingredients']:
                        if isinstance(ing, str):
                            # Handle string ingredients
                            ingredient_data.append((
                                recipe_id,
                                ing,  # Name is the full string
                                None,  # No amount
                                None,  # No unit
                                None,  # No notes
                                None,  # No category
                                False  # Not a main ingredient by default
                            ))
                        else:
                            # Handle dictionary ingredients
                            ingredient_data.append((
                                recipe_id,
                                ing.get('name', ''),
                                str(ing.get('amount', '')) if ing.get('amount') else None,
                                ing.get('unit'),
                                ing.get('notes'),
                                ing.get('category'),
                                False  # Not a main ingredient by default
                            ))
                    
                    execute_values(cursor, """
                        INSERT INTO recipe_ingredients
                        (recipe_id, name, amount, unit, notes, category, is_main_ingredient)
                        VALUES %s
                    """, ingredient_data)
                
                # Insert tags
                if 'tags' in processed_recipe and processed_recipe['tags']:
                    tag_data = [(recipe_id, tag) for tag in processed_recipe['tags']]
                    
                    execute_values(cursor, """
                        INSERT INTO recipe_tags
                        (recipe_id, tag)
                        VALUES %s
                    """, tag_data)
                
                # Insert nutrition if available
                if 'nutrition' in processed_recipe and processed_recipe['nutrition']:
                    nutrition = processed_recipe['nutrition']
                    cursor.execute("""
                        INSERT INTO recipe_nutrition
                        (recipe_id, calories, protein, carbs, fat, fiber, sugar, is_calculated)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        recipe_id,
                        nutrition.get('calories'),
                        nutrition.get('protein'),
                        nutrition.get('carbs'),
                        nutrition.get('fat'),
                        nutrition.get('fiber'),
                        nutrition.get('sugar'),
                        True
                    ))
                
                conn.commit()
                logger.info(f"Successfully saved recipe '{processed_recipe['title']}' with ID {recipe_id}")
                return recipe_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving recipe '{processed_recipe.get('title', 'Unknown')}': {str(e)}")
            return None
        finally:
            conn.close()
    
    def save_recipes(self, processed_recipes):
        """
        Save multiple processed recipes to the database
        
        Args:
            processed_recipes (list): List of processed recipe dictionaries
            
        Returns:
            int: Number of successfully saved recipes
        """
        success_count = 0
        for recipe in processed_recipes:
            if self.save_recipe(recipe):
                success_count += 1
        
        return success_count
    
    def recipe_exists(self, recipe_title, source_url):
        """
        Check if a recipe already exists in the database
        
        Args:
            recipe_title (str): Recipe title
            source_url (str): Source URL
            
        Returns:
            bool: True if recipe exists, False otherwise
        """
        conn = self.db_connector.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM scraped_recipes
                    WHERE title = %s OR source_url = %s
                    LIMIT 1
                """, (recipe_title, source_url))
                
                return cursor.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking if recipe exists: {str(e)}")
            return False
        finally:
            conn.close()

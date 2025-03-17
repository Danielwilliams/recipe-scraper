# database/recipe_storage.py
import json
import logging
from datetime import datetime
from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)

class RecipeStorage:
    """Store processed recipes in the database"""
    
    def save_recipe(self, recipe):
        """
        Save a recipe to the database
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            int: Recipe ID if successful, None otherwise
        """
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
                    logger.info(f"Recipe already exists: {recipe['title']}")
                    return existing[0]
                
                # Extract metadata fields for logging and clarity
                metadata = recipe.get('metadata', {})
                prep_time = metadata.get('prep_time')
                cook_time = metadata.get('cook_time')
                total_time = metadata.get('total_time')
                servings = metadata.get('servings')
                
                # Log the extracted times
                logger.info(f"Saving recipe '{recipe['title']}' with prep_time={prep_time}, cook_time={cook_time}")
                
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
                    recipe['title'],
                    recipe['source'],
                    recipe['source_url'],
                    json.dumps(recipe['instructions']),
                    datetime.now(),
                    datetime.now(),
                    recipe['complexity'],
                    prep_time,  # Using variables instead of nested dict access
                    cook_time,
                    total_time,
                    servings,
                    metadata.get('cuisine'),
                    False,  # Not verified initially
                    recipe.get('raw_content', '')[:1000],  # Limit raw content size
                    json.dumps(metadata)
                ))
                
                recipe_id = cursor.fetchone()[0]
                
                # Insert ingredients
                if 'ingredients' in recipe and recipe['ingredients']:
                    for ing in recipe['ingredients']:
                        if isinstance(ing, dict):
                            # Handle structured ingredient
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, amount, unit, notes, category)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                recipe_id,
                                ing.get('name', ''),
                                ing.get('amount'),
                                ing.get('unit'),
                                ing.get('notes'),
                                ing.get('category', 'unknown')
                            ))
                        else:
                            # Handle string ingredient
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, category)
                                VALUES (%s, %s, %s)
                            """, (
                                recipe_id,
                                ing if isinstance(ing, str) else str(ing),
                                'unknown'
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
                
                # Insert nutrition if available
                if 'nutrition' in recipe and recipe['nutrition']:
                    nutrition = recipe['nutrition']
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
                logger.info(f"Saved recipe '{recipe['title']}' with ID {recipe_id}")
                return recipe_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
            return None
        finally:
            conn.close()

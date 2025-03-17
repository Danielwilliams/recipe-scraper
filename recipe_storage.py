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
                
                # Insert recipe
                cursor.execute("""
                    INSERT INTO scraped_recipes (
                        title, source, source_url, instructions, date_scraped, date_processed,
                        complexity, prep_time, cook_time, total_time, servings, cuisine,
                        is_verified, raw_content, metadata, image_url, categories
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    recipe['title'],
                    recipe['source'],
                    recipe['source_url'],
                    json.dumps(recipe['instructions']),
                    datetime.now(),
                    datetime.now(),
                    recipe['complexity'],
                    recipe['metadata'].get('prep_time'),
                    recipe['metadata'].get('cook_time'),
                    recipe['metadata'].get('total_time'),
                    recipe['metadata'].get('servings'),
                    recipe.get('cuisine'),
                    False,  # Not verified initially
                    recipe.get('raw_content', '')[:5000],  # Limit raw content size
                    json.dumps(recipe['metadata']),
                    recipe.get('image_url'),
                    json.dumps(recipe.get('categories', []))
                ))
                
                recipe_id = cursor.fetchone()[0]
                
                # Insert ingredients
                if 'ingredients' in recipe and recipe['ingredients']:
                    for ing in recipe['ingredients']:
                        # Handle structured ingredient parsing
                        if isinstance(ing, dict):
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, amount, unit, notes, category)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (
                                recipe_id,
                                ing.get('name', ''),
                                str(ing.get('amount')) if ing.get('amount') is not None else None,
                                ing.get('unit'),
                                ing.get('notes'),
                                ing.get('category', 'unknown')
                            ))
                        else:
                            # Fallback for string ingredients
                            cursor.execute("""
                                INSERT INTO recipe_ingredients
                                (recipe_id, name, category)
                                VALUES (%s, %s, %s)
                            """, (
                                recipe_id,
                                str(ing),
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
                
                # Insert nutrition information
                if recipe.get('nutrition'):
                    nutrition = recipe['nutrition']
                    cursor.execute("""
                        INSERT INTO recipe_nutrition (
                            recipe_id, calories, protein, carbs, fat, 
                            saturated_fat, cholesterol, sodium, 
                            total_sugars, added_sugars, fiber, 
                            potassium, nutrition_profiles, is_calculated
                        ) VALUES (
                            %s, %s, %s, %s, %s, 
                            %s, %s, %s, 
                            %s, %s, %s, 
                            %s, %s, %s
                        )
                    """, (
                        recipe_id,
                        nutrition.get('calories'),
                        nutrition.get('protein'),
                        nutrition.get('carbs'),
                        nutrition.get('fat'),
                        nutrition.get('saturated_fat'),
                        nutrition.get('cholesterol'),
                        nutrition.get('sodium'),
                        nutrition.get('total_sugars'),
                        nutrition.get('added_sugars'),
                        nutrition.get('fiber'),
                        nutrition.get('potassium'),
                        recipe.get('nutrition_profiles', []),
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

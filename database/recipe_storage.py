# database/recipe_storage.py
import json
import logging
from datetime import datetime
from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)

class RecipeStorage:
    """Store processed recipes in the database"""
    
    # database/recipe_storage.py - Update the save_recipe method to handle updating existing entries

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
                    SELECT id, image_url, instructions, prep_time, cook_time, servings 
                    FROM scraped_recipes
                    WHERE title = %s AND source = %s
                    LIMIT 1
                """, (recipe['title'], recipe['source']))
                
                existing = cursor.fetchone()
                if existing:
                    # Recipe exists - check if we need to update it
                    recipe_id = existing[0]
                    existing_image_url = existing[1]
                    existing_instructions = existing[2] if isinstance(existing[2], list) else json.loads(existing[2])
                    
                    # Get metadata fields for comparison
                    existing_prep_time = existing[3]
                    existing_cook_time = existing[4]
                    existing_servings = existing[5]
                    
                    # Flag to track if we need to update
                    needs_update = False
                    update_fields = []
                    
                    # Check for missing image URL
                    if not existing_image_url and recipe.get('image_url'):
                        needs_update = True
                        update_fields.append("image_url")
                    
                    # Check for improved instructions (more steps)
                    if (len(recipe.get('instructions', [])) > len(existing_instructions)):
                        needs_update = True
                        update_fields.append("instructions")
                    
                    # Check for added metadata
                    metadata = recipe.get('metadata', {})
                    new_metadata = {}
                    
                    if not existing_prep_time and metadata.get('prep_time'):
                        new_metadata['prep_time'] = metadata.get('prep_time')
                        needs_update = True
                        update_fields.append("prep_time")
                    
                    if not existing_cook_time and metadata.get('cook_time'):
                        new_metadata['cook_time'] = metadata.get('cook_time')
                        needs_update = True
                        update_fields.append("cook_time")
                    
                    if not existing_servings and metadata.get('servings'):
                        new_metadata['servings'] = metadata.get('servings')
                        needs_update = True
                        update_fields.append("servings")
                    
                    if needs_update:
                        # Build the update SQL dynamically
                        update_sql = "UPDATE scraped_recipes SET "
                        params = []
                        
                        if "image_url" in update_fields:
                            update_sql += "image_url = %s, "
                            params.append(recipe.get('image_url'))
                        
                        if "instructions" in update_fields:
                            update_sql += "instructions = %s, "
                            params.append(json.dumps(recipe.get('instructions')))
                        
                        if "prep_time" in update_fields:
                            update_sql += "prep_time = %s, "
                            params.append(metadata.get('prep_time'))
                        
                        if "cook_time" in update_fields:
                            update_sql += "cook_time = %s, "
                            params.append(metadata.get('cook_time'))
                        
                        if "servings" in update_fields:
                            update_sql += "servings = %s, "
                            params.append(metadata.get('servings'))
                        
                        # Remove trailing comma and add WHERE clause
                        update_sql = update_sql.rstrip(", ") + " WHERE id = %s"
                        params.append(recipe_id)
                        
                        # Execute the update
                        cursor.execute(update_sql, params)
                        conn.commit()
                        
                        logger.info(f"Updated recipe '{recipe['title']}' (ID: {recipe_id}) with new data: {', '.join(update_fields)}")
                    else:
                        logger.info(f"Recipe already exists and no updates needed: {recipe['title']}")
                    
                    return recipe_id
                
                # Recipe doesn't exist - insert it
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

# database/recipe_storage.py - FIXED VERSION
import json
import logging
from datetime import datetime
from database.db_connector import get_db_connection

logger = logging.getLogger(__name__)

class RecipeStorage:
    """Store processed recipes in the database"""
    
    def _validate_recipe(self, recipe):
        """
        Validate recipe has required fields and data
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            bool: True if recipe is valid, False otherwise
        """
        # Check required fields
        if not recipe.get('title'):
            logger.warning("Recipe missing title")
            return False
            
        # Check ingredients
        if not recipe.get('ingredients') or len(recipe.get('ingredients', [])) < 2:
            logger.warning(f"Recipe '{recipe.get('title')}' has insufficient ingredients")
            return False
            
        # Check instructions
        if not recipe.get('instructions') or len(recipe.get('instructions', [])) < 2:
            logger.warning(f"Recipe '{recipe.get('title')}' has insufficient instructions")
            return False
            
        return True

    def parse_iso_duration(self, iso_duration):
        """
        Parse ISO 8601 duration to minutes
        
        Args:
            iso_duration (str): ISO 8601 duration string (e.g., 'PT15M')
            
        Returns:
            int: Duration in minutes or None if parsing fails
        """
        if not iso_duration:
            return None
        
        try:
            import re
            # Handle PT1H30M format (ISO 8601 duration)
            hours_match = re.search(r'PT(?:(\d+)H)?', iso_duration)
            minutes_match = re.search(r'PT(?:[^M]*?)(\d+)M', iso_duration)
            
            hours = int(hours_match.group(1)) if hours_match and hours_match.group(1) else 0
            minutes = int(minutes_match.group(1)) if minutes_match and minutes_match.group(1) else 0
            
            total_minutes = hours * 60 + minutes
            return total_minutes if total_minutes > 0 else None
        except Exception as e:
            logger.error(f"Error parsing ISO duration {iso_duration}: {str(e)}")
            return None
        
    def save_recipe(self, recipe):
        """
        Save a recipe to the database with validation
        
        Args:
            recipe (dict): Recipe data
            
        Returns:
            int: Recipe ID if successful, None otherwise
        """
        # Validate recipe before saving
        if not self._validate_recipe(recipe):
            logger.warning(f"Skipping invalid recipe: {recipe.get('title', 'Unknown')}")
            return None
            
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
                    existing_instructions = existing[2] if isinstance(existing[2], list) else json.loads(existing[2]) if existing[2] else []
                    
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
                    if len(recipe.get('instructions', [])) > len(existing_instructions):
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
                
                # Recipe doesn't exist - insert it with dynamic column mapping
                logger.info(f"Inserting new recipe: {recipe['title']}")

                # Check which columns exist in the scraped_recipes table
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'scraped_recipes'
                    AND table_schema = 'public'
                """)
                available_columns = {row[0] for row in cursor.fetchall()}
                logger.debug(f"Available columns: {available_columns}")

                # Prepare JSONB values properly
                instructions_json = json.dumps(recipe.get('instructions', []))
                metadata_json = json.dumps(recipe.get('metadata', {}))
                categories_json = json.dumps(recipe.get('categories', []))

                # Handle new JSONB columns with defaults
                diet_tags_json = json.dumps([])  # Empty array as default
                flavor_profile_json = json.dumps([])  # Empty array as default
                appliances_json = json.dumps([])  # Empty array as default

                # Define all possible columns and their values
                all_columns = {
                    'title': recipe['title'],
                    'source': recipe['source'],
                    'source_url': recipe['source_url'],
                    'instructions': instructions_json,
                    'date_scraped': datetime.now(),
                    'date_processed': datetime.now(),
                    'complexity': recipe.get('complexity'),
                    'prep_time': recipe.get('metadata', {}).get('prep_time'),
                    'cook_time': recipe.get('metadata', {}).get('cook_time'),
                    'total_time': recipe.get('metadata', {}).get('total_time'),
                    'servings': recipe.get('metadata', {}).get('servings'),
                    'cuisine': recipe.get('cuisine'),
                    'is_verified': False,
                    'raw_content': recipe.get('raw_content', '')[:5000] if recipe.get('raw_content') else '',
                    'metadata': metadata_json,
                    'image_url': recipe.get('image_url'),
                    'categories': categories_json,
                    'component_type': None,
                    'diet_tags': diet_tags_json,
                    'flavor_profile': flavor_profile_json,
                    'cooking_method': None,
                    'meal_part': None,
                    'notes': recipe.get('notes'),  # Include notes when available
                    'spice_level': None,
                    'diet_type': None,
                    'meal_prep_type': None,
                    'appliances': appliances_json
                }

                # Build dynamic INSERT statement with only available columns
                insert_columns = []
                insert_values = []
                placeholders = []

                for col_name, col_value in all_columns.items():
                    if col_name in available_columns:
                        insert_columns.append(col_name)
                        insert_values.append(col_value)
                        # Handle JSONB columns
                        if col_name in ['instructions', 'metadata', 'categories', 'diet_tags', 'flavor_profile', 'appliances']:
                            placeholders.append('%s::jsonb')
                        else:
                            placeholders.append('%s')

                # Create the INSERT SQL dynamically
                insert_sql = f"""
                    INSERT INTO scraped_recipes ({', '.join(insert_columns)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING id
                """

                logger.debug(f"Insert SQL: {insert_sql}")
                logger.debug(f"Inserting {len(insert_columns)} columns")

                cursor.execute(insert_sql, insert_values)
                
                recipe_id = cursor.fetchone()[0]
                logger.info(f"Successfully inserted recipe '{recipe['title']}' with ID {recipe_id}")
                
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
                
                # Insert nutrition if available (check if table exists first)
                if 'nutrition' in recipe and recipe['nutrition']:
                    try:
                        nutrition = recipe['nutrition']
                        cursor.execute("""
                            INSERT INTO recipe_nutrition
                            (recipe_id, calories, protein, carbs, fat)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            recipe_id,
                            nutrition.get('calories'),
                            nutrition.get('protein'),
                            nutrition.get('carbs'),
                            nutrition.get('fat')
                        ))
                    except Exception as e:
                        logger.warning(f"Could not insert nutrition data: {e}")
                
                conn.commit()
                logger.info(f"Saved recipe '{recipe['title']}' with ID {recipe_id}")
                return recipe_id
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving recipe '{recipe.get('title', 'Unknown')}': {str(e)}")
            logger.error(f"Full error details: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
        finally:
            conn.close()
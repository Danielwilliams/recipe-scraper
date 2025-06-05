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
                # Check if recipe already exists by title only (regardless of source)
                cursor.execute("""
                    SELECT id
                    FROM scraped_recipes
                    WHERE title = %s
                    LIMIT 1
                """, (recipe['title'],))

                existing = cursor.fetchone()

                if existing:
                    # Recipe exists - skip it
                    recipe_id = existing[0]
                    logger.info(f"Recipe with title '{recipe['title']}' already exists (ID: {recipe_id}) - skipping")
                    return recipe_id  # Return the existing ID and skip further processing
                
                # Recipe doesn't exist - insert it with FIXED column mapping
                logger.info(f"Inserting new recipe: {recipe['title']}")
                
                # Prepare JSONB values properly
                instructions_json = json.dumps(recipe.get('instructions', []))
                metadata_json = json.dumps(recipe.get('metadata', {}))
                categories_json = json.dumps(recipe.get('categories', []))
                
                # Handle new JSONB columns with defaults
                diet_tags_json = json.dumps([])  # Empty array as default
                flavor_profile_json = json.dumps([])  # Empty array as default 
                appliances_json = json.dumps([])  # Empty array as default
                
                # Since we're skipping recipes with the same title, we can always use the auto-increment ID
                cursor.execute("""
                        INSERT INTO scraped_recipes (
                            title, source, source_url, instructions, date_scraped, date_processed,
                            complexity, prep_time, cook_time, total_time, servings, cuisine,
                            is_verified, raw_content, metadata, image_url, categories,
                            component_type, diet_tags, flavor_profile, cooking_method, meal_part,
                            notes, spice_level, diet_type, meal_prep_type, appliances
                        ) VALUES (
                            %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb,
                            %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s::jsonb
                        ) RETURNING id
                    """, (
                        recipe['title'],
                        recipe['source'],
                        recipe['source_url'],
                        instructions_json,  # JSONB
                        datetime.now(),
                        datetime.now(),
                        recipe.get('complexity'),
                        recipe.get('metadata', {}).get('prep_time'),
                        recipe.get('metadata', {}).get('cook_time'),
                        recipe.get('metadata', {}).get('total_time'),
                        recipe.get('metadata', {}).get('servings'),
                        recipe.get('cuisine'),
                        False,  # Not verified initially
                        recipe.get('raw_content', '')[:5000] if recipe.get('raw_content') else '',
                        metadata_json,  # JSONB
                        recipe.get('image_url'),
                        categories_json,  # JSONB
                        None,  # component_type (will be tagged later)
                        diet_tags_json,  # JSONB array
                        flavor_profile_json,  # JSONB array
                        None,  # cooking_method (will be tagged later)
                        None,  # meal_part (will be tagged later)
                        None,  # notes
                        None,  # spice_level (will be tagged later)
                        None,  # diet_type (will be tagged later)
                        None,  # meal_prep_type (will be tagged later)
                        appliances_json  # JSONB array
                    ))
                
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
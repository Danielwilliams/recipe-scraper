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
            iso_duration (str|int): ISO 8601 duration string (e.g., 'PT15M') or integer minutes

        Returns:
            int: Duration in minutes or None if parsing fails
        """
        if not iso_duration:
            return None

        try:
            # If it's already a number, just return it
            if isinstance(iso_duration, (int, float)):
                return int(iso_duration)

            # Convert to string if it's not already
            iso_duration = str(iso_duration)

            # If it's just a number string, return as integer
            if iso_duration.isdigit():
                return int(iso_duration)

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
                # Check if recipe already exists - first try by ID if provided
                if recipe.get('id'):
                    cursor.execute("""
                        SELECT id, image_url, instructions, prep_time, cook_time, servings
                        FROM scraped_recipes
                        WHERE id = %s
                        LIMIT 1
                    """, (recipe['id'],))
                    existing = cursor.fetchone()
                    if existing:
                        logger.info(f"Recipe found by ID: {recipe['id']}")

                # If not found by ID, check by title only (regardless of source)
                if not existing:
                    cursor.execute("""
                        SELECT id
                        FROM scraped_recipes
                        WHERE title = %s
                        LIMIT 1
                    """, (recipe['title'],))
                    existing = cursor.fetchone()
                    if existing:
                        logger.info(f"Recipe with title '{recipe['title']}' already exists (ID: {existing[0]}) - skipping")
                        return existing[0]  # Return the existing ID and skip further processing

                # Recipe doesn't exist - proceed with insertion
                # We'll handle this in the next section where we insert the new recipe

                # Note: The previous update logic has been removed since we're now
                # simply skipping recipes that already exist by title
                
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

                # Handle new columns with defaults - diet_tags and flavor_profile are TEXT[] not JSONB
                diet_tags_array = []  # Empty array for TEXT[] type
                flavor_profile_array = []  # Empty array for TEXT[] type
                appliances_json = json.dumps([])  # Empty array as default for JSONB

                # Define all possible columns and their values
                all_columns = {
                    'title': recipe['title'],
                    'source': recipe['source'],
                    'source_url': recipe['source_url'],
                    'instructions': instructions_json,
                    'date_scraped': datetime.now(),
                    'date_processed': datetime.now(),
                    'complexity': recipe.get('complexity'),
                    'prep_time': self.parse_iso_duration(recipe.get('metadata', {}).get('prep_time')),
                    'cook_time': self.parse_iso_duration(recipe.get('metadata', {}).get('cook_time')),
                    'total_time': self.parse_iso_duration(recipe.get('metadata', {}).get('total_time')),
                    'servings': recipe.get('metadata', {}).get('servings'),
                    'cuisine': recipe.get('cuisine'),
                    'is_verified': False,
                    'raw_content': recipe.get('raw_content', '')[:5000] if recipe.get('raw_content') else '',
                    'metadata': metadata_json,
                    'image_url': recipe.get('image_url'),
                    'categories': categories_json,
                    'component_type': None,
                    'diet_tags': diet_tags_array,
                    'flavor_profile': flavor_profile_array,
                    'cooking_method': None,
                    'meal_part': None,
                    'notes': recipe.get('notes'),  # Include notes when available
                    'spice_level': None,
                    'diet_type': None,
                    'meal_prep_type': None,
                    'appliances': appliances_json
                }

                # We're now skipping recipes with the same title, so we don't need to worry about ID conflicts

                # Build dynamic INSERT statement with only available columns
                insert_columns = []
                insert_values = []
                placeholders = []

                for col_name, col_value in all_columns.items():
                    if col_name in available_columns:
                        insert_columns.append(col_name)
                        insert_values.append(col_value)
                        # Handle JSONB columns (diet_tags and flavor_profile are TEXT[] not JSONB)
                        if col_name in ['instructions', 'metadata', 'categories', 'appliances']:
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
#!/usr/bin/env python
# test_duplicate_handling.py - Test the handling of duplicate recipes

import sys
import logging
from datetime import datetime
import json
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('test_duplicate_handling')

def test_duplicate_handling():
    """Test how the system handles duplicate recipe titles"""
    try:
        # Import modules
        from database.recipe_storage import RecipeStorage
        
        # Create a sample recipe
        test_recipe = {
            'title': 'Test Duplicate Recipe ' + datetime.now().strftime('%Y%m%d%H%M%S'),
            'source': 'Test Source',
            'source_url': 'https://example.com/recipe',
            'instructions': ['Step 1', 'Step 2', 'Step 3'],
            'ingredients': ['Ingredient 1', 'Ingredient 2', 'Ingredient 3'],
            'complexity': 'easy',
            'metadata': {
                'prep_time': 15,
                'cook_time': 30,
                'total_time': 45,
                'servings': 4,
                'notes': 'Test notes'
            }
        }
        
        # Initialize recipe storage
        storage = RecipeStorage()
        
        # First insertion should succeed
        logger.info("Inserting test recipe for the first time...")
        recipe_id = storage.save_recipe(test_recipe)
        if recipe_id:
            logger.info(f"✅ First insertion successful - Recipe ID: {recipe_id}")
        else:
            logger.error("❌ First insertion failed")
            return
            
        # Second insertion with same title should be skipped
        logger.info("Attempting to insert the same recipe again...")
        second_recipe_id = storage.save_recipe(test_recipe)
        
        if second_recipe_id and second_recipe_id == recipe_id:
            logger.info(f"✅ Second insertion correctly returned existing ID: {second_recipe_id}")
        else:
            logger.error("❌ Second insertion should have returned the existing ID but didn't")
            
        # Third insertion with different title should succeed
        test_recipe['title'] = 'Modified ' + test_recipe['title']
        logger.info("Inserting recipe with modified title...")
        third_recipe_id = storage.save_recipe(test_recipe)
        
        if third_recipe_id and third_recipe_id != recipe_id:
            logger.info(f"✅ Third insertion with different title succeeded - Recipe ID: {third_recipe_id}")
        else:
            logger.error("❌ Third insertion with different title failed")
            
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_duplicate_handling()
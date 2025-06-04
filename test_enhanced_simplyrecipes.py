#!/usr/bin/env python3
"""
Test script for the enhanced Simply Recipes scraper

This script tests the enhanced Simply Recipes scraper on specific recipes
to verify that it correctly extracts all the required data.
"""

import logging
import sys
import json
from scrapers.enhanced_simplyrecipes_scraper import EnhancedSimplyRecipesScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_scraper():
    """Test the enhanced Simply Recipes scraper"""
    
    # Sample URLs to test, including the problematic Cassava Cake recipe
    test_urls = [
        "https://www.simplyrecipes.com/cassava-cake-recipe-6832078",  # Problematic recipe
        "https://www.simplyrecipes.com/sheet-pan-shrimp-and-asparagus-recipe-5207690",
        "https://www.simplyrecipes.com/recipes/homemade_chicken_noodle_soup/"
    ]
    
    scraper = EnhancedSimplyRecipesScraper()
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        try:
            recipe = scraper._scrape_recipe(url)
            if recipe:
                print(f"Recipe title: {recipe['title']}")
                print(f"Prep time: {recipe['metadata'].get('prep_time')} minutes")
                print(f"Cook time: {recipe['metadata'].get('cook_time')} minutes")
                print(f"Total time: {recipe['metadata'].get('total_time')} minutes")
                print(f"Servings: {recipe['metadata'].get('servings')}")
                print(f"Ingredients count: {len(recipe['ingredients'])}")
                print(f"Instructions count: {len(recipe['instructions'])}")
                print(f"Notes count: {len(recipe.get('notes', []))}")
                print(f"Image URL: {recipe.get('image_url', 'None')}")
                
                # Print all ingredients to verify they're extracted correctly
                print("\nAll ingredients:")
                for i, ingredient in enumerate(recipe['ingredients']):
                    print(f"  {i+1}. {ingredient}")
                
                print("\nSample instructions:")
                for i, instruction in enumerate(recipe['instructions'][:3]):
                    print(f"  {i+1}. {instruction}")
                
                if len(recipe['instructions']) > 3:
                    print(f"  ... and {len(recipe['instructions']) - 3} more steps")
                
                # Save recipe to JSON file for inspection
                filename = f"recipe_simplyrecipes_{recipe['title'].lower().replace(' ', '_')[:30]}.json"
                with open(filename, 'w') as f:
                    json.dump(recipe, f, indent=2)
                print(f"\nSaved full recipe data to {filename}")
            else:
                print("Failed to extract recipe data")
        except Exception as e:
            print(f"Error scraping recipe: {e}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    test_scraper()
#!/usr/bin/env python3
"""
Test script for the enhanced Pinch of Yum scraper

This script tests the enhanced Pinch of Yum scraper by scraping a few recipes
and printing the extracted data for verification.
"""

import logging
import sys
import json
from scrapers.enhanced_pinchofyum_scraper import EnhancedPinchOfYumScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_enhanced_scraper():
    """Test the enhanced Pinch of Yum scraper"""
    
    # Sample URLs to test
    test_urls = [
        "https://pinchofyum.com/instant-pot-minestrone-soup",
        "https://pinchofyum.com/miracle-no-knead-bread",
        "https://pinchofyum.com/buffalo-chicken-wraps"
    ]
    
    scraper = EnhancedPinchOfYumScraper()
    
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
                print(f"Yield: {recipe['metadata'].get('yield')}")
                print(f"Ingredients count: {len(recipe['ingredients'])}")
                print(f"Instructions count: {len(recipe['instructions'])}")
                print(f"Notes count: {len(recipe.get('notes', []))}")
                print(f"Image URL: {recipe.get('image_url', 'None')}")
                
                # Print sample of ingredients and instructions
                print("\nSample ingredients:")
                for i, ingredient in enumerate(recipe['ingredients'][:5]):
                    print(f"  {i+1}. {ingredient}")
                
                if len(recipe['ingredients']) > 5:
                    print(f"  ... and {len(recipe['ingredients']) - 5} more ingredients")
                
                print("\nSample instructions:")
                for i, instruction in enumerate(recipe['instructions'][:3]):
                    print(f"  {i+1}. {instruction}")
                
                if len(recipe['instructions']) > 3:
                    print(f"  ... and {len(recipe['instructions']) - 3} more steps")
                
                if recipe.get('notes'):
                    print("\nSample notes:")
                    for i, note in enumerate(recipe['notes'][:2]):
                        print(f"  - {note}")
                    
                    if len(recipe['notes']) > 2:
                        print(f"  ... and {len(recipe['notes']) - 2} more notes")
                
                # Save recipe to JSON file for inspection
                filename = f"recipe_{recipe['title'].lower().replace(' ', '_')}.json"
                with open(filename, 'w') as f:
                    json.dump(recipe, f, indent=2)
                print(f"\nSaved full recipe data to {filename}")
            else:
                print("Failed to extract recipe data")
        except Exception as e:
            print(f"Error scraping recipe: {e}")
    
    print("\nTesting category scraping...")
    try:
        category_url = "https://pinchofyum.com/recipes/dinner"
        links = scraper._get_recipe_links(category_url, 5)
        print(f"Found {len(links)} recipe links on category page")
        for link in links:
            print(f"  - {link}")
    except Exception as e:
        print(f"Error scraping category: {e}")

if __name__ == "__main__":
    test_enhanced_scraper()
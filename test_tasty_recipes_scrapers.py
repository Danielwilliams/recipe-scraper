#!/usr/bin/env python3
"""
Test script for all Tasty Recipes format scrapers

This script tests all the scrapers that target websites using the Tasty Recipes plugin
by scraping one recipe from each site and printing the extracted data.
"""

import logging
import sys
import json
import time
from scrapers.enhanced_pinchofyum_scraper import EnhancedPinchOfYumScraper
from scrapers.host_the_toast_scraper import HostTheToastScraper
from scrapers.fit_fab_fodmap_scraper import FitFabFodmapScraper
from scrapers.pickled_plum_scraper import PickledPlumScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def test_scrapers():
    """Test all Tasty Recipes format scrapers"""
    
    # Sample URLs to test for each site
    test_urls = {
        "Pinch of Yum": [
            "https://pinchofyum.com/instant-pot-minestrone-soup"
        ],
        "Host the Toast": [
            "https://hostthetoast.com/the-best-french-onion-soup/"
        ],
        "Fit Fab Fodmap": [
            "https://www.fitfabfodmap.com/low-fodmap-chicken-tikka-masala/"
        ],
        "Pickled Plum": [
            "https://pickledplum.com/chicken-cacciatore/"
        ]
    }
    
    # Initialize all scrapers
    scrapers = {
        "Pinch of Yum": EnhancedPinchOfYumScraper(),
        "Host the Toast": HostTheToastScraper(),
        "Fit Fab Fodmap": FitFabFodmapScraper(),
        "Pickled Plum": PickledPlumScraper()
    }
    
    results = {}
    
    # Test each scraper with sample URLs
    for site_name, scraper in scrapers.items():
        print(f"\n{'='*40}")
        print(f"Testing {site_name} scraper")
        print(f"{'='*40}")
        
        site_results = []
        
        for url in test_urls[site_name]:
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
                    
                    # Save recipe to JSON file for inspection
                    filename = f"recipe_{site_name.lower().replace(' ', '_')}_{recipe['title'].lower().replace(' ', '_')[:30]}.json"
                    with open(filename, 'w') as f:
                        json.dump(recipe, f, indent=2)
                    print(f"\nSaved full recipe data to {filename}")
                    
                    site_results.append({
                        "url": url,
                        "title": recipe['title'],
                        "success": True,
                        "ingredients_count": len(recipe['ingredients']),
                        "instructions_count": len(recipe['instructions']),
                        "has_times": bool(recipe['metadata'].get('prep_time') or recipe['metadata'].get('cook_time')),
                        "has_servings": bool(recipe['metadata'].get('servings')),
                        "has_image": bool(recipe.get('image_url'))
                    })
                else:
                    print("Failed to extract recipe data")
                    site_results.append({
                        "url": url,
                        "success": False
                    })
            except Exception as e:
                print(f"Error scraping recipe: {e}")
                site_results.append({
                    "url": url,
                    "success": False,
                    "error": str(e)
                })
            
            # Add delay between requests
            time.sleep(2)
        
        results[site_name] = site_results
    
    # Print summary
    print("\n\n" + "="*60)
    print("SUMMARY OF TEST RESULTS")
    print("="*60)
    
    for site_name, site_results in results.items():
        success_count = sum(1 for r in site_results if r["success"])
        print(f"\n{site_name}: {success_count}/{len(site_results)} successful")
        
        for result in site_results:
            if result["success"]:
                print(f"  ✓ {result['title']} - {result['ingredients_count']} ingredients, {result['instructions_count']} instructions")
            else:
                print(f"  ✗ {result['url']} - Failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_scrapers()
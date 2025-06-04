#!/usr/bin/env python3
"""
Test script to manually extract ingredients from a recipe URL
"""

import requests
import json
import re
from bs4 import BeautifulSoup

def extract_ingredients(url):
    """
    Extract ingredients from a recipe URL using BeautifulSoup
    
    Args:
        url (str): URL of the recipe to test
        
    Returns:
        list: Extracted ingredients
    """
    print(f"Testing ingredient extraction from: {url}")
    
    # Get the page content
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"Response status: {response.status_code}")
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the Tasty Recipes container
        tasty_container = soup.select_one('.tasty-recipes')
        if not tasty_container:
            print("No Tasty Recipes container found, trying entry content")
            tasty_container = soup.select_one('.entry-content')
            
        if not tasty_container:
            print("No container found")
            return []
            
        print("Found recipe container")
        
        # List to store ingredients
        ingredients = []
        
        # First try the modern format with checkboxes
        checkbox_ingredients = tasty_container.select('li[data-tr-ingredient-checkbox]')
        if checkbox_ingredients:
            print(f"Found {len(checkbox_ingredients)} ingredients with modern checkbox format")
            for item in checkbox_ingredients:
                ingredient_text = item.get_text().strip()
                if ingredient_text:
                    ingredients.append(ingredient_text)
        else:
            print("No checkbox ingredients found")
            
        # If no ingredients found with checkboxes, try other methods
        if not ingredients:
            print("Trying traditional format...")
            ingredients_section = tasty_container.select_one('.tasty-recipes-ingredients, .tasty-recipes-ingredients-body')
            if ingredients_section:
                print("Found ingredients section")
                ingredient_items = ingredients_section.select('li')
                print(f"Found {len(ingredient_items)} ingredient items")
                
                for item in ingredient_items:
                    text = item.get_text().strip()
                    if text:
                        ingredients.append(text)
            else:
                print("No ingredients section found")
                
        # If still no ingredients, try JSON-LD
        if not ingredients:
            print("Trying JSON-LD extraction...")
            json_ld_scripts = soup.select('script[type="application/ld+json"]')
            print(f"Found {len(json_ld_scripts)} JSON-LD scripts")
            
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Look for Recipe type
                    if isinstance(data, dict) and data.get('@type') == 'Recipe' and 'recipeIngredient' in data:
                        ingredients = data['recipeIngredient']
                        print(f"Found {len(ingredients)} ingredients in JSON-LD")
                        break
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe' and 'recipeIngredient' in item:
                                ingredients = item['recipeIngredient']
                                print(f"Found {len(ingredients)} ingredients in JSON-LD array")
                                break
                except Exception as e:
                    print(f"Error parsing JSON-LD: {str(e)}")
                    continue
        
        return ingredients
        
    except Exception as e:
        print(f"Error extracting ingredients: {str(e)}")
        return []

def main():
    """Main test function"""
    # Test URLs
    test_urls = [
        "https://pinchofyum.com/cucumber-agua-fresca",
        "https://pinchofyum.com/coconut-curry-ramen",
        "https://www.simplyrecipes.com/cassava-cake-recipe-6832078"
    ]
    
    for url in test_urls:
        print(f"\n{'='*50}\nTesting URL: {url}\n{'='*50}")
        ingredients = extract_ingredients(url)
        
        if ingredients:
            print(f"\nExtracted {len(ingredients)} ingredients:")
            for i, ingredient in enumerate(ingredients):
                print(f"  {i+1}. {ingredient}")
        else:
            print("No ingredients extracted")
            
        print("\n")

if __name__ == "__main__":
    main()
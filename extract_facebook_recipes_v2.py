import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import html

def clean_html_entities(text: str) -> str:
    """Clean HTML entities from text"""
    # Common HTML entities found in the file
    text = text.replace('&amp;', '&')
    text = text.replace('&zwj;', '')
    text = text.replace('&nbsp;', ' ')
    return html.unescape(text)

def clean_emojis_and_symbols(text: str) -> str:
    """Remove emojis and special symbols but keep common punctuation"""
    # Remove number emojis like 1️⃣, 2️⃣
    text = re.sub(r'[\d️⃣]+', '', text)
    # Remove emoji and other non-ASCII characters
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_recipe_from_block(content: str) -> Optional[Dict[str, Any]]:
    """Extract a single recipe from a content block"""
    lines = content.split('\n')
    
    # First, extract source URL as we might need it for title
    source_url = ""
    for line in lines:
        if 'href="https://www.facebook.com/' in line:
            match = re.search(r'href="(https://www\.facebook\.com/[^"]+)"', line)
            if match:
                source_url = match.group(1)
                break
    
    # Find the recipe title (usually after href and before ingredients)
    title = None
    recipe_start_idx = -1
    
    for i, line in enumerate(lines):
        line = line.strip()
        # Skip HTML lines
        if 'href=' in line or 'class=' in line or line.startswith('<'):
            continue
        # Look for title patterns
        if line and not any(keyword in line.lower() for keyword in ['ingredients', 'directions', 'servings', 'prep time']):
            # Potential title - clean it up
            cleaned_line = clean_html_entities(line)
            cleaned_line = clean_emojis_and_symbols(cleaned_line)
            if cleaned_line and len(cleaned_line) > 10 and len(cleaned_line) < 200:
                title = cleaned_line[:95]  # Limit to 95 chars
                recipe_start_idx = i
                break
    
    # If title is just "Ingredients" or similar, use the source URL
    if title and title.lower().strip() in ['ingredients', 'ingredients:', 'ingredient list']:
        if source_url:
            title = f"Recipe from {source_url.split('/')[-1]}"
        else:
            title = "Untitled Recipe"
    
    if not title or recipe_start_idx == -1:
        return None
    
    # Extract ingredients
    ingredients = []
    in_ingredients = False
    ingredients_keywords = ['ingredients', 'ingredient list', 'ingredients:', '📋 ingredients', 'ingredients 🛒']
    
    for i in range(recipe_start_idx, len(lines)):
        line = clean_html_entities(lines[i].strip())
        line_lower = line.lower()
        
        # Check if we're entering ingredients section
        if any(keyword in line_lower for keyword in ingredients_keywords):
            in_ingredients = True
            continue
        
        # Check if we're leaving ingredients section
        if in_ingredients and any(keyword in line_lower for keyword in ['directions', 'instructions', 'method', 'directions:', '👩‍🍳 directions']):
            break
        
        # Extract ingredients
        if in_ingredients and line:
            # Skip metadata lines
            if any(skip in line_lower for skip in ['prep time', 'cook time', 'servings', 'calories', '⏰', '🍽', '🔥']):
                continue
            
            # Clean ingredient line
            ingredient = clean_emojis_and_symbols(line)
            ingredient = re.sub(r'^[\d\.\-\*•]+\s*', '', ingredient).strip()
            
            # Skip section headers like "For the Sauce:"
            if ingredient.endswith(':') and len(ingredient) < 30:
                continue
                
            if ingredient and len(ingredient) > 3:
                ingredients.append(ingredient)
    
    if not ingredients:
        return None
    
    # Extract instructions
    instructions = []
    in_instructions = False
    instructions_keywords = ['directions', 'instructions', 'method', 'directions:', '👩‍🍳 directions']
    
    for i in range(recipe_start_idx, len(lines)):
        line = clean_html_entities(lines[i].strip())
        line_lower = line.lower()
        
        # Check if we're entering instructions section
        if any(keyword in line_lower for keyword in instructions_keywords):
            in_instructions = True
            continue
        
        # Check if we're leaving instructions section  
        if in_instructions and (any(meta in line_lower for meta in ['prep time', 'cook time', 'servings', 'calories']) or line.startswith('#')):
            break
        
        # Extract instructions
        if in_instructions and line:
            # Clean instruction
            instruction = clean_emojis_and_symbols(line)
            # Remove step numbers
            instruction = re.sub(r'^\d+[\.\)]\s*', '', instruction).strip()
            
            if instruction and len(instruction) > 5:
                instructions.append(instruction)
    
    if not instructions:
        return None
    
    # Extract metadata
    metadata = {'cuisine': 'American'}  # Default
    nutrition = {}
    
    for i in range(recipe_start_idx, len(lines)):
        line = clean_html_entities(lines[i].strip())
        line_lower = line.lower()
        
        # Prep time
        if 'prep time' in line_lower or '⏰ prep' in line_lower:
            match = re.search(r'(\d+)\s*(?:minutes?|mins?)', line_lower)
            if match:
                metadata['prep_time'] = int(match.group(1))
        
        # Cook time
        elif 'cook time' in line_lower or '⏰ cook' in line_lower:
            match = re.search(r'(\d+)\s*(?:minutes?|mins?)', line_lower)
            if match:
                metadata['cook_time'] = int(match.group(1))
        
        # Servings
        elif 'servings' in line_lower or '🍽' in line:
            match = re.search(r'(\d+)', line)
            if match:
                metadata['servings'] = int(match.group(1))
        
        # Calories
        elif 'calories' in line_lower or '🔥' in line:
            match = re.search(r'(\d+)\s*(?:kcal|calories?)', line_lower)
            if match:
                nutrition['calories'] = int(match.group(1))
    
    # Set defaults if not found
    if 'servings' not in metadata:
        metadata['servings'] = 4
    
    # Calculate total time
    if 'prep_time' in metadata and 'cook_time' in metadata:
        metadata['total_time'] = metadata['prep_time'] + metadata['cook_time']
    
    # Generate nutrition if we have calories
    if 'calories' in nutrition:
        calories = nutrition['calories']
        nutrition.update({
            'protein': int(calories * 0.15 / 4),
            'carbs': int(calories * 0.50 / 4),
            'fat': int(calories * 0.35 / 9),
            'fiber': 3,
            'sugar': 8,
            'sodium': 400,
            'per_serving': {
                'calories': calories,
                'protein': int(calories * 0.15 / 4),
                'carbs': int(calories * 0.50 / 4),
                'fat': int(calories * 0.35 / 9),
                'fiber': 3,
                'sugar': 8,
                'sodium': 400
            },
            'per_meal': {
                'calories': calories,
                'protein': int(calories * 0.15 / 4),
                'carbs': int(calories * 0.50 / 4),
                'fat': int(calories * 0.35 / 9),
                'fiber': 3,
                'sugar': 8,
                'sodium': 400
            }
        })
    
    # Generate tags
    tags = generate_tags(title, ingredients, instructions)
    
    # Determine complexity
    if len(ingredients) <= 5 and len(instructions) <= 5:
        complexity = "easy"
    elif len(ingredients) >= 12 or len(instructions) >= 8:
        complexity = "complex"
    else:
        complexity = "medium"
    
    recipe = {
        "title": title,
        "ingredients": ingredients,
        "instructions": instructions,
        "source": "Facebook",
        "source_url": source_url,
        "date_scraped": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "complexity": complexity,
        "metadata": metadata,
        "nutrition": nutrition,
        "image_url": "",
        "tags": tags,
        "raw_content": content[:5000]
    }
    
    return recipe

def generate_tags(title: str, ingredients: List[str], instructions: List[str]) -> List[str]:
    """Generate tags for a recipe"""
    tags = ['facebook']  # Always include source
    
    title_lower = title.lower()
    ingredients_text = ' '.join(ingredients).lower()
    instructions_text = ' '.join(instructions).lower()
    all_text = f"{title_lower} {ingredients_text} {instructions_text}"
    
    # Meal type
    if any(word in title_lower for word in ['breakfast', 'pancake', 'waffle', 'omelette', 'omelet']):
        tags.append('breakfast')
    elif any(word in title_lower for word in ['soup', 'stew', 'chili']):
        tags.append('soup')
    elif any(word in title_lower for word in ['salad']):
        tags.append('salad')
    elif any(word in title_lower for word in ['dessert', 'cake', 'cookie', 'pie', 'pudding']):
        tags.append('dessert')
    else:
        tags.extend(['lunch', 'dinner'])
    
    # Main ingredient
    if 'chicken' in all_text:
        tags.append('chicken')
    if 'beef' in all_text or 'steak' in all_text:
        tags.append('beef')
    if 'pork' in all_text:
        tags.append('pork')
    if 'fish' in all_text or 'salmon' in all_text or 'cod' in all_text:
        tags.append('fish')
    if 'shrimp' in all_text:
        tags.append('seafood')
    if 'pasta' in all_text:
        tags.append('pasta')
    if 'rice' in all_text:
        tags.append('rice')
    
    # Cuisine
    if any(word in all_text for word in ['italian', 'parmesan', 'pecorino', 'alfredo']):
        tags.append('italian')
    if any(word in all_text for word in ['mexican', 'taco', 'burrito', 'salsa']):
        tags.append('mexican')
    if any(word in all_text for word in ['asian', 'chinese', 'teriyaki', 'soy sauce']):
        tags.append('asian')
    if any(word in all_text for word in ['cajun', 'creole', 'gumbo']):
        tags.append('cajun')
    if any(word in all_text for word in ['mediterranean', 'greek', 'feta']):
        tags.append('mediterranean')
    
    # Dietary
    meat_keywords = ['chicken', 'beef', 'pork', 'lamb', 'turkey', 'bacon', 'sausage', 'fish', 'shrimp', 'salmon']
    if not any(keyword in ingredients_text for keyword in meat_keywords):
        tags.append('vegetarian')
        
        dairy_keywords = ['milk', 'cream', 'cheese', 'butter', 'yogurt', 'egg']
        if not any(keyword in ingredients_text for keyword in dairy_keywords):
            tags.append('vegan')
    
    # Cooking method
    if any(word in all_text for word in ['baked', 'bake', 'oven']):
        tags.append('baked')
    if any(word in all_text for word in ['grilled', 'grill']):
        tags.append('grilled')
    if any(word in all_text for word in ['fried', 'fry', 'pan-fry']):
        tags.append('fried')
    if any(word in all_text for word in ['slow cooker', 'crockpot']):
        tags.append('slow-cooker')
    
    # Preparation time
    if 'quick' in title_lower or '30-minute' in title_lower or '30 minute' in title_lower:
        tags.append('quick')
    if 'easy' in title_lower:
        tags.append('easy')
    
    return list(set(tags))  # Remove duplicates

def extract_all_recipes_v2(filename: str) -> List[Dict[str, Any]]:
    """Extract all recipes from the Facebook Recipes URLs file"""
    recipes = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by div blocks that contain recipes
    # Each recipe seems to be in a div with class="x1yztbdb"
    blocks = content.split('<div class="x1yztbdb">')
    
    print(f"Found {len(blocks)} potential recipe blocks")
    
    for i, block in enumerate(blocks[1:], 1):  # Skip first empty block
        recipe = extract_recipe_from_block(block)
        if recipe:
            recipes.append(recipe)
            print(f"Block {i}: Extracted recipe: {recipe['title']}")
        else:
            # Try to see what's in this block
            lines = block.split('\n')
            for line in lines[:10]:
                if line.strip() and not line.strip().startswith('<') and 'class=' not in line:
                    print(f"Block {i}: Could not extract recipe, first text: {line.strip()[:50]}...")
                    break
    
    return recipes

def main():
    """Main function to extract and save recipes"""
    print("Starting enhanced recipe extraction...")
    
    # Extract recipes
    recipes = extract_all_recipes_v2("/mnt/e/recipe-scraper/FB Recipes URLs.txt")
    
    print(f"\nExtracted {len(recipes)} valid recipes")
    
    # Save to JSON file
    output_file = "/mnt/e/recipe-scraper/extracted_facebook_recipes_v2.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
    
    print(f"Recipes saved to: {output_file}")
    
    # Print summary
    print("\nRecipe Summary:")
    print(f"Total recipes: {len(recipes)}")
    if recipes:
        print(f"\nFirst 10 recipes:")
        for i, recipe in enumerate(recipes[:10], 1):
            print(f"{i}. {recipe['title']}")
            print(f"   - Ingredients: {len(recipe['ingredients'])}")
            print(f"   - Instructions: {len(recipe['instructions'])}")
            print(f"   - Tags: {', '.join(recipe['tags'][:5])}...")

if __name__ == "__main__":
    main()
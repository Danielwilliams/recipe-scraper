import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import html

def extract_recipe_title(content: str) -> str:
    """Extract recipe title from content"""
    # Look for pattern like "Crispy Lemon Pecorino Chicken Cutlets 🍋🧀🔥"
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('href=') and not line.startswith('<') and not 'class=' in line:
            # Clean up title - remove emojis and limit to 95 chars
            title = re.sub(r'[^\x00-\x7F]+', '', line).strip()
            if title and len(title) > 10:  # Must be substantial
                return title[:95]
    return "Untitled Recipe"

def extract_ingredients(content: str) -> List[str]:
    """Extract ingredients from recipe content"""
    ingredients = []
    lines = content.split('\n')
    in_ingredients_section = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        line_lower = line.lower()
        
        # Check if we're entering ingredients section
        if any(keyword in line_lower for keyword in ['ingredients', 'ingredient list', 'ingredients 🛒']):
            in_ingredients_section = True
            continue
            
        # Check if we're leaving ingredients section
        if in_ingredients_section and any(keyword in line_lower for keyword in ['directions', 'instructions', 'method', 'directions 👩‍🍳']):
            break
            
        # Extract ingredients
        if in_ingredients_section and line and not line.startswith('⏰') and not line.startswith('🍽'):
            # Clean up ingredient
            ingredient = html.unescape(line)
            ingredient = re.sub(r'^[\d️⃣•\-]+\s*', '', ingredient).strip()
            if ingredient and len(ingredient) > 3:
                ingredients.append(ingredient)
    
    return ingredients

def extract_instructions(content: str) -> List[str]:
    """Extract cooking instructions from recipe content"""
    instructions = []
    lines = content.split('\n')
    in_instructions_section = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        line_lower = line.lower()
        
        # Check if we're entering instructions section
        if any(keyword in line_lower for keyword in ['directions', 'instructions', 'method', 'directions 👩‍🍳']):
            in_instructions_section = True
            continue
            
        # Check if we're leaving instructions section
        if in_instructions_section and (line.startswith('⏰') or line.startswith('🍽') or line.startswith('#')):
            break
            
        # Extract instructions
        if in_instructions_section and line:
            # Clean up instruction
            instruction = html.unescape(line)
            instruction = re.sub(r'^[\d️⃣]+\s*', '', instruction).strip()
            if instruction and len(instruction) > 5:
                instructions.append(instruction)
    
    return instructions

def extract_metadata(content: str) -> Dict[str, Any]:
    """Extract metadata like prep time, cook time, servings, etc."""
    metadata = {}
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        line_lower = line.lower()
        
        # Extract prep time
        if 'prep time:' in line_lower:
            match = re.search(r'(\d+)\s*(?:minutes|mins?)', line_lower)
            if match:
                metadata['prep_time'] = int(match.group(1))
                
        # Extract cook time
        if 'cook time:' in line_lower:
            match = re.search(r'(\d+)\s*(?:minutes|mins?)', line_lower)
            if match:
                metadata['cook_time'] = int(match.group(1))
                
        # Extract servings
        if 'servings:' in line_lower or '🍽' in line:
            match = re.search(r'(\d+)', line)
            if match:
                metadata['servings'] = int(match.group(1))
                
    # Calculate total time
    if 'prep_time' in metadata and 'cook_time' in metadata:
        metadata['total_time'] = metadata['prep_time'] + metadata['cook_time']
        
    return metadata

def extract_nutrition(content: str, servings: int = 4) -> Dict[str, Any]:
    """Extract nutrition information"""
    nutrition = {}
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        line_lower = line.lower()
        
        # Extract calories
        if 'calories:' in line_lower or '🔥' in line:
            match = re.search(r'(\d+)\s*(?:kcal|calories?)', line_lower)
            if match:
                nutrition['calories'] = int(match.group(1))
    
    # If we found calories, estimate other nutrients (simplified)
    if 'calories' in nutrition:
        calories = nutrition['calories']
        nutrition.update({
            'protein': int(calories * 0.15 / 4),  # Rough estimate: 15% from protein
            'carbs': int(calories * 0.50 / 4),    # 50% from carbs
            'fat': int(calories * 0.35 / 9),      # 35% from fat
            'fiber': 3,  # Default estimate
            'sugar': 8,  # Default estimate
            'sodium': 400  # Default estimate
        })
        
        # Add per_serving and per_meal
        nutrition['per_serving'] = nutrition.copy()
        nutrition['per_meal'] = nutrition.copy()
    
    return nutrition

def extract_tags(content: str, title: str, ingredients: List[str]) -> List[str]:
    """Extract and generate tags for the recipe"""
    tags = ['facebook']  # Always include source tag
    
    # Extract hashtags
    hashtags = re.findall(r'#(\w+)', content)
    for tag in hashtags:
        clean_tag = tag.lower()
        if len(clean_tag) > 2 and clean_tag not in tags:
            tags.append(clean_tag)
    
    # Determine complexity based on ingredients and instructions count
    if len(ingredients) <= 5:
        tags.append('easy')
    elif len(ingredients) >= 12:
        tags.append('complex')
    else:
        tags.append('medium')
    
    # Check for dietary tags
    ingredients_text = ' '.join(ingredients).lower()
    title_lower = title.lower()
    
    # Vegetarian/Vegan checks
    meat_keywords = ['chicken', 'beef', 'pork', 'lamb', 'turkey', 'bacon', 'sausage', 'fish', 'shrimp', 'salmon']
    if not any(keyword in ingredients_text for keyword in meat_keywords):
        tags.append('vegetarian')
        
        # Check for vegan
        dairy_keywords = ['milk', 'cream', 'cheese', 'butter', 'yogurt', 'egg']
        if not any(keyword in ingredients_text for keyword in dairy_keywords):
            tags.append('vegan')
    
    # Main ingredient tags
    if 'chicken' in ingredients_text:
        tags.append('chicken')
    if 'pasta' in ingredients_text:
        tags.append('pasta')
    if 'salad' in title_lower:
        tags.append('salad')
        
    # Meal type tags
    if any(word in title_lower for word in ['breakfast', 'pancake', 'waffle', 'omelette']):
        tags.append('breakfast')
    elif any(word in title_lower for word in ['soup', 'stew', 'chili']):
        tags.append('soup')
    elif 'dessert' in title_lower or any(word in title_lower for word in ['cake', 'cookie', 'pie']):
        tags.append('dessert')
    else:
        tags.extend(['lunch', 'dinner'])
    
    return list(set(tags))  # Remove duplicates

def extract_source_url(content: str) -> str:
    """Extract Facebook URL from content"""
    # Look for href="https://www.facebook.com/..." pattern
    match = re.search(r'href="(https://www\.facebook\.com/[^"]+)"', content)
    if match:
        return match.group(1)
    return ""

def parse_recipe(recipe_content: str) -> Optional[Dict[str, Any]]:
    """Parse a single recipe from the content"""
    if not recipe_content.strip():
        return None
        
    title = extract_recipe_title(recipe_content)
    if title == "Untitled Recipe":
        return None
        
    ingredients = extract_ingredients(recipe_content)
    if not ingredients:
        return None
        
    instructions = extract_instructions(recipe_content)
    if not instructions:
        return None
        
    metadata = extract_metadata(recipe_content)
    servings = metadata.get('servings', 4)
    
    nutrition = extract_nutrition(recipe_content, servings)
    tags = extract_tags(recipe_content, title, ingredients)
    source_url = extract_source_url(recipe_content)
    
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
        "image_url": "",  # Will need to be added later
        "tags": tags,
        "raw_content": recipe_content[:5000]  # Limit to 5000 chars
    }
    
    return recipe

def extract_all_recipes(filename: str) -> List[Dict[str, Any]]:
    """Extract all recipes from the Facebook Recipes URLs file"""
    recipes = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into individual recipes
    # Look for patterns that indicate recipe boundaries
    recipe_parts = []
    current_recipe = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        # Check if this line starts a new recipe (contains href and recipe title pattern)
        if 'href="https://www.facebook.com/' in line and i > 0:
            # Check if next few lines contain recipe-like content
            has_recipe_content = False
            for j in range(i, min(i + 10, len(lines))):
                if any(keyword in lines[j].lower() for keyword in ['ingredients', 'directions', 'prep time', '🍋', '🧀', '🔥']):
                    has_recipe_content = True
                    break
            
            if has_recipe_content and current_recipe:
                # Save current recipe and start new one
                recipe_parts.append('\n'.join(current_recipe))
                current_recipe = [line]
            else:
                current_recipe.append(line)
        else:
            current_recipe.append(line)
    
    # Don't forget the last recipe
    if current_recipe:
        recipe_parts.append('\n'.join(current_recipe))
    
    # Parse each recipe
    for recipe_content in recipe_parts:
        recipe = parse_recipe(recipe_content)
        if recipe:
            recipes.append(recipe)
            print(f"Extracted recipe: {recipe['title']}")
    
    return recipes

def main():
    """Main function to extract and save recipes"""
    print("Starting recipe extraction...")
    
    # Extract recipes
    recipes = extract_all_recipes("/mnt/e/recipe-scraper/FB Recipes URLs.txt")
    
    print(f"\nExtracted {len(recipes)} recipes")
    
    # Save to JSON file
    output_file = "/mnt/e/recipe-scraper/extracted_facebook_recipes.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
    
    print(f"Recipes saved to: {output_file}")
    
    # Print summary
    print("\nRecipe Summary:")
    print(f"Total recipes: {len(recipes)}")
    if recipes:
        print(f"First recipe: {recipes[0]['title']}")
        print(f"Last recipe: {recipes[-1]['title']}")

if __name__ == "__main__":
    main()
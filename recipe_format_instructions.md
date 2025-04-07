# Recipe Formatting Instructions

This document provides guidelines for formatting recipes from FB Recipes.txt into a standardized JSON format for import into the recipe database.

## Target Format

Each recipe should be formatted as a JSON object with the following structure:

```json
{
  "title": "Recipe Title",
  "ingredients": ["Ingredient 1", "Ingredient 2", ...],
  "instructions": ["Step 1", "Step 2", ...],
  "source": "Facebook",
  "source_url": "",
  "date_scraped": "YYYY-MM-DDTHH:MM:SS.sssZ",
  "complexity": "easy|medium|complex",
  "metadata": {
    "prep_time": minutes,
    "cook_time": minutes,
    "total_time": minutes,
    "servings": number,
    "cuisine": "type"
  },
  "nutrition": {
    "calories": number,
    "protein": number,
    "carbs": number,
    "fat": number,
    "fiber": number,
    "sugar": number,
    "sodium": number,
    "per_serving": {
      "calories": number,
      "protein": number,
      "carbs": number,
      "fat": number,
      "fiber": number,
      "sugar": number,
      "sodium": number
    },
    "per_meal": {
      "calories": number,
      "protein": number,
      "carbs": number,
      "fat": number,
      "fiber": number,
      "sugar": number,
      "sodium": number
    }
  },
  "image_url": "https://example.com/image.jpg",
  "tags": ["tag1", "tag2", ...],
  "raw_content": "original recipe text"
}
```

## Processing Steps

1. **Title Extraction**:
   - Extract the title from the first line of each recipe
   - Remove emojis and special characters
   - Keep title under 95 characters

2. **Ingredients Section**:
   - Look for "Ingredients" or similar headers
   - Extract all ingredients, preserving the line-by-line format
   - For grouped ingredients (e.g., "For the Sauce:"), maintain the original formatting

3. **Instructions Section**:
   - Look for "Instructions", "Directions", or similar headers
   - Extract all steps, preserving the line-by-line format
   - Remove step numbers but maintain step ordering

4. **Metadata Extraction**:
   - Extract prep time, cook time, total time if available
   - Extract servings if available
   - Extract cuisine type if available
   - Determine complexity based on ingredient count and instruction steps:
     - ≤5 ingredients AND ≤5 steps: "easy"
     - ≥12 ingredients OR ≥8 steps: "complex"
     - Otherwise: "medium"

5. **Nutrition Information**:
   - Extract calories, protein, carbs, fat if available
   - Generate nutritional information if not available using a nutrition API or AI estimation
   - Calculate per serving values by dividing total nutritional values by serving count
   - Calculate per meal values based on standard meal portion (typically 1 serving but may vary based on recipe type)
   - For per_meal calculation, use the following assumptions:
     - Main dishes: 1 serving = 1 meal portion
     - Side dishes: 2-3 servings = 1 meal portion
     - Desserts: 2 servings = 1 meal portion
     - Snacks: 1-2 servings = 1 meal portion

6. **Image URL Processing**:
   - Extract image URL if present in the recipe (look for http/https links)
   - If no image URL is present, generate one using one of these methods:
     1. **API Search**: Use Unsplash API, Pexels API, or similar to search for images using the recipe title and main ingredients
        ```
        API_KEY=your_api_key
        QUERY="Recipe Title main ingredient"
        curl -H "Authorization: Client-ID $API_KEY" \
        "https://api.unsplash.com/search/photos?query=$QUERY&per_page=1"
        ```
     2. **Web Scraping**: Search for images on recipe websites using the recipe title
        ```python
        import requests
        from bs4 import BeautifulSoup
        
        def find_image(recipe_title):
            search_url = f"https://www.google.com/search?q={recipe_title}&tbm=isch"
            response = requests.get(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img', limit=5)
            return img_tags[1]['src'] if len(img_tags) > 1 else None
        ```
     3. **AI Image Generation**: Use AI image generation APIs like DALL-E or Stable Diffusion
        ```
        POST https://api.openai.com/v1/images/generations
        {
          "prompt": "Photo of [Recipe Title], food photography, high quality",
          "n": 1,
          "size": "512x512"
        }
        ```

7. **Tags Generation**:
   - Extract hashtags if present in the recipe
   - Generate standardized tags based on recipe title, ingredients, and cuisine
   - Standard tag categories for Smart Meal Planner:
     - **Meal Type**: breakfast, lunch, dinner, snack, dessert, appetizer, side-dish
     - **Cuisine**: italian, mexican, asian, mediterranean, american, french, indian, thai, japanese, chinese, greek, middle-eastern, spanish
     - **Diet Type**: vegetarian, vegan, gluten-free, keto, low-carb, dairy-free, paleo, whole30
     - **Dish Type**: soup, salad, sandwich, pizza, pasta, stir-fry, casserole, stew, curry, bowl, wrap, burger, taco, pie, bread, cake, cookie, rice
     - **Main Ingredient**: chicken, beef, pork, fish, seafood, tofu, lentils, beans, rice, potato, pasta, vegetables, mushroom
     - **Cooking Method**: baked, grilled, fried, slow-cooker, instant-pot, air-fryer, steamed, sauteed, pressure-cooker, one-pot, sheet-pan
     - **Preparation Time**: quick, make-ahead, meal-prep, 5-ingredients, 30-minute, weeknight
     - **Complexity**: easy, medium, complex
     - **Seasonal**: spring, summer, fall, winter, holiday
     - **Occasion**: party, potluck, family-friendly, date-night, weeknight, weekend
   - Always include "facebook" as a source tag
   - Add dietary tags using these rules:
     - **Vegetarian**: No meat, poultry, fish, or seafood ingredients
     - **Vegan**: Vegetarian + no dairy, eggs, honey, or other animal products
     - **Gluten-Free**: No wheat, barley, rye, or ingredients containing gluten
     - **Dairy-Free**: No milk, cheese, yogurt, cream, butter, or other dairy
     - **Keto**: Very low carb (≤10g net carbs per serving), high fat
     - **Low-Carb**: Moderate carb restriction (<30g carbs per serving)
     - **Paleo**: No grains, legumes, dairy, refined sugar, or processed foods

   - Add nutritional focus tags when appropriate:
     - **High-Protein**: ≥20g protein per serving
     - **Low-Fat**: ≤3g fat per serving
     - **Low-Calorie**: ≤300 calories per serving
     - **High-Fiber**: ≥5g fiber per serving

   - Add flavor profile tags based on dominant flavors:
     - **Spicy**, **Sweet**, **Savory**, **Tangy**, **Smoky**, **Herby**, **Garlicky**

   - Add contextual tags based on recipe use:
     - **Freezer-Friendly**, **Meal-Prep**, **Leftover-Friendly**, **Kid-Friendly**

8. **Recipe Separation**:
   - Look for common separators between recipes:
     - Lines of dashes/underscores (e.g., "________")
     - Numbered recipes (e.g., "1. Recipe Name")
     - Double line breaks between recipes

## Implementation

For implementation, follow these steps:

1. Read the FB Recipes.txt file
2. Split the content into individual recipes using the separation rules
3. For each recipe:
   - Process and extract all components mentioned above
   - Generate missing components (nutrition, images, tags)
   - Format into the JSON structure
4. Save the formatted recipes to a JSON file for import

## Additional Notes

- **Nutrition Calculation APIs**:
  - USDA FoodData Central API: https://fdc.nal.usda.gov/api-guide.html
  - Nutritionix API: https://developer.nutritionix.com/
  - Edamam Nutrition API: https://developer.edamam.com/edamam-nutrition-api
  - Example API call:
    ```
    curl -X GET "https://api.edamam.com/api/nutrition-data?app_id=YOUR_APP_ID&app_key=YOUR_APP_KEY&ingr=1%20large%20apple"
    ```

- **Image Search APIs**:
  - Unsplash API: https://unsplash.com/documentation
  - Pexels API: https://www.pexels.com/api/documentation/
  - Pixabay API: https://pixabay.com/api/docs/
  - Example Unsplash API call:
    ```
    curl -H "Authorization: Client-ID YOUR_ACCESS_KEY" https://api.unsplash.com/search/photos?query=pasta%20salad
    ```

- **Tag Generation**:
  - Use NLP techniques to extract key ingredients, cooking methods, and cuisine types
  - Match extracted keywords against a predefined list of standard tags
  - For dietary analysis, maintain lists of:
    - Meat/animal ingredients (for vegetarian/vegan detection)
    - Gluten-containing ingredients (for gluten-free detection)
    - High-carb ingredients (for keto/low-carb detection)
    - Dairy ingredients (for dairy-free detection)

- Limit raw_content to 5000 characters
- Generate a unique ID for each recipe

## Example

Original recipe:
```
Vegetarian Pasta Salad 🍅🥑
This Vegetarian Pasta Salad is a fresh and flavorful twist on the classic BLT-inspired dish. Packed with juicy cherry tomatoes, creamy avocado, and a vibrant avocado-ranch dressing, it's a light and satisfying meal perfect for picnics, potlucks, or a quick lunch.
________________________________________
Recipe Overview
• Prep Time: 30 minutes
• Cook Time: 10 minutes
• Total Time: 40 minutes
• Servings: 6–8
• Cuisine: American
• Skill Level: Easy
________________________________________
Ingredients
Salad
• 1 (16-ounce) package rotini pasta
...
```

Formatted output:
```json
{
  "title": "Vegetarian Pasta Salad",
  "ingredients": [
    "1 (16-ounce) package rotini pasta",
    "½ teaspoon salt",
    "½ teaspoon pepper",
    "1 (0.75-ounce) packet fresh dill (finely chopped)",
    "6 cups shredded romaine lettuce",
    "2½ cups halved cherry tomatoes",
    "1 cup thinly sliced red onion",
    "1 large avocado (diced)",
    "2 small avocados",
    "½ cup low-fat buttermilk",
    "½ cup mayo",
    "2 large lemons (zested and juiced)",
    "1½ teaspoons dried parsley",
    "1½ teaspoons onion powder",
    "1½ teaspoons garlic powder",
    "Salt and pepper (to taste)"
  ],
  "instructions": [
    "Cook the rotini pasta according to package instructions in well-salted water.",
    "Drain the pasta but do not rinse it. Cover and refrigerate, tossing occasionally, until fully cooled.",
    "Finely chop the fresh dill and set aside ¼ cup for the dressing.",
    "Shred the romaine lettuce and ensure it's completely dry.",
    "Halve the cherry tomatoes, thinly slice the red onion, and dice the avocado.",
    "Zest the lemons to get ½ teaspoon zest and juice them to get ¼ cup lemon juice.",
    "Mash the avocados to measure 1¼ cups flesh.",
    "Add avocado flesh, buttermilk, mayo, lemon zest, lemon juice, parsley, onion powder, garlic powder, salt, and pepper to a blender.",
    "Blend until smooth. The dressing will be thick.",
    "In a large bowl, toss the cooled pasta with the shredded lettuce.",
    "Add cherry tomatoes, red onion, and diced avocado.",
    "Scoop the dressing over the salad and add the remaining chopped dill.",
    "Gently toss to combine. Taste and adjust seasoning with salt and pepper if needed."
  ],
  "source": "Facebook",
  "source_url": "",
  "date_scraped": "2024-10-14T00:00:00.000Z",
  "complexity": "medium",
  "metadata": {
    "prep_time": 30,
    "cook_time": 10,
    "total_time": 40,
    "servings": 7,
    "cuisine": "American"
  },
  "nutrition": {
    "calories": 320,
    "protein": 7,
    "carbs": 42,
    "fat": 14,
    "fiber": 5,
    "sugar": 4,
    "sodium": 380,
    "per_serving": {
      "calories": 320,
      "protein": 7,
      "carbs": 42,
      "fat": 14,
      "fiber": 5,
      "sugar": 4,
      "sodium": 380
    },
    "per_meal": {
      "calories": 320,
      "protein": 7,
      "carbs": 42,
      "fat": 14,
      "fiber": 5,
      "sugar": 4,
      "sodium": 380
    }
  },
  "image_url": "https://scontent-den2-1.xx.fbcdn.net/v/t39.30808-6/489304422_122163810284448211_3882683620644022086_n.jpg?stp=dst-jpg_s640x640_tt6&_nc_cat=103&ccb=1-7&_nc_sid=127cfc&_nc_ohc=kXkAxIoM9uIQ7kNvwGUpTkv&_nc_oc=AdlwAX_Lf6yzBEyZ0RpBlW1fs7b7vWseIjb2ZHjqmPvOEzn3Z-2Lphvw7SZUsAiUOc4&_nc_zt=23&_nc_ht=scontent-den2-1.xx&_nc_gid=X5xwN630maXEVBbglwYgpQ&oh=00_AfH9-ldfC2STEolU2MW8FEDYEigShwO7LaqqTmA6zjjCJQ&oe=67F9E379",
  "tags": ["vegetarian", "pasta", "salad", "avocado", "tomato", "american", "easy", "lunch", "dinner", "facebook", "main-dish", "cold"],
  "raw_content": "Vegetarian Pasta Salad 🍅🥑\nThis Vegetarian Pasta Salad is a fresh and flavorful twist on the classic BLT-inspired dish. Packed with juicy cherry tomatoes, creamy avocado, and a vibrant avocado-ranch dressing, it's a light and satisfying meal perfect for picnics, potlucks, or a quick lunch.\n________________________________________\nRecipe Overview\n• Prep Time: 30 minutes\n• Cook Time: 10 minutes\n• Total Time: 40 minutes\n• Servings: 6–8\n• Cuisine: American\n• Skill Level: Easy\n________________________________________\n..."
}
```
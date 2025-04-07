# Recipe Tag Generation Prompt

Use this prompt with Claude.ai or Claude Console to generate standardized tags for your recipes.

## Instructions

Copy and paste the following prompt, replacing the placeholder text with your recipe information:

```
I need you to generate standardized tags for the following recipe for a meal planning application. The tags should be comprehensive, covering meal type, cuisine, diet type, dish type, main ingredients, cooking methods, preparation time, complexity, seasonal aspects, and occasion suitability.

Here's the recipe:

Title: [RECIPE TITLE]

Ingredients:
- [INGREDIENT 1]
- [INGREDIENT 2]
- ...

Instructions:
1. [STEP 1]
2. [STEP 2]
...

[INCLUDE ANY OTHER RELEVANT INFORMATION SUCH AS PREP TIME, COOK TIME, SERVINGS, ETC.]

Please provide:
1. A JSON array of standardized tags following these guidelines:

- Meal Type: breakfast, lunch, dinner, snack, dessert, appetizer, side-dish
- Cuisine: italian, mexican, asian, mediterranean, american, french, indian, thai, japanese, chinese, greek, middle-eastern, spanish
- Diet Type: vegetarian, vegan, gluten-free, keto, low-carb, dairy-free, paleo, whole30
- Dish Type: soup, salad, sandwich, pizza, pasta, stir-fry, casserole, stew, curry, bowl, wrap, burger, taco, pie, bread, cake, cookie, rice
- Main Ingredient: chicken, beef, pork, fish, seafood, tofu, lentils, beans, rice, potato, pasta, vegetables, mushroom
- Cooking Method: baked, grilled, fried, slow-cooker, instant-pot, air-fryer, steamed, sauteed, pressure-cooker, one-pot, sheet-pan
- Preparation Time: quick, make-ahead, meal-prep, 5-ingredients, 30-minute, weeknight
- Complexity: easy, medium, complex
- Seasonal: spring, summer, fall, winter, holiday
- Occasion: party, potluck, family-friendly, date-night, weeknight, weekend
- Nutritional Focus: high-protein, low-fat, low-calorie, high-fiber
- Flavor Profile: spicy, sweet, savory, tangy, smoky, herby, garlicky
- Contextual Use: freezer-friendly, meal-prep, leftover-friendly, kid-friendly

2. A brief explanation of why each tag was selected for this recipe.

3. Estimated per-serving macro values in the following format:
```json
{
  "calories": number,
  "protein": number,
  "carbs": number,
  "fat": number,
  "fiber": number,
  "sugar": number,
  "sodium": number
}
```
```

## Example Usage

Here's an example with an actual recipe:

```
I need you to generate standardized tags for the following recipe for a meal planning application. The tags should be comprehensive, covering meal type, cuisine, diet type, dish type, main ingredients, cooking methods, preparation time, complexity, seasonal aspects, and occasion suitability.

Here's the recipe:

Title: Creamy Parmesan Italian Sausage Ditalini Soup

Ingredients:
- 1 lb Italian sausage (mild or spicy)
- 1 onion, chopped
- 3 garlic cloves, minced
- 4 cups chicken broth
- 1 cup heavy cream
- 1/2 cup grated Parmesan cheese
- 1 can (14.5 oz) diced tomatoes
- 2 cups ditalini pasta
- 1 tsp Italian seasoning
- Salt and pepper to taste
- Fresh parsley, chopped

Instructions:
1. Heat olive oil in a large pot over medium heat. Add the Italian sausage and cook until browned and crumbled, about 5-7 minutes.
2. Add the chopped onion and garlic to the pot and cook for 3 more minutes until fragrant and softened.
3. Pour in the chicken broth and diced tomatoes, bringing the mixture to a boil. Reduce heat and simmer for 10 minutes.
4. Stir in the ditalini pasta and cook for 8-10 minutes, or until the pasta is tender.
5. Stir in the heavy cream, Parmesan cheese, and Italian seasoning. Let it simmer for another 2-3 minutes, until the soup is creamy and well combined.
6. Adjust seasoning with salt and pepper to taste. Top with fresh parsley and serve hot.

Preparation time: 10 minutes
Cooking time: 30 minutes
Servings: 6
Cuisine: Italian-American

Please provide:
1. A JSON array of standardized tags following the guidelines mentioned.
2. A brief explanation of why each tag was selected for this recipe.
3. Estimated per-serving macro values.
```

## Processing JSON Results

After receiving the tags from Claude:

1. Copy the JSON array of tags
2. Open your recipe JSON file
3. Add or replace the "tags" field in the recipe object with the new tags
4. Save the file
5. Import the updated recipes into your database using your existing import script

## Batch Processing

For multiple recipes, you can either:

1. Process each recipe individually using Claude.ai or Claude Console
2. Group 3-5 recipes at a time in one prompt, asking Claude to return tags for each recipe separately
3. For large datasets, consider developing a custom script that uses Claude API to automate the process

## Important Notes

- Claude may occasionally generate tags outside the standardized list. Review and adjust as needed.
- For nutritional estimates, Claude will provide rough approximations. For more accurate values, consider using a nutrition API like Edamam.
- Always include "facebook" as a source tag for recipes from Facebook.
- Tag consistency is important for search functionality, so try to use the standardized tags rather than creating new ones.
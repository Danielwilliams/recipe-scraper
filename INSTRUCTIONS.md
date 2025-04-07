# Facebook Recipe Import Instructions

This document provides detailed instructions for importing recipes saved from Facebook using the enhanced recipe import system.

## Overview

The enhanced recipe import system allows you to:

1. Import recipes from Facebook in a standardized format
2. Automatically find images for recipes that don't have them
3. Generate nutrition information including per-serving and per-meal macros
4. Tag recipes with standardized categories for better search and filtering
5. Store recipes in your database for use with the Smart Meal Planner

## Prerequisites

1. Ensure you have Python 3.10+ installed
2. Install all dependencies from requirements.txt
3. Configure your environment with necessary API keys
4. Ensure database connection is properly set up

## Step 1: Collect Facebook Recipes

### Option A: Manual Collection

1. When you find recipes on Facebook you'd like to save:
   - Copy the entire recipe text, including title, ingredients, instructions, and any nutrition info
   - Paste it into a text file (e.g., `FB_Recipes.txt`) in the `data` directory
   - Include image URLs when available by copying the image link (right-click → Copy image address)
   - Separate multiple recipes with blank lines or dashed lines (e.g., `--------`)

### Option B: Using Browser Extensions

1. Install a content scraper extension like "Copy All Content" or "Facebook Post Exporter"
2. Navigate to your saved recipe posts on Facebook
3. Use the extension to copy the entire post content
4. Paste the content into your `FB_Recipes.txt` file
5. Add proper separators between recipes if needed

### Recipe Format Best Practices

While the system can handle various formats, the following structure works best:

```
Recipe Title 🍲

Brief description (optional)

Ingredients:
- Ingredient 1
- Ingredient 2
...

Instructions:
1. Step 1
2. Step 2
...

Nutrition Info: (optional)
Calories: 350
Protein: 25g
...

[Image URL] (optional)
```

## Step 2: Process Recipes Locally

### Setup Environment

1. Create or update your `.env` file with necessary API keys:

```
# Database
DATABASE_URL=your_database_url

# API Keys
UNSPLASH_API_KEY=your_unsplash_api_key
PEXELS_API_KEY=your_pexels_api_key
EDAMAM_APP_ID=your_edamam_app_id
EDAMAM_APP_KEY=your_edamam_app_key
```

2. Install dependencies if you haven't already:

```bash
pip install -r requirements.txt
```

### Run the Import Process

1. Process the recipes and save to JSON:

```bash
python enhanced_import_custom_recipes.py data/FB_Recipes.txt data/processed_recipes.json
```

This will:
- Parse each recipe in the file
- Extract title, ingredients, instructions, etc.
- Apply standardized formatting
- Save to a JSON file for review
- Import to the database

2. Find images for recipes missing them:

```bash
python find_recipe_images.py --update-db --limit 50
```

This will:
- Find recipes in the database that don't have images
- Search for appropriate images using Unsplash or Pexels APIs
- Update the database with found images

3. Generate nutrition data for recipes:

```bash
python generate_nutrition.py --update-db --limit 50
```

This will:
- Find recipes in the database that don't have nutrition information
- Use Edamam API to calculate nutrition based on ingredients
- Calculate per-serving and per-meal macros
- Update the database with nutrition information

## Step 3: Use GitHub Actions (Recommended)

For automated processing, use the GitHub Actions workflow:

1. Commit your FB_Recipes.txt file to the `data` directory in the repository
2. Push to GitHub
3. Go to the "Actions" tab in your GitHub repository
4. Select "Process Facebook Recipes" workflow
5. Click "Run workflow"
6. Enter the filename (default: FB_Recipes.txt)
7. Click "Run workflow" to start the process

The GitHub Action will:
- Run all three processing scripts automatically
- Upload the processed recipes JSON as an artifact
- Upload logs for troubleshooting if needed

## Step 4: Verify the Results

1. Check the logs for any errors during processing
2. Review the processed_recipes.json file to ensure recipes were parsed correctly
3. Check your database to confirm recipes were imported properly
4. Look for any recipes missing images or nutrition data and process them again if needed

## Troubleshooting

### Common Issues

1. **Recipe not parsing correctly:**
   - Ensure recipes have clear section headers like "Ingredients:" and "Instructions:"
   - Add more separation between recipes (use `--------` between recipes)
   - Check for special characters that might cause parsing issues

2. **Missing images:**
   - Check if the image URL in the recipe is valid
   - If using API services, verify your API keys are correct and not rate-limited
   - Try running the image finder script again with `--limit 10` to process fewer recipes

3. **Missing nutrition data:**
   - Ensure ingredient lists are clear and recognizable
   - Check if your Edamam API key is valid and not rate-limited
   - Try running the nutrition generator script again with `--limit 10`

4. **Database connection issues:**
   - Verify your database connection string is correct
   - Check if your database is accessible from your environment
   - Ensure necessary tables exist in the database

### Getting Help

If you encounter issues not covered here:
1. Check the logs for specific error messages
2. Review the documentation for the specific component causing issues
3. File an issue in the GitHub repository with detailed information about the problem

## Advanced Usage

### Custom Image Finding

If you want to find images for specific recipes only:

```bash
python find_recipe_images.py --output-json found_images.json --limit 10
```

This will save the found images to a JSON file without updating the database.

### Nutrition Data Only

If you want to generate nutrition data without updating the database:

```bash
python generate_nutrition.py --output-json nutrition_data.json --limit 10
```

This will save the nutrition data to a JSON file for review.

### Processing a Different File

To process a custom file in a different location:

```bash
python enhanced_import_custom_recipes.py path/to/your/recipes.txt path/to/output.json
```

## Reference

For more detailed information on how the recipe formatting system works, refer to the `recipe_format_instructions.md` file.

The standardized format includes:
- Recipe title
- Ingredients list
- Step-by-step instructions
- Metadata (prep time, cook time, servings, etc.)
- Nutrition information (including per-serving and per-meal)
- Image URL
- Tags for categorization
- Raw content for reference

This system integrates with the Smart Meal Planner to provide a complete recipe management solution.
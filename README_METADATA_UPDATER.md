# Recipe Metadata Updater

The Recipe Metadata Updater is a tool for automatically enhancing recipe data by scraping missing metadata from source websites. It focuses on ensuring all recipes have complete metadata including ingredients, cooking times, servings, nutrition information, and notes.

## Key Features

- **Comprehensive Metadata Checking**: Identifies recipes with missing ingredients, prep time, cook time, servings, and nutrition information.
- **Multi-Source Support**: Works with various recipe websites including Simply Recipes, Pinch of Yum, and more.
- **Enhanced Extraction**: Uses specialized scrapers for each website format, with multiple fallback mechanisms.
- **JSON-LD Support**: Extracts structured data from Schema.org Recipe markup.
- **Intelligent Updates**: Only updates fields that are missing, preserving existing data.

## How It Works

1. The updater scans the database for recipes with missing metadata fields.
2. For each recipe, it attempts to scrape the original source URL.
3. It uses enhanced site-specific scrapers for better extraction accuracy.
4. Multiple fallback methods ensure maximum data retrieval.
5. The database is updated with the newly extracted information.

## Running the Updater

You can run the metadata updater in several ways:

### Manual Command Line

```bash
python recipe_metadata_updater.py --limit 100
```

This will process up to 100 recipes with missing metadata.

### GitHub Actions Workflow

The updater is integrated into the GitHub Actions workflow and runs:
- On a weekly schedule (Sunday at 2 AM UTC)
- When manually triggered via workflow dispatch
- After new custom recipes are imported

## Debugging

If the updater is failing to extract metadata for certain recipes, you can enable more detailed logging by adding the following at the top of the script:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Required Fields

The updater checks for and attempts to complete the following metadata fields:

- **ingredients_list**: Complete list of recipe ingredients
- **prep_time**: Preparation time in minutes
- **cook_time**: Cooking time in minutes
- **total_time**: Total time to make the recipe
- **servings**: Number of people the recipe serves
- **yield**: Text description of the recipe yield
- **notes**: Additional recipe notes or tips
- **nutrition**: Nutritional information including calories, fat, carbs, protein, etc.

## Compatibility

The metadata updater is designed to work with the following recipe websites:
- Simply Recipes
- Pinch of Yum
- Host the Toast
- Fit Fab Fodmap
- Pickled Plum
- MyProtein
- AllRecipes
- Food Network
- EatingWell
- Epicurious

Additional websites can be supported by adding appropriate selectors to the `_get_ingredient_selectors` method.
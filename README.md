# Recipe Scraper

This tool scrapes recipes from various websites and imports them into a database for use with the Smart Meal Planner application.

## Features

- **Web Scraping**: Scrape recipes from popular websites like Pinch of Yum, Simply Recipes, Host the Toast, Fit Fab Fodmap, Pickled Plum and more
- **Enhanced Tasty Recipes Format Support**: Specialized extraction for sites using the Tasty Recipes WordPress plugin
- **Custom Recipe Import**: Import custom recipes from text files, including Facebook-saved recipes
- **Image Finding**: Automatically find images for recipes that don't have them
- **Nutrition Calculation**: Generate nutrition information using API services
- **Database Storage**: Store recipes in a PostgreSQL database
- **Ingredient Update**: Automated updater for missing ingredients

## Configuration

Configure the application by setting environment variables in a `.env` file:

```
# Database
DATABASE_URL=postgres://username:password@hostname:5432/database_name

# API Keys
UNSPLASH_API_KEY=your_unsplash_api_key
PEXELS_API_KEY=your_pexels_api_key
EDAMAM_APP_ID=your_edamam_app_id
EDAMAM_APP_KEY=your_edamam_app_key

# Facebook
FACEBOOK_ACCESS_TOKEN=your_facebook_token
FACEBOOK_PAGES=page1,page2
```

## Usage

### Scraping Recipes

```bash
# Scrape recipes from all sources
python main.py --source all --limit 50

# Scrape recipes from a specific source
python main.py --source pinchofyum --limit 50

# Scrape from other Tasty Recipes sites
python main.py --source hostthetoast --limit 50
python main.py --source fitfabfodmap --limit 50
python main.py --source pickledplum --limit 50
```

### Updating Recipes with Missing Ingredients

```bash
# Find and update recipes with missing ingredients
python ingredient_updater.py --limit 50
```

### Testing the Tasty Recipes Scrapers

```bash
# Test the original enhanced Pinch of Yum scraper
python test_enhanced_pinchofyum.py

# Test all Tasty Recipes format scrapers
python test_tasty_recipes_scrapers.py
```

### Processing Facebook Recipes

This feature allows you to format and import recipes saved from Facebook.

1. Save recipes in a text file (e.g., `FB_Recipes.txt`) in the `data` directory
2. Run the enhanced import script:

```bash
python enhanced_import_custom_recipes.py data/FB_Recipes.txt data/processed_recipes.json
```

3. Find images for recipes missing them:

```bash
python find_recipe_images.py --update-db --limit 50
```

4. Generate nutrition data for recipes:

```bash
python generate_nutrition.py --update-db --limit 50
```

Alternatively, you can run the GitHub workflow:

1. Go to "Actions" in your GitHub repository
2. Select "Process Facebook Recipes"
3. Click "Run workflow"
4. Enter the filename (default: FB_Recipes.txt)
5. Click "Run workflow"

### Formatting Guidelines

See `recipe_format_instructions.md` for detailed guidelines on how recipes are formatted.

## Project Structure

- `scrapers/` - Website-specific scrapers
  - `tasty_recipes_base_scraper.py` - Base class for Tasty Recipes format scrapers
  - `enhanced_pinchofyum_scraper.py` - Specialized scraper for Pinch of Yum
  - `host_the_toast_scraper.py` - Scraper for Host the Toast
  - `fit_fab_fodmap_scraper.py` - Scraper for Fit Fab Fodmap
  - `pickled_plum_scraper.py` - Scraper for Pickled Plum
- `processors/` - Recipe processing modules
- `database/` - Database connection and storage functions
- `data/` - Input and output data files
- `.github/workflows/` - GitHub Actions workflows
  - `update_recipes_workflow.yml` - Workflow for scraping new recipes
  - `update_ingredients_workflow.yml` - Workflow for updating missing ingredients

## Requirements

Python 3.10+ and the packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```
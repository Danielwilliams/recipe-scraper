# Recipe Scraper

This tool scrapes recipes from various websites and imports them into a database for use with the Smart Meal Planner application.

## Features

- **Web Scraping**: Scrape recipes from popular websites like AllRecipes, FoodNetwork, and more
- **Custom Recipe Import**: Import custom recipes from text files, including Facebook-saved recipes
- **Image Finding**: Automatically find images for recipes that don't have them
- **Nutrition Calculation**: Generate nutrition information using API services
- **Database Storage**: Store recipes in a PostgreSQL database

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
python main.py
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
- `processors/` - Recipe processing modules
- `database/` - Database connection and storage functions
- `data/` - Input and output data files
- `.github/workflows/` - GitHub Actions workflows

## Requirements

Python 3.10+ and the packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```
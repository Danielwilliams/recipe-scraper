# Recipe Image Downloader

This module downloads recipe images from source URLs and saves them locally.

## Features

- Extracts recipe images from source URLs using multiple methods:
  - Open Graph meta tags
  - Twitter Card meta tags
  - JSON-LD structured data
  - Common recipe image CSS selectors
- Downloads images with recipe ID and sanitized title as filename
- Can update the database with discovered image URLs
- Supports batch processing or specific recipe IDs
- GitHub Actions workflow for automated downloads

## Usage

### Command Line

```bash
# Download images for first 10 recipes
python download_recipe_images.py --limit 10

# Download images for specific recipes
python download_recipe_images.py --recipe-ids 1185,1186,1187

# Download and update database with image URLs
python download_recipe_images.py --limit 50 --update-db

# Specify custom output directory
python download_recipe_images.py --output-dir my_images
```

### GitHub Actions

The workflow can be triggered:

1. **Manually** via GitHub Actions UI with options:
   - `limit`: Number of recipes to process
   - `recipe_ids`: Specific recipe IDs (comma-separated)
   - `update_db`: Whether to update database with image URLs

2. **Scheduled** daily at 2 AM UTC

### Example

For the recipe "Easy Chili Dip" (ID: 1185) from SimplyRecipes:
- Source URL: https://www.simplyrecipes.com/chili-dip-recipe-8424967
- Extracted image: https://www.simplyrecipes.com/thmb/4_hWYJsC1hmHLLi9GEgAr0V6TZQ=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/Simply-Recipes-Chili-Dip-LEAD-4-2f628ea815b6443db813605899036ded.jpg
- Saved as: `recipe_images/1185_Easy Chili Dip.jpg`

## Output

- Images are saved to `recipe_images/` directory (configurable)
- Filenames format: `{recipe_id}_{sanitized_title}.{extension}`
- Logs are written to `download_images.log`
- GitHub Actions artifacts include both images and logs

## Requirements

- Python 3.8+
- Database connection (PostgreSQL)
- Dependencies: requests, beautifulsoup4, psycopg2

## Image Extraction Methods

The script tries multiple methods to find recipe images:

1. **Open Graph**: `<meta property="og:image">`
2. **Twitter Cards**: `<meta name="twitter:image">`
3. **JSON-LD**: Structured data with Recipe schema
4. **CSS Selectors**: Common recipe image classes/IDs

## Error Handling

- Skips recipes that already have image URLs
- Logs failures but continues processing
- Validates that downloaded content is actually an image
- Handles various URL formats and makes them absolute
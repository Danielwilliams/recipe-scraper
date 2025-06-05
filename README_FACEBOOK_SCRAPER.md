# Facebook URL Processor

This enhanced Facebook scraper processes saved Facebook URLs, checks for existing recipes in the database, and updates source URLs and images as needed.

## Setup for GitHub Actions

### 1. Upload your FB URLs file

**Important:** Upload your `FB URLs.txt` file to the `data/` directory in your repository:

```
data/FB_URLs.txt
```

### 2. Configure Database Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `DATABASE_URL` - Full PostgreSQL connection string (recommended)
- Or individual connection parameters:
  - `DB_HOST` - Database host
  - `DB_NAME` - Database name  
  - `DB_USER` - Database username
  - `DB_PASSWORD` - Database password
  - `DB_PORT` - Database port (usually 5432)

### 3. Run the Workflow

1. Go to Actions tab in your GitHub repository
2. Select "Process Facebook URLs" workflow
3. Click "Run workflow"
4. Set parameters (optional):
   - **Limit**: Maximum number of URLs to process (default: 50)
   - **Force Update**: Check to force update existing recipes (default: false)

## What it does

### For Existing Recipes:
- ✅ Checks if recipe exists by title and source
- ✅ Updates `source_url` if missing or different
- ✅ Downloads and saves recipe images if missing
- ✅ Updates database with new information

### For New Recipes:
- ✅ Extracts recipe information from Facebook post content
- ✅ Downloads and saves recipe images
- ✅ Creates new recipe entries in database
- ✅ Includes ingredients, instructions, metadata

## Features

### URL Extraction
- Extracts Facebook post URLs from HTML content
- Handles various Facebook URL formats:
  - `/groups/[group_id]/permalink/[post_id]/`
  - `/groups/[group_id]/posts/[post_id]/`
  - `/permalink.php?story_fbid=...`

### Recipe Detection
- Identifies recipe content using keywords and patterns
- Looks for ingredients, instructions, cooking times
- Filters out non-recipe posts

### Image Processing
- Downloads high-quality recipe images
- Saves locally with recipe ID and title
- Updates database with image URLs
- Handles various image formats (JPG, PNG)

### Database Integration
- Uses existing database schema (`scraped_recipes` table)
- Maintains data integrity with proper foreign keys
- Updates related tables (ingredients, tags, nutrition)

## File Structure

```
data/
  └── FB_URLs.txt          # Your Facebook URLs file (upload here)

.github/
  └── workflows/
      └── process-facebook-urls.yml  # GitHub Actions workflow

enhanced_facebook_scraper.py         # Main processing script
recipe_images/                       # Downloaded images (created automatically)
```

## Local Development

If running locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Run the scraper
python enhanced_facebook_scraper.py --file data/FB_URLs.txt --limit 10
```

### Command Line Options

```bash
python enhanced_facebook_scraper.py \
  --file data/FB_URLs.txt \     # Path to FB URLs file
  --limit 50 \                  # Max URLs to process
  --force-update \              # Force update existing recipes
  --output-dir recipe_images    # Image download directory
```

## Logs and Artifacts

After running, the workflow will upload:
- Processing logs (`enhanced_facebook_scraper.log`)
- Downloaded images (`recipe_images/` directory)

These are available in the Actions run artifacts for 7 days.

## Troubleshooting

### No URLs Found
- Ensure `FB_URLs.txt` is in the `data/` directory
- Check file contains HTML with Facebook URLs
- Verify file encoding is UTF-8

### Database Connection Issues
- Verify all database secrets are set correctly
- Test connection with a simple query first
- Check firewall settings allow GitHub Actions IPs

### Recipe Not Detected
- Content may not contain recipe keywords
- Try adjusting detection patterns in `_is_recipe_content()`
- Check logs for extraction details

### Image Download Failures
- Source image may be unavailable
- Check network connectivity
- Verify image URLs are valid

## Monitoring

The script provides detailed logging:
- URLs processed
- Recipes found/created/updated
- Images downloaded
- Errors encountered

Check the logs in GitHub Actions artifacts or console output for detailed information.
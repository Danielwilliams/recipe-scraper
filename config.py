# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

# API Keys and Credentials
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGES = os.getenv('FACEBOOK_PAGES', '').split(',')

# Scraping Configuration
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
REQUEST_TIMEOUT = 30
SCRAPE_DELAY = 3  # seconds between requests

# Recipe websites to scrape
RECIPE_WEBSITES = [
    {'name': 'AllRecipes', 'base_url': 'https://www.allrecipes.com/recipes/', 'pages': 5},
    {'name': 'Food Network', 'base_url': 'https://www.foodnetwork.com/recipes/recipes-a-z', 'pages': 3},
    {'name': 'Epicurious', 'base_url': 'https://www.epicurious.com/recipes-menus', 'pages': 3}
]

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'recipe_scraper.log'

# Food Categories for ingredient classification
FOOD_CATEGORIES = {
    'PROTEIN': ['chicken', 'beef', 'pork', 'turkey', 'fish', 'tofu', 'eggs', 'beans', 'lentils'],
    'VEGETABLE': ['spinach', 'broccoli', 'carrots', 'onions', 'garlic', 'bell pepper', 'tomato'],
    'FRUIT': ['apple', 'banana', 'orange', 'lemon', 'lime', 'berries', 'grapes'],
    'GRAIN': ['rice', 'pasta', 'bread', 'oats', 'quinoa', 'barley'],
    'DAIRY': ['milk', 'cheese', 'yogurt', 'cream', 'butter'],
    'SPICE': ['salt', 'pepper', 'cumin', 'cinnamon', 'oregano', 'basil', 'thyme'],
    'OIL': ['olive oil', 'vegetable oil', 'coconut oil', 'sesame oil'],
    'SWEETENER': ['sugar', 'honey', 'maple syrup', 'agave'],
    'NUTS': ['almonds', 'walnuts', 'peanuts', 'cashews'],
    'CONDIMENT': ['ketchup', 'mustard', 'soy sauce', 'vinegar']
}
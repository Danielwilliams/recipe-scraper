from scrapers.tasty_recipes_base_scraper import TastyRecipesBaseScraper

class EnhancedPinchOfYumScraper(TastyRecipesBaseScraper):
    """Enhanced scraper for Pinch of Yum using Tasty Recipes plugin"""
    
    def __init__(self):
        """Initialize the Pinch of Yum scraper"""
        site_name = "Pinch of Yum"
        base_url = "https://pinchofyum.com"
        
        # Category URLs for different recipe types
        category_urls = [
            "https://pinchofyum.com/recipes/breakfast",
            "https://pinchofyum.com/recipes/lunch",
            "https://pinchofyum.com/recipes/dinner",
            "https://pinchofyum.com/recipes/appetizer",
            "https://pinchofyum.com/recipes/snack",
            "https://pinchofyum.com/recipes/dessert",
            "https://pinchofyum.com/recipes/drinks",
            "https://pinchofyum.com/recipes/instant-pot",
            "https://pinchofyum.com/recipes/crockpot",
            "https://pinchofyum.com/recipes/vegetarian",
            "https://pinchofyum.com/recipes/vegan",
            "https://pinchofyum.com/recipes/gluten-free",
            "https://pinchofyum.com/recipes/dairy-free",
            "https://pinchofyum.com/recipes/soup",
            "https://pinchofyum.com/recipes/salad"
        ]
        
        super().__init__(site_name, base_url, category_urls)
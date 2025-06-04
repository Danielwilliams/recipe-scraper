from scrapers.tasty_recipes_base_scraper import TastyRecipesBaseScraper

class PickledPlumScraper(TastyRecipesBaseScraper):
    """Scraper for Pickled Plum blog using Tasty Recipes plugin"""
    
    def __init__(self):
        """Initialize the Pickled Plum scraper"""
        site_name = "Pickled Plum"
        base_url = "https://pickledplum.com"
        
        # Category URLs for different recipe types
        category_urls = [
            "https://pickledplum.com/recipes/",
            "https://pickledplum.com/category/recipes/appetizers/",
            "https://pickledplum.com/category/recipes/breakfast/",
            "https://pickledplum.com/category/recipes/dinner/",
            "https://pickledplum.com/category/recipes/lunch/",
            "https://pickledplum.com/category/recipes/soup/",
            "https://pickledplum.com/category/recipes/salad/",
            "https://pickledplum.com/category/recipes/snack/",
            "https://pickledplum.com/category/recipes/vegan/",
            "https://pickledplum.com/category/recipes/vegetarian/"
        ]
        
        super().__init__(site_name, base_url, category_urls)
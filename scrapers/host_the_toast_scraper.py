from scrapers.tasty_recipes_base_scraper import TastyRecipesBaseScraper

class HostTheToastScraper(TastyRecipesBaseScraper):
    """Scraper for Host the Toast blog using Tasty Recipes plugin"""
    
    def __init__(self):
        """Initialize the Host the Toast scraper"""
        site_name = "Host the Toast"
        base_url = "https://hostthetoast.com"
        
        # Category URLs for different recipe types
        category_urls = [
            "https://hostthetoast.com/recipes/",
            "https://hostthetoast.com/category/recipes/appetizers/",
            "https://hostthetoast.com/category/recipes/breakfast-brunch/",
            "https://hostthetoast.com/category/recipes/main-dishes/",
            "https://hostthetoast.com/category/recipes/sides/",
            "https://hostthetoast.com/category/recipes/soup/",
            "https://hostthetoast.com/category/recipes/dessert/",
            "https://hostthetoast.com/category/recipes/drinks/"
        ]
        
        super().__init__(site_name, base_url, category_urls)
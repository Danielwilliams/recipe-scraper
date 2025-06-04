from scrapers.tasty_recipes_base_scraper import TastyRecipesBaseScraper

class FitFabFodmapScraper(TastyRecipesBaseScraper):
    """Scraper for Fit Fab Fodmap blog using Tasty Recipes plugin"""
    
    def __init__(self):
        """Initialize the Fit Fab Fodmap scraper"""
        site_name = "Fit Fab Fodmap"
        base_url = "https://www.fitfabfodmap.com"
        
        # Category URLs for different recipe types
        category_urls = [
            "https://www.fitfabfodmap.com/recipes/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/breakfast/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/dinner/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/lunch/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/desserts/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/sides/",
            "https://www.fitfabfodmap.com/category/low-fodmap-recipes/snacks/"
        ]
        
        super().__init__(site_name, base_url, category_urls)
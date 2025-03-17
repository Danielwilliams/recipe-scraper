# scrapers/__init__.py
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    """Abstract base class for all scrapers"""
    
    @abstractmethod
    def scrape(self, limit=None):
        """
        Scrape recipes from the source
        
        Args:
            limit (int, optional): Maximum number of recipes to scrape
            
        Returns:
            list: List of scraped recipe dictionaries
        """
        pass
    
    @abstractmethod
    def _extract_recipe_info(self, content):
        """
        Extract structured recipe information from content
        
        Args:
            content: Source-specific content (HTML, JSON, etc.)
            
        Returns:
            dict: Structured recipe information
        """
        pass
    
    def _is_recipe(self, content):
        """
        Determine if the content contains a valid recipe
        
        Args:
            content: Source-specific content
            
        Returns:
            bool: True if content contains a recipe, False otherwise
        """
        return True
import re
import logging
from datetime import datetime
import string
from processors.ingredient_parser import parse_ingredient

logger = logging.getLogger(__name__)

class RecipeProcessor:
    """Process and standardize scraped recipes"""
    
    def __init__(self):
        self.common_cuisines = [
            'italian', 'mexican', 'chinese', 'indian', 'japanese', 'thai', 'french', 
            'greek', 'spanish', 'korean', 'vietnamese', 'american', 'cajun', 'caribbean',
            'mediterranean', 'middle eastern', 'southern', 'german', 'british', 'irish'
        ]
        
        self.diet_terms = [
            'vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'paleo', 'keto',
            'low-carb', 'low-fat', 'sugar-free', 'whole30', 'pescatarian'
        ]
        
        self.meal_types = [
            'breakfast', 'lunch', 'dinner', 'appetizer', 'snack', 'dessert',
            'side dish', 'main course', 'salad', 'soup', 'sandwich', 'drink'
        ]
    
    def process_recipe(self, raw_recipe):
        """
        Process a raw scraped recipe into a standardized format
        
        Args:
            raw_recipe (dict): Raw scraped recipe
            
        Returns:
            dict: Processed recipe with standardized fields
        """
        logger.info(f"Processing recipe: {raw_recipe.get('title', 'Untitled')}")
        
        try:
            processed = {
                'title': self._clean_title(raw_recipe.get('title', 'Untitled Recipe')),
                'ingredients': self._process_ingredients(raw_recipe.get('ingredients', [])),
                'instructions': self._process_instructions(raw_recipe.get('instructions', [])),
                'source': raw_recipe.get('source', 'Unknown'),
                'source_url': raw_recipe.get('source_url', ''),
                'date_scraped': raw_recipe.get('date_scraped', datetime.now().isoformat()),
                'date_processed': datetime.now().isoformat(),
                'complexity': raw_recipe.get('complexity', self._infer_complexity(raw_recipe)),
                'tags': self._generate_tags(raw_recipe),
                'cuisine': self._infer_cuisine(raw_recipe),
                'metadata': self._process_metadata(raw_recipe),
                'raw_content': raw_recipe.get('raw_content', '')
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing recipe: {str(e)}")
            return None
    
    def _clean_title(self, title):
        """Clean and standardize recipe title"""
        title = re.sub(r'\brecipe\b', '', title, flags=re.IGNORECASE).strip()
        title = string.capwords(title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title
    
    def _process_ingredients(self, ingredients_list):
        """Process list of ingredient strings into structured data"""
        processed_ingredients = []
        
        for ingredient_text in ingredients_list:
            if not ingredient_text or ingredient_text.strip() == '':
                continue
                
            parsed = parse_ingredient(ingredient_text)
            processed_ingredients.append(parsed)
        
        return processed_ingredients
    
    def _process_instructions(self, instructions_list):
        """Clean and standardize instruction steps"""
        processed_instructions = []
        
        for step in instructions_list:
            if not step or step.strip() == '':
                continue
                
            cleaned_step = re.sub(r'^\s*\d+\.\s*', '', step).strip()
            cleaned_step = re.sub(r'\s+', ' ', cleaned_step).strip()
            
            if cleaned_step:
                if len(cleaned_step) > 0:
                    cleaned_step = cleaned_step[0].upper() + cleaned_step[1:]
                if not cleaned_step.endswith('.') and not cleaned_step.endswith('!') and not cleaned_step.endswith('?'):
                    cleaned_step += '.'
                processed_instructions.append(cleaned_step)
        
        return processed_instructions
    
    def _process_metadata(self, raw_recipe):
        """Extract and standardize recipe metadata"""
        metadata = raw_recipe.get('metadata', {})
        
        for key in ['prep_time', 'cook_time', 'total_time', 'servings']:
            if key in metadata and metadata[key] is not None:
                try:
                    metadata[key] = int(metadata[key])
                except (ValueError, TypeError):
                    metadata[key] = None
        
        if 'total_time' not in metadata and 'prep_time' in metadata and 'cook_time' in metadata:
            prep_time = metadata.get('prep_time', 0) or 0
            cook_time = metadata.get('cook_time', 0) or 0
            if prep_time > 0 or cook_time > 0:
                metadata['total_time'] = prep_time + cook_time
        
        return metadata
    
    def _generate_tags(self, raw_recipe):
        """Generate relevant tags for the recipe"""
        tags = set()
        
        if 'tags' in raw_recipe and isinstance(raw_recipe['tags'], list):
            for tag in raw_recipe['tags']:
                tags.add(tag.lower().strip())
        
        cuisine = self._infer_cuisine(raw_recipe)
        if cuisine:
            tags.add(cuisine.lower())
        
        combined_text = (
            raw_recipe.get('title', '') + ' ' + 
            ' '.join(raw_recipe.get('ingredients', [])) + ' ' + 
            ' '.join(raw_recipe.get('instructions', []))
        ).lower()
        
        for diet in self.diet_terms:
            if diet in combined_text:
                tags.add(diet)
        
        for meal in self.meal_types:
            if meal in combined_text:
                tags.add(meal)
        
        complexity = raw_recipe.get('complexity', self._infer_complexity(raw_recipe))
        if complexity:
            tags.add(complexity + ' recipe')
        
        return list(tags)
    
    def _infer_cuisine(self, raw_recipe):
        """Infer cuisine based on ingredients, title, and text"""
        if 'cuisine' in raw_recipe and raw_recipe['cuisine']:
            return raw_recipe['cuisine']
        
        if 'categories' in raw_recipe:
            for category in raw_recipe['categories']:
                for cuisine in self.common_cuisines:
                    if cuisine in category.lower():
                        return cuisine
        
        title = raw_recipe.get('title', '').lower()
        for cuisine in self.common_cuisines:
            if cuisine in title:
                return cuisine
        
        ingredients_text = ' '.join([str(ing) for ing in raw_recipe.get('ingredients', [])])
        
        cuisine_indicators = {
            'italian': ['pasta', 'parmesan', 'mozzarella', 'basil', 'oregano', 'olive oil'],
            'mexican': ['tortilla', 'salsa', 'cilantro', 'jalapeno', 'chipotle', 'avocado'],
            'asian': ['soy sauce', 'ginger', 'sesame oil', 'rice vinegar', 'sriracha'],
            'indian': ['curry', 'turmeric', 'cumin', 'coriander', 'garam masala']
        }
        
        for cuisine, indicators in cuisine_indicators.items():
            if any(indicator in ingredients_text.lower() for indicator in indicators):
                return cuisine
        
        return None
    
    def _infer_complexity(self, raw_recipe):
        """Infer complexity based on number of ingredients and steps"""
        num_ingredients = len(raw_recipe.get('ingredients', []))
        num_steps = len(raw_recipe.get('instructions', []))
        
        if num_ingredients <= 5 and num_steps <= 3:
            return 'easy'
        elif num_ingredients >= 12 or num_steps >= 8:
            return 'complex'
        else:
            return 'medium'
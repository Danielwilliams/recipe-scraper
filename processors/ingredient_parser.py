# processors/ingredient_parser.py
import re
import logging
from config import FOOD_CATEGORIES

logger = logging.getLogger(__name__)

# Common units of measurement
UNITS = {
    'cup': ['cup', 'cups', 'c', 'c.'],
    'tablespoon': ['tablespoon', 'tablespoons', 'tbsp', 'tbsp.', 'tbs', 'tbs.', 'T'],
    'teaspoon': ['teaspoon', 'teaspoons', 'tsp', 'tsp.', 't'],
    'pound': ['pound', 'pounds', 'lb', 'lb.', 'lbs', 'lbs.'],
    'ounce': ['ounce', 'ounces', 'oz', 'oz.'],
    'gram': ['gram', 'grams', 'g', 'g.'],
    'kilogram': ['kilogram', 'kilograms', 'kg', 'kg.'],
    'liter': ['liter', 'liters', 'l', 'l.'],
    'milliliter': ['milliliter', 'milliliters', 'ml', 'ml.'],
    'clove': ['clove', 'cloves'],
    'piece': ['piece', 'pieces'],
    'pinch': ['pinch', 'pinches'],
    'slice': ['slice', 'slices'],
    'can': ['can', 'cans'],
    'package': ['package', 'packages', 'pkg', 'pkg.']
}

# Reverse mapping for unit identification
UNIT_LOOKUP = {}
for standard, variants in UNITS.items():
    for variant in variants:
        UNIT_LOOKUP[variant] = standard

def parse_ingredient(ingredient_text):
    """
    Parse an ingredient string into structured data
    
    Args:
        ingredient_text (str): Raw ingredient text (e.g., "2 cups flour, sifted")
        
    Returns:
        dict: Structured ingredient data with amount, unit, name, and notes
    """
    ingredient_text = ingredient_text.strip().lower()
    
    # Initialize result dictionary
    result = {
        'name': ingredient_text,
        'amount': None,
        'unit': None,
        'notes': None,
        'category': None
    }
    
    try:
        # Extract quantity, unit, and ingredient name
        # Pattern for quantity: number or fraction at start
        quantity_pattern = r'^(\d+\s*\/\s*\d+|\d+\.\d+|\d+)(\s+to\s+(\d+\s*\/\s*\d+|\d+\.\d+|\d+))?'
        quantity_match = re.search(quantity_pattern, ingredient_text)
        
        if quantity_match:
            # Get the quantity text
            quantity_text = quantity_match.group(0)
            
            # Convert fractions to decimal
            if '/' in quantity_text:
                if ' to ' in quantity_text:
                    parts = quantity_text.split(' to ')
                    quantity_text = parts[0]
                
                if ' ' in quantity_text and not ' to ' in quantity_text:
                    # Mixed number (e.g., "1 1/2")
                    whole_part, frac_part = quantity_text.split()
                    if '/' in frac_part:
                        num, denom = frac_part.split('/')
                        quantity = float(whole_part) + float(num) / float(denom)
                    else:
                        quantity = float(whole_part + '.' + frac_part)
                else:
                    # Simple fraction (e.g., "1/2")
                    if '/' in quantity_text:
                        num, denom = quantity_text.split('/')
                        quantity = float(num) / float(denom)
                    else:
                        quantity = float(quantity_text)
            else:
                # Simple decimal or integer
                quantity = float(quantity_text)
            
            result['amount'] = quantity
            
            # Remove quantity from the text
            ingredient_text = ingredient_text[len(quantity_match.group(0)):].strip()
            
            # Look for units
            unit_pattern = r'^(\s*[a-zA-Z]+\.?\s+)'
            unit_match = re.search(unit_pattern, ingredient_text)
            
            if unit_match:
                unit_text = unit_match.group(0).strip()
                
                # Check if this is a known unit
                for unit_variant in UNIT_LOOKUP:
                    if unit_text == unit_variant or unit_text.startswith(unit_variant + ' '):
                        result['unit'] = UNIT_LOOKUP[unit_variant]
                        # Remove unit from the text
                        ingredient_text = ingredient_text[len(unit_match.group(0)):].strip()
                        break
        
        # Extract notes in parentheses
        notes_pattern = r'\((.*?)\)'
        notes_match = re.search(notes_pattern, ingredient_text)
        
        if notes_match:
            result['notes'] = notes_match.group(1).strip()
            # Remove notes from the name
            ingredient_text = ingredient_text.replace(notes_match.group(0), '').strip()
        
        # Remove any trailing commas, periods
        ingredient_text = re.sub(r'[,\.]+$', '', ingredient_text).strip()
        
        # Ingredient name is what's left
        result['name'] = ingredient_text
        
        # Categorize ingredient
        result['category'] = categorize_ingredient(ingredient_text)
        
        return result
    
    except Exception as e:
        logger.error(f"Error parsing ingredient '{ingredient_text}': {str(e)}")
        return result

def categorize_ingredient(ingredient_name):
    """
    Categorize an ingredient based on predefined categories
    
    Args:
        ingredient_name (str): Ingredient name
        
    Returns:
        str: Category name or None if not categorized
    """
    ingredient_name = ingredient_name.lower()
    
    for category, terms in FOOD_CATEGORIES.items():
        for term in terms:
            if term in ingredient_name:
                return category
    
    return None
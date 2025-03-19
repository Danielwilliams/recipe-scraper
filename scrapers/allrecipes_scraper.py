# Update for AllRecipesScraper

def _extract_from_json_ld(self, soup, url):
    """
    Extract recipe data from JSON-LD
    
    Args:
        soup (BeautifulSoup): Parsed HTML
        url (str): URL of the recipe
        
    Returns:
        dict: Extracted recipe information or None
    """
    script_tag = soup.find('script', {'type': 'application/ld+json'})
    if not script_tag:
        logger.warning(f"No JSON-LD data found in {url}")
        return None
    
    try:
        json_data = json.loads(script_tag.string)
        
        # Sometimes the data is in an array
        if isinstance(json_data, list):
            recipe_data = next((item for item in json_data if item.get('@type') == 'Recipe'), None)
        else:
            recipe_data = json_data if json_data.get('@type') == 'Recipe' else None
        
        if not recipe_data:
            logger.warning(f"No recipe data found in JSON-LD for {url}")
            return None
        
        # Extract basic recipe information
        title = recipe_data.get('name', 'Untitled Recipe')
        
        # Extract ingredients
        ingredients = recipe_data.get('recipeIngredient', [])
        
        # Extract instructions
        instructions = []
        instruction_data = recipe_data.get('recipeInstructions', [])
        
        if isinstance(instruction_data, list):
            for step in instruction_data:
                if isinstance(step, dict) and 'text' in step:
                    instructions.append(step['text'])
                elif isinstance(step, str):
                    instructions.append(step)
        
        # Skip recipes with minimal information
        if len(ingredients) < 3 or len(instructions) < 2:
            logger.warning(f"Recipe has too few ingredients or instructions in JSON-LD: {url}")
            return None
        
        # Extract metadata
        metadata = {}
        
        # Prep time
        if 'prepTime' in recipe_data:
            prep_time = recipe_data['prepTime']
            # Convert ISO duration to minutes
            minutes = self._parse_iso_duration(prep_time)
            if minutes:
                metadata['prep_time'] = minutes
        
        # Cook time
        if 'cookTime' in recipe_data:
            cook_time = recipe_data['cookTime']
            # Convert ISO duration to minutes
            minutes = self._parse_iso_duration(cook_time)
            if minutes:
                metadata['cook_time'] = minutes
        
        # Total time
        if 'totalTime' in recipe_data:
            total_time = recipe_data['totalTime']
            # Convert ISO duration to minutes
            minutes = self._parse_iso_duration(total_time)
            if minutes:
                metadata['total_time'] = minutes
        
        # Servings
        if 'recipeYield' in recipe_data:
            servings = recipe_data['recipeYield']
            if isinstance(servings, list):
                servings = servings[0]
            # Try to extract number
            servings_match = re.search(r'(\d+)', str(servings))
            if servings_match:
                metadata['servings'] = int(servings_match.group(1))
        
        # Categories and keywords
        categories = []
        if 'recipeCategory' in recipe_data:
            categories.extend(recipe_data['recipeCategory'] if isinstance(recipe_data['recipeCategory'], list) else [recipe_data['recipeCategory']])
        
        if 'recipeCuisine' in recipe_data:
            cuisine = recipe_data['recipeCuisine']
            if isinstance(cuisine, list):
                cuisine = cuisine[0] if cuisine else None
            metadata['cuisine'] = cuisine
        
        tags = []
        if 'keywords' in recipe_data:
            keywords = recipe_data['keywords']
            if isinstance(keywords, str):
                tags = [k.strip() for k in keywords.split(',')]
            elif isinstance(keywords, list):
                tags = keywords
        
        # Determine complexity based on number of ingredients and steps
        complexity = "easy"
        if len(ingredients) >= 10 or len(instructions) >= 7:
            complexity = "complex"
        elif len(ingredients) >= 6 or len(instructions) >= 4:
            complexity = "medium"
        
        # UPDATED: Extract image URL with better handling
        image_url = None
        if 'image' in recipe_data:
            image_data = recipe_data['image']
            if isinstance(image_data, list) and image_data:
                # Handle array of images - take the first one
                first_image = image_data[0]
                if isinstance(first_image, dict) and 'url' in first_image:
                    image_url = first_image['url']
                else:
                    image_url = first_image
            elif isinstance(image_data, dict) and 'url' in image_data:
                # Handle image object with url property
                image_url = image_data['url']
            else:
                # Handle direct image URL
                image_url = image_data
        
        # If no image in JSON-LD, try to find it in HTML
        if not image_url:
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                image_url = og_image.get('content')
            
            if not image_url:
                img_tag = soup.find('img', {'class': 'primary-image__image'}) or \
                          soup.find('img', {'class': 'recipe-lead-image'}) or \
                          soup.find('img', {'data-src': True, 'alt': lambda x: x and 'recipe' in x.lower()})
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
        
        return {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions,
            'source': 'AllRecipes',
            'source_url': url,
            'date_scraped': datetime.now().isoformat(),
            'complexity': complexity,
            'tags': tags,
            'categories': categories,
            'metadata': metadata,
            'image_url': image_url,  # Added image URL
            'raw_content': html_content[:1000]  # Store just a portion to save space
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON-LD in {url}: {str(e)}")
        return None

def _extract_from_html(self, soup, url, html_content):
    """
    Extract recipe information from HTML when JSON-LD is not available
    
    Args:
        soup (BeautifulSoup): Parsed HTML
        url (str): Recipe URL
        html_content (str): Raw HTML content
        
    Returns:
        dict: Extracted recipe information
    """
    try:
        # Extract title
        title_elem = soup.select_one('h1.recipe-title') or soup.select_one('h1.headline') or soup.find('h1')
        title = title_elem.text.strip() if title_elem else "Untitled Recipe"
        
        # Extract ingredients
        ingredients = []
        ingredient_elems = soup.select('.ingredients-item-name') or soup.select('.ingredients-list li')
        for elem in ingredient_elems:
            ingredient_text = elem.text.strip()
            if ingredient_text and not ingredient_text.startswith('Add all ingredients to list'):
                ingredients.append(ingredient_text)
        
        # Extract instructions
        instructions = []
        instruction_elems = soup.select('.instructions-section .section-body p') or \
                           soup.select('.recipe-directions__list--item') or \
                           soup.select('.instructions-section li')
        
        for elem in instruction_elems:
            step = elem.text.strip()
            if step and not step.startswith('Watch Now'):
                instructions.append(step)
        
        # Extract image
        image_url = None
        
        # Try multiple image selectors
        image_elem = soup.select_one('.primary-image__image') or \
                    soup.select_one('.recipe-lead-image') or \
                    soup.select_one('.lead-media-image') or \
                    soup.select_one('.universal-image__image')
        
        if image_elem:
            image_url = image_elem.get('src') or image_elem.get('data-src')
        
        # Try OG image as fallback
        if not image_url:
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                image_url = og_image.get('content')
        
        # Try other image containers
        if not image_url:
            image_container = soup.select_one('.image-container') or soup.select_one('.recipe-image')
            if image_container:
                img = image_container.find('img')
                if img:
                    image_url = img.get('src') or img.get('data-src')
        
        # Extract metadata (Prep time, Cook time, etc.)
        metadata = self._extract_metadata(soup)
        
        # Try to extract nutrition information
        nutrition = self._extract_nutrition(soup)
        
        # Determine complexity based on number of ingredients and steps
        complexity = "easy"
        if len(ingredients) >= 10 or len(instructions) >= 7:
            complexity = "complex"
        elif len(ingredients) >= 6 or len(instructions) >= 4:
            complexity = "medium"
        
        return {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions,
            'source': 'AllRecipes',
            'source_url': url,
            'date_scraped': datetime.now().isoformat(),
            'complexity': complexity,
            'metadata': metadata,
            'nutrition': nutrition,
            'image_url': image_url,
            'raw_content': html_content[:1000]  # Store just a portion to save space
        }
    
    except Exception as e:
        logger.error(f"Error extracting recipe from HTML: {str(e)}")
        return None

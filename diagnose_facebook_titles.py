#!/usr/bin/env python3
"""
Diagnostic script to see what titles are being extracted and what's in the database
"""

import os
import re
import logging
import sys
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from database.db_connector import get_db_connection
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    DEPENDENCIES_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def extract_titles_from_html(html_content):
    """Extract titles from HTML and show what we're finding"""
    print("=== EXTRACTING TITLES FROM HTML ===")
    
    # Pattern to find Facebook URLs
    url_pattern = r'href="(https://www\.facebook\.com/groups/[^"]+/(?:permalink|posts)/[^"]+/)"'
    urls = re.findall(url_pattern, html_content)
    
    print(f"Found {len(urls)} Facebook URLs")
    
    titles_found = []
    
    for i, url in enumerate(urls[:10]):  # Check first 10 URLs
        print(f"\n--- URL {i+1}: {url} ---")
        
        # Find the position of the URL in the content
        url_pos = html_content.find(url)
        if url_pos == -1:
            print("URL not found in content")
            continue
        
        # Look in a window around the URL
        window_size = 1000
        start = max(0, url_pos - window_size)
        end = min(len(html_content), url_pos + window_size)
        window = html_content[start:end]
        
        # Show some context
        print("Context around URL:")
        context_start = max(0, url_pos - start - 200)
        context_end = min(len(window), url_pos - start + 200)
        context = window[context_start:context_end]
        print(repr(context))
        
        # Try to find titles
        title_patterns = [
            r'<span[^>]*>([^<]{10,100})</span>',
            r'>([A-Z][^<]{10,80})<',
            r'title="([^"]{10,100})"',
            r'aria-label="([^"]{10,100})"'
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, window)
            if matches:
                print(f"Pattern '{pattern}' found: {matches[:3]}")  # Show first 3 matches
                
                for match in matches:
                    # Clean up the title
                    clean_title = clean_title_text(match)
                    if clean_title and len(clean_title) > 10:
                        titles_found.append(clean_title)
                        print(f"  -> Cleaned title: '{clean_title}'")
    
    print(f"\n=== SUMMARY: Found {len(titles_found)} potential titles ===")
    for title in titles_found[:10]:  # Show first 10
        print(f"  - '{title}'")
    
    return titles_found

def clean_title_text(title):
    """Clean up extracted title"""
    # Remove HTML entities
    title = re.sub(r'&[a-zA-Z0-9#]+;', ' ', title)
    
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Remove emojis and special characters
    title = re.sub(r'[🍽️🔥🍋🧀🥘🌟✨🎉💯❤️👌🤤😋]+', '', title).strip()
    
    # Remove common prefixes/suffixes
    title = re.sub(r'^(Recipe:|Recipe\s+)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+(Recipe)$', '', title, flags=re.IGNORECASE)
    
    return title[:100] if len(title) <= 100 else title[:100]

def get_sample_database_titles():
    """Get sample titles from database"""
    print("\n=== SAMPLE DATABASE TITLES ===")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT id, title, source_url 
                FROM scraped_recipes 
                WHERE source = 'Facebook'
                ORDER BY id DESC 
                LIMIT 20
            """)
            
            results = cursor.fetchall()
            print(f"Found {len(results)} Facebook recipes in database:")
            
            for recipe in results:
                has_url = "✅" if recipe['source_url'] else "❌"
                print(f"  {has_url} ID {recipe['id']}: '{recipe['title']}'")
                if recipe['source_url']:
                    print(f"      URL: {recipe['source_url']}")
            
            return [r['title'] for r in results]
    
    except Exception as e:
        print(f"Error getting database titles: {e}")
        return []
    finally:
        conn.close()

def compare_titles(html_titles, db_titles):
    """Compare HTML titles with database titles"""
    print("\n=== TITLE COMPARISON ===")
    
    print("Looking for potential matches...")
    
    for html_title in html_titles[:10]:  # Check first 10 HTML titles
        print(f"\nHTML Title: '{html_title}'")
        
        # Look for similar database titles
        matches = []
        for db_title in db_titles:
            # Simple similarity checks
            if html_title.lower() in db_title.lower():
                matches.append(('substring', db_title))
            elif db_title.lower() in html_title.lower():
                matches.append(('contains', db_title))
            elif len(set(html_title.lower().split()) & set(db_title.lower().split())) >= 2:
                matches.append(('words', db_title))
        
        if matches:
            print("  Potential matches:")
            for match_type, db_title in matches[:3]:  # Show top 3
                print(f"    {match_type}: '{db_title}'")
        else:
            print("  No obvious matches found")

def main():
    if not DEPENDENCIES_AVAILABLE:
        print("Cannot run diagnostic due to missing dependencies")
        return
    
    # Find FB URLs file
    possible_paths = [
        "data/FB URLs.txt",
        "data/FB_URLs.txt",
        "FB URLs.txt"
    ]
    
    fb_urls_file = None
    for path in possible_paths:
        if os.path.exists(path):
            fb_urls_file = path
            break
    
    if not fb_urls_file:
        print(f"FB URLs file not found in any of these locations: {possible_paths}")
        return
    
    print(f"Using FB URLs file: {fb_urls_file}")
    
    # Read HTML content
    with open(fb_urls_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print(f"Read HTML file: {len(html_content)} characters")
    
    # Extract titles from HTML
    html_titles = extract_titles_from_html(html_content)
    
    # Get database titles
    db_titles = get_sample_database_titles()
    
    # Compare them
    compare_titles(html_titles, db_titles)

if __name__ == "__main__":
    main()
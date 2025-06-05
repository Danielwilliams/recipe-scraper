#!/usr/bin/env python3
"""
Simple test script to extract URLs from FB URLs.txt
"""

import re
import os

def extract_facebook_urls(html_content):
    """Extract Facebook post URLs from HTML content"""
    urls = []
    
    # Pattern to match Facebook post URLs
    url_patterns = [
        r'href="(https://www\.facebook\.com/groups/[\w]+/permalink/[\w]+/)"',
        r'href="(https://www\.facebook\.com/groups/[\w]+/posts/[\w]+/)"',
        r'href="(https://www\.facebook\.com/permalink\.php\?story_fbid=[^"]+)"',
        r'href="(/groups/[\w]+/permalink/[\w]+/)"',
        r'href="(/groups/[\w]+/posts/[\w]+/)"',
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, html_content)
        for match in matches:
            # Convert relative URLs to absolute
            if match.startswith('/'):
                url = f"https://www.facebook.com{match}"
            else:
                url = match
            
            if url not in urls:
                urls.append(url)
    
    return urls

def main():
    fb_urls_file = "/mnt/e/recipe-scraper/FB URLs.txt"
    
    if not os.path.exists(fb_urls_file):
        print(f"FB URLs file not found: {fb_urls_file}")
        return
    
    # Read the HTML content
    with open(fb_urls_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Extract URLs
    urls = extract_facebook_urls(html_content)
    
    print(f"Found {len(urls)} Facebook URLs:")
    for i, url in enumerate(urls[:10], 1):  # Show first 10
        print(f"{i}. {url}")
    
    if len(urls) > 10:
        print(f"... and {len(urls) - 10} more")

if __name__ == "__main__":
    main()
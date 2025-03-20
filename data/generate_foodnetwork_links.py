import json
import os
import re
from bs4 import BeautifulSoup

# Create data directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Function to extract links from HTML content
def extract_links_from_html(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    links = []
    
    link_elements = soup.select('.m-PromoList__a-ListItem a')
    for link in link_elements:
        href = link.get('href')
        if href:
            # Convert relative URLs to absolute
            if href.startswith('//'):
                href = f"https:{href}"
            links.append(href)
    
    return links

# Process all HTML files with recipe links
recipe_links = []

# Process first HTML content (paste.txt)
with open('paste.txt', 'r', encoding='utf-8') as f:
    html_content = f.read()
    links = extract_links_from_html(html_content)
    recipe_links.extend(links)
    print(f"Extracted {len(links)} links from paste.txt")

# Process second HTML content (paste-2.txt) if it exists
try:
    with open('paste-2.txt', 'r', encoding='utf-8') as f:
        html_content = f.read()
        links = extract_links_from_html(html_content)
        recipe_links.extend(links)
        print(f"Extracted {len(links)} links from paste-2.txt")
except FileNotFoundError:
    print("paste-2.txt not found, skipping")

# Remove any duplicates while preserving order
unique_links = []
seen = set()
for link in recipe_links:
    if link not in seen:
        unique_links.append(link)
        seen.add(link)

print(f"Total unique links: {len(unique_links)}")

# Save links to JSON file
with open('data/foodnetwork_links.json', 'w', encoding='utf-8') as f:
    json.dump(unique_links, f, indent=2)
    
print(f"Links saved to data/foodnetwork_links.json")

# Also save HTML files to data directory for reference
with open('data/foodnetwork_recipe_links.html', 'w', encoding='utf-8') as f:
    f.write('<ul class="m-PromoList o-Capsule__m-PromoList">\n')
    for link in unique_links:
        # Extract the relative path
        match = re.search(r'foodnetwork\.com(/.+)', link)
        if match:
            rel_path = match.group(1)
            f.write(f'  <li class="m-PromoList__a-ListItem"><a href="//{link}">{link}</a></li>\n')
        else:
            f.write(f'  <li class="m-PromoList__a-ListItem"><a href="{link}">{link}</a></li>\n')
    f.write('</ul>')
    
print(f"HTML saved to data/foodnetwork_recipe_links.html")
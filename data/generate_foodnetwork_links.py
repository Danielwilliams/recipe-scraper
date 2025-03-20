import json
import os
import re
from bs4 import BeautifulSoup

# Create data directory if it doesn't exist
os.makedirs('foodnetwork_data', exist_ok=True)

# Function to extract links from HTML content
def extract_links_from_html(html_content):
    # Try to use lxml, but fall back to html.parser if not available
    try:
        soup = BeautifulSoup(html_content, 'lxml')
    except:
        soup = BeautifulSoup(html_content, 'html.parser')
    
    links = []
    
    link_elements = soup.select('.m-PromoList__a-ListItem a')
    print(f"Found {len(link_elements)} link elements")
    
    for link in link_elements:
        href = link.get('href')
        if href:
            # Convert relative URLs to absolute
            if href.startswith('//'):
                href = f"https:{href}"
            links.append(href)
    
    return links

# Function to find all .txt files with Food Network HTML content
def process_all_html_files():
    all_links = []
    
    # Look for any txt files that might contain HTML
    html_files = [f for f in os.listdir('.') if f.endswith('.txt')]
    
    if not html_files:
        print("No .txt files found in the current directory.")
        print("Please save your Food Network HTML content in a .txt file.")
        return []
    
    for html_file in html_files:
        try:
            print(f"Processing {html_file}...")
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            links = extract_links_from_html(html_content)
            print(f"Extracted {len(links)} links from {html_file}")
            all_links.extend(links)
        except Exception as e:
            print(f"Error processing {html_file}: {str(e)}")
    
    return all_links

# Main script
links = process_all_html_files()

# Remove any duplicates while preserving order
unique_links = []
seen = set()
for link in links:
    if link not in seen:
        unique_links.append(link)
        seen.add(link)

print(f"Total unique links: {len(unique_links)}")

# Save links to JSON file
with open('foodnetwork_data/foodnetwork_links.json', 'w', encoding='utf-8') as f:
    json.dump(unique_links, f, indent=2)
    
print(f"Links saved to foodnetwork_data/foodnetwork_links.json")
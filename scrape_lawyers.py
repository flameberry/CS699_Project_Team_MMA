import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
import random
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://lawrato.com/lawyers?&page="
OUTPUT_FILE = "lawyers.csv"

def get_lawyer_details(lawyer_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }
    updates = {
        "specialization": "",
        "rating": "N/A",
        "experience": "N/A"
    }
    
    try:
        # print(f"Fetching details for {lawyer_url}...")
        response = requests.get(lawyer_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return updates
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for <span class="item-label">Practice areas: </span>
        labels = soup.find_all('span', class_='item-label')
        for label in labels:
            if 'Practice areas' in label.get_text():
                # The next sibling span contains the comma-separated list
                sibling = label.find_next_sibling('span')
                if sibling:
                    updates["specialization"] = sibling.get_text(strip=True)
            elif 'Experience' in label.get_text():
                 sibling = label.find_next_sibling('span')
                 if sibling:
                     updates["experience"] = sibling.get_text(strip=True)

        # <div class="rating"> <span class="score">4.7</span> ... </div>
        rating_div = soup.find('div', class_='rating')
        if rating_div:
            score_span = rating_div.find('span', class_='score')
            if score_span:
                updates["rating"] = score_span.get_text(strip=True)
                
    except Exception as e:
        print(f"Error scraping details for {lawyer_url}: {e}")
        
    return updates

def scrape_lawyers(max_pages=5):
    all_lawyers = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}{page}"
        print(f"Scraping List Page {page}: {url}...")
        
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # JSON-LD parsing
            scripts = soup.find_all('script', type='application/ld+json')
            page_lawyers = []
            
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'LegalService':
                                lawyer = {
                                    'name': item.get('name'),
                                    'url': item.get('url'),
                                    'image_url': item.get('image'),
                                    'city': item.get('address', {}).get('addressLocality'),
                                    'state': item.get('address', {}).get('addressRegion'),
                                    'address': item.get('address', {}).get('streetAddress'),
                                    # Init placeholders
                                    'specialization': 'General', 
                                    'experience': 'N/A',
                                    'rating': 'N/A'
                                }
                                page_lawyers.append(lawyer)
                except:
                    continue
            
            if page_lawyers:
                print(f"  Found {len(page_lawyers)} lawyers. Fetching details...")
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    urls = [l['url'] for l in page_lawyers]
                    results = list(executor.map(get_lawyer_details, urls))
                    
                for i, lawyer in enumerate(page_lawyers):
                    details = results[i]
                    if details['specialization']:
                        lawyer['specialization'] = details['specialization']
                    if details['rating'] != 'N/A':
                        lawyer['rating'] = details['rating']
                    if details['experience'] != 'N/A':
                        lawyer['experience'] = details['experience']
                        
                all_lawyers.extend(page_lawyers)
            else:
                print(f"No lawyers found on page {page}. Stopping.")
                break
            
            time.sleep(1) 

        except Exception as e:
            print(f"Error scraping page {page}: {e}")
            continue

    df = pd.DataFrame(all_lawyers)
    df.drop_duplicates(subset=['url'], inplace=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Scraping complete. Saved {len(df)} lawyers to {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_lawyers(max_pages=5)

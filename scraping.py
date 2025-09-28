import requests
from bs4 import BeautifulSoup
import time
import json
import pandas as pd  # for CSV/Excel export

BASE_URL = "https://indiankanoon.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36"
}

def search_cases(query, page=0):
    """
    Search India Kanoon and return list of case metadata.
    """
    url = f"{BASE_URL}/search/?formInput={query}&pagenum={page}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch search page: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    cases = []
    for result in soup.select("div.result_title a"):
        case_url = BASE_URL + result.get("href")
        case_title = result.text.strip()

        parent = result.find_parent("div", class_="result_title")
        meta_div = parent.find_next_sibling("div", class_="result_subtitle")
        meta = meta_div.text.strip() if meta_div else ""

        cases.append({
            "title": case_title,
            "url": case_url,
            "meta": meta
        })

    return cases


def get_case_text(case_url):
    """
    Fetch full judgment text from a case URL.
    """
    resp = requests.get(case_url, headers=HEADERS)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch case page: {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.find("div", {"id": "content"})
    text = content_div.get_text(separator="\n").strip() if content_div else ""
    return text


def scrape_india_kanoon(query, max_pages=1, delay=2):
    """
    Scrape India Kanoon search results and fetch judgments.
    """
    all_cases = []

    for p in range(max_pages):
        print(f"Fetching search results page {p+1}...")
        cases = search_cases(query, page=p)
        print(f"  Found {len(cases)} cases")

        for case in cases:
            try:
                case_text = get_case_text(case["url"])
                case["text"] = case_text  # store full text
                all_cases.append(case)
                print(f"    ✔ Scraped {case['title']}")
                time.sleep(delay)
            except Exception as e:
                print(f"    ✘ Failed: {e}")

    return all_cases


def save_to_csv_excel(cases, query):
    """
    Save scraped cases into CSV and Excel.
    """
    df = pd.DataFrame(cases)
    csv_file = f"indiankanoon_{query.replace(' ', '_')}.csv"
    excel_file = f"indiankanoon_{query.replace(' ', '_')}.xlsx"

    df.to_csv(csv_file, index=False, encoding="utf-8")
    df.to_excel(excel_file, index=False, engine="openpyxl")

    print(f"\nSaved {len(cases)} cases → {csv_file} and {excel_file}")


if __name__ == "__main__":
    query = "right to privacy"
    results = scrape_india_kanoon(query, max_pages=1)

    # Preview first case
    print("\nSample result:")
    print(json.dumps(results[0], indent=2))

    # Save all results
    save_to_csv_excel(results, query)

import fitz
import time
import re
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Config
BASE = "https://scr.sci.gov.in"
SEARCH_URL = f"{BASE}/scrsearch/?p=pdf_search/home"
OUT_CSV = "scr_search_results.csv"
PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)
SHORT_DELAY = 0.6
PAGE_LOAD_TIMEOUT = 12
MAX_PDF_VERIFY_BYTES = 4096


def init_driver():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(5)
    return driver


def wait_for_user_to_solve(driver, query="Robbery"):
    driver.get(SEARCH_URL)
    time.sleep(1.0)
    try:
        elem = driver.find_element(By.ID, "search_text")
        elem.clear()
        elem.send_keys(query)
    except Exception:
        pass
    print("\nACTION REQUIRED")
    print("1) In the opened browser, solve the CAPTCHA (if present).")
    print("2) Click the website's Search button.")
    print(
        "3) Wait until results appear. Then come back here and press ENTER to continue."
    )
    input("Press ENTER after the results page shows up in the browser... ")


def get_selenium_cookies(driver):
    return driver.get_cookies()


def attach_cookies_to_session(session, cookies):
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        domain = c.get("domain")
        try:
            if domain:
                session.cookies.set(name, value, domain=domain)
            else:
                session.cookies.set(name, value)
        except Exception:
            pass


# This is the filename fix (for macOS)
def sanitize_filename(s: str):
    # Remove all illegal characters, including colons and forward slashes
    s = re.sub(r'[\\/*?:"<>|:/]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200]


def extract_title_from_pdf(pdf_path):
    """Opens a PDF and attempts to extract the case title from the first page."""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]  # Get first page
        text = page.get_text("text")
        doc.close()

        # Regex to find the text between the INSC line and the line after the title
        match = re.search(r"INSC \d+\s+(.*?)\s+\(", text, re.DOTALL)

        if match:
            title_block = match.group(1)

            # Clean up the text
            title = re.sub(r"\s+V\.\s+", " V. ", title_block)
            # 2. Replace all other newlines and extra spaces with a single space
            title = re.sub(r"\s+", " ", title).strip()

            # Check if it's a valid title (not just whitespace)
            if len(title) > 10:  # Reasonable title length > 10
                return title
        return None
    except Exception as e:
        tqdm.write(f"  [PDF Read Error] {e}")
        return None


def extract_text_from_row_html(html):
    """Takes the HTML of a single TR and returns a dict of its text data."""
    soup = BeautifulSoup(html, "html.parser")
    tr = soup

    title = ""
    citation = ""
    coram = ""
    decision_date = ""
    case_no = ""
    bench = ""

    btn = tr.find("button")
    if btn:
        title = " ".join(btn.stripped_strings)
    else:
        all_a = tr.find_all("a")
        for a in all_a:
            onclick = a.get("onclick", "")
            if "open_pdf" not in onclick:
                title = " ".join(a.stripped_strings)
                if title:
                    break

    es = tr.find("span", class_="escrText")
    if es:
        citation = es.get_text(strip=True)
    strongs = tr.find_all("strong")
    for s in strongs:
        txt = s.get_text(" ", strip=True)
        if txt.lower().startswith("coram"):
            coram = txt

    textall = tr.get_text(" ", strip=True)
    m_date = re.search(
        r"Decision Date\s*[:\-]?\s*([0-9]{2}-[0-9]{2}-[0-9]{4})", textall
    )
    if m_date:
        decision_date = m_date.group(1)

    m_case = re.search(r"Case No\s*[:\-]?\s*([^\|]+)", textall)
    if m_case:
        case_no = m_case.group(1).strip()

    m_bench = re.search(
        r"Bench\s*[:\-]?\s*([0-9]+\s*Judges|[A-Za-z0-9 ,\-&]+)", textall
    )
    if m_bench:
        bench = m_bench.group(1).strip()

    return {
        "title": title,
        "citation": citation,
        "coram": coram,
        "decision_date": decision_date,
        "case_no": case_no,
        "bench": bench,
    }


def verify_and_save_pdf(session, url, out_path, timeout=20):
    """GETs the URL and writes the entire stream to out_path."""
    try:
        resp = session.get(url, stream=True, timeout=timeout, allow_redirects=True)
    except Exception as e:
        tqdm.write(f"\n[Debug] Request failed for {url}: {e}")
        return False

    if resp.status_code != 200:
        tqdm.write(f"\n[Debug] Bad status {resp.status_code} for {url}")
        return False

    try:
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(1024 * 32):  # 32KB chunks
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        tqdm.write(f"\n[Debug] Error during file write for {out_path.name}: {e}")
        return False


# Pagination Helpers
def attempt_next_page_via_datatables(driver):
    js = """
    try {
        var t = $('#example_pdf').DataTable();
        var info = t.page.info();
        if (info.page < info.pages - 1) {
            t.page('next').draw('page');
            return true;
        } else {
            return false;
        }
    } catch(e) {
        return 'DT_ERROR';
    }
    """
    try:
        res = driver.execute_script(js)
    except Exception:
        res = None
    return res


def scrape_and_download(driver, session, base_results_url):
    all_rows_data = []
    current_page_num = 1  # User-facing page number (1-based)
    max_pages_to_scrape = 100
    rate_limit_hit = False

    while current_page_num <= max_pages_to_scrape:
        print(f"\nStarting processing for Page {current_page_num}")

        # 1. Navigate to the target page from scratch
        try:
            print(f"Navigating to base URL...")
            driver.get(base_results_url)
            WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table#example_pdf tbody tr")
                )
            )
            time.sleep(1.5)  # Wait for initial table load

            if current_page_num > 1:
                print(
                    f"Clicking 'Next' {current_page_num - 1} times to reach page {current_page_num}..."
                )
                for click_count in range(current_page_num - 1):
                    first_row_text_before = ""
                    try:
                        first_row_text_before = driver.find_element(
                            By.CSS_SELECTOR, "table#example_pdf tbody tr:first-child"
                        ).text
                    except Exception:
                        tqdm.write(
                            "  Warning: Could not get first row text before click."
                        )

                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        lambda d: d.execute_script(
                            "return typeof jQuery !== 'undefined' && jQuery.fn.dataTable.isDataTable('#example_pdf');"
                        )
                    )
                    js_next_api = """
                    var t = $('#example_pdf').DataTable();
                    var info = t.page.info();
                    if (info.page < info.pages - 1) {
                        t.page('next').draw('page'); return true;
                    } else { return false; }
                    """
                    api_result = driver.execute_script(js_next_api)

                    if api_result is True:
                        tqdm.write(f"  Clicked Next (API) for page {click_count + 2}")
                        tqdm.write("  Waiting for page content to load...")
                        WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until_not(
                            EC.presence_of_element_located(
                                (By.ID, "example_pdf_processing")
                            )
                        )
                        WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until(
                            lambda d: d.find_element(
                                By.CSS_SELECTOR,
                                "table#example_pdf tbody tr:first-child",
                            ).text
                            != first_row_text_before
                        )
                        time.sleep(1.0)  # Stability
                    else:
                        tqdm.write("  API reports no next page.")
                        rate_limit_hit = True  # Treat as end of pages
                        break
                if rate_limit_hit:
                    break 

            print(f"Successfully on Page {current_page_num}")

        except Exception as e:
            print(
                f"Error navigating to page {current_page_num}: {type(e).__name__} - {e}."
            )
            break

        # 2. Get rows for the current page
        try:
            page_rows_elements = driver.find_elements(
                By.CSS_SELECTOR, "table#example_pdf tbody tr"
            )
            num_rows_on_page = len(page_rows_elements)
            if num_rows_on_page == 0:
                print(f"No rows found on page {current_page_num}.")
                break
            print(f"Found {num_rows_on_page} rows.")
        except Exception as e:
            print(f"Error finding rows on page {current_page_num}: {e}.")
            break

        # 3. Process rows for this page only
        for i in range(num_rows_on_page):
            verified_url = ""
            text_data = {}
            saved_path = ""
            title_for_log = f"Row {i + 1}"  # 1-based for logging

            try:
                # 1. Wait for the specific row to be present and find it
                row_selector = f"table#example_pdf tbody tr:nth-child({i + 1})"
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, row_selector))
                )
                time.sleep(0.7)
                row = driver.find_element(By.CSS_SELECTOR, row_selector)

                # 2. Extract text data (using the fixed HTML function)
                row_html = row.get_attribute("outerHTML")
                text_data = extract_text_from_row_html(row_html)
                title_for_log = (
                    text_data.get("title") or text_data.get("case_no") or f"Row {i + 1}"
                )
                tqdm.write(
                    f"Processing (Page {current_page_num}, Row {i + 1}): {title_for_log}"
                )

                # 3. Find and click the PDF link
                pdf_link_element = row.find_element(
                    By.CSS_SELECTOR, "a[onclick*='open_pdf']"
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                    pdf_link_element,
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", pdf_link_element)

                # 4. Wait and get URL
                time.sleep(4.0)
                verified_url = driver.current_url

                # 5. Download Logic
                if verified_url.lower().endswith(".pdf"):
                    tqdm.write(f"  [Found URL] {verified_url}")
                    url_to_download = verified_url.replace(
                        "https://scr.sci.gov.in//", "https://scr.sci.gov.in/"
                    )
                    fname = (
                        sanitize_filename(
                            f"{text_data.get('decision_date') or 'nodate'}_{title_for_log}"
                        )
                        + ".pdf"
                    )
                    out_path = PDF_DIR / fname
                    ok = verify_and_save_pdf(session, url_to_download, out_path)

                    if ok:
                        saved_path = str(out_path)
                        tqdm.write(f"  [SAVED] {fname}")

                        pdf_title = extract_title_from_pdf(out_path)
                        if pdf_title:
                            text_data["title"] = (
                                pdf_title  # Overwrite with the better title
                            )
                            print(
                                "Extracted and overwritten title from pdf: ", pdf_title
                            )
                            tqdm.write(f"  [Found PDF Title] {pdf_title}")

                            # Rename the pdf with the title found
                            new_path = PDF_DIR / f"{pdf_title}.pdf"
                            try:
                                out_path.rename(new_path)
                                saved_path = str(new_path)
                            except:
                                print("Failed to rename pdf")

                    else:
                        tqdm.write(
                            f"  [FAIL] Failed to save file from: {url_to_download}"
                        )
                else:
                    tqdm.write(
                        f"  [STOP] Rate-limit likely hit. URL was not a PDF: {verified_url}"
                    )
                    rate_limit_hit = True

                # Navigation Logic
                delay = random.uniform(3.5, 5.5)
                tqdm.write(f"  Delaying for {delay:.1f}s...")
                time.sleep(delay)

                tqdm.write(f"  Returning to base results page...")
                driver.get(base_results_url)
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "table#example_pdf tbody tr")
                    )
                )

                if current_page_num > 1:
                    tqdm.write(f"  Re-navigating to Page {current_page_num}...")
                    for click_count in range(current_page_num - 1):
                        first_row_text_before = ""
                        try:
                            first_row_text_before = driver.find_element(
                                By.CSS_SELECTOR,
                                "table#example_pdf tbody tr:first-child",
                            ).text
                        except Exception:
                            pass

                        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                            lambda d: d.execute_script(
                                "return typeof jQuery !== 'undefined' && jQuery.fn.dataTable.isDataTable('#example_pdf');"
                            )
                        )
                        js_next_api = "var t = $('#example_pdf').DataTable(); var info = t.page.info(); if (info.page < info.pages - 1) { t.page('next').draw('page'); return true; } else { return false; }"
                        api_result = driver.execute_script(js_next_api)

                        if api_result is True:
                            WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until_not(
                                EC.presence_of_element_located(
                                    (By.ID, "example_pdf_processing")
                                )
                            )
                            WebDriverWait(driver, PAGE_LOAD_TIMEOUT + 5).until(
                                lambda d: d.find_element(
                                    By.CSS_SELECTOR,
                                    "table#example_pdf tbody tr:first-child",
                                ).text
                                != first_row_text_before
                            )
                        else:
                            tqdm.write(
                                "  Error: API reports no next page during re-click."
                            )
                            rate_limit_hit = True
                            break
                    if rate_limit_hit:
                        break  # Exit row loop

                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "table#example_pdf tbody tr")
                    )
                )
                time.sleep(1.5)  # Final stability wait

            except Exception as e:
                tqdm.write(
                    f"  [ERROR] Failed to process (Page {current_page_num}, Row {i + 1}): {type(e).__name__} - {e}"
                )
                tqdm.write("  Attempting to recover by reloading base URL...")
                try:
                    driver.get(base_results_url)  # Go to base URL
                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        EC.presence_of_element_located((By.ID, "example_pdf"))
                    )
                    tqdm.write("  Recovery successful. Continuing to next row...")
                    continue  # Skip saving this row, move to next 'i'
                except Exception as recovery_e:
                    tqdm.write(f"  [CRITICAL] Recovery failed: {recovery_e}.")
                    rate_limit_hit = True  # Treat as fatal

            # Save data
            text_data["pdf_path_or_url"] = saved_path or verified_url
            all_rows_data.append(text_data)

            if rate_limit_hit:
                break  # Exit row loop

        if rate_limit_hit:
            print("Rate limit hit or error, stopping outer page loop.")
            break  # Exit page loop

        # 4. Check for next page and increment
        try:
            WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                lambda d: d.execute_script(
                    "return typeof jQuery !== 'undefined' && jQuery.fn.dataTable.isDataTable('#example_pdf');"
                )
            )
            js_page_info = "return $('#example_pdf').DataTable().page.info();"
            info = driver.execute_script(js_page_info)

            if info and info["page"] < info["pages"] - 1:
                current_page_num += 1
                print(
                    f"Finished page {current_page_num - 1}. Proceeding to page {current_page_num}."
                )
            else:
                print("Reached the last page according to DataTables or info is null.")
                break  # Exit the outer while loop
        except Exception as e:
            print(f"Error getting page info to check for next page: {e}.")
            break
        # End of outer while loop for pages

    return all_rows_data


def main():
    driver = init_driver()

    # Create one session to be used for all downloads
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    base_results_url = None

    try:
        wait_for_user_to_solve(driver, query="Robbery")

        # Capture the base results page URL after solving CAPTCHA and searching
        base_results_url = driver.current_url
        print(f"Base results URL captured: {base_results_url}")

        # Update session with cookies and Referer from the logged-in page
        cookies = get_selenium_cookies(driver)
        attach_cookies_to_session(session, cookies)
        session.headers.update({"Referer": base_results_url})  # Use base URL as referer

        # This one function now does all the work
        scraped_data = scrape_and_download(driver, session, base_results_url)

        print(f"\nAll Scraping Complete")
        print(f"Collected {len(scraped_data)} rows from search results.")
        if not scraped_data:
            print("No rows found. Exiting.")
            return

        # Save the collected data to CSV
        df = pd.DataFrame(scraped_data)
        df.to_csv(OUT_CSV, index=False)

        print(f"Saved CSV: {OUT_CSV}")
        print(f"PDF folder: {PDF_DIR.resolve()}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        session.close()


if __name__ == "__main__":
    main()

project-root/
│
├── csv/                          # Holds the CSVs for various scraping sessions of Supreme Court Website
│
├── pdfs/                         # Stores scraped or uploaded PDF documents
│
├── .gitignore                    # Specifies files/folders to ignore in Git
│
├── app.py                        # Main Flask application entry point
├── Check-LLM.py                  # Script to validate available LLM models
├── lawyers.csv                   # Scraped Lawyer data
├── merge_all_csv.py              # Script to merge multiple CSVs into one
├── scrape_merged_data.csv        # Final merged dataset from scraping
├── README.md                     # Project overview and documentation
├── requirements.txt              # Python dependencies for the project
├── scraping.py                   # Main scraping logic for documents or lawyers
├── scrape_lawyers.py             # Specific scraper for lawyer data
├── users.csv                     # User data DB (login, history, cases, lawyers)
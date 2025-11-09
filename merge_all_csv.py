import pathlib
import fitz
import pandas as pd

CSV_PATH = pathlib.Path("./csv")
PROJECT_ROOT_DIR = pathlib.Path(__file__).parent


if __name__ == "__main__":
    merged_csv = pd.DataFrame()
    for csv in CSV_PATH.iterdir():
        if csv.is_file():
            merged_csv = pd.concat(
                [merged_csv, pd.read_csv(csv)],
                axis=0,
                ignore_index=True,
            )
    merged_csv.dropna(inplace=True)
    merged_csv.reset_index(drop=True)

    mask = ~merged_csv["pdf_path_or_url"].astype(str).str.contains("https", na=False)
    merged_csv = merged_csv[mask]

    merged_csv.drop_duplicates(inplace=True)
    merged_csv.reset_index(drop=True, inplace=True)

    merged_csv["snippet"] = ""
    # Add the snippet column to each row of the merged csv
    for i, path in enumerate(merged_csv["pdf_path_or_url"]):
        pdf_path = PROJECT_ROOT_DIR / path

        if not pdf_path.is_file():
            print(merged_csv.loc[i, "title"])

        doc = fitz.open(pdf_path)
        # Get first page of the pdf
        page = doc[0]
        text = page.get_text("text")
        doc.close()

        snippet = ""
        found = False
        for line in str(text).splitlines():
            if found:
                snippet += line
            if "Headnotes" in line:
                found = True

        merged_csv.at[i, "snippet"] = snippet

    merged_csv.to_csv("merged_scraped_data.csv", index=False)

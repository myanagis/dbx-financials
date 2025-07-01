import requests
from shared import data_access
import streamlit as st
from bs4 import BeautifulSoup, NavigableString
import pandas as pd
import numpy as np
import zipfile
import io
import html2text
from markdownify import markdownify as md
import re
from datetime import datetime, date
from dateutil.parser import parse

###### 
HEADERS = {"User-Agent": "Your Name/your_email@example.com"}


####
# Tidying tables and HTML

def clean_up_soup(soup):
    
    # Remove <?xml ...?> declarations (not inside soup, but can show up in raw text)
    # Find only top-level text nodes (e.g., those not wrapped in a tag)
    i = 0
    for node in soup.find_all(string=True):
        if "xml" in node:
            node.extract()

    # Remove <title>, <meta>, <link> tags
    for tag in soup.find_all(["title", "meta"]):
        tag.decompose()

    # Remove <div style="display:none"> and other hidden divs
    for div in soup.find_all("div", style=True):
        if "display:none" in div.get("style", "").replace(" ", "").lower():
            div.decompose()


def is_empty_cell(text):
    return not text.strip()

def tidy_html_tables_in_soup(soup):
  # Step 1: Find all <table> elements
  tables = soup.find_all("table")

  # Step 3: Loop through each table
  for table_idx, table in enumerate(tables):
      #print(f"\nTable {table_idx + 1}--------")
      tidy_html_table(table)
      


def tidy_html_table(table):
    table_empty_tracker = []

    # Step 1a: Remove empty rows --------------
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        is_full_row_empty = all(is_empty_cell(cell.get_text(separator=" ", strip=True)) for cell in cells)
        
        if is_full_row_empty:
            row.decompose()  # Removes the tag from the tree


    # Step 1b. If the table has no rows after step 1a, then remove it ------
    rows = table.find_all("tr")
    if len(rows) == 0:
        table.decompose()  # Removes the entire <table> from the DOM
        return

    # Step 2: Find the columns we can remove --------------
    
    for _, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        
        start_col, end_col = 1, 1
        row_empty_tracker = []

        for cell_idx, cell in enumerate(cells):
            text = cell.get_text(separator=" ", strip=True)
            colspan = int( cell.get("colspan", 1) )
            is_empty = is_empty_cell(text)

            # Calculate the start/end columns
            end_col = start_col + colspan

            # Build the "empty row tracker" to see which columns are empty. Pieces: (isempty:bool, colspan: int, is_first_col_in_colspan: bool)
            row_empty_tracker += [(is_empty, colspan, True)] 
            if colspan > 1:
              row_empty_tracker += [(is_empty, colspan, False)] * (colspan - 1)

            start_col = end_col
        
        # After processing a row, merge the table empty tracker with the row empty tracker
        
        # Initialize
        while end_col >= len(table_empty_tracker):
            table_empty_tracker.append(True)
        #if len(table_empty_tracker) == 0:
        #  table_empty_tracker = [True] * end_col
        
        # If the row is empty OR row's colspan > 1, then the col still has the potential to be removed
        # (Note: always keep the first column of the colspan ... this is kind of arbitrary but keeps the logic simpler)
        merged_table_tracker = []
        for ix, table_tracker in enumerate(table_empty_tracker):
            row_tracker = row_empty_tracker[ix] if ix < len(row_empty_tracker) else (True, 1, False)
            text_is_empty = row_tracker[0]
            is_nonfirst_piece_of_colspan = (row_tracker[1] > 1) and (not row_tracker[2])

            if table_tracker and (text_is_empty or is_nonfirst_piece_of_colspan):
                merged_table_tracker.append(True)
            else:
                merged_table_tracker.append(False)

        table_empty_tracker = merged_table_tracker

    # We have a list of table_empty_tracker, full of the columns that we actually want
    cols_to_keep =  [not x for x in table_empty_tracker]
    if all(cols_to_keep):
      return

    # Step 3: Remove the columns that we don't need --------------
    for _, row in enumerate(rows):
        cells_list = list(row.find_all(["td", "th"]))
        
        start_col, end_col = 1, 1
        row_empty_tracker = []
        #print("Row ----")

        for cell_idx, cell in enumerate(cells_list):
            text = cell.get_text(separator=" ", strip=True)
            style = cell.get("style", "")
            colspan = int( cell.get("colspan", 1) )

            end_col = start_col + colspan

            #print("Processing cell", text, ""...")
            # Is this col one that we want to remove?
            
            # Case 1: this is just a single cell. Just remove it.
            if colspan == 1:
              if not cols_to_keep[start_col - 1]:
                  cell.decompose()

            # Case 2: this is a col-span. Count how many cols this now spans.
            else:
              cols_to_keep_slice = cols_to_keep[start_col - 1:end_col-1]
              count_of_cols_to_keep = sum(cols_to_keep_slice)

              if count_of_cols_to_keep == 0:
                cell.decompose()
              else:
                cell["colspan"] = count_of_cols_to_keep

            start_col = end_col


def inline_styles_to_semantic(soup):

    for span in soup.find_all("span"):
        style = span.get("style", "").lower()
        new_wrapper = None

        # Bolding
        if "font-weight" in style:
            weight_value = style.split("font-weight:")[1].split(";")[0].strip()
            try:
                weight = int(weight_value)
            except ValueError:
                weight = 700 if "bold" in weight_value else 400
            if weight >= 600:
                new_wrapper = soup.new_tag("strong")

        # Italic
        if "font-style:italic" in style:
            new_wrapper = soup.new_tag("em")

        # Underline
        if "text-decoration" in style and "underline" in style:
            new_wrapper = soup.new_tag("u")

        # Font Size
        if "font-size" in style:
            size_str = style.split("font-size:")[1].split(";")[0].strip()
            try:
                size_val = float(size_str.replace("px", "").replace("pt", ""))
                if size_val >= 24:
                    new_wrapper = soup.new_tag("h1")
                elif size_val >= 18:
                    new_wrapper = soup.new_tag("h2")
                elif size_val >= 14:
                    new_wrapper = soup.new_tag("h3")
            except ValueError:
                pass

        # If we chose a wrapper, replace span with the wrapped content
        if new_wrapper:
            new_wrapper.string = span.get_text()
            span.replace_with(new_wrapper)

############################
# Data retrieval

def get_cik_from_ticker_cik_link(ticker_cik_link_df, ticker):
    return ticker_cik_link_df.loc[ticker, data_access.FactTickerCIKLinkSchema.COL_CIK_STR]


def get_filings_for_cik(cik:str):

    # Headers for requests

    # Step 1: Retrieve the latest filing URLs
    base_url = 'https://data.sec.gov/submissions/CIK{}.json'.format(str(cik).zfill(10))
    try:
        response = requests.get(base_url, headers=HEADERS)
        response.raise_for_status()
        filing_data = response.json()
    except Exception as e:
        raise

    # Step 2: Extract document URL for a specific filing type
    recent_filings = filing_data['filings']['recent']

    # Create a dataframe of recent filings
    recent_filings_dict = {}
    for tag in recent_filings:
        recent_filings_dict[tag] = recent_filings[tag]
    filings_df = pd.DataFrame(recent_filings_dict)

    
    # Cast the date columns
    filings_df["filingDate"] = pd.to_datetime(filings_df["filingDate"], errors="coerce")

    return filings_df

def build_link_to_primary_document(cik, accession_number, primary_document):
    accession_number_no_dashes = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number_no_dashes}/{primary_document}"


def build_link_to_full_submission_file(cik, accession_number):
    accession_number_no_dashes = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number_no_dashes}/{accession_number}.txt"


def parse_sec_edgar_full_submission_file(cik, accession_number):
    url = build_link_to_full_submission_file(cik, accession_number)
    
    try:
        response = requests.get(url, headers=HEADERS) 
        response.raise_for_status()
    except:
        raise

    raw_txt = response.text

    # --- Step 1: Extract all <DOCUMENT>...</DOCUMENT> blocks safely ---
    documents = re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw_txt, re.DOTALL)

    parsed_docs = []

    def extract_field(tag):
            match = re.search(fr"<{tag}>(.*?)\n", doc)
            return match.group(1).strip() if match else None

    # Loop through all the documents
    for i, doc in enumerate(documents):
    
        # Get all of the information from the file
        doc_type = extract_field("TYPE")
        filename = extract_field("FILENAME")
        description = extract_field("DESCRIPTION")

        # FILTERS ---
        # If it doesn't end in ".htm", don't include it
        if not filename.lower().endswith(".htm"):
            continue
        if doc_type == "XML": # I don't love this check -- it needs to be refined
            continue

        text_match = re.search(r"<TEXT>(.*)", doc, re.DOTALL)
        text = text_match.group(1).strip() if text_match else ""

        parsed_docs.append({
            "type": doc_type,
            "filename": filename or f"doc_{i}.txt",
            "description": description,
            "text": text
        })

    # --- Step 2: Now parse the TEXT field with BeautifulSoup *if* it's HTML ---

    full_markdown = ""
    for doc in parsed_docs:
        doc_type = doc["type"]
        filename = doc["filename"]
        description = doc["description"]
        text = doc["text"]
        
        # st.write(f"\n--- {doc['type']} ({doc['filename']}) ---")

        soup = BeautifulSoup(text, "html.parser")
        md_header = f"# {doc_type} ({filename})"
        md_output = convert_soup_to_markdown(soup)

        full_markdown += md_header + "\n" + md_output + "\n\n***\n***\n\n" # divider

    return full_markdown

def convert_soup_to_markdown(soup):
    clean_up_soup(soup)
    tidy_html_tables_in_soup(soup)
    inline_styles_to_semantic(soup)
    md_output = md( str(soup) , heading_style="ATX")
    return md_output


def retrieve_filings_text(filings_df, cik, filing_types:list, start_year, end_year, display_progress=False):
    
    # Filter by filing type and year
    filtered_df = filings_df[ filings_df["form"].isin(filing_types) ] 
    filtered_df = filtered_df[(filtered_df["filingDate"].dt.year.isin(range(start_year, end_year+1))) ]

    md_filings_list = []

    for index, row in filtered_df.iterrows():
        accession_number = row.get("accessionNumber")
        filing_date = row.get("filingDate")
        report_date = row.get("reportDate")
        form = row.get("form")
        items = row.get("items")
        # core_type = row.get("core_type")
        primary_document = row.get("primaryDocument")

        md = parse_sec_edgar_full_submission_file(cik, accession_number)
        md_filings_list.append(
            {
                "accession_number": accession_number,
                "filing_date": filing_date,
                "report_date": report_date,
                "form": form,
                "items": items,
                "md_text": md,
                "primary_document": primary_document
            }
        )

        if display_progress:
            st.write(f"Retrieving {form} filed on {try_format_date(filing_date)}...")
    
    #st.write("Count: ", len(filtered_df))
    #st.dataframe(filtered_df)
    return md_filings_list

def try_format_date(value):
    try:
        # If it's a Pandas Series with datetime-like values
        if isinstance(value, pd.Series) and pd.api.types.is_datetime64_any_dtype(value):
            return value.dt.date
        # If it's a single datetime or date
        elif isinstance(value, (datetime, date)):
            return value.date() if isinstance(value, datetime) else value
        # If it's a string
        elif isinstance(value, str):
            return parse(value).date()
    except Exception:
        pass
    return value  # Return original if not parsable

def zip_all_filesand_create_button(md_filings_list, ticker, cik):
    # --- Create ZIP archive in memory ---
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filing in md_filings_list:
            accession_number = filing.get("accession_number")
            filing_date = filing.get("filing_date")
            filing_date = try_format_date(filing_date)
            report_date = filing.get("report_date")
            form = filing.get("form")
            items = filing.get("items")
            md_text = filing.get("md_text")
            primary_document = filing.get("primary_document")
            primary_document_link = build_link_to_primary_document(cik, accession_number, primary_document)
            
            filename = f"{ticker} {form} ({filing_date}).txt"

            header =   "---"
            header += f"Form:             {form}"
            header += f"Filing Date:      {filing_date}"
            header += f"Report Date:      {report_date}"
            header += f"Items:            {items}"
            header += f"Primary Document: {primary_document_link}"
            header += f"Accession Number: {accession_number}"
            header += f"---"
            zipf.writestr(filename, header + "\n" + md_text)

    # Seek to start so Streamlit can read it
    zip_buffer.seek(0)

    st.download_button(
        label="Download All as ZIP",
        data=zip_buffer,
        file_name=f"{ticker} filings.zip",
        mime="application/zip"
    )

import pandas as pd
import streamlit as st
import requests
from shared import data_access, sec_edgar_utils
from datetime import datetime


# Title
st.title("SEC EDGAR File Download")

# Interlude
st.write("""
This utility downloads filings from [SEC EDGAR](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and
converts them into Markdown files (which are very useful for LLMs). This list of text (.txt) files is then packaged into a
zip file for you to download.

This utility does minor clean-up on the filings' tables (which have a lot of blank rows/columns). If a filing contains attached "exhibits," 
then the exhibits are added to the end of the given file.

Questions/comments? Email me at michael.yanagisawa@gmail.com

""")

st.divider()


##################
### Inputs #######
##################
st.subheader("Inputs")

# Input: ticker
conn = data_access.connect_to_database() 
ticker_cik_link_df = data_access.get_ticker_to_cik_map(conn)
selected_ticker = st.selectbox("Ticker", 
                               ticker_cik_link_df.index,
                               format_func=lambda ticker: f"""{ticker_cik_link_df.loc[ticker, data_access.FactTickerCIKLinkSchema.COL_TITLE]} ({ticker}) """ )

# Input: filing types
all_option = "all"
filing_types = ["10-K", "10-Q", "8-K", "3", "4", "5", "13D", "13G", "144"]
selected_filing_types = st.pills("Filings to include:", 
                                    filing_types + [all_option],  
                                    selection_mode="multi",
                                    default=["10-K", "10-Q", "8-K"])
if all_option in selected_filing_types:
    selected_filing_types = filing_types

# Input: date range
now = datetime.now()
current_year = now.year
selected_range = st.slider(
    "FIling years to include:", 
    min_value=2010,
    max_value=current_year,
    value=(current_year-2, current_year)
)
start_year = selected_range[0]
end_year = selected_range[1]


st.caption("Note: the API only retrieves at least the last year of filings, but only up to the last 1000 filings.")


return_format = st.pills("Output format", options=["markdown", "html"], default="markdown")

# ------------------------------------
# Processing
cik = sec_edgar_utils.get_cik_from_ticker_cik_link(ticker_cik_link_df, selected_ticker)
if cik is None:
    st.error(f"Unable to find CIK {cik}. Please select another stock ticker.")
    st.stop()

##################
### Results ######
##################

st.divider()

st.subheader("Results")

if st.button("Click for results"):
    
    try:
        # Step 1: Get the filings
        filings_df = sec_edgar_utils.get_filings_for_cik(cik)

        # Step 2: Look up all the filing text
        with st.status("Downloading data from the SEC ...", expanded=False) as status:
            md_filings_list = sec_edgar_utils.retrieve_filings_text(filings_df, cik, selected_filing_types, 
                                                                    start_year, end_year, 
                                                                    display_progress_to_streamlit=True,
                                                                    return_format=return_format)

        zip_buffer = sec_edgar_utils.zip_all_files_and_create_button(md_filings_list, selected_ticker, cik)

        # Step 3. Create download button
        st.download_button(
            label="Download All as ZIP",
            data=zip_buffer,
            file_name=f"{selected_ticker} filings.zip",
            mime="application/zip"
        )

    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed: {e}")
    except Exception as e:
        st.exception(e)  # Shows full traceback nicely in Streamlit

    
    
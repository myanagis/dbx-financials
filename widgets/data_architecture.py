import streamlit as st
import pandas as pd

# PREP ----
st.set_page_config(page_title="Data Architecture | Mike Yanagisawa",
                   layout="wide")

st.title(f"Data Architecture")
st.caption("Mike Yanagisawa | June 5, 2025")

st.write("""
In a data project, the work is typically broken down into two parts:

1. Data gathering/wrangling (more professionally known as "data engineering"), and
2. Insight generation (aka "data analysis")

These two roles are often employed by two distinct people. The first builds the data pipelines, figuring out where all the data lives, how frequently to import it, and what transformations need to be done to be able to easily manipulate the data. The second then takes this data and runs regressions, builds charts, etc. to draw insights. 

         """)

st.divider()

st.subheader("Data Pipelines")

data_pipelines = {
    "2024 NACUBO-Commonfund Study of Endowments":
        {
            "Description": "Analysis of endowment returns done in 2024",
            "Data Collected": "List of university systems",
            "Data Format": "Excel file",
            "Frequency": "One-time download",
            "Link": "https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fedge.sitecorecloud.io%2Fnacubo1-nacubo-prd-dc8b%2Fmedia%2FNacubo%2FDocuments%2FEndowmentFiles%2F2024-NCSE-Endowment-Market-Values-for-US-and-Canadian-Institutions-FINAL-Feb-12-2025.xlsx&wdOrigin=BROWSELINK"
        },
    "Propublica/Federal 990 Filings":
        {
            "Description": "Annual filings required by US non-profits. Looked up with tax ID (or EIN)",
            "Data Collected": "Financial information, including endowment level and expenses",
            "Data Format": "XMLs pulled from Propublica",
            "Frequency": "Yearly",
            "Link": ""
        },

}

data_pipelines_df = pd.DataFrame(data_pipelines)
st.table(data_pipelines_df.T)

data_processing = {
    "2024 NACUBO-Commonfund Study of Endowments":
        {
            "Processing": "Copy first few columns and load.",
            "Notes": "Some university systems roll up multiple schools from multiple campuses (especially public universities). Some universities also have foundations that hold the endowment funds. Some non-universities are listed, too."},
    "Propublica/Federal 990 Filings":
        {
            "Processing": "Minimal.",
            "Notes": "TBD"},

}
# Import python packages
import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from databricks import sql


# Define the pages
#main_page = st.Page("streamlit_app.py", title="Main Page")
endowment_tax = st.Page("widgets/endowment_tax_analysis.py", title="Endowment Tax: Portfolio Allocation")
endowment_tax_by_university = st.Page("widgets/endowment_tax_by_university.py", title="Endowment Tax By University (beta)")
historical_returns = st.Page("widgets/historical_returns.py", title="Historical Returns")
data_architecture = st.Page("widgets/data_architecture.py", title="Data Architecture")
pdf_parser = st.Page("widgets/pdf_parser.py", title="PDF Parser")
sec_file_download = st.Page("widgets/sec_file_download.py", title="SEC File Download")
llm_tester = st.Page("widgets/llm_tester.py", title="LLM Testing Utility")
llm_chat = st.Page("widgets/llm_chat.py", title="LLM Chat")
call_logger = st.Page("widgets/call_logger.py", title="Call logger")

# Set up navigation
pg = st.navigation(
    {
        #"Home": [main_page],
        #"Tools": [endowment_tax, historical_returns]
        #"Tools": [endowment_tax, endowment_tax_by_university, sec_file_download, historical_returns, data_architecture, llm_tester, llm_chat, call_logger]
        "Tools": [endowment_tax, sec_file_download, historical_returns, pdf_parser]
    }
)
pg.run()



st.divider()

# Footer
current_year = datetime.now().year
if current_year == 2025:
    date_range_str = "2025"
else:
    date_range_str = f"2025-{current_year}"
st.markdown(
    f"""
    <div style="text-align: center; color=gray; font-size: 0.8em;">
     &copy; {date_range_str} Mike Yanagisawa | <a href="https://github.com/myanagis/dbx-financials">Github</a> | 
     Feedback or comments? Email: michael.yanagisawa (at) gmail.com
    </div>
""", unsafe_allow_html=True
)
# Import python packages
import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from databricks import sql


# Define the pages
#main_page = st.Page("streamlit_app.py", title="Main Page")
endowment_tax = st.Page("widgets/endowment_tax_analysis.py", title="Endowment Tax Analysis")
historical_returns = st.Page("widgets/historical_returns.py", title="Historical Returns")

# Set up navigation
pg = st.navigation(
    {
        #"Home": [main_page],
        "Tools": [endowment_tax, historical_returns]
    }
)
pg.run()

import streamlit as st
from databricks import sql
import pandas as pd
from datetime import datetime


from shared import data_access, finance_utils, display_utils

# Helpers for displaying in streamlit -----

# 
def get_column_config_for_percentage_df(df):
    column_config = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            column_config[col] = st.column_config.NumberColumn(
                col,
                format = "%.2f%%"
            )
    return column_config



### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
conn = data_access.connect_to_databricks()

lookback_years_list = [1, 3, 5, 10, 20, 30]

end_year = datetime.now().year
start_year = end_year - max(lookback_years_list)

monthly_returns_df = data_access.get_benchmark_returns_data(conn, start_year, end_year )

# Historical returns ------
def geometric_mean(series):
    if len(series) == 0:
        return(float('nan'))
    product = (1 + series).prod()
    return product ** (1 / len(series)) - 1

def annualize_monthly_geometric_mean(monthly_geometric_mean):
    return (1 + monthly_geometric_mean)**12 - 1
    
# Constants etc.
max_date = monthly_returns_df.index.max()
means_dict = {}

# %%TODO>correctness - check for NaN handling

index_display_names = {
    "DJUSRE": "Dow Jones U.S. Real Estate Index",
    "DJUSRET": "Dow Jones U.S. Real Estate Total Return",
    "HEDGNAV": "Credit Suisse Hedge Fund Index",
    "LBUSTRUU": "Bloomberg Barclays US Aggregate Bond Index", 
    "NDUEACWF": "MSCI ACWI ETF",
    "RU20INTR": "Russell 2000 Total Return",
    "SPBDUB3T": "S&P U.S. Treasury Bill 0-3 Month",
    "SPGINRTR": "S&P Global Natural Resources",
    "SPXT": "Proshares S&P 500 EX-Technology ETF Fund"
}

# Timeframes
timeframes = {}
# Add the following years
# Build a dictionary: {"1Y": (start_date, end_date), ...}
for years_lookback in lookback_years_list:
    upper_cutoff = max_date 
    lower_cutoff = max_date - years_lookback*100
    timeframes[str(years_lookback)+"Y"] = (lower_cutoff, upper_cutoff)


for label, cutoff_params in timeframes.items():
    lower_cutoff, upper_cutoff = cutoff_params

    # %%TODO>refactor%% - This is subtle -- it should only include the past 12 months
    subset = monthly_returns_df[(monthly_returns_df.index > lower_cutoff) &
                                (monthly_returns_df.index <= upper_cutoff)  ] 
    
    # Build a dictionary:
    #  {"1Y": [list of means for all asset classes]}
    means_dict[label] = subset.apply(geometric_mean).apply(annualize_monthly_geometric_mean)


#model_portfolio_df = model_portfolio_df.rename(columns={model_portfolio_name: "Portfolio Weights"})

means_df_tmp = pd.DataFrame(means_dict)

# Add display name
means_df_tmp["Display Name"] = means_df_tmp.index.map(index_display_names)

# Tidy up for display
columns_to_display = ["Display Name"] + list(timeframes.keys())
means_df = means_df_tmp[columns_to_display]
means_df.index.name = "Ticker"


# Display

# DISPLAY ---------------
st.title("Historical Returns")

st.markdown("""
Calculates the mean historical (geometric) returns for the following tickers using monthly data. Information current up to Feb 2025.
            """)
display_utils.display_streamlit_table(means_df)

st.caption("Source: Bloomberg. Table above shows annualized returns, looking back X months starting with the most recent data")

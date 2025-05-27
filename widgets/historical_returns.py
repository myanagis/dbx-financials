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

end_year = datetime.now().year()
start_year = end_year - lookback_years_list.max()

pivot_df = data_access.get_benchmark_returns_data(conn, start_year, end_year)

# Historical returns ------
def geometric_mean(series):
    if len(series) == 0:
        return(float('nan'))
    product = (1 + series).prod()
    return product ** (1 / len(series)) - 1

def annualize_monthly_geometric_mean(monthly_geometric_mean):
    return (1 + monthly_geometric_mean)**12 - 1
    
# Constants etc.
max_date = pivot_df.index.max()
means_dict = {}

# %%TODO>correctness - check for NaN handling

# Timeframes
timeframes = {}
# Add the following years
for years_lookback in lookback_years_list:
    upper_cutoff = max_date 
    lower_cutoff = max_date - years_lookback*100
    timeframes[str(years_lookback)+"Y"] = (lower_cutoff, upper_cutoff)

# Also add the custom timeframe entered
'''
upper_cutoff = (end_year+1)*100 - 1 # TODO>refactor
lower_cutoff = start_year*100
timeframes["Custom timeframe"] = (lower_cutoff, upper_cutoff)
'''

for label, cutoff_params in timeframes.items():
    lower_cutoff, upper_cutoff = cutoff_params

    # %%TODO>refactor%% - This is subtle -- it should only include the past 12 months
    subset = pivot_df[(pivot_df.index > lower_cutoff) &
                      (pivot_df.index <= upper_cutoff)  ]    
    means_dict[label] = subset.apply(geometric_mean).apply(annualize_monthly_geometric_mean)

means_df = pd.DataFrame(means_dict)


# Display
st.subheader("Mean Returns")

display_utils.display_streamlit_table(means_df)

st.caption("Note: Table above shows annualized returns, looking back X months starting with the most recent data")


# DISPLAY ---------------

'''
with st.expander("Full Data (expandable)"):

    
    # Show result
    st.dataframe(filtered_df,
                column_config={
                    "DATE_ID": st.column_config.TextColumn(
                        "Date"
                    )
                })
    


df = pd.DataFrame(
    [
       {"name": "Equities", "percent": 4, "is_widget": True},
       {"name": "Bonds", "percent": 5, "is_widget": False},
       {"name": "Cash", "percent": 3, "is_widget": True},
   ]
)
edited_df = st.data_editor(df)

st.write(f'Sum of percents: {edited_df["percent"].sum()}')
'''
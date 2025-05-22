import streamlit as st
from databricks import sql
import pandas as pd
from datetime import datetime


from shared.data_access import connect_to_databricks, query_database


'''
st.sidebar.title("DBX financials")
st.sidebar.markdown("Use sidebar to navigate")
'''

st.title("Page 1")
st.write("This is the first additional page.")



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
conn = connect_to_databricks()

returns_df = query_database(conn, "SELECT * FROM financials.default.fact_monthly_benchmark_returns")
dim_df     = query_database(conn, "SELECT * FROM financials.default.dim_security")


returns_df = returns_df.merge(
    dim_df[["security_id", "short_name"]],
    how="left", 
    left_on="security_id",
    right_on="security_id"
)


# DATA PROCESSING ----

#Callable objects:
# - pivot_df (all of the financial data, with index of "Date" and columns of different short_name)

pivot_df = returns_df.pivot_table(
    index="date_id",
    columns="short_name",
    values="return_percent",
    aggfunc="first"  # or "mean", "max", etc., depending on your use case
)


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
for years_lookback in [1, 3, 5, 10, 20, 30]:
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



# Prep the table
means_df_for_display = means_df * 100
column_config = get_column_config_for_percentage_df(means_df_for_display)
column_config["SHORT_NAME"] = st.column_config.TextColumn("Security Name")

# Display
st.subheader("Mean Returns")

st.dataframe(means_df_for_display, column_config=column_config)

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
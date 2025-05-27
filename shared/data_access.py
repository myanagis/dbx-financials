from databricks import sql
import streamlit as st
import pandas as pd
from pathlib import Path

### Read CSV -----
def read_csv_from_folder(filepath, index_col=0, convert_percents=True):
    """
    Reads a CSV file from an internal file
    """
    
    # Go up two parents to get to the core /dbx folder (assume that this file is in /dbx/shared/data_access.py)
    data_filename = Path(__file__).parent.parent/filepath
    df = pd.read_csv(data_filename, index_col=index_col)

    # Convert percents to floats if asked to
    if convert_percents:
        for col in df.columns:
            if df[col].astype(str).str.contains('%').any():
                df[col] = df[col].str.rstrip('%').astype(float) / 100
    return df


### Databricks - Generic ------------------

def connect_to_databricks():
    """
    Establish a connection to Databricks using credentials stored in Streamlit secrets.

    Returns:
        databricks.sql.client.Connection: A connection object for executing SQL queries on Databricks.

    Raises:
        KeyError: If required keys are missing from Streamlit secrets.
        databricks.sql.exc.InterfaceError: If the connection fails due to network or credential issues.
    """
    conn = sql.connect(
        server_hostname = st.secrets["databricks"]["server_hostname"],
        http_path = st.secrets["databricks"]["http_path"],
        access_token = st.secrets["databricks"]["access_token"] 
    )
    return conn

@st.cache_data(ttl=600)
def query_database(_conn, query):
    """
    Execute a SQL query using the provided Databricks connection and return the results as a pandas DataFrame.
    This function caches the result for 600 seconds to avoid redundant queries.

    Args:
        _conn (databricks.sql.client.Connection): An active Databricks SQL connection object.
        query (str): The SQL query to execute.

    Returns:
        pd.DataFrame: A DataFrame containing the query results, with column names inferred from the cursor description.

    Raises:
        databricks.sql.exc.OperationalError: If the query fails or the connection is invalid.
    """
    with _conn.cursor() as cursor:
        cursor.execute(query)
        return pd.DataFrame(cursor.fetchall(), columns=[desc[0] for desc in cursor.description])
    

### Databricks: Specific -----------------

class FactMonthlyBenchmarkReturnsSchema():
    FULL_TABLE_NAME = "financials.default.fact_monthly_benchmark_returns"
    COL_DATE_ID = "date_id"
    COL_SECURITY_ID = "security_id"
    COL_RETURN_PERCENT = "return_percent"

class DimSecuritySchema():
    FULL_TABLE_NAME = "financials.default.dim_security"
    COL_SECURITY_ID = "security_id"
    COL_SHORT_NAME = "short_name"

def filter_monthly_returns_by_year(df, start_year, end_year):
    upper_cutoff = (end_year+1)*100 - 1
    lower_cutoff = start_year*100
    filtered_df = df[
                       (df.index >= lower_cutoff) & 
                       (df.index <= upper_cutoff)
                      ]
    return filtered_df

def get_benchmark_returns_data(conn, start_year, end_year, indexes_to_use):
    
    # Get the raw returns data from SQL database
    long_form_returns_df = query_database(conn, f"SELECT * FROM {FactMonthlyBenchmarkReturnsSchema.FULL_TABLE_NAME}")
    dim_df     = query_database(conn, f"SELECT * FROM {DimSecuritySchema.FULL_TABLE_NAME}")

    long_form_returns_df = long_form_returns_df.merge(
        dim_df[[DimSecuritySchema.COL_SECURITY_ID, 
                DimSecuritySchema.COL_SHORT_NAME]],
        how      = "left",
        left_on  = FactMonthlyBenchmarkReturnsSchema.COL_SECURITY_ID,
        right_on = DimSecuritySchema.COL_SECURITY_ID
    )


    # Create a pivot table (to put the security names in the columns)
    all_monthly_returns_df = long_form_returns_df.pivot_table(
        index   = FactMonthlyBenchmarkReturnsSchema.COL_DATE_ID,
        columns = DimSecuritySchema.COL_SHORT_NAME,
        values  = FactMonthlyBenchmarkReturnsSchema.COL_RETURN_PERCENT,
        aggfunc ="first"  # or "mean", "max", etc.
    )

    # Filter monthly returns by year
    upper_cutoff = (end_year+1)*100 - 1
    lower_cutoff = start_year*100
    monthly_returns_df = all_monthly_returns_df[
                       (all_monthly_returns_df.index >= lower_cutoff) & 
                       (all_monthly_returns_df.index <= upper_cutoff)
                      ]

    # Filter monthly returns by year, then by the indexes we're interested in
    monthly_returns_df = filter_monthly_returns_by_year(all_monthly_returns_df, start_year, end_year)

    # Then filter by the indexes we're interested in
    if len(indexes_to_use)>0:
        monthly_returns_df = monthly_returns_df[indexes_to_use]
    
    return monthly_returns_df

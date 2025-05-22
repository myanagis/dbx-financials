from databricks import sql
import streamlit as st
import pandas as pd

### DATA PULL ------------------

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
    
from databricks import sql
import streamlit as st
import pandas as pd

### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
def connect_to_databricks():
    conn = sql.connect(
        server_hostname = st.secrets["databricks"]["server_hostname"],
        http_path = st.secrets["databricks"]["http_path"],
        access_token = st.secrets["databricks"]["access_token"] 
    )
    return conn

@st.cache_data(ttl=600)
def run_query(_conn, query):
    with _conn.cursor() as cursor:
        cursor.execute(query)
        return pd.DataFrame(cursor.fetchall(), columns=[desc[0] for desc in cursor.description])
    
import streamlit as st
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "call_data.db"

# Initialize DB if it doesn't exist
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            job_title TEXT,
            company TEXT,
            date DATETIME,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_data(name:str, job_title:str, company:str, date, notes:str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO submissions2 (name, job_title, company, date, notes) VALUES (?, ?, ?, ?, ?)", 
                   (name, job_title, company, date, notes))
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, job_title, company, date, notes FROM submissions2")
    rows = cursor.fetchall()
    conn.close()
    return rows

#############################################
# Streamlit UI
st.title("Feedback Form")
st.write("Note: this data will not persist if deployed to Streamlit Cloud. It runs in a stateless container.")
init_db()


name = st.text_input("Name")
job_title = st.text_input("Job Title")
company = st.text_input("Company")
date = st.date_input("Date")
notes = st.text_area("Notes")

if st.button("Submit"):
    insert_data(name, job_title, company, date, notes)
    st.success("Submitted!")

st.subheader("Past Submissions")
for name, job_title, company, date, notes in get_data():
    st.write(f"**{name}** ({job_title} at {company}) ({date}): \n{notes}")
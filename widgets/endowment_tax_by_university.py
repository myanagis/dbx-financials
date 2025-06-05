# Import python packages
import altair as alt
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np

from shared import data_access, finance_utils, display_utils, input_utils


### PREP ----
st.set_page_config(page_title="Endowment Tax Analysis: By University | Mike Yanagisawa",
                   layout="wide")


# Write directly to the app
st.title(f"Analyzing Endowment Tax Impact to Universities")
st.caption("Mike Yanagisawa | June 5, 2025")




### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
conn = data_access.connect_to_databricks()

university_df = data_access.get_university_financial_and_enrollment_data(conn)


### MANIPULATIONS ###

# Manipulate
# Calculate per-student endowment
university_df["endowment_per_student"] = university_df["cy_endowment_end_balance"] / university_df["total_enrollment"]




# Full data Display --------------------------
st.header("Full data")
st.dataframe(university_df)

# Get the enrollment data alone
st.header("Raw Data")
fact_university_enrollment = data_access.query_mock_database(data_access.FactUniversityEnrollment.FULL_TABLE_NAME)
fact_university_financials = data_access.query_mock_database(data_access.FactUniversityFinancials.FULL_TABLE_NAME)


name_filter = st.text_input("Text to filter university name by:")

# Enrollment data
st.subheader("Enrollment data")
if name_filter is not "":
    filtered_university_enrollment = fact_university_enrollment[ fact_university_enrollment["institution_name"].str.contains(name_filter, case=False, na=False) ]
else:
    filtered_university_enrollment = fact_university_enrollment
st.dataframe(filtered_university_enrollment)

st.subheader("Financial Data")
if name_filter is not "":
    filtered_university_financials = university_df[ university_df["university_name"].str.contains(name_filter, case=False, na=False) ]
else:
    filtered_university_financials = university_df

cols_to_show = ["university_name"] + fact_university_financials.columns.to_list()
cols_to_show.remove("reference_link")
st.dataframe(filtered_university_financials[cols_to_show])


def highlight_per_student_endowment(val):
    styles = []
    if val > 500000:
        styles.append("background-color: yellow")
    return styles



class UniversityDataSchema():
    COL_INVESTMENT_INCOME = "investment_income"
    COL_GROSS_RENT_INCOME = "gross_rent_income"
    COL_ROYALTIES_INCOME = "royalties_income"
    COL_SALE_OF_ASSETS_INCOME = "sale_of_assets_income"
    COL_INVESTMENT_MANAGEMENT_FEES = "investment_management_fees"
    COL_ROYALTIES_EXPENSE = "royalties_expenses"

# CASE STUDY


st.header(f"Case Study: Endowment Taxes in Year")

# Inputs
year_to_find = st.number_input("Year:", value=2022)
per_student_endowment_cutoff = st.number_input("Per student endowment cutoff:", value=500_000, step=10_000)
student_cutoff = st.number_input("Student enrollment cutoff:", value=500, step=100)
TAX_RATE = st.number_input("Tax rate", value=.014, step=.01)


def estimate_tax(row):
    estimated_investment_income = (
        row[UniversityDataSchema.COL_INVESTMENT_INCOME] 
      + row[UniversityDataSchema.COL_GROSS_RENT_INCOME]
      + row[UniversityDataSchema.COL_ROYALTIES_INCOME]
      + row[UniversityDataSchema.COL_SALE_OF_ASSETS_INCOME]
      - row[UniversityDataSchema.COL_ROYALTIES_EXPENSE]
    )
    
    tax_rate = TAX_RATE
    return estimated_investment_income*tax_rate

def estimate_tax_no_royalties(row):
    estimated_investment_income = (
        row[UniversityDataSchema.COL_INVESTMENT_INCOME] 
      + row[UniversityDataSchema.COL_GROSS_RENT_INCOME]
      + row[UniversityDataSchema.COL_SALE_OF_ASSETS_INCOME]
    )
    
    tax_rate = TAX_RATE
    return estimated_investment_income*tax_rate

def estimate_tax_royalties(row):
    estimated_investment_income = (
      + row[UniversityDataSchema.COL_ROYALTIES_INCOME]
      - row[UniversityDataSchema.COL_ROYALTIES_EXPENSE]
    )
    
    tax_rate = TAX_RATE
    return estimated_investment_income*tax_rate


# Filters
# 1. By Year
university_subset_df = university_df[ university_df["year"] == year_to_find]
# 2. By per-student endowment
university_subset_df = university_subset_df[ university_subset_df["endowment_per_student"] > per_student_endowment_cutoff ]
# 3. By student enrollment
university_subset_df = university_subset_df[ university_subset_df["total_enrollment"] > student_cutoff ]


university_subset_df = university_subset_df[ university_subset_df["ncse_response_type"].str.contains("Private") ]

# Estimate tax
university_subset_df["estimated_tax_no_royalties"] = university_subset_df.apply(estimate_tax_no_royalties, axis=1)
university_subset_df["estimated_tax_royalties"] = university_subset_df.apply(estimate_tax_royalties, axis=1)


university_subset_df.drop_duplicates(inplace=True)


#additional_styles = [ (highlight_per_student_endowment, ["endowment_per_student"]) ]

# Prepare for display
columns_to_display = ["university_name", "city", "state", "endowment_per_student", "cy_endowment_end_balance", 
                      "total_enrollment", "estimated_tax_no_royalties", "estimated_tax_royalties"]

university_subset_df = university_subset_df[columns_to_display]
university_subset_df = university_subset_df.sort_values(by="endowment_per_student", ascending=False)




# Display the count and table
display_utils.display_streamlit_table(university_subset_df) #, additional_styles=additional_styles)
st.write(f"Rows: {university_subset_df.shape[0]}")
st.write(f"Sum of estimated_tax: {university_subset_df['estimated_tax_no_royalties'].sum():,.0f}")
st.write(f"Sum of estimated_tax royalties: {university_subset_df['estimated_tax_royalties'].sum():,.0f}")
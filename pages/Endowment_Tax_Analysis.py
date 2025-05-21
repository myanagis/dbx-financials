# Import python packages
import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from databricks import sql

from shared.data_access import connect_to_databricks, run_query



### PREP ----
st.set_page_config(layout="wide")

### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
conn = connect_to_databricks()
returns_df = run_query(conn, "SELECT * FROM financials.default.fact_monthly_benchmark_returns")
dim_df     = run_query(conn, "SELECT * FROM financials.default.dim_security")


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



# HELPERS for data calculations -----

# INPUT: monthly returns.
# OUTPUT: annualized covariance matrix
def calculate_covariance_matrix(monthly_returns_df, type="standard"):
    monthly_cov_matrix = pd.DataFrame()

    # "Standard" covariance
    if type == "standard":
        monthly_cov_matrix = monthly_returns_df.cov() 
    
    # EWMA covariance using half-life
    elif type == "ewma":
        half_life = 60
        ewma_lambda = 0.5 ** (1 / half_life)
        alpha = 1 - ewma_lambda

        # Compute EWMA covariance
        # This returns a MultiIndex DataFrame: index is (time, asset1), columns are asset2
        ewma_cov = monthly_returns_df.ewm(alpha=alpha, adjust=False).cov(pairwise=True)

        # Get the most recent (last date's) covariance matrix
        last_timestamp = monthly_returns_df.index[-1]
        monthly_cov_matrix = ewma_cov.loc[last_timestamp]

    else:
        raise ValueError("Invalid type. Choose 'standard' or 'ewma'.")

    # Annualize the covariance matrix (monthly → annual)
    return 12 * monthly_cov_matrix

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




# Callable function
def streamlit_display_table(df, percent_columns=[]):
    column_config = {}
    
    # Copy the dataframe
    display_df = df.copy()

    # Handle percent columns
    for col_name in percent_columns:
        display_df[col_name] = display_df[col_name] * 100
        column_config[col_name] = st.column_config.NumberColumn(
                col_name,
                format = "%.2f%%"
            )
    
    st.dataframe(display_df, column_config=column_config)






# HEADER ----------------

# Write directly to the app
st.title(f"Analyzing Impact of Endowment Taxes :balloon:")
st.caption("Mike Yanagisawa | May 13, 2025")

st.write("""
In the Tax Cuts and Jobs Act in 2017, Trump taxed select endowments' net investment income at 1.4%. 
Since returning to office, he's had his eyes set on cranking up endowment taxes, especially on the so-called elite institutions 
such as Yale and Princeton.

- The first question is: how likely is a new tax bill to pass, and how large will the tax percent be?
- The second question: if this were to pass, how should endowments/foundations change their asset allocation?

Geddes et al. at Aperio (now part of BlackRock) wrote a paper in 2015, provocatively titled 'What Would Yale Do If It Were Taxable?':  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2447403")
The module below extends this mean-variance analysis up to today, as well as making transparent our assumptions.
""")


# HORIZONTAL LINE
st.divider()

# INPUTS -----
st.header("Data Inputs")


# Get current date
now = datetime.now()
current_year = now.year

# Slider
selected_range = st.slider(
    "Enter a year range:", 
    min_value=1977,
    max_value=current_year,
    value=(current_year-5, current_year)
)

start_year = selected_range[0]
end_year = selected_range[1]

# Display
col1, col2, col3 = st.columns(3)
col1.metric(label="Start Year", value=start_year, border=True)
col2.metric(label="End Year", value=end_year, border=True)


# Portfolio --------------

index_display_names = {
    "DJUSRET": "Dow Jones U.S. Real Estate Total Return",
    "HEDGNAV": "Credit Suisse Hedge Fund Index",
    "LBUSTRUU": "Bloomberg Barclays US Aggregate Bond Index", 
    "NDUEACWF": "MSCI ACWI ETF",
    "RU20INTR": "Russell 2000 Total Return",
    "SPBDUB3T": "S&P U.S. Treasury Bill 0-3 Month",
    "SPGINRTR": "S&P Global Natural Resources",
    "SPXT": "Proshares S&P 500 EX-Technology ETF Fund"
}

portfolio_structure = {
    "Absolute Return": "HEDGNAV",
    "World Public Equity": "NDUEACWF",
    "Bonds": "LBUSTRUU",
    "Natural Resources": "SPGINRTR",
    "Real Estate": "DJUSRET",
    "Private Equity": "RU20INTR", 
    "Cash": "SPBDUB3T"
}

w_RE = .202
w_HF = .178
w_bonds = 0.049
w_public_eq = 0.157 # NDUEACWF
w_private_eq = 0.320 # RU20INTR (russell 2000)
w_cash = .015 # T-bills (SPBDUB3T)
w_natl_resources = 0.079 # SPGINRTR
w_spx = 0

portfolio_weights = {
    "World Public Equity": w_public_eq,
    "Absolute Return": w_HF,
    "Bonds": w_bonds,
    "Natural Resources": w_natl_resources,
    "Real Estate": w_RE,
    "Private Equity": w_private_eq, 
    "Cash": w_cash
}



# Get the display table
st.write("Our portfolio allocation assumptions and proxies (based on Yale's asset allocation as of December 2013, and the asset class proxies used by Aperio.")

display_df = pd.DataFrame(list(portfolio_structure.items()), columns=["Asset Class", "Benchmark Ticker"])
display_df["Display Name"] = display_df["Benchmark Ticker"].map(index_display_names)
display_df["Portfolio Weights"] = display_df["Asset Class"].map(portfolio_weights)
streamlit_display_table( display_df, percent_columns=["Portfolio Weights"] )

st.caption("Source: Bloomberg. Aperio uses 'Blend of Credit Suisse Fund Indexes' for Absolute Return; we use a simple 'Credit Suisse Hedge Fund Index'. We also use S&P Global Natural Resources; Aperio uses North America. Aperio's sample period was January 1999 to June 2013.")





# HORIZONTAL LINE
st.divider()





# Filtered covariances, etc. ----------------------

# ASSUMPTIONS: Expected market returns
expected_market_return = 0.103
rf = 0.02 

# EXPLANATION
st.header("Step 1: Calculate Pre-Tax Implied Returns")

st.markdown(f"""
We are given the WEIGHTS and COVARIANCES, so using a mean-variance optimizer, we can calculate the implied (pre-tax) returns of each asset class. 
We use the covariance matrix in the time range input above, and we make some assumptions required for the reverse optimizer: 
    
- Expected market return: {expected_market_return*100:.1f}% 
- Risk-free rate: {rf*100}%
"""
)

lambda_formula = "\\lambda = \\frac{\\mathbb{E}[R_p] - R_f}{\\sigma_p^2}"
expected_return_formula = "\\mathbb{E}[R_p]"

st.write(f"""
This allows us to calculate the risk aversion: ${lambda_formula}$, 
where ${expected_return_formula}$ is the expected return of the portfolio, $R_f$ is the risk-free rate, 
and $\\sigma_p^2$ is the portfolio standard deviation, calculated by $\\sigma_p^2 = w^\\top \\Sigma w$
($w$ are the portfolio weights and $\\Sigma$ is the covariances).
The implied returns $\\mu$ are then easy to calculate: $\\mu = \\lambda \\cdot \\Sigma w$

""")

# Filter by selected year
# The "filtered_df" is the DF filtered to ONLY the date range
upper_cutoff = (end_year+1)*100 - 1
lower_cutoff = start_year*100
  
date_filtered_df = pivot_df[
                       (pivot_df.index >= lower_cutoff) & 
                       (pivot_df.index <= upper_cutoff)
                      ]

# Only get the funds from the portfolio above
indexes_to_use = list(portfolio_structure.values())
filtered_df = date_filtered_df[indexes_to_use]

# Display (OPTIONAL)
#st.subheader("Covariance Analysis")
#st.dataframe(ewma_cov_matrix)


# calculate, using reverse optimization
weights = np.array( list(portfolio_weights.values()) )
cov_matrix = calculate_covariance_matrix(filtered_df, type="standard")

portfolio_var = weights @ cov_matrix @ weights
portfolio_std = np.sqrt(portfolio_var)
mkt_var = weights @ cov_matrix @ weights
lambda_risk_aversion = (expected_market_return - rf) / mkt_var

# Calculate the implied returns, as well as the portfolio return
implied_returns = lambda_risk_aversion * cov_matrix @ weights
return_portfolio = weights @ implied_returns
implied_returns_df = pd.DataFrame(implied_returns, columns=["Implied Pre-Tax Returns"])


# Display the implied returns
merged_display_df = display_df.merge(implied_returns_df, left_on="Benchmark Ticker", right_index=True, how="left")
streamlit_display_table( merged_display_df, ["Portfolio Weights", "Implied Pre-Tax Returns"] )

# EWMA calcuations
#ewma_cov_matrix = calculate_covariance_matrix(filtered_df, type="ewma")
#mkt_var = weights @ ewma_cov_matrix @ weights
#lambda_risk_aversion = (expected_market_return - rf) / mkt_var

#ewma_portfolio_var = weights @ ewma_cov_matrix @ weights
#ewma_portfolio_std = np.sqrt(ewma_portfolio_var)

#st.write(f"St dev: {ewma_portfolio_std}")
#st.write(f"Lambda risk aversion: {lambda_risk_aversion}")
#st.write(mkt_var)

# reverse_opt
#implied_returns = lambda_risk_aversion * ewma_cov_matrix @ weights
#return_portfolio = weights @ implied_returns
#st.write(f"Portfolio return: { return_portfolio }")
#implied_returns_df = pd.DataFrame(implied_returns, columns=["Imputed Returns"])

#st.write("Implied expected returns (EWMA)")
#streamlit_display_table( display_df, ["Portfolio Weights"] )
#streamlit_display_table(implied_returns_df, percent_columns=["Imputed Returns"])






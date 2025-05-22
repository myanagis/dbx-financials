# Import python packages
import altair as alt
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

from shared import data_access
from shared import finance_utils


### PREP ----
st.set_page_config(layout="wide")

### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
conn = data_access.connect_to_databricks()
returns_df = data_access.query_database(conn, "SELECT * FROM financials.default.fact_monthly_benchmark_returns")
dim_df     = data_access.query_database(conn, "SELECT * FROM financials.default.dim_security")

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

# Helpers for displaying in streamlit -----

def get_column_config_for_percentage_df(df):
    column_config = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            column_config[col] = st.column_config.NumberColumn(
                col,
                format = "%.2f%%"
            )
    return column_config


# TODO: table visualization styler: https://pandas.pydata.org/pandas-docs/stable/user_guide/style.html

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
st.title(f"Analyzing Impact of Endowment Taxes")
st.caption("Mike Yanagisawa | May 13, 2025")

st.markdown("""
In the Tax Cuts and Jobs Act in 2017, Trump taxed select endowments' net investment income at 1.4%. 
Since returning to office, he's had his eyes set on cranking up endowment taxes, especially on the so-called elite institutions 
such as Yale and Princeton.

- The first question is: how likely is a new tax bill to pass, and how large will the tax percent be?
- The second question: if this were to pass, how should endowments/foundations change their asset allocation?

Geddes et al. (from a customized indexing company Aperio, [acquired](https://www.blackrock.com/corporate/newsroom/press-releases/article/corporate-one/press-releases/blackrock-to-acquire-aperio) 
by BlackRock in 2020) wrote a paper in 2015, provocatively titled 
['What Would Yale Do If It Were Taxable?'](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2447403)
The page below extends this mean-variance analysis up to today, as well as making our assumptions transparent.
""")


# HORIZONTAL LINE
st.divider()

# INPUTS -----
st.header("Data Inputs")


# Get current date
now = datetime.now()
current_year = now.year

st.badge("Adjust date range here.")

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

st.header("Assumptions")
st.subheader("Our Model Portfolio")

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
    "Absolute Return": w_HF,
    "World Public Equity": w_public_eq,
    "Bonds": w_bonds,
    "Natural Resources": w_natl_resources,
    "Real Estate": w_RE,
    "Private Equity": w_private_eq, 
    "Cash": w_cash
}

# Get the display table
st.write("Our portfolio allocation assumptions and proxies (based on Yale's asset allocation as of December 2013, and the asset class proxies used by Aperio.")

portfolio_df_for_display = pd.DataFrame(list(portfolio_structure.items()), columns=["Asset Class", "Benchmark Ticker"])
portfolio_df_for_display["Display Name"] = portfolio_df_for_display["Benchmark Ticker"].map(index_display_names)
portfolio_df_for_display["Portfolio Weights"] = portfolio_df_for_display["Asset Class"].map(portfolio_weights)
streamlit_display_table( portfolio_df_for_display, percent_columns=["Portfolio Weights"] )

st.caption("Source: Bloomberg. Aperio uses 'Blend of Credit Suisse Fund Indexes' for Absolute Return; we use a simple 'Credit Suisse Hedge Fund Index'. We also use S&P Global Natural Resources; Aperio uses North America. Aperio's sample period was January 1999 to June 2013.")


st.subheader("Other Assumptions")

# ASSUMPTIONS: Expected market returns
expected_market_return = 0.103
rf = 0.02 

st.markdown(f"""
We make some assumptions required for the reverse optimizer (Step 1): 
- Expected market return: {expected_market_return*100:.1f}% 
- Risk-free rate: {rf*100:.1f}%
""")

# HORIZONTAL LINE
st.divider()


# Filtered covariances, etc. ----------------------


# EXPLANATION
st.header("Step 1: Calculate Pre-Tax Implied Returns")

st.markdown(f"""
We are given the WEIGHTS and COVARIANCES, so using a mean-variance optimizer, we can calculate the implied (pre-tax) returns of each asset class. 
We calculate the covariance matrix for the time range input above and use other assumptions listed above.
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

# Calculate, using reverse optimization
weights = np.array( list(portfolio_weights.values()) ) #TODO: remove portfolio weights from here, tidy up 
cov_matrix = finance_utils.calculate_covariance_matrix(filtered_df, type="standard")

portfolio_var = weights @ cov_matrix @ weights
portfolio_std = np.sqrt(portfolio_var)
mkt_var = weights @ cov_matrix @ weights
lambda_risk_aversion = (expected_market_return - rf) / mkt_var

# Calculate the implied returns, as well as the portfolio return
implied_returns = lambda_risk_aversion * cov_matrix @ weights
return_portfolio = weights @ implied_returns
implied_returns_df = pd.DataFrame(implied_returns, columns=["Implied Pre-Tax Returns"])


# Display the implied returns
merged_portfolio_returns_display_df = portfolio_df_for_display.merge(implied_returns_df, left_on="Benchmark Ticker", right_index=True, how="left")
streamlit_display_table( merged_portfolio_returns_display_df, percent_columns=["Portfolio Weights", "Implied Pre-Tax Returns"] )

# Bar chart # TODO: use plotly?
#fig, ax = plt.subplots()
#merged_display_df.plot(x="Display Name", y="Implied Pre-Tax Returns", kind="barh", ax=ax)
#st.pyplot(fig)


# Display covariance table #TODO: display this?
#st.dataframe(filtered_df.corr())


# Dataframes to use
# portfolio_df_for_display: contains 
# implied_returns_df: 

st.header("Step 2: Apply Tax Haircuts to Pre-Tax Returns")

st.markdown(
"""
The Aperio paper targets a personal investor with a worst-case tax scenario. In applying the tax haircut, 
they assume a 44.6% short-term and ordinary tax, and a 25% long-term/dividends tax rate.

Endowment taxes are based on net investment income (NII), and so 
they do not have a distinction between short-term and long-term returns.
We assume that all realized returns (ordinary income, realized short-term, realized long-term, dividends) 
are taxed at the NII rate. 
"""
)

tax_rate_options = {
    "0%": 0.0,
    "1.4%": 0.014,
    "7%": 0.07,
    "14%": 0.14,
    "21%": 0.21,
    "Other": None
}

st.badge("Modify tax rate here.")

col1, col2 = st.columns(2)
with col2:
    raw_selected_tax_rate = st.pills(
        "Endowment Tax Rate", 
        options=tax_rate_options.keys(),
        default="14%",
        #format_func=(lambda option: tax_rate_options[option]),
        selection_mode="single"
        )

    raw_other_tax_rate = st.number_input("Custom endowment tax rate (in %):")

# Get the selected tax rate (in float)
selected_tax_rate_float = 0.0
if raw_selected_tax_rate == "Other":
    if raw_other_tax_rate is None:
        st.badge("Please input a custom endowment tax rate.")
    else:
        selected_tax_rate_float = raw_other_tax_rate/100
else:
    selected_tax_rate_float = tax_rate_options[raw_selected_tax_rate]

# Display the tax rate selected
col1.metric(label="Selected Tax Rate", value=f"{selected_tax_rate_float*100:.1f}%", border=True)


# Display the portfolio tax haircut assumptions
headers = ["Ordinary Income", "Realized Short Gains", "Realized Long Gains", "Unrealized Capital Gains", "Dividend Return"]
tax_penalty = {
    "Absolute Return":     [  0, .23, .47, .30,   0],
    "World Public Equity": [  0,   0,   0, 1.0, .02],
    "Bonds":               [1.0,   0,   0,   0,   0], 
    "Natural Resources":   [  0, .10, .20, .70,   0], 
    "Real Estate":         [.30,   0,   0, .70,   0],
    "Private Equity":      [  0,   0, .30, .70, .02],
    "Cash":                [1.0,   0,   0,   0,   0]
}
tax_penalty_df = pd.DataFrame.from_dict(tax_penalty, orient="index", columns=headers)

tax_penalty_df["Percent Realized"] = tax_penalty_df.sum(axis=1) - tax_penalty_df["Unrealized Capital Gains"]

with st.expander("Tax Rate Assumptions (click to expand)"):
    st.dataframe(tax_penalty_df)
    st.caption("Assumptions are taken from the Aperio paper. Realized (Taxed) Returns are calculated.")

    st.markdown(
    """
    Our post-tax returns are calculated by taxing the realized return percent:

    $r_{post-tax} = r_{pre-tax}*W_{taxed}*(1-t) + r_{pre-tax}*(1-W_{taxed})$

    Where $r_{pre-tax}$ is the pre-tax return, $t$ is the tax rate, and $W_{taxed}$ is the percent of the returns that are realized/taxable. 
    """
    )

    def calculate_post_tax_return(pre_tax_return, percent_realized, tax_rate):
        realized_returns = pre_tax_return*percent_realized*(1-tax_rate) # taxed
        unrealized_returns = pre_tax_return*(1-percent_realized)
        return realized_returns + unrealized_returns

    # Collate the table together
    merged_portfolio_tax_df = merged_portfolio_returns_display_df.merge(tax_penalty_df, left_on="Asset Class", right_index=True, how="left")

    # Calculate the post-tax returns
    merged_portfolio_tax_df["Post-Tax Returns"] = merged_portfolio_tax_df.apply( 
        lambda row: calculate_post_tax_return(row["Implied Pre-Tax Returns"], row["Percent Realized"], selected_tax_rate_float),
        axis=1
    )

    # Display
    columns_to_display=["Asset Class", "Display Name", "Percent Realized", "Implied Pre-Tax Returns", "Post-Tax Returns"]
    streamlit_display_table( merged_portfolio_tax_df[columns_to_display]) #, percent_columns=["Portfolio Weights"] )

    st.caption("Note: Public equity is assumed to be indexed. Bonds are assumed to be taxable bonds.")



st.header("Step 3: Calculate Post-Tax Portfolio Weights")
st.markdown(
"""
Re-run the mean-variance optimization to get the implied portfolio weights.
"""
)

def calculate_efficient_frontier_coefficients(mu, cov, R_target):
    # Step 1: Invert covariance matrix
    inv_cov = np.linalg.inv(cov)
    ones = np.ones_like(mu)

    # Step 2: Compute efficient frontier
    A = mu.T @ inv_cov @ mu
    B = mu.T @ inv_cov @ ones
    C = ones.T @ inv_cov @ ones 

    # Step 3: Solve for gamma and lambda
    M = np.array([[A, B], [B, C]])
    b = np.array([R_target, 1])
    lambd, gamma = np.linalg.solve(M, b)

    # Step 4: Compute weights
    w = lambd * (inv_cov @ mu) + gamma * (inv_cov @ ones)

    #st.write("Optimal weights:", w)
    #st.write("Expected return:", np.dot(w, mu))
    #st.write("Portfolio variance:", w.T @ cov @ w)
    #st.write("Portfolio standard deviation:", np.sqrt(w.T @ cov @ w))

    return w

#st.dataframe(cov_matrix)


with st.expander("Pre- and Post-Tax Weights and Returns (click to expand)"):
    #mu = merged_portfolio_tax_df["Implied Pre-Tax Returns"]
    mu = merged_portfolio_tax_df["Post-Tax Returns"]
    post_tax_weights = calculate_efficient_frontier_coefficients( mu, cov_matrix, expected_market_return - rf )

    merged_portfolio_tax_df["Pre-Tax Weights"] = merged_portfolio_tax_df["Portfolio Weights"]
    merged_portfolio_tax_df["Post-Tax Weights"] = post_tax_weights
    merged_portfolio_tax_df["Portfolio Weight Change"] = merged_portfolio_tax_df["Post-Tax Weights"] - merged_portfolio_tax_df["Pre-Tax Weights"]


    st.dataframe(merged_portfolio_tax_df)


# Summary
st.header("Summary")

#st.subheader("Assumptions")
col1, col2, col3, col4 = st.columns(4)
col1.metric(label="Start Year", value=start_year, border=True)
col2.metric(label="End Year", value=end_year, border=True)
col3.metric(label="Tax Rate", value=f"{selected_tax_rate_float*100:.1f}%", border=True)

st.subheader("Impact")

# Sample DataFrame
df = merged_portfolio_tax_df.melt(
    id_vars="Asset Class",
    value_vars=["Pre-Tax Weights", "Post-Tax Weights"],
    var_name="Type",
    value_name="Weight"
)

asset_order = merged_portfolio_tax_df["Asset Class"].tolist()

chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("Weight:Q"),
    y=alt.Y("Asset Class:N", sort=asset_order),
    color=alt.Color("Type:N", sort=["Pre-Tax Weights", "Post-Tax Weights"]),
    #order=alt.Order("Type", sort="descending"),
    yOffset=alt.YOffset("Type:N", sort=["Pre-Tax Weights", "Post-Tax Weights"])
).properties(
    width=600,
    height=300,
    title="Pre-Tax vs Post-Tax Portfolio Weights"
)

st.altair_chart(chart, use_container_width=True)
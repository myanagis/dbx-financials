# Import python packages
import altair as alt
import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np

from shared import data_access, finance_utils, display_utils, input_utils


### PREP ----
st.set_page_config(page_title="Endowment Tax Analysis: Portfolio Allocation | Mike Yanagisawa",
                   layout="wide")

### DATA PULL ------------------

# Securely use secrets in production
# Found in: Databricks > SQL Warehouses
conn = data_access.connect_to_databricks()

REFERENCES_COUNT=0
REFERENCES_LIST = [] # (count, link, references section display, tooltip)
REFERENCES_DICTIONARY = {}


def add_ref(link: str, link_title:str = ""):
    global REFERENCES_COUNT

    # Add to dictionary
    ref_key = f"REF{REFERENCES_COUNT+1}"
    add_reference_to_dictionary(ref_key, link, link_title)

    # Determine which ref number gets assigned
    ref_str = link_to_ref(ref_key)

    return ref_str

# Two-step method
def link_to_ref(ref_key: str, return_link_title = False):
    global REFERENCES_COUNT, REFERENCES_LIST,REFERENCES_DICTIONARY

    # Get the reference number
    # First, check if the value exists. Otherwise, create one.
    ref_number = REFERENCES_DICTIONARY.get(ref_key).get("ref_number")
    if ref_number is None:
        REFERENCES_COUNT += 1
        ref_number = REFERENCES_COUNT
        REFERENCES_LIST.append( (REFERENCES_COUNT, "ref_key", ref_key) )
        REFERENCES_DICTIONARY[ref_key]["ref_number"] = ref_number

    link = REFERENCES_DICTIONARY.get(ref_key).get("link")
    link_title = REFERENCES_DICTIONARY.get(ref_key).get("link_title") or link
    # Build the return
    if return_link_title:
        ref_text = f"""[{link_title}](link)"""
    else:
        
        ref_text = f"""<span title=""><sup>[{ref_number}]({link})</sup></span>"""
    return ref_text

def add_reference_to_dictionary(ref_key: str, link: str, link_title: str = ""):
    global REFERENCES_DICTIONARY
    REFERENCES_DICTIONARY[ref_key] = {"link": link, "link_title": link_title}

def add_footnote(footnote: str):
    global REFERENCES_COUNT, REFERENCES_LIST
    REFERENCES_COUNT += 1
    REFERENCES_LIST.append( (REFERENCES_COUNT, "footnote", footnote) )

    ref = f"""<span title=""><sup>{REFERENCES_COUNT}</sup></span>"""
    return ref

def spill_references():
    global REFERENCES_LIST, REFERENCES_DICTIONARY
    references_markdown = ""

    for item in REFERENCES_LIST:
        ref_number, ref_type, ref_text = item

        if ref_type == "footnote":
            this_ref_text = ref_text
        elif ref_type == "ref_key":
            link_title = REFERENCES_DICTIONARY[ref_text]["link_title"]
            link = REFERENCES_DICTIONARY[ref_text]["link"]
            if link_title == "":
                link_title = link
            this_ref_text = f"[{link_title}]({link})"

        references_markdown += f"- {ref_number}. {this_ref_text} \n"

    with st.expander("References (click to expand)"):
        st.markdown(references_markdown)

# Build references list
add_reference_to_dictionary("nyt-10bn-savings", 
                            "https://static01.nyt.com/newsgraphics/documenttools/28cb85c5ed1f6c52/44e83eb4-full.pdf", 
                            "Congressional document retrieved by the New York Times")
add_reference_to_dictionary("tax_rev_22_23", 
                            "https://www.nonprofitissues.com/article/university-endowment-tax-receipts-rise-again",
                            "University endowment tax receipts rise again | Nonprofit Issues")
add_reference_to_dictionary("aperio-paper",
                            "http://dx.doi.org/10.2139/ssrn.2447403",
                            "Geddes, Patrick and Goldberg, Lisa R. and Bianchi, Stephen, What Would Yale Do If It Were Taxable? (June 8, 2014). Financial Analysts Journal, Vol. 71, No. 4, 2015")

# ----------------------------------------------------------
# Header ---------------------------------------------------
# ----------------------------------------------------------

# Write directly to the app
st.title(f"Analyzing Portfolio Impact of Endowment Taxes")
st.caption("Mike Yanagisawa | May 27, 2025")


# ----------------------------------------------------------
# Exposition -----------------------------------------------
# ----------------------------------------------------------


st.markdown(f"""
In the Tax Cuts and Jobs Act of 2017, Trump taxed select endowments at a rate of 1.4%. In the past year, Republicans have increasingly looked to taxing the wealthy endowments (such as Yale and Harvard) as both a way to fight the US deficit and a weapon against the so-called elite institutions. 
A document floating around Congress (and retrieved by the New York Times) estimated that the endowment tax could generate up to $10bn in "savings" over 10 years.{link_to_ref("nyt-10bn-savings")} 
Below is how much has been collected by the IRS in the past few years from this tax {link_to_ref("tax_rev_22_23")}:
""", unsafe_allow_html=True)

# Display graphs showing
def millionify(dollar_amount):
    return f"${dollar_amount}mn"

endowment_rev_df = pd.DataFrame({
    "Year": [2021, 2022, 2023],
    "IRS Tax Revenue": [60, 244, 380],
    "Universities Affected": [33, 58, 56]
})

endowment_rev_df["revenue_formatted"] = endowment_rev_df["IRS Tax Revenue"].apply(millionify)

# IRS Revenue chart
chart_revenue = alt.Chart(endowment_rev_df).mark_bar().encode(
    x=alt.X("IRS Tax Revenue:Q", axis=alt.Axis(labelExpr='"$" + datum.value + "mn"')),
    y=alt.Y("Year:O"),
    tooltip=[alt.Tooltip("Year:O", title="Year"), 
             alt.Tooltip("revenue_formatted:N", title="IRS Revenue")]
).properties(
    height=80,
    width=350,
)

labels_revenue = alt.Chart(endowment_rev_df).mark_text(
    align="right",
    dx=-6,
    color="white"
).encode(
    x="IRS Tax Revenue:Q",
    y="Year:O",
    text=alt.Text("revenue_formatted:N")
)

# Universities
chart_universities = alt.Chart(endowment_rev_df).mark_bar().encode(
    x=alt.X("Universities Affected:Q"),
    y=alt.Y("Year:O"),
    tooltip=["Year", "Universities Affected"]
).properties(
    height=80,
    width=350
)

labels_universities = alt.Chart(endowment_rev_df).mark_text(
    align="right",
    dx=-6,
    color="white"
).encode(
    x="Universities Affected:Q",
    y="Year:O",
    text="Universities Affected"
)

st.markdown("###### Endowment Tax Impact at 1.4%: IRS Revenue and Universities Affected")
final_chart = alt.hconcat(chart_revenue + labels_revenue, chart_universities + labels_universities).resolve_scale(
    y="shared"
)
st.altair_chart(final_chart)
st.caption(f'Source: {link_to_ref("tax_rev_22_23", True)}')

st.markdown(f"""

##### How large will the tax be?

Currently, the endowment tax rate sits at **1.4%** of "net investment income,"{add_footnote("Depeer discussion of code is in [IRC 4968](https://www.irs.gov/pub/newsroom/1-excise-tax-on-net-investment-income-colleges-4968-13701_508.pdf). Very roughly speaking, net investment income = (gross investment income + capital gain net income) – allowable deductions")}
To qualify for the tax, a university must:
- Have at least 500 tuition-paying students
- Have more than 50 percent of students in the US, and
- The fair market value (FMV) of assets per full-time student must be at least $500K.

In the past year or so, Congressmen have proposed various amendments, which give us a sense of the direction (and political motivations) for the tax:
| Date | Proposed By | Tax Rate | Changes to Qualification Criteria | Notes | Ref |
|-------------|----------------|-----------------|-------------|----------------|-----------------|
| Dec 2023 | Sen JD Vance | 35% | Applies if FMV > $10bn | | {add_ref("https://www.congress.gov/bill/118th-congress/senate-bill/3514", "S.3514 - A bill to amend the Internal Revenue Code of 1986 to increase the excise tax on net investment income of certain private colleges and universities.")} | 
| Jan 2025 | Congressman Troy Nehls | 21% | No new criteria | Tax rate rationale is to have endowment tax match corporate tax rate. | {add_ref("https://nehls.house.gov/media/press-releases/rep-troy-e-nehls-introduces-bill-hold-elite-university-endowments-accountable#:~:text=Prior%20to%20the%20enactment%20of,at%20a%20rate%20of%201.4%25.", "Rep. Troy E. Nehls Introduces Bill to Hold Elite University Endowments Accountable")} | 
| Feb 2025 | Congressmen Dave Joyce and Nicole Malliotakis | 10% | Lower per-student threshold to $250K | Increase tax rate to 20% if tuition increases by more than inflation. | {add_ref("https://joyce.house.gov/posts/joyce-malliotakis-introduces-bill-to-hold-higher-education-institutions-accountable-for-student-debt-crisis", "Joyce, Malliotakis Introduces Bill to Hold Higher Education Institutions Accountable for Student Debt Crisis")} |
| Feb 2025 | Congressman Mike Lawler | 10% | Lower per-student threshold to $200K | | {add_ref("https://lawler.house.gov/news/documentsingle.aspx?DocumentID=3716", "Congressman Lawler Reintroduces the Endowment Accountability Act to Ensure Wealthy Universities Invest in Students")} |
| Mar 2025 | Congressman Vern Buchanan | 10% | Exclude non-US citizens from per-student threshold | Would tax about 10-12 additional schools, including Columbia and Cornell | {add_ref("https://buchanan.house.gov/2025/3/buchanan-introduces-bill-to-prioritize-enrolling-american-students-in-higher-education", "Buchanan Introduces Bill to Prioritize Enrolling American Students in Higher Education") } |


##### Current tax rate proposal (as of May 26, 2025)
All of these proposed bills have culminated in the omnibus "One, Big, Beautiful Bill" in May 2025{add_ref("https://waysandmeans.house.gov/wp-content/uploads/2025/05/SMITMO_017_xml.pdf", "'THE ONE, BIG, BEAUTIFUL BILL' full text")}:
| Endowment NII Tax Rate | Per-student endowment threshold |
|---|---|
| 7% | \$750K to \$1.25mn | 
| 14% | \$1.25mn to \$2mn | 
| 21% | $2mn+ | 

As a side note: on page 283, it also updates foundations' tax rate based on total AUM:
| Foundation NII Tax Rate | Endowment total AUM |
|---|---|
| 1.39% | <$50mn | 
| 2.78% | \$50mn to \$250mn | 
| 5% | \$250mn to \$5bn | 
| 10% | >\$5bn | 

##### What will the impact be on asset allocation?

Patrick Geddes and his team at Aperio Group (a company acquired by BlackRock in 2020) wrote a paper in 2015, provocatively titled "What Would Yale Do If It Were Taxable?"{link_to_ref("aperio-paper")}. When they wrote the paper, they initially had ultra-high net worth individuals in mind. (Coincidentally, Aperio specialized in customizable indexes like tax-efficient ones.) Little did they know that the ideas in the paper would be relevant 10 years later for endowments and foundations. 

What follows is an extension of this paper's ideas, bringing the mean-variance optimization and analysis up to present day. 
""",
unsafe_allow_html=True)

spill_references()


# ----------------------------------------------------------
# Portfolio ------------------------------------------------
# ----------------------------------------------------------

st.divider()
st.header("Our Model Portfolio")

# Text
st.write("""
By default, the portfolio allocation assumptions use Yale's 2013 asset allocation (as provided by Aperio). The asset class proxies we use are similar to the ones Aperio uses.
""")

# GENERAL PORTFOLIO INFO
# TODO: Refactor these out
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

# MODEL PORTFOLIO
# Retrieve the portfolio weights from CSV
all_portfolio_weights_df = data_access.read_csv_from_folder("data/endowment_portfolio_weights.csv")

MODEL_PORTFOLIO_CUSTOM = "Custom"
MODEL_PORTFOLIO_YALE_2013 = "Yale 2013"

# Retrieve the portfolio weights to use
model_portfolio_name = st.pills("Portfolio weights to use:", 
                                options=all_portfolio_weights_df.columns,
                                default=MODEL_PORTFOLIO_YALE_2013)

# Handle custom
all_asset_classes = portfolio_structure.keys()
custom_weights = all_portfolio_weights_df[MODEL_PORTFOLIO_CUSTOM].loc[all_asset_classes] # Get a Series

with st.expander("Custom Portfolio Builder (click to expand)"):
    st.write("Enter custom weight for portfolio:")
    col1, col2, col3 = st.columns(3)
    cols = [(col1, "Absolute Return"), (col2, "World Public Equity"), (col3, "Bonds")]
    for pair in cols:
        col, asset_class = pair
        with col:
            custom_weights[asset_class] = input_utils.percent_input(f"{asset_class}:", custom_weights[asset_class] )
            
    col1, col2, col3 = st.columns(3)
    cols = [(col1, "Natural Resources"), (col2, "Real Estate"), (col3, "Private Equity")]
    for pair in cols:
        col, asset_class = pair
        with col:
            custom_weights[asset_class] = input_utils.percent_input(f"{asset_class}:", custom_weights[asset_class] )

    col1, _, _ = st.columns(3)
    with col1:
        
        # Reset the cash weight (which is fixed to 100% minus everything else)
        custom_weights["Cash"] = 1 - (custom_weights.sum() - custom_weights["Cash"])
        st.write(f'Cash: {custom_weights["Cash"]*100:.2f}%')

if custom_weights["Cash"] < 0:
    st.badge(f'WARNING: Cash allocation ({custom_weights["Cash"]*100:.2f}%) is less than 0. Please check allocation weights.')

st.caption("Note: in the future, we will allow ability to select different benchmarks.")

# Create the "model portfolio" dataframe, and re-name the column (which is good for the merge)
if model_portfolio_name == MODEL_PORTFOLIO_CUSTOM:
    model_portfolio_df = custom_weights.to_frame()
else:
    model_portfolio_df = all_portfolio_weights_df[[model_portfolio_name]]
model_portfolio_df = model_portfolio_df.rename(columns={model_portfolio_name: "Portfolio Weights"})


# MASTER PORTFOLIO
# Create the master portfolio dataframe
master_portfolio_df = pd.DataFrame(list(portfolio_structure.items()), columns=["Asset Class", "Benchmark Ticker"])
master_portfolio_df = master_portfolio_df.set_index("Asset Class")

master_portfolio_df["Display Name"] = master_portfolio_df["Benchmark Ticker"].map(index_display_names)

# Merge in the portfolio weights
master_portfolio_df = master_portfolio_df.merge(
    model_portfolio_df,
    left_index=True,
    right_index=True, 
    how="left"
)

# Display the portfolio
display_utils.display_streamlit_table( 
    master_portfolio_df, 
    highlight_columns=["Portfolio Weights"] 
)

st.caption("Source: Bloomberg. Aperio uses 'Blend of Credit Suisse Fund Indexes' for Absolute Return; we use a simple 'Credit Suisse Hedge Fund Index'. We also use S&P Global Natural Resources; Aperio uses North America. Aperio's sample period was January 1999 to June 2013.")


# ----------------------------------------------------------
# Inputs ---------------------------------------------------
# ----------------------------------------------------------

st.divider()
st.header("Inputs and Assumptions")


# Get current date
now = datetime.now()
current_year = now.year

# Years -----

st.markdown("##### Date Range")

# Slider
selected_range = st.slider(
    "Years to use for covariance calculations:", 
    min_value=1977,
    max_value=current_year,
    value=(current_year-10, current_year)
)

# Write selected start date
start_year = selected_range[0]
end_year = selected_range[1]


# Tax rate -----

st.markdown("##### Tax Rate")

tax_rate_options = {
    "0%": 0.0,
    "1.4%": 0.014,
    "7%": 0.07,
    "14%": 0.14,
    "21%": 0.21,
    "Other": None
}

col1, col2 = st.columns(2)
with col1:
    raw_selected_tax_rate = st.pills(
        "Endowment tax rate:", 
        options=tax_rate_options.keys(),
        default="14%",
        #format_func=(lambda option: tax_rate_options[option]),
        selection_mode="single"
        )

with col2:
    raw_other_tax_rate = st.number_input("""Custom endowment tax rate (in %) (if "Other" selected):""", step=1.)

# Get the selected tax rate (in float)
selected_tax_rate_float = 0.0
if raw_selected_tax_rate == "Other":
    if raw_other_tax_rate is None:
        st.badge("Please input a custom endowment tax rate.")
    else:
        selected_tax_rate_float = raw_other_tax_rate/100
else:
    selected_tax_rate_float = tax_rate_options[raw_selected_tax_rate]


# Other assumptions ------
default_expected_market_return = 0.103
default_rf = 0.02 

with st.expander("Other Assumptions"):
    col1, col2, _ = st.columns(3)

    with col1:
        expected_market_return = input_utils.percent_input("""Expected market return (in %, e.g. "8" for "8%"):""", 
                                                           value=default_expected_market_return)
    with col2:
        rf = input_utils.percent_input("""Risk-free rate (in %, e.g. "2" for "2%"):""", 
                                           value=default_rf)

    st.markdown(f"""
- Expected market return: {expected_market_return *100:.2f}%
- Risk-free rate: {rf*100:.2f}%
""")

#st.subheader("Assumptions")
col1, col2, col3 = st.columns(3)
col1.metric(label="Date Range", value=f"{start_year} to {end_year}", border=True)
col2.metric(label="Tax Rate", value=f"{selected_tax_rate_float*100:.1f}%", border=True)
col3.metric(label="Portolio Weights", value=f"{model_portfolio_name}", border=True)



# ----------------------------------------------------------
# Calculations ---------------------------------------------
# ----------------------------------------------------------

# Step 1: Get the historical data and calculate implied returns -----

# Get the data
indexes_to_use = list(master_portfolio_df["Benchmark Ticker"])
monthly_returns_df = data_access.get_benchmark_returns_data(conn, start_year, end_year, indexes_to_use)

# Calculate, using reverse optimization
weights = np.array( list(master_portfolio_df["Portfolio Weights"]) ) 
cov_matrix = finance_utils.calculate_covariance_matrix(monthly_returns_df, type="standard")

var_portfolio = weights @ cov_matrix @ weights
lambda_risk_aversion = (expected_market_return - rf) / var_portfolio

# Calculate the implied returns, as well as the portfolio return
implied_returns = lambda_risk_aversion * cov_matrix @ weights
implied_returns_df = pd.DataFrame(implied_returns, columns=["Implied Pre-Tax Returns"])


# Merge in the implied returns
master_portfolio_df = master_portfolio_df.merge(implied_returns_df, left_on="Benchmark Ticker", right_index=True, how="left")


# Step 2: Calculate tax impact ------------

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

def calculate_post_tax_return(pre_tax_return, percent_realized, tax_rate):
    realized_returns = pre_tax_return*percent_realized*(1-tax_rate) # taxed
    unrealized_returns = pre_tax_return*(1-percent_realized)
    return realized_returns + unrealized_returns

# Collate the table together
master_portfolio_with_tax_df = master_portfolio_df.merge(tax_penalty_df, left_index=True, right_index=True, how="left")

# Calculate the post-tax returns
master_portfolio_with_tax_df["Post-Tax Returns"] = master_portfolio_with_tax_df.apply( 
    lambda row: calculate_post_tax_return(row["Implied Pre-Tax Returns"], row["Percent Realized"], selected_tax_rate_float),
    axis=1
)


# Step 3: Calculate post-tax portfolio weights ------------

mu = master_portfolio_with_tax_df["Post-Tax Returns"]
post_tax_weights = finance_utils.calculate_optimized_weights( mu, cov_matrix, expected_market_return - rf) 

master_portfolio_with_tax_df["Pre-Tax Weights"] = master_portfolio_with_tax_df["Portfolio Weights"]
master_portfolio_with_tax_df["Post-Tax Weights"] = post_tax_weights
master_portfolio_with_tax_df["Portfolio Weight Change"] = master_portfolio_with_tax_df["Post-Tax Weights"] - master_portfolio_with_tax_df["Pre-Tax Weights"]


# ----------------------------------------------------------
# Pretty Visuals -------------------------------------------
# ----------------------------------------------------------

st.divider()
st.subheader("Impact")


asset_order = master_portfolio_with_tax_df.index.tolist()

# Pre vs. post-tax returns 
df = (master_portfolio_with_tax_df
        .reset_index()
        .melt(
            id_vars="Asset Class",
            value_vars=["Implied Pre-Tax Returns", "Post-Tax Returns"],
            var_name="Type",
            value_name="Returns"
        )
)

chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("Returns:Q", axis=alt.Axis(format=".2%")),
    y=alt.Y("Asset Class:N", sort=asset_order),
    color=alt.Color("Type:N", sort=["Implied Pre-Tax Returns", "Post-Tax Returns"]),
    yOffset=alt.YOffset("Type:N", sort=["Implied Pre-Tax Returns", "Post-Tax Returns"])
).properties(
    width=600,
    height=400
)

labels = alt.Chart(df).mark_text(
    #align="left",
    #baseline="middle",
    #dx=3  # adjust as needed to position the text
    align=alt.expr("datum.Returns < 0 ? 'right' : 'left'"),
    baseline="middle",
    dx=alt.expr("datum.Returns < 0 ? -5 : 3"),
).encode(
    x=alt.X("Returns:Q"),
    y=alt.Y("Asset Class:N", sort=asset_order),
    yOffset=alt.YOffset("Type:N", sort=["Implied Pre-Tax Returns", "Post-Tax Returns"]),
    text=alt.Text("Returns:Q", format=".2%"),
    detail="Type:N"
)

st.markdown("##### Post-Tax Returns: Small Haircuts on Expected Returns")
tab1, tab2 = st.tabs(["Graph", "Data"])
with tab1:
    st.altair_chart(chart + labels, use_container_width=True)
with tab2:
    st.dataframe(master_portfolio_with_tax_df[["Implied Pre-Tax Returns", "Post-Tax Returns"]])
st.caption("Source: Bloomberg and own analysis.")


# Allocation impact
df = (master_portfolio_with_tax_df
        .reset_index()
        .melt(
            id_vars="Asset Class",
            value_vars=["Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change"],
            var_name="Type",
            value_name="Weight"
        )
)

# Display bar chart
chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("Weight:Q", axis=alt.Axis(format=".2%")),
    y=alt.Y("Asset Class:N", sort=asset_order),
    color=alt.Color("Type:N", sort=["Pre-Tax Weights", "Post-Tax Weights"]),
    yOffset=alt.YOffset("Type:N", sort=["Pre-Tax Weights", "Post-Tax Weights"])
).properties(
    width=600,
    height=500
)

labels = alt.Chart(df).mark_text(
    align=alt.expr("datum.Weight < 0 ? 'right' : 'left'"),
    baseline="middle",
    dx=alt.expr("datum.Weight < 0 ? -5 : 3"),
    dy=2 # adjustment to make it line up nicely
).encode(
    x=alt.X("Weight:Q", axis=alt.Axis(format=".2%")),
    y=alt.Y("Asset Class:N", sort=asset_order),
    yOffset=alt.YOffset("Type:N", sort=["Pre-Tax Weights", "Post-Tax Weights"]),
    text=alt.Text("Weight:Q", format=".2%"),
    detail="Type:N"
)


st.markdown("##### Post-Tax Asset Allocation: Small Haircuts Imply Large Changes")
tab1, tab2 = st.tabs(["Graph", "Data"])
with tab1:
    st.altair_chart(chart + labels, use_container_width=True)
with tab2:
    st.dataframe(master_portfolio_with_tax_df[["Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change"]])
st.caption("Source: Bloomberg and own analysis.")

st.markdown("##### Table: Post-Tax Asset Allocation")
columns_to_display = ["Benchmark Ticker", "Display Name", "Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change", "Implied Pre-Tax Returns", "Post-Tax Returns"]
display_utils.display_streamlit_table(master_portfolio_with_tax_df[columns_to_display],
                                      highlight_columns=["Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change"])


# ----------------------------------------------------------
# Details of calculations ----------------------------------
# ----------------------------------------------------------

st.divider()

st.header("Details and Discussion")

st.markdown("""
A diagram of the inputs and steps taken to calculate the post-tax portfolio weights:
""")

flowchart_code = """
digraph G {
    rankdir=LR
    node [shape=rectangle, style=filled, fillcolor=lightblue, penwidth=1];
    subgraph cluster_1 {
        A1 [label="Portfolio Weights"];
        A2 [label="Expected Portfolio Return"];
        A3 [label="Historical Covariances", shape=box];
    }
    subgraph cluster_2 {
        B1 [label="Implied Returns", shape=box]
        B2 [label="Tax Assumptions", shape=box]
    }
    subgraph cluster_3 {
        C1 [label="Post-Tax Returns", shape=box]
    }
    subgraph cluster_4 {
        D1 [label="Post-Tax Portfolio Weights", shape=box]
    }

    A1 -> B1 [label="Step 1"]
    A2 -> B1 
    A3 -> B1 
    B1 -> C1 [label="Step 2"]
    B2 -> C1
    C1 -> D1 [label="Step 3"]
    A3 -> D1
 
}
"""

st.graphviz_chart(flowchart_code)


# Step 1 ----------------------------------------------

st.subheader("Step 1: Calculate Pre-Tax Implied Returns")

st.markdown(f"""
The first step of the process is to calculate the implied returns, based on portfolio weights. The process uses (a) portfolio weights and (b) historical covariances to calculate the implied expected returns using a reverse mean-variance optimizer. We calculate the covariance matrix for the time range input above and use the other assumptions listed above.
"""
)

lambda_formula = "\\lambda = \\frac{\\mathbb{E}[R_p] - R_f}{\\sigma_p^2}"
expected_return_formula = "\\mathbb{E}[R_p]"

st.write(f"""
We first calculate risk aversion: ${lambda_formula}$, where:
- ${expected_return_formula}$ is the expected return of the portfolio,
- $R_f$ is the risk-free rate, 
- $\\sigma_p^2$ is the portfolio variance, calculated by $\\sigma_p^2 = w^\\top \\Sigma w$
  - $w$ are the portfolio weights (n x 1 matrix)
  -  $\\Sigma$ is the covariances (n x n matrix)

The implied returns $\\mu$ are then calculated with: $\\mu = \\lambda \\cdot \\Sigma w$. The results:

""")

st.markdown("###### Implied Pre-Tax Returns by Asset Class")
columns_to_display = ["Asset Class", "Benchmark Ticker", "Display Name", "Portfolio Weights", "Implied Pre-Tax Returns"]
display_utils.display_streamlit_table(master_portfolio_df, 
                                      percent_columns=["Portfolio Weights", "Implied Pre-Tax Returns"],
                                      highlight_columns=["Implied Pre-Tax Returns"] )

abs_return_ticker = master_portfolio_df.loc["Absolute Return", "Benchmark Ticker"]
world_public_eq_return_ticker = master_portfolio_df.loc["World Public Equity", "Benchmark Ticker"]
corr_matrix = monthly_returns_df.corr()

st.markdown(f"""
###### Correlation Matrix
The correlations between assets is also important. The full correlation matrix is copied below. Of note:
- Correlation between World Public Equity ({world_public_eq_return_ticker}) and Absolute Return ({abs_return_ticker}): **{corr_matrix.loc[abs_return_ticker, world_public_eq_return_ticker]:.3f}**
""")

st.write(corr_matrix)

# Step 2 ----------------------------------------------

st.subheader("Step 2: Apply Tax Haircuts to Pre-Tax Returns")

st.markdown(
"""
The next step is to apply a tax haircut to the pre-tax returns. For example, a 10% realized return with a 30% tax rate shrinks to a 7% return. The Aperio paper targets personal investors with a worst-case tax scenario with a 44.6% short-term/ordinary tax, and a 25% long-term/dividends tax rate.

Endowment taxes are based on net investment income (NII), which does not distinguish between short-term and long-term returns. Therefore, we assume that all realized returns (ordinary income, realized short-term, realized long-term, dividends) are taxed at the NII rate. 

Aperio makes some estimates on the estimated realized vs. unrealized returns are by asset class. We use their assumptions unmodified and calculate a total percent of the asset class's returns that are realized.
"""
)

st.markdown("###### Realized vs. Unrealized Return Assumptions by Asset Class")
display_utils.display_streamlit_table(tax_penalty_df, highlight_columns=["Percent Realized"])

st.markdown(
"""
Our post-tax returns are calculated by taxing the realized return percent:

$r_{post} = r_{pre}*W_{realized}*(1-t) + r_{pre}*(1-W_{realized})$

Where $r_{pre}$ is the pre-tax return, $t$ is the tax rate, and $W_{realized}$ is the percent of the returns that are realized/taxable. 
"""
)

# Display
st.markdown("###### Post-Tax Returns by Asset Class")
columns_to_display=["Display Name", "Percent Realized", "Implied Pre-Tax Returns", "Post-Tax Returns"]
display_utils.display_streamlit_table(master_portfolio_with_tax_df[columns_to_display],
                                      highlight_columns=["Post-Tax Returns"]) 

st.caption("Note: Public equity is assumed to be indexed. Bonds are assumed to be taxable bonds.")



# Step 3 ----------------------------------------------

st.subheader("Step 3: Calculate Post-Tax Portfolio Weights")

st.markdown(
"""
Our last step is to run the mean-variance optimization on the new post-tax weights to try to answer the ultimate question, "what would
taxes do to our portfolio weights?" The process we use is to minimize portfolio variance, subject to a few constraints:
- Long-only (all portfolio weights are greater than 0%)
- The expected portfolio returns equals the target return

The long-only constraint makes a closed-form solution impossible, so our formula looks something like this:
- Minimize $\\sigma_p^2$
- Subject to:
  - Every weight $w_i > 0$
    - $w$ are the portfolio weights (n x 1 matrix)
  - $w^\\top r_p = \\mathbb{E}[R_p] - R_f$
    - $r_p$ is the expected return on each asset class in the portfolio (n x 1 matrix) 
"""
)

st.markdown("###### Post-Tax Portfolio Weights")
columns_to_display = ["Benchmark Ticker", "Display Name", "Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change", "Implied Pre-Tax Returns", "Post-Tax Returns"]
display_utils.display_streamlit_table(master_portfolio_with_tax_df[columns_to_display],
                                      highlight_columns=["Pre-Tax Weights", "Post-Tax Weights", "Portfolio Weight Change"])


# Takeaways ---------------------------------------------

st.divider()

st.subheader("Takeaways")

st.markdown("""

When I first read the Aperio paper, I assumed the large implied portfolio allocation changes stemmed from
the exorbitant tax rate assumptions (44.6% short-term/ordinary tax, and a 25% long-term/dividends tax rate).What surprised me, though, was that **even a "small" change in the tax rate can imply large 
changes in portfolio allocation**.

Let's take one example: a 7% tax on the Yale 2020 portfolio, using data from 2006 to 2025. 
The allocation impact on such a "small" tax rate increase is striking:
- Significantly less absolute return (23.5% to 9.7%) and significantly more cash (1.5% to 9.1%), and
- Significantly more public equity (14.0% to 24.9%) and slightly less private equity (41% to 39.3%)
""")

st.subheader("Discussion")


st.markdown("""
Some parting thoughts:

**Portfolio allocation is more than mean-variance optimization.** 
We use mean-variance optimization to calculate expected returns from portfolio weights and vice versa, but I'll be the first to 
acknowledge that portfolio allocation shouldn't be made on these formulas alone. I do think these tools can help illustrate
how much small changes can have on the overall build-up of the portfolio, though.

**The inputs, assumptions, and models all have uncertainty.**
I've tried to lay out all of the assumptions we've made (and let you modify them!), but all the inputs and assumptions are all arguably
inaccurate. For example, we project future covariance off of past covariance, but past covariance is not indicative of future results.

**We're missing other important allocation inputs like liquidity.**
We disregard many other pieces of the portfolio, including important things like liquidity. These can be added back as 
bounds in Step 3, but this perhaps further emphasizes that mean-variance optimization isn't the whole story.

**Further directions:**
- The Aperio paper goes a step further and tweaks the covariance matrix using a Monte Carlo simulation. I haven't implemented these quite yet.
- We use the same asset class proxies as Aperio. I hope to allow you the ability to select the proxies used (as well as break out venture capital from private equity).
""")

# Takeaways ---------------------------------------------

st.divider()

st.subheader("Technical Notes")

st.markdown("""
- Financial data downloaded from Bloomberg via flatfile and ETL'ed into a Databricks SQL database. (Due to costs of running Databricks, I subsequently am storing the data in a mock SQL database.)
""")

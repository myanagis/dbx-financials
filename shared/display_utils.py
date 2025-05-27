import pandas as pd
import streamlit as st


# Helpers for displaying in streamlit -----

def bold_highlight(val):
    return "font-weight: bold; background-color: #fef9e7"

# Callable function
def display_streamlit_table(df, percent_columns=[], highlight_columns=[]):
    
    # Auto-detect percent columns
    autodetected_percent_columns = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        col_max = df[col].max()
        col_min = df[col].min()

        if col_max <= 1.5 and col_min >= -1:
            autodetected_percent_columns.append(col)

    all_percent_columns = list(set(autodetected_percent_columns + percent_columns))
    styled_df = (
        df.style
          .format({
                     **{col: "{:.1%}" for col in all_percent_columns}
                 })
          .applymap(bold_highlight, subset=highlight_columns)
    )

    # Display
    st.dataframe(styled_df)
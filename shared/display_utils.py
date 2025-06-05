import pandas as pd
import streamlit as st


# Helpers for displaying in streamlit -----

def bold_highlight(val):
    return "font-weight: bold; background-color: #fef9e7"

# Callable function
def display_streamlit_table(df, percent_columns=[], highlight_columns=[], additional_styles=[]):
    
    # Auto-detect percent columns
    autodetected_percent_columns = []
    autodetected_large_number_columns = []
    autodetected_normal_numeric_columns = []
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        col_max = df[col].max()
        col_min = df[col].min()

        if col_max <= 1.5 and col_min >= -1:
            autodetected_percent_columns.append(col)
        elif col_max > 1000 or col_min < -1000:
            autodetected_large_number_columns.append(col)
        else:
            autodetected_normal_numeric_columns.append(col)

    # Percent columns
    all_percent_columns = list(set(autodetected_percent_columns + percent_columns))
    format_dict = {
        **{col: "{:.1%}" for col in all_percent_columns},
        **{col: "{:,.0f}" for col in autodetected_large_number_columns},
        **{col: "{:,.1f}" for col in autodetected_normal_numeric_columns}
    }
    styled_df = df.style.format(format_dict)

    # Additional styles
    styled_df = styled_df.applymap(bold_highlight, subset=highlight_columns)
    
    # TODO: additional_styles
    #for style in additional_styles:
    #    function, subset = style
    #    styled_df = styled_df.applymap(function, subset=subset)

    
    # Display
    st.dataframe(styled_df)
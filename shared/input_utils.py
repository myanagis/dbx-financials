import streamlit as st

def percent_input(label: str, value: float):
    raw_input = st.number_input(label, 
                                value=value*100,  
                                min_value=0., 
                                max_value=100., 
                                step=1., 
                                format="%.2f")

    return raw_input/100
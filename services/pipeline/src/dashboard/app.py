"""Main entrypoint for the Streamlit dashboard."""

import streamlit as st

from dashboard.db import get_connection

st.set_page_config(
    page_title="Air Quality Dashboard",
    page_icon="🌍",
    layout="wide",
)

@st.cache_resource
def init_connection():
    """Cache the database connection across Streamlit reruns."""
    return get_connection()

st.title("🌍 Air Quality Dashboard")
st.markdown(
    """
    Welcome to the Air Quality Dashboard! 
    
    👈 **Select a view from the sidebar** to explore current conditions, 
    historical data, or compare cities.
    """
)
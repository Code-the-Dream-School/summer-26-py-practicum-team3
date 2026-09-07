"""Main entrypoint for the Air Quality Streamlit dashboard."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Air Quality Dashboard",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 Air Quality Dashboard")
st.markdown(
    """
    Welcome to the Air Quality Dashboard!

    👈 **Select a view from the sidebar** to explore current conditions,
    historical data, or compare cities.
    """
)

with st.expander("About this project"):
    st.markdown(
        """
        This dashboard visualizes air pollution data collected by the team's
        OpenWeather air-pollution pipeline and stored in PostgreSQL.

        - **Summary** — latest air quality reading for every active city.
        - **City detail** — history for a single city.
        - **Compare** — several cities side by side over a time window.

        Built by Team 3 for the Code the Dream Python practicum.
        [Source on GitHub](https://github.com/Code-the-Dream-School/summer-26-py-practicum-team3)
        """
    )

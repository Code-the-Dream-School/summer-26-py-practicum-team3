"""Compare/Trends view: compare cities side-by-side and see change over time."""
from datetime import datetime, timezone, timedelta

import pandas as pd
import psycopg
import streamlit as st

from dashboard.app import init_connection
from dashboard.queries import list_cities, get_cities_comparison


STALE_THRESHOLD = timedelta(hours=3)

# Maps a friendly label -> the underlying column returned by get_cities_comparison.
POLLUTANT_OPTIONS = {
    "AQI": "aqi",
    "PM2.5 (μg/m³)": "pm2_5",
    "PM10 (μg/m³)": "pm10",
    "CO (μg/m³)": "co",
    "NO2 (μg/m³)": "no2",
    "O3 (μg/m³)": "o3",
    "SO2 (μg/m³)": "so2",
}


def _city_label(row: dict) -> str:
    """Build a display label consistent with 1_Summary.py's location formatting."""
    state = f", {row['state_code']}" if row.get("state_code") else ""
    return f"{row['city_name']} ({row['country_code']}{state})"


def render_compare():
    st.title("📈 Compare Cities & Trends")

    # Loading / error state for the connection itself
    try:
        conn = init_connection()
    except ValueError as e:
        st.error(f"Configuration Error: {e}")
        return
    except psycopg.Error as e:
        st.error(f"Database Connection Error: {e}")
        return

    # Loading / error state for the city list
    with st.spinner("Loading cities..."):
        try:
            cities = list_cities(conn)
        except psycopg.Error as e:
            st.error(f"Failed to fetch city list: {e}")
            return

    # Empty state - no active cities configured at all
    if not cities:
        st.info("No cities configured yet. Add cities to the pipeline config to get started.")
        return

    # city_id is a string identifier (e.g. 'berlin-de'), not a surrogate int.
    label_to_id = {_city_label(row): row["city_id"] for row in cities}
    labels = sorted(label_to_id.keys())

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_labels = st.multiselect(
            "Cities to compare",
            options=labels,
            default=labels[: min(3, len(labels))],
        )
    with col2:
        metric_label = st.selectbox("Metric", options=list(POLLUTANT_OPTIONS.keys()), index=0)
    with col3:
        lookback_days = st.selectbox("Lookback window", options=[1, 3, 7, 14, 30], index=2)

    if not selected_labels:
        st.info("Select at least one city to see trends.")
        return

    selected_ids = [label_to_id[label] for label in selected_labels]
    metric_col = POLLUTANT_OPTIONS[metric_label]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    # Loading / error state for the historical query
    with st.spinner("Fetching historical readings..."):
        try:
            history = get_cities_comparison(conn, city_ids=selected_ids, start=start, end=end)
        except psycopg.Error as e:
            st.error(f"Failed to fetch historical data: {e}")
            return
        except ValueError as e:
            # Raised by get_cities_comparison if start/end aren't tz-aware 
            st.error(f"Invalid time window: {e}")
            return

    # Empty state  query ran fine but returned nothing in this window
    if not history:
        st.info(
            "No historical readings in this window yet. "
            "Try a longer lookback window or check that the pipeline has run."
        )
        return

    df = pd.DataFrame(history)
    df["city_label"] = df.apply(_city_label, axis=1)

    # Incomplete-data state  some selected cities came back with zero rows
    returned_ids = set(df["city_id"].unique())
    missing = [label for label, cid in zip(selected_labels, selected_ids) if cid not in returned_ids]
    if missing:
        st.warning(f"No data returned for: {', '.join(missing)} in this window.")

    # Stale-data state - a city's most recent point is older than the threshold
    latest_per_city = df.groupby("city_label")["observed_at"].max()
    stale_cities = [label for label, ts in latest_per_city.items() if (end - ts) > STALE_THRESHOLD]
    if stale_cities:
        st.warning(f"Data may be stale for: {', '.join(stale_cities)} (no reading in the last 3h).")

    # Render - change-over-time view
    st.subheader(f"{metric_label} over the last {lookback_days} day(s)")
    pivot = df.pivot_table(index="observed_at", columns="city_label", values=metric_col).sort_index()
    st.line_chart(pivot)

    # Render - city-vs-city snapshot view
    st.subheader("Latest snapshot comparison")
    latest_rows = (
        df.sort_values("observed_at")
        .groupby("city_label")
        .tail(1)
        .sort_values(metric_col, ascending=False)
    )
    display_cols = ["city_label", "observed_at", metric_col]
    st.dataframe(
        latest_rows[display_cols].rename(
            columns={"city_label": "City", "observed_at": "Last Observed", metric_col: metric_label}
        ),
        hide_index=True,
        use_container_width=True,
    )


if __name__ == "__main__":
    render_compare()

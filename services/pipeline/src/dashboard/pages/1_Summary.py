"""Summary view: the latest air quality reading for every active city."""

from __future__ import annotations

from datetime import datetime, timezone

import psycopg
import streamlit as st

from dashboard.db import init_connection
from dashboard.format_data import (
    aqi_display,
    city_label,
    format_relative_time,
    is_stale,
)
from dashboard.queries import get_latest_readings

# Sort options -> a key function over a reading row. Sorting happens client-side
# on the already-fetched rows: one row per active city is a small list.
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)
SORT_OPTIONS: dict[str, tuple] = {
    "City name": (lambda row: city_label(row).lower(), False),
    "AQI (worst first)": (lambda row: row.get("aqi") or 0, True),
    "Last updated": (lambda row: row.get("observed_at") or _OLDEST, True),
}


def render_summary() -> None:
    st.title("📊 Current Air Quality Summary")

    # Connection: configuration and database errors both surface as a message
    # rather than an unhandled traceback on the page.
    try:
        conn = init_connection()
    except ValueError as exc:
        st.error(f"Configuration Error: {exc}")
        return
    except psycopg.Error as exc:
        st.error(f"Database Connection Error: {exc}")
        return

    # Loading state around the query itself.
    with st.spinner("Fetching latest readings..."):
        try:
            readings = get_latest_readings(conn)
        except psycopg.Error as exc:
            st.error(f"Failed to fetch data: {exc}")
            return

    # Empty state: the query worked, there is simply nothing stored yet.
    if not readings:
        st.info("No air pollution data available. Run the pipeline to populate the database.")
        return

    st.write(f"Showing latest observations for {len(readings)} active cities.")

    sort_choice = st.selectbox("Sort by", options=list(SORT_OPTIONS.keys()), index=0)
    key_func, descending = SORT_OPTIONS[sort_choice]
    readings = sorted(readings, key=key_func, reverse=descending)

    now = datetime.now(timezone.utc)
    cols = st.columns(3)

    for idx, row in enumerate(readings):
        observed_at = row.get("observed_at")
        label_text, icon = aqi_display(row.get("aqi"), row.get("aqi_label"))

        with cols[idx % 3], st.container(border=True):
            st.subheader(city_label(row))

            # Stale-data state: flag it instead of presenting it as current.
            if is_stale(observed_at, now):
                st.warning(f"⚠️ Stale data ({format_relative_time(observed_at)})")
            else:
                st.caption(f"🕒 Updated {format_relative_time(observed_at)}")

            aqi = row.get("aqi")
            st.metric(
                label="Air Quality Index",
                value=f"{icon} {aqi} - {label_text}" if aqi is not None else f"{icon} {label_text}",
            )

            with st.expander("View Pollutants (μg/m³)", expanded=False):
                st.markdown(
                    f"""
                    - **PM2.5**: {row.get('pm2_5')}
                    - **PM10**: {row.get('pm10')}
                    - **CO**: {row.get('co')}
                    - **NO2**: {row.get('no2')}
                    - **O3**: {row.get('o3')}
                    - **SO2**: {row.get('so2')}
                    - **NH3**: {row.get('nh3')}
                    - **NO**: {row.get('no')}
                    """
                )


if __name__ == "__main__":
    render_summary()

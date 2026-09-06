"""Summary view for the latest air quality readings across active cities."""

from datetime import datetime, timezone, timedelta

import psycopg
import streamlit as st

from dashboard.app import init_connection
from dashboard.queries import get_latest_readings

# OpenWeather AQI scale mapping for UI colors
AQI_COLORS = {
    1: ("Good", "🟢"),
    2: ("Fair", "🟡"),
    3: ("Moderate", "🟠"),
    4: ("Poor", "🔴"),
    5: ("Very Poor", "🟣"),
}

# Assume data is stale if older than 3 hours (adjust based on pipeline schedule)
STALE_THRESHOLD = timedelta(hours=3)

def format_relative_time(dt: datetime) -> str:
    """Format datetime into a readable relative string."""
    now = datetime.now(timezone.utc)
    diff = now - dt
    minutes = int(diff.total_seconds() / 60)
    
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    return f"{hours}h ago"

def render_summary():
    st.title("📊 Current Air Quality Summary")
    
    # 1. Loading State & Error Handling for Connection
    try:
        conn = init_connection()
    except ValueError as e:
        st.error(f"Configuration Error: {e}")
        return
    except psycopg.Error as e:
        st.error(f"Database Connection Error: {e}")
        return

    # 2. Loading State & Error Handling for Query
    with st.spinner("Fetching latest readings..."):
        try:
            readings = get_latest_readings(conn)
        except psycopg.Error as e:
            st.error(f"Failed to fetch data: {e}")
            return

    # 3. Empty State
    if not readings:
        st.info("No air pollution data available. Run the pipeline to populate the database.")
        return

    # 4. Render Data
    st.write(f"Showing latest observations for {len(readings)} active cities.")
    
    now = datetime.now(timezone.utc)
    
    # Render in a grid (3 columns per row)
    cols = st.columns(3)
    
    for idx, row in enumerate(readings):
        col = cols[idx % 3]
        
        city = row['city_name']
        country = row['country_code']
        state = f", {row['state_code']}" if row.get('state_code') else ""
        location = f"{city} ({country}{state})"
        
        aqi = row['aqi']
        # Fallback if label is missing or unknown
        label_text, icon = AQI_COLORS.get(aqi, (row.get('aqi_label', 'Unknown'), "⚪"))
        
        observed_at = row['observed_at']
        is_stale = (now - observed_at) > STALE_THRESHOLD
        
        with col:
            with st.container(border=True):
                st.subheader(location)
                
                # Stale data badge
                if is_stale:
                    st.warning(f"⚠️ Stale data ({format_relative_time(observed_at)})")
                else:
                    st.caption(f"🕒 Updated {format_relative_time(observed_at)}")
                
                st.metric(
                    label="Air Quality Index",
                    value=f"{icon} {aqi} - {label_text}"
                )
                
                # Expandable section for pollutant details
                with st.expander("View Pollutants (μg/m³)", expanded=False):
                    st.markdown(
                        f"""
                        - **PM2.5**: {row['pm2_5']}
                        - **PM10**: {row['pm10']}
                        - **CO**: {row['co']}
                        - **NO2**: {row['no2']}
                        - **O3**: {row['o3']}
                        - **SO2**: {row['so2']}
                        - **NH3**: {row['nh3']}
                        - **NO**: {row['no']}
                        """
                    )

if __name__ == "__main__":
    render_summary()
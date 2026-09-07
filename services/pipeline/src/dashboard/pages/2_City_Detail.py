"""City Detail view: history for a single active city."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import psycopg
import streamlit as st
from dashboard.db import init_connection
from dashboard.queries import get_city_history, list_cities

STALE_THRESHOLD = timedelta(hours=3)

AQI_COLORS: dict[int, tuple[str, str]] = {
    1: ("Good", "🟢"),
    2: ("Fair", "🟡"),
    3: ("Moderate", "🟠"),
    4: ("Poor", "🔴"),
    5: ("Very Poor", "🟣"),
}
UNKNOWN_AQI: tuple[str, str] = ("Unknown", "⚪")

# (low, high, hex) bands drawn behind the AQI trend chart, same 1-5 scale as AQI_COLORS.
AQI_BANDS = [
    (1, 2, "#2e7d32"),
    (2, 3, "#558b2f"),
    (3, 4, "#f57c00"),
    (4, 5, "#d32f2f"),
    (5, 6, "#7b1fa2"),
]
AQI_HEX: dict[int, str] = {low: color for low, _, color in AQI_BANDS}
UNKNOWN_HEX = "#666666"

POLLUTANT_OPTIONS = {
    "AQI": "aqi",
    "PM2.5 (μg/m³)": "pm2_5",
    "PM10 (μg/m³)": "pm10",
    "CO (μg/m³)": "co",
    "NO2 (μg/m³)": "no2",
    "O3 (μg/m³)": "o3",
    "SO2 (μg/m³)": "so2",
}

# All raw pollutant columns air_pollution_gold has, for the "all pollutants" small-multiples
# grid. Wider than POLLUTANT_OPTIONS (which feeds the single-metric selector) since NH3/NO
# don't need their own selector entry to still be worth showing in the grid.
POLLUTANT_DISPLAY: dict[str, str] = {
    "pm2_5": "PM2.5 (μg/m³)",
    "pm10": "PM10 (μg/m³)",
    "co": "CO (μg/m³)",
    "no": "NO (μg/m³)",
    "no2": "NO2 (μg/m³)",
    "o3": "O3 (μg/m³)",
    "so2": "SO2 (μg/m³)",
    "nh3": "NH3 (μg/m³)",
}


def city_label(row: dict) -> str:
    """Build a display label consistent with the Summary page's location formatting."""
    state = f", {row['state_code']}" if row.get("state_code") else ""
    return f"{row['city_name']} ({row['country_code']}{state})"


def format_relative_time(observed_at: datetime) -> str:
    """Format an observation timestamp as a readable relative string."""
    minutes = int((datetime.now(timezone.utc) - observed_at).total_seconds() / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    return f"{hours}h ago"


def _get_latest_coordinates(conn: psycopg.Connection, city_id: str) -> tuple[float, float] | None:
    """Fetch a city's most recent known lat/lon.

    Queried directly here rather than via dashboard.queries: no other page needs
    coordinates yet, so this stays scoped to City Detail instead of widening the
    shared query layer for a single caller.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lat, lon
            FROM air_pollution_gold
            WHERE city_id = %(city_id)s
            ORDER BY observed_at DESC
            LIMIT 1;
            """,
            {"city_id": city_id},
        )
        row = cur.fetchone()
    return (row["lat"], row["lon"]) if row else None


def _resample(series: pd.Series, daily: bool) -> pd.Series:
    """Collapse a time-indexed series to a daily mean when `daily` is set."""
    if not daily:
        return series
    return series.resample("D").mean()


def _aqi_band_figure(series: pd.Series) -> go.Figure:
    """AQI trend line, layered over shaded Good/Fair/Moderate/Poor/Very Poor bands.

    A translucent fill alone (no border) all but disappears when alpha-blended
    over Streamlit's dark-mode plot background, so each band also gets a
    solid-color edge that stays visible regardless of theme.
    """
    fig = go.Figure()
    for low, high, color in AQI_BANDS:
        fig.add_hrect(
            y0=low,
            y1=high,
            fillcolor=color,
            opacity=0.35,
            line_width=1,
            line_color=color,
            layer="below",
        )
    fig.add_trace(
        go.Scatter(
            x=series.index,
            y=series.values,
            mode="lines",
            name="AQI",
            line={"color": "#1f77b4", "width": 2},
        )
    )
    fig.update_layout(
        yaxis={"range": [1, 5.5], "title": "AQI"},
        xaxis_title="Observed at",
        height=320,
        margin={"t": 20, "b": 20},
        showlegend=False,
    )
    return fig


def render_city_detail() -> None:
    title = st.empty()
    title.title("🏙️ City Detail")

    try:
        conn = init_connection()
    except ValueError as exc:
        st.error(f"Configuration Error: {exc}")
        return
    except psycopg.Error as exc:
        st.error(f"Database Connection Error: {exc}")
        return

    with st.spinner("Loading cities..."):
        try:
            cities = list_cities(conn)
        except psycopg.Error as exc:
            st.error(f"Failed to fetch city list: {exc}")
            return

    if not cities:
        st.info("No cities configured yet. Add cities to the pipeline config to get started.")
        return

    label_to_id = {city_label(row): row["city_id"] for row in cities}
    labels = sorted(label_to_id.keys())

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_label = st.selectbox("City", options=labels, index=0)
    with col2:
        metric_label = st.selectbox("Metric", options=list(POLLUTANT_OPTIONS.keys()), index=0)
    with col3:
        lookback_days = st.selectbox(
            "Lookback window",
            options=[1, 3, 7, 14, 30],
            index=2,
            format_func=lambda d: f"{d} day" if d == 1 else f"{d} days",
        )

    title.title(f"🏙️ City Detail - {selected_label}")

    city_id = label_to_id[selected_label]
    metric_col = POLLUTANT_OPTIONS[metric_label]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    with st.spinner("Fetching historical readings..."):
        try:
            history = get_city_history(conn, city_id=city_id, start=start, end=end)
        except psycopg.Error as exc:
            st.error(f"Failed to fetch historical data: {exc}")
            return
        except ValueError as exc:
            st.error(f"Invalid time window: {exc}")
            return

    if not history:
        st.info(
            "No historical readings in this window yet. "
            "Try a longer lookback window or check that the pipeline has run."
        )
        return

    df = pd.DataFrame(history)
    latest = df.sort_values("observed_at").iloc[-1]
    is_stale = (end - latest["observed_at"]) > STALE_THRESHOLD

    with st.container(border=True):
        st.subheader(selected_label)

        if is_stale:
            st.warning(f"⚠️ Stale data ({format_relative_time(latest['observed_at'])})")
        else:
            st.caption(f"🕒 Updated {format_relative_time(latest['observed_at'])}")

        label_text, icon = AQI_COLORS.get(latest["aqi"], UNKNOWN_AQI)
        st.metric(label="Air Quality Index", value=f"{icon} {latest['aqi']} - {label_text}")

        with st.expander("View Pollutants (μg/m³)", expanded=False):
            st.markdown(
                f"""
                - **PM2.5**: {latest['pm2_5']}
                - **PM10**: {latest['pm10']}
                - **CO**: {latest['co']}
                - **NO2**: {latest['no2']}
                - **O3**: {latest['o3']}
                - **SO2**: {latest['so2']}
                - **NH3**: {latest['nh3']}
                - **NO**: {latest['no']}
                """
            )

    coordinates = _get_latest_coordinates(conn, city_id)
    if coordinates:
        lat, lon = coordinates
        marker_color = AQI_HEX.get(latest["aqi"], UNKNOWN_HEX)
        st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), color=marker_color, zoom=9)

    st.subheader(f"{metric_label} over the last {lookback_days} day(s)")

    metric_series = df.set_index("observed_at")[metric_col].sort_index()
    stat_cols = st.columns(3)
    stat_cols[0].metric(f"Min {metric_label}", f"{metric_series.min():.1f}")
    stat_cols[1].metric(f"Max {metric_label}", f"{metric_series.max():.1f}")
    stat_cols[2].metric(f"Avg {metric_label}", f"{metric_series.mean():.1f}")

    worst_at = metric_series.idxmax()
    st.caption(
        f"Worst reading: {metric_series.max():.1f} on {worst_at.strftime('%b %d, %I:%M %p UTC')}"
    )

    st.download_button(
        "Download raw data (CSV)",
        data=df.sort_values("observed_at").to_csv(index=False).encode("utf-8"),
        file_name=f"{city_id}_{lookback_days}d.csv",
        mime="text/csv",
    )

    daily = st.checkbox("Aggregate by day", value=False)
    plotted_metric = _resample(metric_series, daily)

    if metric_col == "aqi":
        st.plotly_chart(_aqi_band_figure(plotted_metric), use_container_width=True)
    else:
        st.line_chart(plotted_metric)

    with st.expander("All pollutants over time", expanded=False):
        grid_cols = st.columns(2)
        for idx, (col_name, label) in enumerate(POLLUTANT_DISPLAY.items()):
            series = _resample(df.set_index("observed_at")[col_name].sort_index(), daily)
            with grid_cols[idx % 2]:
                st.caption(label)
                st.line_chart(series, height=180)


if __name__ == "__main__":
    render_city_detail()

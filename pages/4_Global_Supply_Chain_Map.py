"""Dark control-tower map for archived ports, corridors, and congestion."""

from __future__ import annotations

from datetime import date
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scripts.app_ui import configure_page
from scripts.data_paths import data_quality_for_mode, get_data_mode, is_demo_mode
from scripts.global_supply_chain_map import (
    match_congestion_to_ports,
    match_ocean_route_endpoints,
)
from scripts.stage5_intelligence import (
    add_provenance_for_export,
    load_stage5_dataset,
)


configure_page("Global Supply-Chain Map", "🌐")

st.markdown(
    """
    <style>
    .stApp { background: #0b1220; color: #e6edf7; }
    [data-testid="stHeader"] { background: rgba(11, 18, 32, 0.92); }
    [data-testid="stSidebar"] { background: #101a2b; }
    [data-testid="stMetric"] {
        background: #111d30; border: 1px solid #26364f;
        padding: 14px; border-radius: 8px;
    }
    [data-testid="stMarkdownContainer"] p { color: #d3deec; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load(dataset_id: str, mode: str) -> pd.DataFrame:
    return load_stage5_dataset(dataset_id, mode=mode)


def read(dataset_id: str) -> pd.DataFrame:
    try:
        return load(dataset_id, get_data_mode())
    except FileNotFoundError:
        st.error(
            f"Required dataset `{dataset_id}` is unavailable. "
            f"Provision it under the selected `{get_data_mode()}` data root."
        )
        st.stop()
    except ValueError as error:
        st.error(f"Dataset `{dataset_id}` failed validation: {error}")
        st.stop()


def date_window(frame: pd.DataFrame, column: str) -> tuple[date, date] | None:
    start = frame[column].min().date()
    end = frame[column].max().date()
    selection = st.sidebar.date_input(
        "Synthetic date range" if is_demo_mode() else "Historical reporting period",
        value=(start, end),
        min_value=start,
        max_value=end,
        key="map_congestion_range",
    )
    if not isinstance(selection, (tuple, list)) or len(selection) != 2:
        st.info("Select both a start and end date.")
        return None
    return selection[0], selection[1]


def source_quality_caption(dataset_id: str) -> None:
    member = {
        "ports": "ports.csv",
        "port_congestion": "port_congestion.csv",
        "route_benchmark": "benchmark-2026-11.csv",
    }[dataset_id]
    if is_demo_mode():
        st.caption(
            f"Demo file: `{member}` · Data quality: `{data_quality_for_mode()}` · "
            "Synthetic values; no external source."
        )
    else:
        archive = {
            "ports": "archive (1).zip",
            "port_congestion": "archive (2).zip",
            "route_benchmark": "archive.zip",
        }[dataset_id]
        st.caption(
            f"Archive member: `{archive}::{member}` · "
            f"Data quality: `{data_quality_for_mode()}` · "
            "Original publisher URL was not supplied."
        )


def add_base_map_layout(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b1220",
        plot_bgcolor="#0b1220",
        height=650,
        margin={"l": 8, "r": 8, "t": 58, "b": 8},
        legend={"bgcolor": "rgba(17,29,48,0.82)", "bordercolor": "#26364f"},
        geo={
            "projection": {"type": "natural earth"},
            "showland": True,
            "landcolor": "#1b2a3d",
            "showocean": True,
            "oceancolor": "#0d1a2a",
            "showlakes": True,
            "lakecolor": "#0d1a2a",
            "showcoastlines": True,
            "coastlinecolor": "#52657e",
            "showcountries": True,
            "countrycolor": "#34465d",
            "bgcolor": "#0b1220",
        },
    )
    return figure


st.title("Global Supply-Chain Control Tower")
if is_demo_mode():
    st.caption("Synthetic port, route, and congestion examples. No actual locations or live vessel tracking.")
else:
    st.caption(
        "Archived port locations, matched benchmark corridors, and historical "
        "congestion observations. No live vessel tracking is integrated."
    )
    st.error(
        "Ports, congestion, and route benchmark files are "
        "`ARCHIVE_SOURCE_UNVERIFIED`; original publishers and source URLs were not "
        "included. These views are historical archive records, not verified or live conditions."
    )

ports = read("ports")
congestion = read("port_congestion")
benchmarks = read("route_benchmark")
congestion["week_start"] = pd.to_datetime(congestion["week_start"])
benchmarks["as_of"] = pd.to_datetime(benchmarks["as_of"])

matched_routes = match_ocean_route_endpoints(ports, benchmarks)
matched_congestion = match_congestion_to_ports(ports, congestion)

st.sidebar.header("Map filters")
regions = sorted(ports["continent"].dropna().unique())
selected_regions = st.sidebar.multiselect(
    "Region / continent",
    regions,
    default=regions,
    key="map_regions",
)
region_ports = ports[ports["continent"].isin(selected_regions)]
countries = sorted(region_ports["country"].dropna().unique())
selected_countries = st.sidebar.multiselect(
    "Country",
    countries,
    default=[],
    key="map_countries",
)
if selected_countries:
    region_ports = region_ports[region_ports["country"].isin(selected_countries)]

port_search = st.sidebar.text_input(
    "Port name contains",
    help="Leave blank to include all ports in the selected region/countries.",
)
if port_search.strip():
    region_ports = region_ports[
        region_ports["port"].astype(str).str.contains(
            re.escape(port_search.strip()), case=False, na=False
        )
    ]

selection = date_window(congestion, "week_start")
if selection is None:
    st.stop()
st.sidebar.caption(
    (
        "The date filter applies to generated weekly examples; route benchmarks "
        "are a separate synthetic scenario snapshot."
        if is_demo_mode()
        else "The reporting-period filter applies to weekly historical congestion. "
        "Route benchmarks remain the separate snapshot dated 2026-11-06."
    )
)
period_start, period_end = selection
available_weeks = sorted(
    congestion.loc[
        congestion["week_start"].between(
            pd.Timestamp(period_start), pd.Timestamp(period_end)
        ),
        "week_start",
    ].drop_duplicates()
)
if not available_weeks:
    st.warning(
        "No synthetic weeks fall in the selected period."
        if is_demo_mode()
        else "No congestion reporting weeks fall in the selected period."
    )
    st.stop()
selected_week = st.sidebar.selectbox(
    "Synthetic snapshot week" if is_demo_mode() else "Congestion snapshot week",
    available_weeks,
    index=len(available_weeks) - 1,
    format_func=lambda value: value.strftime("%Y-%m-%d"),
    key="map_snapshot_week",
)

congestion_regions = sorted(matched_congestion["region"].dropna().unique())
selected_congestion_regions = st.sidebar.multiselect(
    "Congestion region",
    congestion_regions,
    default=congestion_regions,
    key="map_congestion_regions",
)
show_routes = st.sidebar.checkbox(
    "Show synthetic route examples" if is_demo_mode() else "Show matched ocean benchmark corridors",
    value=True,
    key="map_show_routes",
)
animate_congestion = st.sidebar.checkbox(
    "Animate synthetic congestion examples"
    if is_demo_mode()
    else "Animate historical congestion playback",
    value=False,
    key="map_animate_congestion",
)

visible_ports = region_ports.copy()
visible_port_names = set(
    visible_ports["port"].dropna().astype(str).str.strip().str.casefold()
)

visible_congestion = matched_congestion[
    matched_congestion["week_start"].between(
        pd.Timestamp(period_start), pd.Timestamp(period_end)
    )
    & matched_congestion["region"].isin(selected_congestion_regions)
    & matched_congestion["port"].astype(str).str.strip().str.casefold().isin(visible_port_names)
]
if selected_countries:
    visible_congestion = visible_congestion[
        visible_congestion["port_country"].isin(selected_countries)
    ]
if port_search.strip():
    visible_congestion = visible_congestion[
        visible_congestion["port"].astype(str).str.contains(
            re.escape(port_search.strip()), case=False, na=False
        )
    ]
snapshot_congestion = visible_congestion[
    visible_congestion["week_start"] == pd.Timestamp(selected_week)
]

visible_routes = matched_routes.copy()
if selected_countries:
    visible_routes = visible_routes[
        visible_routes["origin_country"].isin(selected_countries)
        | visible_routes["destination_country"].isin(selected_countries)
    ]
if selected_regions:
    visible_routes = visible_routes[
        visible_routes["origin_continent"].isin(selected_regions)
        | visible_routes["destination_continent"].isin(selected_regions)
    ]
if port_search.strip():
    search = re.escape(port_search.strip())
    visible_routes = visible_routes[
        visible_routes["origin"].str.contains(search, case=False, na=False)
        | visible_routes["destination"].str.contains(search, case=False, na=False)
    ]

metrics = st.columns(4)
metrics[0].metric("Ports in view", f"{len(visible_ports):,}")
metrics[1].metric(
    "Synthetic congestion points" if is_demo_mode() else "Historical congestion points",
    f"{snapshot_congestion['port'].nunique():,}",
    selected_week.strftime("%Y-%m-%d"),
)
metrics[2].metric(
    "Matched ocean corridors",
    f"{len(visible_routes):,}" if show_routes else "Hidden",
    f"of {len(matched_routes):,} exact coordinate matches",
)
metrics[3].metric(
    "Synthetic benchmark date" if is_demo_mode() else "Benchmark snapshot",
    benchmarks["as_of"].max().strftime("%Y-%m-%d"),
)

figure = go.Figure()
if show_routes:
    for route in visible_routes.itertuples(index=False):
        route_label = (
            f"{route.corridor_id}: {route.origin} → {route.destination}"
            f"<br>{'Synthetic benchmark' if is_demo_mode() else 'Benchmark'}: "
            f"{route.benchmark_usd:,.2f} {route.unit}"
            f"<br>As of: {pd.Timestamp(route.as_of).date()}"
            f"<br>Quality: {route.data_quality}"
        )
        figure.add_trace(
            go.Scattergeo(
                lon=[route.origin_longitude, route.destination_longitude],
                lat=[route.origin_latitude, route.destination_latitude],
                mode="lines",
                line={"color": "#38bdf8", "width": 1.4},
                opacity=0.65,
                name=(
                    "Synthetic endpoint connector"
                    if is_demo_mode()
                    else "Archived benchmark endpoint connector"
                ),
                legendgroup="routes",
                showlegend=False,
                text=[route_label, route_label],
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if not visible_routes.empty:
        figure.add_trace(
            go.Scattergeo(
                lon=[None],
                lat=[None],
                mode="lines",
                line={"color": "#38bdf8", "width": 2},
                name="Matched benchmark endpoint connectors",
                legendgroup="routes",
            )
        )

palette = {
    "Asia & Pacific": "#60a5fa",
    "Europe": "#a78bfa",
    "North America": "#34d399",
    "South America": "#fbbf24",
    "Africa": "#fb7185",
}
for region, group in visible_ports.groupby("continent", sort=True):
    custom = group[
        ["port_id", "country", "continent", "locode", "latitude", "longitude"]
    ].fillna("Not supplied").to_numpy()
    figure.add_trace(
        go.Scattergeo(
            lon=group["longitude"],
            lat=group["latitude"],
            text=group["port"],
            customdata=custom,
            mode="markers",
            marker={
                "size": 5,
                "color": palette.get(region, "#94a3b8"),
                "opacity": 0.76,
                "line": {"width": 0.25, "color": "#0b1220"},
            },
            name=f"Port location — {region}",
            hovertemplate=(
                "<b>%{text}</b><br>Country: %{customdata[1]}"
                "<br>Region: %{customdata[2]}<br>LOCODE: %{customdata[3]}"
                "<br>Coordinates: %{customdata[4]}, %{customdata[5]}"
                f"<br>Quality: {data_quality_for_mode()}<extra></extra>"
            ),
        )
    )

if not snapshot_congestion.empty:
    figure.add_trace(
        go.Scattergeo(
            lon=snapshot_congestion["longitude"],
            lat=snapshot_congestion["latitude"],
            text=snapshot_congestion["port"],
            customdata=snapshot_congestion[
                ["week_start", "avg_wait_days", "congestion_index", "region"]
            ].to_numpy(),
            mode="markers",
            marker={
                "size": 11,
                "symbol": "diamond",
                "color": snapshot_congestion["congestion_index"],
                "colorscale": "YlOrRd",
                "cmin": float(matched_congestion["congestion_index"].min()),
                "cmax": float(matched_congestion["congestion_index"].max()),
                "showscale": True,
                "colorbar": {
                    "title": {
                        "text": (
                            "Synthetic congestion index"
                            if is_demo_mode()
                            else "Congestion index<br>(as stored)"
                        ),
                        "font": {"color": "#d3deec"},
                    },
                    "tickfont": {"color": "#d3deec"},
                },
                "line": {"width": 0.8, "color": "#f8fafc"},
            },
            name=(
                "Synthetic congestion example"
                if is_demo_mode()
                else "Historical congestion observation"
            ),
            hovertemplate=(
                "<b>%{text}</b><br>Week: %{customdata[0]|%Y-%m-%d}"
                "<br>avg_wait_days: %{customdata[1]}"
                "<br>congestion_index: %{customdata[2]}"
                "<br>Congestion region: %{customdata[3]}"
                f"<br>Quality: {data_quality_for_mode()}<extra></extra>"
            ),
        )
    )

figure.update_layout(
    title=(
        "Synthetic port and congestion examples with illustrative connectors"
        if is_demo_mode()
        else "Port locations, selected-week congestion and matched routes"
    )
)
figure = add_base_map_layout(figure)
st.plotly_chart(figure, width="stretch", key="global_supply_chain_map")
st.caption(
    (
        "All locations and benchmark endpoints are synthetic; straight connectors "
        "are illustrative only and are not sea lanes or vessel tracks."
        if is_demo_mode()
        else "Solid lines are schematic straight endpoint connectors from archived "
        "benchmark records, not verified sea-lane geometry or vessel tracks. "
        "The port master has no observation date; only congestion diamonds correspond "
        "to the selected historical week. No route movement is inferred."
    )
)
source_quality_caption("ports")
source_quality_caption("port_congestion")
if show_routes:
    source_quality_caption("route_benchmark")

if show_routes and len(matched_routes) < len(
    benchmarks[benchmarks["mode"].astype(str).str.casefold() == "ocean"]
):
    unmapped = len(
        benchmarks[benchmarks["mode"].astype(str).str.casefold() == "ocean"]
    ) - len(matched_routes)
    warning = (
        f"{unmapped} of the "
        f"{'synthetic demo' if is_demo_mode() else 'archived'} Ocean benchmark rows were not drawn because "
        "both endpoints did not have unique exact-name matches in the port master. "
        + (
            "The coordinates in the demo data are fictional."
            if is_demo_mode()
            else "No fuzzy name/code joins or coordinates were invented."
        )
    )
    st.warning(warning)

st.markdown("### Synthetic port examples" if is_demo_mode() else "### Port details")
if visible_ports.empty:
    st.info("No ports match the selected geography filters.")
else:
    port_records = visible_ports.assign(_port_label=visible_ports.apply(
        lambda row: f"{row['port']} — {row['country']} [{row['port_id']}]",
        axis=1,
    ))
    selected_port_label = st.selectbox(
        "Select a port",
        port_records["_port_label"].tolist(),
        key="map_port_details",
    )
    selected_port = port_records[
        port_records["_port_label"] == selected_port_label
    ].iloc[0]
    detail_columns = st.columns(4)
    detail_columns[0].metric("Port", str(selected_port["port"]))
    detail_columns[1].metric("Country", str(selected_port["country"]))
    detail_columns[2].metric(
        "Coordinates",
        f"{selected_port['latitude']:.4f}, {selected_port['longitude']:.4f}",
    )
    detail_columns[3].metric(
        "LOCODE",
        "Not supplied" if pd.isna(selected_port["locode"]) else str(selected_port["locode"]),
    )
    observation_text = (
        "Synthetic coordinates and records; no real observation date."
        if is_demo_mode()
        else "Observation date: not supplied."
    )
    st.caption(
        f"Port ID: `{selected_port['port_id']}` · "
        f"Quality: `{data_quality_for_mode()}` · {observation_text}"
    )

    port_congestion_history = matched_congestion[
        matched_congestion["port_id"].astype(str) == str(selected_port["port_id"])
    ].sort_values("week_start")
    if port_congestion_history.empty:
        st.info(
            "No exact unique-name port-congestion join is available for this port; "
            "no coordinates or congestion values are substituted."
        )
    else:
        at_selected_week = port_congestion_history[
            port_congestion_history["week_start"] == pd.Timestamp(selected_week)
        ]
        if at_selected_week.empty:
            st.info("No congestion row exists for this port at the selected week.")
        else:
            record = at_selected_week.iloc[0]
            congestion_metrics = st.columns(4)
            congestion_metrics[0].metric(
                "Synthetic wait (days)" if is_demo_mode() else "Historical wait (days as named)",
                f"{record['avg_wait_days']:,.1f}",
            )
            congestion_metrics[1].metric(
                "Synthetic congestion index" if is_demo_mode() else "Congestion index (as stored)",
                f"{record['congestion_index']:,.2f}",
            )
            congestion_metrics[2].metric(
                "Vessels at anchor (as named)",
                f"{record['vessels_at_anchor']:,}",
            )
            congestion_metrics[3].metric(
                "Scenario week" if is_demo_mode() else "Historical week",
                record["week_start"].strftime("%Y-%m-%d"),
            )

        measure = st.selectbox(
            "Synthetic port series" if is_demo_mode() else "Historical port series",
            ["avg_wait_days", "congestion_index", "vessels_at_anchor", "berth_delay_hrs"],
            key="map_port_history_measure",
        )
        filtered_history = port_congestion_history[
            port_congestion_history["week_start"].between(
                pd.Timestamp(period_start), pd.Timestamp(period_end)
            )
        ]
        history_figure = px.line(
            filtered_history,
            x="week_start",
            y=measure,
            title=(
                f"{selected_port['port']} — {measure} (synthetic weekly demo)"
                if is_demo_mode()
                else f"{selected_port['port']} — {measure} (archived weekly values)"
            ),
            labels={
                "week_start": "Week",
                measure: (
                    f"{measure} (synthetic illustrative value)"
                    if is_demo_mode()
                    else f"{measure} (unit as named)"
                ),
            },
        )
        history_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b1220",
            plot_bgcolor="#0b1220",
            height=330,
        )
        st.plotly_chart(history_figure, width="stretch")
        st.caption(
            (
                f"Demo dataset: `port_congestion.csv` · Quality: `{data_quality_for_mode()}`."
                if is_demo_mode()
                else f"Congestion provenance: `archive (2).zip::port_congestion.csv` · "
                f"Quality: `{data_quality_for_mode()}`."
            )
        )

st.markdown("### Synthetic route examples" if is_demo_mode() else "### Matched route benchmarks")
if visible_routes.empty:
    st.info(
        "No synthetic route examples match the current port filters."
        if is_demo_mode()
        else "No Ocean benchmark corridors match the current port filters."
    )
else:
    route_columns = [
        "corridor_id",
        "origin",
        "destination",
        "benchmark_usd",
        "unit",
        "low_usd",
        "high_usd",
        "transit_min_days",
        "transit_max_days",
        "as_of",
        "coordinate_match",
        "data_quality",
    ]
    st.dataframe(
        visible_routes[route_columns].sort_values("benchmark_usd"),
        hide_index=True,
        width="stretch",
        column_config={
            "benchmark_usd": st.column_config.NumberColumn(
                "Synthetic benchmark USD" if is_demo_mode() else "Benchmark USD (as supplied)",
                format="%.2f",
            ),
            "low_usd": st.column_config.NumberColumn(
                "Synthetic low USD" if is_demo_mode() else "Low USD (as supplied)",
                format="%.2f",
            ),
            "high_usd": st.column_config.NumberColumn(
                "Synthetic high USD" if is_demo_mode() else "High USD (as supplied)",
                format="%.2f",
            ),
        },
    )
    route_export = add_provenance_for_export(
        visible_routes[route_columns], "route_benchmark"
    )
    st.download_button(
        "Download matched route records with provenance",
        data=route_export.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
        file_name="matched_ocean_route_benchmarks.csv",
        mime="text/csv",
    )
st.caption(
    (
        "Fictional demo endpoints are joined by exact port names. Connectors are "
        "illustrative straight lines, not routes, vessel tracks, or quotes."
        if is_demo_mode()
        else "Routes require an Ocean mode record and exact, unique origin/destination "
        "name matches to coordinate-bearing ports. Codes are not used to guess "
        "coordinates; the benchmark code system is undocumented and is not cross-validated. "
        "The line is only an endpoint connector, not an observed route path. "
        "Route endpoints and benchmark values remain "
        f"`{data_quality_for_mode()}`."
    )
)

if animate_congestion:
    st.markdown(
        "### Synthetic congestion playback"
        if is_demo_mode()
        else "### Historical congestion playback"
    )
    animation = visible_congestion.copy()
    animation["week_label"] = animation["week_start"].dt.strftime("%Y-%m-%d")
    if animation.empty:
        st.info(
            "No exact-name congestion/port joins exist in this selection."
            if is_demo_mode()
            else "No exact-name congestion/port coordinate matches exist in this "
            "selection, so no animation is available."
        )
    else:
        animation_figure = px.scatter_geo(
            animation,
            lat="latitude",
            lon="longitude",
            animation_frame="week_label",
            animation_group="port_id",
            color="congestion_index",
            color_continuous_scale="YlOrRd",
            range_color=[
                float(matched_congestion["congestion_index"].min()),
                float(matched_congestion["congestion_index"].max()),
            ],
            hover_name="port",
            hover_data={
                "week_label": True,
                "avg_wait_days": True,
                "congestion_index": True,
                "region": True,
                "port_id": True,
                "latitude": False,
                "longitude": False,
            },
            title=(
                "Synthetic weekly congestion playback — no vessel movement"
                if is_demo_mode()
                else "Weekly historical congestion playback — no vessel movement"
            ),
            projection="natural earth",
            category_orders={
                "week_label": sorted(animation["week_label"].unique())
            },
        )
        animation_figure.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b1220",
            height=560,
            geo={
                "projection": {"type": "natural earth"},
                "showland": True,
                "landcolor": "#1b2a3d",
                "showocean": True,
                "oceancolor": "#0d1a2a",
                "showcoastlines": True,
                "coastlinecolor": "#52657e",
                "bgcolor": "#0b1220",
            },
        )
        st.plotly_chart(animation_figure, width="stretch")
        st.caption(
            (
                "Animation frames are synthetic demo records. Markers represent "
                "illustrative locations, not moving vessels."
                if is_demo_mode()
                else "Animation frames are the actual archived weekly congestion records "
                "within the selected dates. Markers represent ports, not moving "
                "vessels; route movement is not animated because no route-time "
                "positions or trajectories are available."
            )
        )

"""Corporate control-tower map for ports, route benchmarks, and congestion."""

from __future__ import annotations

from datetime import date
import html
import hashlib
import re

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from scripts.app_ui import configure_page
from scripts.data_paths import data_quality_for_mode, get_data_mode, is_demo_mode
from scripts.global_supply_chain_map import (
    PORT_REGION_COLORS,
    filter_congestion_for_port,
    filter_routes_for_focus,
    highlighted_port_ids,
    match_congestion_to_ports,
    match_ocean_route_endpoints,
    port_id_from_map_click,
)
from scripts.stage5_intelligence import (
    add_provenance_for_export,
    load_stage5_dataset,
)


configure_page("Global Supply-Chain Map")

ALL_CONTINENTS = (
    "Africa",
    "Asia & Pacific",
    "Europe",
    "North America",
    "South America",
)
ALL_CONTINENTS_LABEL = "All continents"


def clear_dependent_map_filters() -> None:
    st.session_state["map_countries"] = []
    st.session_state["map_port_search"] = ""
    st.session_state["map_selected_port_id"] = None


def set_map_continent(continent: str) -> None:
    st.session_state["map_selected_continent"] = continent
    clear_dependent_map_filters()


def reset_map_selection() -> None:
    st.session_state["map_selected_continent"] = ALL_CONTINENTS_LABEL
    clear_dependent_map_filters()
    st.session_state["map_show_routes"] = True


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
regions = list(ALL_CONTINENTS) + sorted(
    set(ports["continent"].dropna().astype(str)) - set(ALL_CONTINENTS)
)
pending_continent = st.session_state.pop("map_pending_continent", None)
if pending_continent in regions:
    st.session_state["map_selected_continent"] = pending_continent
    st.session_state["map_countries"] = []
    st.session_state["map_port_search"] = ""
selected_continent = st.sidebar.radio(
    "Continent focus",
    [ALL_CONTINENTS_LABEL, *regions],
    key="map_selected_continent",
    on_change=clear_dependent_map_filters,
)
country_source_ports = (
    ports
    if selected_continent == ALL_CONTINENTS_LABEL
    else ports[ports["continent"].eq(selected_continent)]
)
countries = sorted(country_source_ports["country"].dropna().astype(str).unique())
stored_countries = st.session_state.get("map_countries", [])
valid_countries = [country for country in stored_countries if country in countries]
if valid_countries != stored_countries:
    st.session_state["map_countries"] = valid_countries
selected_countries = st.sidebar.multiselect(
    "Country",
    countries,
    key="map_countries",
)

port_search = st.sidebar.text_input(
    "Port name contains",
    help="Leave blank to include all ports in the selected region/countries.",
    key="map_port_search",
)
st.sidebar.button(
    "Reset map selection",
    on_click=reset_map_selection,
    key="map_reset_selection",
    use_container_width=True,
)

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

visible_ports = ports.copy()
if selected_countries:
    visible_ports = visible_ports[visible_ports["country"].isin(selected_countries)]
if port_search.strip():
    visible_ports = visible_ports[
        visible_ports["port"].astype(str).str.contains(
            re.escape(port_search.strip()), case=False, na=False
        )
    ]

selected_port_id = st.session_state.get("map_selected_port_id")
visible_port_ids = set(visible_ports["port_id"].dropna().astype(str))
if selected_port_id is not None and str(selected_port_id) not in visible_port_ids:
    selected_port_id = None
    st.session_state["map_selected_port_id"] = None

visible_congestion = matched_congestion[
    matched_congestion["week_start"].between(
        pd.Timestamp(period_start), pd.Timestamp(period_end)
    )
    & matched_congestion["port_id"].astype(str).isin(visible_port_ids)
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
if port_search.strip():
    search = re.escape(port_search.strip())
    visible_routes = visible_routes[
        visible_routes["origin"].str.contains(search, case=False, na=False)
        | visible_routes["destination"].str.contains(search, case=False, na=False)
    ]

selected_port_row = (
    visible_ports.loc[
        visible_ports["port_id"].astype(str).eq(str(selected_port_id))
    ].iloc[0]
    if selected_port_id is not None
    else None
)
focused_routes = filter_routes_for_focus(
    visible_routes,
    selected_continent=(
        None
        if selected_continent == ALL_CONTINENTS_LABEL
        else selected_continent
    ),
    selected_port_name=(
        str(selected_port_row["port"])
        if selected_port_row is not None
        else None
    ),
)

st.markdown("#### Interactive continent legend")
legend_labels = [ALL_CONTINENTS_LABEL, *regions]
for start in range(0, len(legend_labels), 3):
    legend_columns = st.columns(3)
    for column, label in zip(
        legend_columns, legend_labels[start : start + len(legend_columns)]
    ):
        column.button(
            label,
            key=f"map_legend_{label.casefold().replace(' ', '_').replace('&', 'and')}",
            type="primary" if label == selected_continent else "secondary",
            on_click=set_map_continent,
            args=(label,),
            use_container_width=True,
        )

if selected_port_row is not None:
    focus_label = (
        f"{selected_port_row['port']} — {selected_port_row['country']}"
    )
elif selected_continent != ALL_CONTINENTS_LABEL:
    focus_label = selected_continent
else:
    focus_label = "All ports"
st.caption(f"Map focus: {focus_label}. Click a port marker for details.")

focus_continent = (
    None
    if selected_continent == ALL_CONTINENTS_LABEL
    else selected_continent
)
focused_port_ids = highlighted_port_ids(
    visible_ports,
    selected_continent=focus_continent,
    selected_port_id=selected_port_id,
)
focused_congestion = snapshot_congestion[
    snapshot_congestion["port_id"].astype(str).isin(focused_port_ids)
]
metrics = st.columns(3)
metrics[0].metric("Ports highlighted", f"{len(focused_port_ids):,}")
metrics[1].metric(
    "Congestion points in focus",
    f"{focused_congestion['port'].nunique():,}",
    selected_week.strftime("%Y-%m-%d"),
)
metrics[2].metric(
    "Route examples" if is_demo_mode() else "Matched corridors",
    f"{len(focused_routes):,}" if show_routes else "Hidden",
)
st.caption(
    f"Synthetic benchmark scenario date: {benchmarks['as_of'].max():%Y-%m-%d}"
    if is_demo_mode()
    else f"Benchmark snapshot date: {benchmarks['as_of'].max():%Y-%m-%d}"
)
st.caption(
    f"{len(focused_routes):,} route rows with exact endpoint matches are in the "
    "current view."
)

map_ports = visible_ports.copy()
map_ports["latitude"] = pd.to_numeric(map_ports["latitude"], errors="coerce")
map_ports["longitude"] = pd.to_numeric(map_ports["longitude"], errors="coerce")
map_ports = map_ports[
    map_ports["latitude"].between(-90, 90)
    & map_ports["longitude"].between(-180, 180)
]
highlighted_ids = highlighted_port_ids(
    map_ports,
    selected_continent=focus_continent,
    selected_port_id=selected_port_id,
)
focus_active = focus_continent is not None or selected_port_id is not None
if selected_port_row is not None:
    map_title = f"Port focus — {selected_port_row['port']}"
elif focus_continent is not None:
    map_title = f"Port and route focus — {focus_continent}"
else:
    map_title = (
        "Synthetic ports and congestion"
        if is_demo_mode()
        else "Ports and selected-week congestion"
    )

st.markdown(f"#### {map_title}")
map_figure = folium.Map(
    location=[20, 0],
    zoom_start=2,
    tiles="OpenStreetMap",
    control_scale=True,
    prefer_canvas=True,
)
if show_routes:
    route_layer = folium.FeatureGroup(name="Endpoint connectors")
    for route in focused_routes.itertuples(index=False):
        route_label = html.escape(
            f"{route.corridor_id}: {route.origin} → {route.destination} | "
            f"{'Synthetic benchmark' if is_demo_mode() else 'Benchmark'}: "
            f"{route.benchmark_usd:,.2f} {route.unit} | "
            f"As of: {pd.Timestamp(route.as_of).date()} | "
            f"Quality: {route.data_quality}"
        )
        folium.PolyLine(
            locations=[
                [route.origin_latitude, route.origin_longitude],
                [route.destination_latitude, route.destination_longitude],
            ],
            color="#3d7c78",
            weight=1.5,
            opacity=0.58,
            tooltip=route_label,
        ).add_to(route_layer)
    route_layer.add_to(map_figure)

port_layer = folium.FeatureGroup(name="Ports")
for port in map_ports.itertuples(index=False):
    port_id = str(port.port_id)
    is_highlighted = port_id in highlighted_ids
    if selected_port_id is not None and is_highlighted:
        color, radius, opacity = "#1f7a83", 9, 1.0
    elif focus_active and is_highlighted:
        color, radius, opacity = "#2c6782", 7, 0.96
    elif focus_active:
        color, radius, opacity = "#aebac5", 4, 0.14
    else:
        color = PORT_REGION_COLORS.get(port.continent, "#8292a4")
        radius, opacity = 5, 0.82
    tooltip = html.escape(
        f"{port.port} — {port.country} ({port.continent}) [{port_id}]"
    )
    folium.CircleMarker(
        location=[port.latitude, port.longitude],
        radius=radius,
        color=color,
        weight=1,
        opacity=opacity,
        fill=True,
        fill_color=color,
        fill_opacity=opacity,
        tooltip=tooltip,
    ).add_to(port_layer)
port_layer.add_to(map_figure)

if not snapshot_congestion.empty:
    congestion_layer = folium.FeatureGroup(
        name=(
            f"Congestion — {selected_week:%Y-%m-%d}"
            if is_demo_mode()
            else f"Historical congestion — {selected_week:%Y-%m-%d}"
        )
    )
    for observation in snapshot_congestion.itertuples(index=False):
        port_id = str(observation.port_id)
        is_highlighted = port_id in highlighted_ids
        opacity = 0.96 if is_highlighted and focus_active else 0.8
        if focus_active and not is_highlighted:
            opacity = 0.12
        color = "#1f7a83" if selected_port_id == port_id else "#7399ad"
        tooltip_parts = [
            f"{observation.port} [{port_id}]",
            f"Week: {pd.Timestamp(observation.week_start):%Y-%m-%d}",
            f"Congestion index: {observation.congestion_index}",
            f"Average waiting days: {observation.avg_wait_days}",
        ]
        if pd.notna(observation.throughput_teu_mn):
            tooltip_parts.append(
                f"Throughput (TEU millions): {observation.throughput_teu_mn}"
            )
        if pd.notna(observation.vessels_at_anchor):
            tooltip_parts.append(
                f"Vessels at anchor: {observation.vessels_at_anchor}"
            )
        tooltip = html.escape(" | ".join(tooltip_parts))
        folium.CircleMarker(
            location=[observation.latitude, observation.longitude],
            radius=8 if selected_port_id == port_id else 6,
            color=color,
            weight=1,
            opacity=opacity,
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            tooltip=tooltip,
        ).add_to(congestion_layer)
    congestion_layer.add_to(map_figure)
folium.LayerControl(collapsed=True).add_to(map_figure)

selection_token = "|".join(
    [
        selected_continent,
        str(selected_port_id or ""),
        *selected_countries,
        port_search.strip(),
        str(period_start),
        str(period_end),
        str(selected_week),
    ]
)
chart_key = (
    "global_supply_chain_map_folium_"
    + hashlib.sha1(selection_token.encode("utf-8")).hexdigest()[:12]
)
map_event = st_folium(
    map_figure,
    key=chart_key,
    height=560,
    use_container_width=True,
    returned_objects=[
        "last_clicked",
        "last_object_clicked_tooltip",
        "zoom",
    ],
)
clicked_port_id = port_id_from_map_click(
    map_event.get("last_object_clicked_tooltip"),
    map_event.get("last_clicked"),
    map_event.get("zoom"),
    map_ports,
)
if clicked_port_id is not None and clicked_port_id != str(selected_port_id):
    clicked_port = visible_ports.loc[
        visible_ports["port_id"].astype(str).eq(clicked_port_id)
    ].iloc[0]
    st.session_state["map_selected_port_id"] = clicked_port_id
    if str(clicked_port["continent"]) != selected_continent:
        st.session_state["map_pending_continent"] = str(clicked_port["continent"])
    st.rerun()
st.caption(
    (
        "All locations and benchmark endpoints are synthetic; connectors are "
        "illustrative only and are not sea lanes or vessel tracks."
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
    port_labels = {
        str(row.port_id): f"{row.port} — {row.country} [{row.port_id}]"
        for row in visible_ports.itertuples(index=False)
    }
    port_options: list[str | None] = [None, *port_labels]
    port_selector_key = (
        f"map_port_details_{selected_port_id or 'all'}"
    )
    selected_port_choice = st.selectbox(
        "Select a port or click a map marker",
        port_options,
        index=(
            port_options.index(str(selected_port_id))
            if selected_port_id is not None
            else 0
        ),
        format_func=lambda value: (
            "All ports (no individual highlight)"
            if value is None
            else port_labels.get(str(value), str(value))
        ),
        key=port_selector_key,
    )
    if selected_port_choice != selected_port_id:
        st.session_state["map_selected_port_id"] = selected_port_choice
        if selected_port_choice is not None:
            chosen_port = visible_ports.loc[
                visible_ports["port_id"].astype(str).eq(str(selected_port_choice))
            ].iloc[0]
            st.session_state["map_selected_continent"] = str(
                chosen_port["continent"]
            )
        st.rerun()

    if selected_port_row is None:
        st.info("Select a port from the map or the port list to inspect its details.")
    else:
        selected_port = selected_port_row
        selected_port_history = filter_congestion_for_port(
            visible_congestion, str(selected_port["port_id"])
        ).sort_values("week_start")
        st.markdown(
            f"#### {selected_port['port']} — {selected_port['country']}"
        )
        st.caption(
            f"Continent: {selected_port['continent']} · "
            f"Port ID: `{selected_port['port_id']}` · "
            f"Quality: `{data_quality_for_mode()}`"
        )

        selected_observation = (
            selected_port_history.iloc[-1]
            if not selected_port_history.empty
            else None
        )
        detail_rows = [
            {"Field": "Port", "Value": str(selected_port["port"])},
            {"Field": "Country", "Value": str(selected_port["country"])},
            {"Field": "Continent", "Value": str(selected_port["continent"])},
        ]
        if "vessels_total" in selected_port and pd.notna(
            selected_port["vessels_total"]
        ):
            detail_rows.append(
                {
                    "Field": "Vessels total (as named)",
                    "Value": str(selected_port["vessels_total"]),
                }
            )
        if selected_observation is not None:
            field_labels = (
                ("congestion_index", "Congestion index (as stored)"),
                ("throughput_teu_mn", "Throughput (TEU mn, as named)"),
                ("vessels_at_anchor", "Vessels at anchor (as named)"),
                ("avg_wait_days", "Average wait (days, as named)"),
            )
            for field, label in field_labels:
                if field in selected_observation and pd.notna(
                    selected_observation[field]
                ):
                    detail_rows.append(
                        {
                            "Field": label,
                            "Value": str(selected_observation[field]),
                        }
                    )
            detail_rows.append(
                {
                    "Field": (
                        "Scenario week" if is_demo_mode() else "Historical week"
                    ),
                    "Value": selected_observation["week_start"].strftime(
                        "%Y-%m-%d"
                    ),
                }
            )
        else:
            st.info(
                "No congestion record is available for this port in the selected "
                "reporting period; no values are substituted."
            )
        st.dataframe(
            pd.DataFrame(detail_rows),
            hide_index=True,
            width="stretch",
        )
        observation_text = (
            "Synthetic coordinates and records; no real observation date."
            if is_demo_mode()
            else "Port master observation date: not supplied."
        )
        st.caption(observation_text)

        if selected_port_history.empty:
            st.info(
                "No exact unique-name congestion/port join is available for this "
                "port; no coordinates or congestion values are substituted."
            )
        else:
            measure_options = [
                measure
                for measure in (
                    "throughput_teu_mn",
                    "avg_wait_days",
                    "congestion_index",
                    "vessels_at_anchor",
                    "berth_delay_hrs",
                )
                if measure in selected_port_history
                and selected_port_history[measure].notna().any()
            ]
            measure = st.selectbox(
                "Synthetic port series" if is_demo_mode() else "Historical port series",
                measure_options,
                key="map_port_history_measure",
            )
            filtered_history = selected_port_history[
                selected_port_history["week_start"].between(
                    pd.Timestamp(period_start), pd.Timestamp(period_end)
                )
            ]
            if filtered_history.empty:
                st.info(
                    "No observations for this port fall in the selected reporting period."
                )
            else:
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
                    template="rane_corporate",
                    height=330,
                )
                st.plotly_chart(history_figure, width="stretch")
                st.caption(
                    (
                        f"Demo dataset: `port_congestion.csv` · "
                        f"Quality: `{data_quality_for_mode()}`."
                        if is_demo_mode()
                        else f"Congestion provenance: "
                        f"`archive (2).zip::port_congestion.csv` · "
                        f"Quality: `{data_quality_for_mode()}`."
                    )
                )

st.markdown("### Synthetic route examples" if is_demo_mode() else "### Matched route benchmarks")
if focused_routes.empty:
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
        focused_routes[route_columns].sort_values("benchmark_usd"),
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
        focused_routes[route_columns], "route_benchmark"
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
    animation = filter_congestion_for_port(
        visible_congestion, str(selected_port_id) if selected_port_id else None
    )
    if focus_continent is not None and selected_port_id is None:
        animation = animation[animation["continent"].eq(focus_continent)]
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
            color_continuous_scale="Blues",
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
            template="rane_corporate",
            height=560,
            geo={
                "projection": {"type": "natural earth"},
                "showland": True,
                "landcolor": "#e6edf2",
                "showocean": True,
                "oceancolor": "#f4f7fa",
                "showcoastlines": True,
                "coastlinecolor": "#a9b8c5",
                "showcountries": True,
                "countrycolor": "#c8d3dc",
                "bgcolor": "#f4f7fa",
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

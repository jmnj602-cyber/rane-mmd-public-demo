"""Historical logistics views for the recovered Stage 5 archives."""

from __future__ import annotations

from datetime import date
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.app_ui import configure_page
from scripts.data_paths import get_data_mode, is_demo_mode
from scripts.stage5_intelligence import (
    add_provenance_for_export,
    dataset_provenance,
    load_stage5_dataset,
)


configure_page("Logistics Intelligence")


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


def date_window(frame: pd.DataFrame, column: str, key: str) -> tuple[date, date] | None:
    start = frame[column].min().date()
    end = frame[column].max().date()
    selection = st.sidebar.date_input(
        "Synthetic date range" if is_demo_mode() else "Date range",
        value=(start, end),
        min_value=start,
        max_value=end,
        key=key,
    )
    if not isinstance(selection, (tuple, list)) or len(selection) != 2:
        st.info("Select both a start and end date.")
        return None
    return selection[0], selection[1]


def show_dataset_provenance(dataset_id: str) -> None:
    provenance = dataset_provenance(dataset_id)
    source_label = (
        "Synthetic illustrative data; no external publisher or URL."
        if is_demo_mode()
        else "Original publisher and URL were not included."
    )
    st.caption(
        f"Data record: `{provenance['archive_member']}` · "
        f"Quality: `{provenance['data_quality']}` · {source_label}"
    )


def download_csv(frame: pd.DataFrame, dataset_id: str, filename: str) -> None:
    if frame.empty:
        return
    export = add_provenance_for_export(frame, dataset_id)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", filename)
    st.download_button(
        "Download filtered records with provenance status",
        data=export.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"),
        file_name=f"{safe_name}.csv",
        mime="text/csv",
    )


st.title("Logistics Intelligence")
if is_demo_mode():
    st.info("All logistics values, locations, routes, and event records are synthetic illustrations.")
else:
    st.error(
        "The recovered files have archive-member provenance only. Original "
        "publishers, source URLs, and data-quality labels are absent. Results are "
        "exploratory historical archive views, not verified or live logistics conditions."
    )
    st.info(
        "No live congestion, shipping-rate, or disruption alerts are generated. "
        "Port master data has no observation date; shipping history ends in 2024."
    )

view = st.sidebar.radio(
    "Logistics view",
    [
        "Port congestion",
        "Shipping-rate trends",
        "Port geography",
        "Route benchmarks",
        "Synthetic event scenarios"
        if is_demo_mode()
        else "Historical logistics disruptions",
    ],
)

if view == "Port congestion":
    st.subheader(
        "Synthetic port-congestion examples"
        if is_demo_mode()
        else "Historical port congestion"
    )
    frame = read("port_congestion")
    selection = date_window(frame, "week_start", "logistics_congestion_range")
    if selection is None:
        st.stop()
    start, end = selection
    visible = frame[frame["week_start"].between(pd.Timestamp(start), pd.Timestamp(end))]
    regions = sorted(visible["region"].dropna().unique())
    region = st.selectbox("Region", ["All"] + regions, key="logistics_congestion_region")
    if region != "All":
        visible = visible[visible["region"] == region]
    ports = sorted(visible["port"].dropna().unique())
    port = st.selectbox("Port", ["All"] + ports, key="logistics_congestion_port")
    if port != "All":
        visible = visible[visible["port"] == port]
    measure = st.selectbox(
        "Synthetic measure" if is_demo_mode() else "Recorded measure",
        [
            "avg_wait_days",
            "congestion_index",
            "vessels_at_anchor",
            "port_utilization_pct",
            "berth_delay_hrs",
            "throughput_teu_mn",
        ],
        key="logistics_congestion_measure",
    )
    if visible.empty:
        st.warning("No congestion records match these filters.")
    else:
        st.metric(
            "Latest synthetic week" if is_demo_mode() else "Latest archived week in selection",
            visible["week_start"].max().date().isoformat(),
        )
        missing_measure = int(visible[measure].isna().sum())
        if missing_measure:
            st.warning(
                f"{missing_measure:,} selected rows have no value for `{measure}`."
            )
        fig = px.line(
            visible,
            x="week_start",
            y=measure,
            color="port" if port == "All" else None,
            title=(
                f"Synthetic {measure} by week"
                if is_demo_mode()
                else f"{measure} by week (as supplied)"
            ),
            labels={
                "week_start": "Week",
                measure: (
                    f"{measure} (synthetic illustrative value)"
                    if is_demo_mode()
                    else f"{measure} (unit definition unverified)"
                ),
            },
        )
        fig.update_layout(template="rane_corporate", height=420)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(visible, hide_index=True, width="stretch")
        download_csv(visible, "port_congestion", "port_congestion_filtered")
    show_dataset_provenance("port_congestion")
    st.caption(
        "Synthetic port metrics are illustrative and do not describe actual terminals."
        if is_demo_mode()
        else "`port_utilization_pct` is stored as values from 0.43 to 0.99; the archive "
        "does not define whether these are fractions or percentage points. "
        "`throughput_teu_mn` and other units are likewise unverified."
    )

elif view == "Shipping-rate trends":
    st.subheader("Synthetic shipping-rate examples" if is_demo_mode() else "Historical shipping-rate trends")
    frame = read("shipping_rates")
    selection = date_window(frame, "date", "logistics_shipping_range")
    if selection is None:
        st.stop()
    start, end = selection
    visible = frame[frame["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    measures = [
        "baltic_dry_index",
        "container_rate_usd_40ft",
        "air_cargo_rate_usd_kg",
        "bdi_mom_change_pct",
        "container_yoy_pct",
        "tanker_rate_aframax_usd_day",
        "bulk_carrier_handysize_usd_day",
        "supply_chain_pressure_index",
        "on_time_delivery_pct",
    ]
    measure = st.selectbox(
        "Synthetic series" if is_demo_mode() else "Series",
        measures,
        key="logistics_shipping_measure",
    )
    if visible.empty:
        st.warning("No shipping-rate records match this date range.")
    else:
        missing_measure = int(visible[measure].isna().sum())
        if missing_measure:
            st.warning(
                f"{missing_measure:,} selected months have no value for `{measure}`."
            )
        fig = px.line(
            visible,
            x="date",
            y=measure,
            title=f"Synthetic {measure}" if is_demo_mode() else f"{measure} (as supplied)",
            labels={
                "date": "Month",
                measure: (
                    f"{measure} (synthetic illustrative value)"
                    if is_demo_mode()
                    else f"{measure} (field-name units)"
                ),
            },
        )
        fig.update_layout(template="rane_corporate", height=420)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(visible, hide_index=True, width="stretch")
        download_csv(visible, "shipping_rates", "shipping_rates_filtered")
        last = visible.iloc[-1]
        st.metric(
            "Latest synthetic month" if is_demo_mode() else "Latest archived month",
            last["date"].strftime("%Y-%m"),
        )
    show_dataset_provenance("shipping_rates")
    st.caption(
        "All rates and percentages are synthetic examples; no carrier quote or service record is represented."
        if is_demo_mode()
        else "History ends 2024-12. Rate units are suggested by column names, but no "
        "publisher or data dictionary was included. `on_time_delivery_pct` is "
        "stored as a fraction (0.687–0.980); the app does not rescale it."
    )

elif view == "Port geography":
    st.subheader("Port geography")
    frame = read("ports")
    continents = sorted(frame["continent"].dropna().unique())
    selected_continents = st.multiselect(
        "Continents",
        continents,
        default=continents,
        key="logistics_ports_continent",
    )
    visible = frame[frame["continent"].isin(selected_continents)]
    countries = sorted(visible["country"].dropna().unique())
    selected_countries = st.multiselect(
        "Countries",
        countries,
        default=[],
        key="logistics_ports_country",
    )
    if selected_countries:
        visible = visible[visible["country"].isin(selected_countries)]
    if visible.empty:
        st.warning("No ports match these filters.")
    else:
        fig = px.scatter_geo(
            visible,
            lat="latitude",
            lon="longitude",
            color="continent",
            size="vessels_total",
            hover_name="port",
            hover_data={
                "country": True,
                "iso3": True,
                "locode": True,
                "vessels_total": True,
                "share_of_country_imports": True,
                "share_of_country_exports": True,
                "latitude": False,
                "longitude": False,
            },
            title=(
                "Synthetic illustrative port coordinates (not actual locations)"
                if is_demo_mode()
                else "Archived port coordinates and associated fields (not a live map)"
            ),
            projection="natural earth",
        )
        fig.update_layout(height=600, margin={"l": 0, "r": 0, "t": 55, "b": 0})
        st.plotly_chart(fig, width="stretch")
        st.metric("Ports shown", f"{len(visible):,}")
        st.dataframe(visible, hide_index=True, width="stretch")
        download_csv(visible, "ports", "ports_filtered")
    show_dataset_provenance("ports")
    st.warning(
        "Port names, coordinates, vessel counts, and trade-share fields are generated examples."
        if is_demo_mode()
        else "This master has no observation/as-of date. Coordinates and displayed "
        "vessel/import/export fields must not be interpreted as current. "
        "585 rows have no LOCODE."
    )

elif view == "Route benchmarks":
    st.subheader(
        "Synthetic route benchmark examples"
        if is_demo_mode()
        else "Route benchmark comparison"
    )
    frame = read("route_benchmark")
    as_of = frame["as_of"].max().date()
    st.metric(
        "Synthetic scenario date" if is_demo_mode() else "Snapshot date",
        as_of.isoformat(),
    )
    unit = st.selectbox(
        "Compare only within unit",
        sorted(frame["unit"].dropna().unique()),
        key="logistics_route_unit",
    )
    visible = frame[frame["unit"] == unit]
    modes = sorted(visible["mode"].dropna().unique())
    mode = st.selectbox("Transport mode", ["All"] + modes, key="logistics_route_mode")
    if mode != "All":
        visible = visible[visible["mode"] == mode]
    groups = sorted(visible["group"].dropna().unique())
    group = st.selectbox("Route group", ["All"] + groups, key="logistics_route_group")
    if group != "All":
        visible = visible[visible["group"] == group]
    visible = visible.sort_values("benchmark_usd")
    if visible.empty:
        st.warning("No route benchmarks match these filters.")
    else:
        st.dataframe(
            visible,
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
        download_csv(visible, "route_benchmark", "route_benchmarks_filtered")
    show_dataset_provenance("route_benchmark")
    st.caption(
        "Synthetic single-date examples; not a quote, route observation, or shipping-rate time series."
        if is_demo_mode()
        else "This is a single 2026-11-06 snapshot, not a shipping-rate time series. "
        "Comparisons are restricted to the exact selected `unit`; no conversion "
        "or route-level time trend is inferred. Benchmark methodology is absent."
    )

else:
    st.subheader("Synthetic illustrative logistics events" if is_demo_mode() else "Historical logistics disruption events")
    events = read("disruption_events")
    logistics_types = ["logistics", "labor", "geopolitical", "natural", "energy"]
    visible = events[events["disruption_type"].isin(logistics_types)].copy()
    selection = date_window(visible, "date", "logistics_events_range")
    if selection is None:
        st.stop()
    start, end = selection
    visible = visible[visible["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    types = sorted(visible["disruption_type"].dropna().unique())
    selected_types = st.multiselect(
        "Event types",
        types,
        default=types,
        key="logistics_event_types",
    )
    visible = visible[visible["disruption_type"].isin(selected_types)]
    if visible.empty:
        st.info(
            "No synthetic event examples match these filters."
            if is_demo_mode()
            else "No archived events match these filters."
        )
    else:
        timeline = px.scatter(
            visible,
            x="date",
            y="disruption_type",
            color="severity",
            hover_name="event_name",
            hover_data=["region_affected", "duration_days", "freight_rate_shock_pct"],
            title=(
                "Fictional dated event scenarios"
                if is_demo_mode()
                else "Selected dated event records (historical only)"
            ),
            labels={"date": "Event date", "disruption_type": "Recorded event type"},
        )
        timeline.update_layout(template="rane_corporate", height=390)
        st.plotly_chart(timeline, width="stretch")
        st.dataframe(visible, hide_index=True, width="stretch")
        download_csv(visible, "disruption_events", "logistics_events_filtered")
    show_dataset_provenance("disruption_events")
    st.caption(
        "Fictional scenarios only; no actual disruptions, impacts, or current alerts are represented."
        if is_demo_mode()
        else "Events are archived dated records, not current disruptions or live alerts. "
        "Original event sources and impact calculation methods were not included."
    )

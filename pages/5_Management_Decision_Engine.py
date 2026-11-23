"""Historical, explainable management screening across existing RANE datasets."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.app_ui import configure_page
from scripts.data_paths import get_data_mode, is_demo_mode
from scripts.decision_engine import (
    INDICATOR_COLUMNS,
    build_chokepoint_indicators,
    build_congestion_indicators,
    build_country_indicators,
    build_freshness_report,
    build_gscpi_indicator,
    build_material_indicators,
    build_shipping_rate_indicators,
    build_tariff_indicators,
    build_trade_flow_indicators,
    route_benchmark_context,
    summarize_material_latest,
)
from scripts.material_price_intelligence import (
    MATERIAL_LABELS,
    material_rows,
    load_integrated_data,
)
from scripts.scenario_dashboard import render_scenario_dashboard
from scripts.stage5_intelligence import (
    ARCHIVE_SOURCE_UNVERIFIED,
    GSCPI_SOURCE_URL,
    dataset_provenance,
    load_stage5_dataset,
)


configure_page("Management Decision Support")


@st.cache_data(show_spinner=False)
def load_market_history(mode: str) -> pd.DataFrame:
    return load_integrated_data(mode=mode)


@st.cache_data(show_spinner=False)
def load_stage5(dataset_id: str, mode: str) -> pd.DataFrame:
    return load_stage5_dataset(dataset_id, mode=mode)


def read_sources() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    try:
        mode = get_data_mode()
        integrated = load_market_history(mode)
    except FileNotFoundError:
        st.error(
            f"The integrated market dataset is unavailable in `{get_data_mode()}` "
            "mode. No fallback data is loaded."
        )
        st.stop()
    except ValueError as error:
        st.error(f"Integrated market data failed validation: {error}")
        st.stop()

    datasets: dict[str, pd.DataFrame] = {}
    for dataset_id in (
        "gscpi",
        "chokepoint_daily",
        "country_monthly",
        "trade_flows",
        "tariff_timeline",
        "port_congestion",
        "shipping_rates",
        "route_benchmark",
        "ports",
    ):
        try:
            datasets[dataset_id] = load_stage5(dataset_id, mode)
        except FileNotFoundError:
            st.error(
                f"Required dataset `{dataset_id}` is unavailable. "
                f"Provision it under the selected `{mode}` data root."
            )
            st.stop()
        except ValueError as error:
            st.error(f"Dataset `{dataset_id}` failed validation: {error}")
            st.stop()
    return integrated, datasets


def freshness_sources(
    integrated: pd.DataFrame, datasets: dict[str, pd.DataFrame]
) -> dict[str, dict[str, object]]:
    sources: dict[str, dict[str, object]] = {}
    for material in MATERIAL_LABELS:
        rows = material_rows(integrated, material)
        quality = (
            ", ".join(sorted(rows["data_quality"].dropna().astype(str).unique()))
            if not rows.empty
            else "NO_MARKET_PRICE_DATA"
        )
        source = (
            "; ".join(sorted(rows["source"].dropna().astype(str).unique()))
            if not rows.empty
            else "No price observations available"
        )
        urls = (
            rows["source_url"].dropna().astype(str).str.strip()
            if not rows.empty
            else pd.Series(dtype=str)
        )
        urls = urls[urls.ne("")]
        extraction_dates = (
            pd.to_datetime(rows["extraction_date"], errors="coerce").dropna()
            if not rows.empty
            else pd.Series(dtype="datetime64[ns]")
        )
        sources[f"Material market — {material}"] = {
            "frame": rows,
            "date_column": "date",
            "data_quality": quality,
            "source": source,
            "source_url": urls.iloc[-1] if not urls.empty else None,
            "extraction_date": (
                extraction_dates.max().date().isoformat()
                if not extraction_dates.empty
                else "Not recorded"
            ),
        }

    date_columns = {
        "gscpi": "month",
        "chokepoint_daily": "date",
        "country_monthly": "month",
        "trade_flows": "year",
        "tariff_timeline": "date",
        "port_congestion": "week_start",
        "shipping_rates": "date",
        "route_benchmark": "as_of",
        "ports": None,
    }
    for dataset_id, date_column in date_columns.items():
        frame = datasets[dataset_id]
        if dataset_id == "gscpi" and not is_demo_mode():
            quality = "OFFICIAL_SOURCE_MATCH_VERIFIED"
            source = "Federal Reserve Bank of New York"
            source_url = GSCPI_SOURCE_URL
        else:
            provenance = dataset_provenance(dataset_id)
            quality = provenance["data_quality"]
            source = f"{provenance['archive']}::{provenance['archive_member']}"
            source_url = None
        sources[dataset_id] = {
            "frame": frame,
            "date_column": date_column,
            "data_quality": quality,
            "source": source,
            "source_url": source_url,
            "extraction_date": (
                "Not recorded"
                if dataset_id != "gscpi"
                else (
                    "Synthetic scenario label"
                    if is_demo_mode()
                    else "Archived extraction date not supplied"
                )
            ),
        }
    return sources


def show_indicator_table(frame: pd.DataFrame, key: str) -> None:
    if frame.empty:
        st.info("No indicator rows are available for this selection.")
        return
    displayed = frame[INDICATOR_COLUMNS].copy()
    if is_demo_mode() and "indicator_group" in displayed.columns:
        displayed["indicator_group"] = displayed["indicator_group"].replace(
            {
                "Historical chokepoint": "Synthetic chokepoint example",
                "Historical port congestion": "Synthetic port example",
                "Historical shipping rate": "Synthetic shipping-rate example",
                "Historical tariff record": "Synthetic tariff scenario",
            }
        )
    displayed["observation_date"] = displayed["observation_date"].map(
        lambda value: (
            ""
            if pd.isna(value)
            else value.date().isoformat()
            if isinstance(value, pd.Timestamp)
            else value.isoformat()
            if isinstance(value, date)
            else str(value)
        )
    )
    st.dataframe(
        displayed,
        hide_index=True,
        width="stretch",
        key=key,
        column_config={
            "source_url": st.column_config.LinkColumn(
                "Source URL",
                display_text="Open source",
            ),
        },
    )


st.title("Management Decision Support")
if is_demo_mode():
    st.info(
        "All indicators are generated examples. Threshold screens demonstrate "
        "the interface only and must not guide business decisions."
    )
else:
    st.error(
        "Historical screening only—not a live alert or validated predictive model. "
        "The recovered Stage 5 archives are source-unverified except for the "
        "New York Fed GSCPI match. No RANE supplier, contract, purchase-order, "
        "inventory, production, or company-specific trade exposure records are supplied."
    )
    st.caption(
        "Rule-based indicators use observed records and explicit thresholds. "
        "Recommendations are cautious review prompts; no procurement decision or "
        "financial-savings estimate is automated."
    )

integrated, datasets = read_sources()
material_indicators = build_material_indicators(integrated)
gscpi_indicator = build_gscpi_indicator(datasets["gscpi"])
chokepoint_indicators = build_chokepoint_indicators(datasets["chokepoint_daily"])
country_indicators = build_country_indicators(datasets["country_monthly"])
congestion_indicators = build_congestion_indicators(datasets["port_congestion"])
shipping_indicators = build_shipping_rate_indicators(datasets["shipping_rates"])
trade_indicators = build_trade_flow_indicators(datasets["trade_flows"])
route_context = route_benchmark_context(datasets["route_benchmark"])
all_indicators = pd.concat(
    [
        material_indicators,
        gscpi_indicator,
        chokepoint_indicators,
        country_indicators,
        congestion_indicators,
        shipping_indicators,
        trade_indicators,
    ],
    ignore_index=True,
)
review_indicators = all_indicators[
    all_indicators["status"] == "Review threshold met"
].copy()

metric_columns = st.columns(3)
st.caption("Counts of indicators meeting a rule-based review threshold, by category.")
screen_groups = (
    ({"Material market"}, "Materials"),
    (
        {"Historical chokepoint", "Historical port congestion"},
        "Supply chain",
    ),
    (
        {
            "Historical shipping rate",
            "Country trade context",
            "Country-pair trade context",
        },
        "Trade & freight",
    ),
)
for column, (groups, title) in zip(metric_columns, screen_groups):
    count = int(
        review_indicators["indicator_group"].isin(groups).sum()
    )
    column.metric(title, f"{count:,}")

st.markdown(
    "### Synthetic threshold examples"
    if is_demo_mode()
    else "### Management attention candidates"
)
st.caption(
    "These fictional rows demonstrate configured rule behavior; they are not "
    "management alerts or operational recommendations."
    if is_demo_mode()
    else "Rows below meet an explicitly stated screening rule. They are historical "
    "review prompts, not confirmed disruptions, forecasts, or RANE exposures."
)
show_indicator_table(review_indicators, "management_review_indicators")

freshness = build_freshness_report(freshness_sources(integrated, datasets), date.today())
st.markdown(
    "### Synthetic data date coverage and quality"
    if is_demo_mode()
    else "### Data freshness and quality"
)
st.caption(
    "Dates are generated scenario labels, not freshness or data-validity measures."
    if is_demo_mode()
    else "Age is measured against today's date and describes the latest observation "
    "available in each file; it is not a live-feed or data-validity check."
)
st.dataframe(
    freshness,
    hide_index=True,
    width="stretch",
    column_config={
        "source_url": st.column_config.LinkColumn(
            "Source URL",
            display_text="Open source",
        ),
        "extraction_date": st.column_config.TextColumn("Extraction date"),
        "days_since_observation": st.column_config.NumberColumn(
            "Days since observation",
            format="%d",
        ),
    },
)

market_tab, supply_tab, trade_tab, tariff_tab, simulator_tab = st.tabs(
    [
        "Material markets",
        "Supply chain",
        "Trade and freight",
        "Tariff scenarios" if is_demo_mode() else "Tariff history",
        "Case-study simulator",
    ]
)

with market_tab:
    st.subheader("Material market movements")
    latest_materials = summarize_material_latest(integrated)
    st.dataframe(
        latest_materials,
        hide_index=True,
        width="stretch",
        column_config={
            "latest_value": st.column_config.NumberColumn(
                "Latest synthetic value" if is_demo_mode() else "Latest observed value",
                format="%.4f",
            ),
            "observation_date": st.column_config.DateColumn(
                "Scenario date" if is_demo_mode() else "Observation date"
            ),
        },
    )
    st.caption(
        (
            "Synthetic material values use illustrative currencies and units; "
            "they are not market prices."
            if is_demo_mode()
            else "Values retain their source currencies and units; unlike series are not "
            "ranked or combined. Phenolic Resin has no price observations."
        )
    )
    st.markdown(
        "#### Synthetic monthly movement examples"
        if is_demo_mode()
        else "#### Monthly movement screens"
    )
    st.caption(
        "All materials are listed, including movements below threshold and "
        "materials without an available comparison."
    )
    show_indicator_table(material_indicators, "all_material_indicators")
    selected_material = st.selectbox(
        "Inspect one material series",
        list(MATERIAL_LABELS),
        format_func=lambda value: MATERIAL_LABELS[value],
        key="decision_material",
    )
    material_history = material_rows(integrated, selected_material)
    if material_history.empty:
        st.warning(
            "No Phenolic Resin price series is available. No price is estimated "
            "or substituted from customs import unit values."
        )
    else:
        fig = px.line(
            material_history,
            x="date",
            y="value",
            title=(
                f"{MATERIAL_LABELS[selected_material]} — synthetic demo values"
                if is_demo_mode()
                else f"{MATERIAL_LABELS[selected_material]} — observed values only"
            ),
            labels={
                "date": "Observation date",
                "value": (
                    f"Value ({material_history.iloc[0]['currency']} / "
                    f"{material_history.iloc[0]['unit']})"
                ),
            },
            custom_data=["data_quality", "source_series"],
        )
        fig.update_traces(
            hovertemplate=(
                "Date: %{x|%Y-%m-%d}<br>Value: %{y:,.4f}"
                "<br>Quality: %{customdata[0]}"
                "<br>Source series: %{customdata[1]}<extra></extra>"
            )
        )
        fig.update_layout(template="rane_corporate", height=380)
        st.plotly_chart(fig, width="stretch")
        movement = material_indicators[
            material_indicators["indicator"].str.contains(
                MATERIAL_LABELS[selected_material], regex=False
            )
        ]
        show_indicator_table(movement, "selected_material_indicator")
        if selected_material in {"Steel HR", "Steel CR"} and not is_demo_mode():
            st.warning(
                "Steel observations and derived movement are approximate "
                "chart-digitized values, not exact raw prices."
            )
        if selected_material in {"Copper", "Nickel", "Aluminium"} and not is_demo_mode():
            st.warning(
                "Legacy source provenance is unverified; the plotted history "
                "is not validated as an authentic market-price series."
            )
        if selected_material == "Natural Rubber" and not is_demo_mode():
            st.info(
                "The historical source changes grade: Malaysia RSS1 before 2000, "
                "Singapore RSS1 during 2000–2003, and RSS3 from 2004."
            )

with supply_tab:
    st.subheader(
        "Synthetic supply-chain examples"
        if is_demo_mode()
        else "Supply-chain pressure and historical disruption"
    )
    gscpi = datasets["gscpi"].sort_values("month")
    latest_gscpi = gscpi.iloc[-1]
    pressure_cols = st.columns(3)
    pressure_cols[0].metric(
        "Latest synthetic index" if is_demo_mode() else "Latest verified GSCPI",
        f"{latest_gscpi['gscpi']:.4f}",
        latest_gscpi["month"].strftime("%Y-%m"),
    )
    pressure_cols[1].metric(
        "Chokepoints screened",
        f"{len(chokepoint_indicators):,}",
        "synthetic examples" if is_demo_mode() else "historical archive",
    )
    pressure_cols[2].metric(
        "Congestion ports screened",
        f"{len(congestion_indicators):,}",
        "synthetic examples" if is_demo_mode() else "historical archive",
    )
    pressure_figure = px.line(
        gscpi,
        x="month",
        y="gscpi",
        title=(
            "Synthetic pressure index illustration"
            if is_demo_mode()
            else "New York Fed Global Supply Chain Pressure Index (verified source match)"
        ),
        labels={"month": "Month", "gscpi": "Index"},
    )
    pressure_figure.update_layout(template="rane_corporate", height=350)
    st.plotly_chart(pressure_figure, width="stretch")
    show_indicator_table(gscpi_indicator, "gscpi_context")
    st.caption(
        "Synthetic illustration; not the official GSCPI."
        if is_demo_mode()
        else f"Verified source: {GSCPI_SOURCE_URL}"
    )

    st.markdown(
        "#### Synthetic chokepoint examples"
        if is_demo_mode()
        else "#### Historical chokepoint transit screens"
    )
    st.caption(
        (
            "Latest synthetic date is used. Baseline is the previous 28 calendar "
            "days excluding the latest day; at least 14 finite rows are required. "
            "Illustrative thresholds are high <= -25% and watch <= -10%."
            if is_demo_mode()
            else "Latest archive date is used. Baseline is the previous 28 calendar days "
            "excluding the latest day; at least 14 finite rows are required. "
            "Thresholds are high <= -25% and watch <= -10%."
        )
    )
    chokepoint_filter = st.checkbox(
        "Show only chokepoint review screens",
        value=True,
        key="decision_chokepoint_review_only",
    )
    visible_chokepoints = chokepoint_indicators
    if chokepoint_filter:
        visible_chokepoints = visible_chokepoints[
            visible_chokepoints["status"] == "Review threshold met"
        ]
    show_indicator_table(visible_chokepoints, "chokepoint_decision_indicators")

    st.markdown(
        "#### Synthetic port congestion examples"
        if is_demo_mode()
        else "#### Historical port congestion screens"
    )
    st.caption(
        (
            "Each fictional port's latest example index is compared with its own "
            "90th percentile; at least 52 weekly records are required. The index "
            "and threshold are illustrative, not operational."
            if is_demo_mode()
            else "Each port's latest archived congestion index is compared with its own "
            "historical 90th percentile; at least 52 weekly observations are required. "
            "The unit/definition is not documented and the dataset ends in 2024."
        )
    )
    show_indicator_table(congestion_indicators, "port_congestion_decision_indicators")

with trade_tab:
    st.subheader("Shipping rates and trade context")
    st.markdown("#### Month-over-month shipping-rate screens")
    show_indicator_table(shipping_indicators, "shipping_rate_decision_indicators")

    st.markdown("#### Synthetic route benchmark examples" if is_demo_mode() else "#### Route benchmark snapshot")
    benchmark_units = sorted(route_context["unit"].dropna().astype(str).unique())
    selected_unit = st.selectbox(
        "Benchmark unit (no cross-unit conversion)",
        benchmark_units,
        key="decision_route_unit",
    )
    selected_benchmarks = route_context[route_context["unit"] == selected_unit].copy()
    if not selected_benchmarks.empty:
        st.caption(
            (
                f"Synthetic scenario snapshot as of "
                f"{selected_benchmarks['as_of'].max():%Y-%m-%d}; not a carrier quote."
                if is_demo_mode()
                else f"Single archive snapshot as of "
                f"{selected_benchmarks['as_of'].max():%Y-%m-%d}; no trend or change "
                "is inferred from one observation."
            )
        )
        st.dataframe(
            selected_benchmarks[
                [
                    "corridor_id",
                    "mode",
                    "origin",
                    "destination",
                    "benchmark_usd",
                    "unit",
                    "low_usd",
                    "high_usd",
                    "as_of",
                    "data_quality",
                    "observation_note",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "benchmark_usd": st.column_config.NumberColumn(
                    "Synthetic benchmark USD"
                    if is_demo_mode()
                    else "Benchmark USD (as supplied)",
                    format="%.2f",
                ),
                "as_of": st.column_config.DateColumn(
                    "Scenario date" if is_demo_mode() else "Snapshot date"
                ),
            },
        )
        st.warning(
            "These fictional values are not carrier quotes or procurement guidance."
            if is_demo_mode()
            else f"Archive source is {ARCHIVE_SOURCE_UNVERIFIED}. Verify current "
            "carrier quotations and route applicability before any procurement decision."
        )

    st.markdown("#### Synthetic country-pair examples" if is_demo_mode() else "#### Country-pair trade context")
    trade_categories = ["All"] + sorted(
        datasets["trade_flows"]["trade_category"].dropna().astype(str).unique()
    )
    selected_category = st.selectbox(
        "Trade category",
        trade_categories,
        key="decision_trade_category",
    )
    visible_trade = trade_indicators
    if selected_category != "All":
        visible_trade = visible_trade[
            visible_trade["indicator"].str.contains(
                f"({selected_category})", regex=False
            )
        ]
    show_indicator_table(visible_trade, "trade_flow_decision_indicators")
    st.caption(
        "Fictional trade values and categories; no customs records or supplier "
        "relationships are represented."
        if is_demo_mode()
        else "The latest annual archive records end in 2024. `concentration_risk` "
        "scale/method and archive authenticity are unverified. These are not "
        "RANE-specific country, supplier, or goods exposures."
    )

    st.markdown(
        "#### Synthetic country trade-change examples"
        if is_demo_mode()
        else "#### Latest country-level trade-change context"
    )
    country_options = sorted(
        country_indicators["indicator"].dropna().astype(str).unique()
    )
    selected_country = st.selectbox(
        "Country indicator",
        country_options,
        key="decision_country_indicator",
    )
    country_row = country_indicators[
        country_indicators["indicator"] == selected_country
    ]
    show_indicator_table(country_row, "selected_country_trade_indicator")
    with st.expander("All latest country indicators"):
        show_indicator_table(country_indicators, "all_country_trade_indicators")
    st.caption(
        "Country records are fictional demo examples, not trade flows."
        if is_demo_mode()
        else "Country-level archive trade changes are not confirmed as RANE trade "
        "flows; source units and methodology are undocumented."
    )

with tariff_tab:
    st.subheader("Synthetic tariff scenario examples" if is_demo_mode() else "Historical tariff-event screening")
    tariffs = datasets["tariff_timeline"]
    target_options = ["All"] + sorted(
        tariffs["target_country"].dropna().astype(str).unique()
    )
    selected_target = st.selectbox(
        "Target country",
        target_options,
        key="decision_tariff_target",
    )
    category_keyword = st.text_input(
        "Trade category / material keyword",
        help=(
            (
                "Searches fictional scenario text only; it represents no law, product "
                "scope, or RANE exposure."
                if is_demo_mode()
                else "Searches only archived policy names and descriptions. A text match "
                "does not establish legal product scope or RANE exposure."
            )
        ),
        key="decision_tariff_keyword",
    )
    tariff_rows = build_tariff_indicators(
        tariffs,
        keyword=category_keyword,
        target_country=None if selected_target == "All" else selected_target,
    )
    show_indicator_table(tariff_rows, "tariff_history_indicators")
    st.warning(
        "Fictional policy scenarios only; no real law, tariff action, or legal "
        "applicability is represented."
        if is_demo_mode()
        else "These records are historical and archive-source-unverified. Keyword "
        "matches are text matches only; confirm current rules with official "
        "sources and legal/product classification. No RANE impact is inferred."
    )

with simulator_tab:
    render_scenario_dashboard(integrated, datasets["shipping_rates"])

"""Historical supply-chain risk views for the recovered Stage 5 archives."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.app_ui import configure_page
from scripts.data_paths import get_data_mode, is_demo_mode
from scripts.stage5_intelligence import (
    chokepoint_indicators,
    classify_trade_contraction,
    country_contraction_indicators,
    dataset_provenance,
    finite_measure_rows,
    load_stage5_dataset,
)


configure_page("Supply-Chain Risk")


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
    if is_demo_mode():
        source_text = "Synthetic illustrative data; there is no external source."
    else:
        if provenance["original_source_url"] == "Not supplied in the archive data":
            source_text = "Original publisher and URL were not included."
        else:
            source_text = (
                f"Matched publisher: {provenance['source_organization']} · "
                f"[Source file]({provenance['original_source_url']})"
            )
    st.caption(
        f"{'Data file' if is_demo_mode() else 'Archive member'}: "
        f"`{provenance['archive']}::{provenance['archive_member']}` · "
        f"Quality: `{provenance['data_quality']}` · "
        f"{source_text}"
    )


def filtered_dates(frame: pd.DataFrame, column: str, start: date, end: date) -> pd.DataFrame:
    return frame[frame[column].between(pd.Timestamp(start), pd.Timestamp(end))].copy()


st.title("Supply-chain Risk")
if is_demo_mode():
    st.info("All risk records are synthetic examples; no live alerts or source observations are included.")
else:
    st.error(
        "Only the GSCPI series was independently matched to an official source. "
        "The other recovered files have archive-member provenance only; their "
        "publishers, URLs, and source quality labels are absent. Their historical "
        "views and classifications are exploratory and source-unverified."
    )
    st.info(
        "Historical analysis only—not a live feed and not live disruption alerts. "
        "The latest source dates differ by dataset."
    )

view = st.sidebar.radio(
    "Risk view",
    [
        "Chokepoints",
        "Country indicators",
        "Global pressure",
        "Events and industry exposure",
        "Tariffs and trade flows",
    ],
)

if view == "Chokepoints":
    st.subheader("Chokepoint disruption monitoring")
    daily = read("chokepoint_daily")
    monthly = read("chokepoint_monthly")
    selection = date_window(daily, "date", "risk_chokepoint_range")
    if selection is None:
        st.stop()
    start, end = selection
    visible = filtered_dates(daily, "date", start, end)
    if visible.empty:
        st.warning("No daily records in the selected window.")
        st.stop()

    as_of = visible["date"].max()
    indicators = chokepoint_indicators(daily, as_of=as_of)
    st.markdown(
        "#### Synthetic decline examples"
        if is_demo_mode()
        else "#### Historical decline classification"
    )
    st.caption(
        (
            f"Illustrative classification uses the latest synthetic selected date "
            f"({as_of:%Y-%m-%d}); it is not a current status."
            if is_demo_mode()
            else f"Classification is calculated at the last available selected date "
            f"({as_of:%Y-%m-%d}), not as a current status."
        )
    )
    st.dataframe(
        indicators,
        hide_index=True,
        width="stretch",
        column_config={
            "latest_transits": st.column_config.NumberColumn("Latest daily transits"),
            "baseline_median_transits": st.column_config.NumberColumn(
                "Prior 28-calendar-day median", format="%.1f"
            ),
            "change_vs_baseline_pct": st.column_config.NumberColumn(
                "Change vs baseline (%)", format="%.1f%%"
            ),
        },
    )
    with st.expander("Classification calculation"):
        st.markdown(
            "- Baseline: median `transits` from the 28 calendar days before the "
            "selected as-of date; the as-of date is excluded.\n"
            "- At least 14 finite daily baseline rows and a baseline above zero "
            "are required.\n"
            "- Change (%) = `(latest transits / baseline median - 1) × 100`.\n"
            "- `High historical decline threshold`: change ≤ -25%; "
            "`Watch historical decline threshold`: -25% < change ≤ -10%; "
            "`No decline threshold triggered`: change > -10%.\n"
            "- These are project-defined screening thresholds, not source "
            "classifications, externally validated risk scores, or alerts."
        )
    show_dataset_provenance("chokepoint_daily")

    chokepoint = st.selectbox(
        "Chokepoint",
        sorted(visible["chokepoint"].dropna().unique()),
        key="risk_chokepoint_select",
    )
    series = visible[visible["chokepoint"] == chokepoint].sort_values("date")
    fig = px.line(
        series,
        x="date",
        y="transits",
        title=(
            f"{chokepoint} — daily transits (synthetic demo)"
            if is_demo_mode()
            else f"{chokepoint} — daily transits (archive records)"
        ),
        labels={"date": "Date", "transits": "Transits (count as named)"},
    )
    fig.update_layout(template="rane_corporate", height=380)
    st.plotly_chart(fig, width="stretch")
    monthly_series = monthly[
        (monthly["chokepoint"] == chokepoint)
        & monthly["month"].between(pd.Timestamp(start), pd.Timestamp(end))
    ]
    if not monthly_series.empty:
        monthly_fig = px.line(
            monthly_series,
            x="month",
            y="transits_per_day",
            title=(
                f"{chokepoint} — monthly average transits per day (synthetic demo)"
                if is_demo_mode()
                else f"{chokepoint} — monthly average transits per day (as supplied)"
            ),
            labels={"month": "Month", "transits_per_day": "Transits per day (as named)"},
        )
        monthly_fig.update_layout(template="rane_corporate", height=330)
        st.plotly_chart(monthly_fig, width="stretch")
        st.caption(
            "Monthly and daily values are generated examples."
            if is_demo_mode()
            else "Monthly source ends at 2026-10; daily source ends at 2026-11-15."
        )
    if monthly["transits_yoy_pct"].isna().any():
        st.warning(
            (
                f"The synthetic monthly examples contain "
                f"{int(monthly['transits_yoy_pct'].isna().sum()):,} missing "
                "`transits_yoy_pct` values; no values are filled."
                if is_demo_mode()
                else f"The monthly archive contains {int(monthly['transits_yoy_pct'].isna().sum()):,} "
                "missing `transits_yoy_pct` values; the charts and daily classification "
                "do not use that field."
            )
        )

elif view == "Country indicators":
    st.subheader("Country-level indicators")
    monthly = read("country_monthly")
    monthly["iso3"] = monthly["iso3"].astype(str)
    countries = monthly[monthly["iso3"].str.fullmatch(r"[A-Z]{3}", na=False)]
    if countries.empty:
        st.warning("No three-letter country-code records are available.")
        st.stop()
    options = (
        countries[["iso3", "country"]]
        .drop_duplicates()
        .sort_values("country")
    )
    selected_code = st.selectbox(
        "Country",
        options["iso3"].tolist(),
        format_func=lambda code: f"{options.loc[options['iso3'] == code, 'country'].iloc[0]} ({code})",
        key="risk_country_select",
    )
    selection = date_window(monthly, "month", "risk_country_range")
    if selection is None:
        st.stop()
    start, end = selection
    country_monthly = countries[
        (countries["iso3"] == selected_code)
        & countries["month"].between(pd.Timestamp(start), pd.Timestamp(end))
    ].sort_values("month")
    missing_trade_changes = int(country_monthly["trade_yoy_pct"].isna().sum())
    if missing_trade_changes:
        st.warning(
            f"{missing_trade_changes:,} selected monthly rows have no `trade_yoy_pct`; "
            "they are not classified."
        )
    latest = finite_measure_rows(country_monthly, "trade_yoy_pct")
    if not latest.empty:
        latest_row = latest.iloc[-1]
        classification = classify_trade_contraction(latest_row["trade_yoy_pct"])
        st.metric(
            "Latest trade change classification",
            classification,
            f"{latest_row['trade_yoy_pct']:.2f}% · {latest_row['month']:%Y-%m}",
        )
    else:
        st.warning("No finite trade_yoy_pct value is available for this selection.")
    st.caption(
        (
            "The synthetic `trade_yoy_pct` values are illustrative; no real trade "
            "units or country observations are represented."
            if is_demo_mode()
            else "Indicator uses the archive field `trade_yoy_pct` as recorded; trade "
            "value units and the source calculation are undocumented."
        )
    )
    with st.expander("Country contraction thresholds"):
        st.markdown(
            (
                "For the synthetic `trade_yoy_pct`: ≤ -25% is `High contraction "
                if is_demo_mode()
                else "For the supplied `trade_yoy_pct`: ≤ -25% is `High contraction "
            )
            + "threshold`; -25% to -10% is `Watch contraction threshold`; above "
            "-10% is `No contraction threshold triggered`. These simple "
            "screening thresholds are not source-provided or calibrated. "
            "Missing and non-finite values are not classified."
        )
    if not country_monthly.empty:
        trade_fig = px.line(
            country_monthly,
            x="month",
            y="trade_yoy_pct",
            title=(
                f"{selected_code} — synthetic monthly trade_yoy_pct"
                if is_demo_mode()
                else f"{selected_code} — supplied monthly trade_yoy_pct"
            ),
            labels={"month": "Month", "trade_yoy_pct": "Change (%) as named"},
        )
        trade_fig.update_layout(template="rane_corporate", height=340)
        st.plotly_chart(trade_fig, width="stretch")
    show_dataset_provenance("country_monthly")

    st.markdown(
        "#### Latest synthetic country examples"
        if is_demo_mode()
        else "#### Latest available country classifications"
    )
    classifications = country_contraction_indicators(monthly)
    st.dataframe(classifications, hide_index=True, width="stretch")
    st.caption(
        "The synthetic aggregate uses a non-ISO code and is excluded from country-level examples."
        if is_demo_mode()
        else "Aggregate codes are excluded by retaining only three-letter uppercase "
        "codes. The archive uses numeric codes for aggregate entities."
    )

    daily = read("country_daily")
    daily = daily[~daily["is_aggregate"].fillna(True)].copy()
    daily = daily[daily["iso3"].astype(str).str.fullmatch(r"[A-Z]{3}", na=False)]
    daily_for_country = daily[daily["iso3"] == selected_code]
    if not daily_for_country.empty:
        daily_selection = date_window(
            daily_for_country, "date", "risk_country_daily_range"
        )
        if daily_selection is not None:
            daily_start, daily_end = daily_selection
            daily_for_country = filtered_dates(
                daily_for_country, "date", daily_start, daily_end
            )
            metric = st.selectbox(
                "Daily country measure",
                ["portcalls", "shipment", "import", "export", "shipment_30ma_yoy"],
                key="risk_country_daily_metric",
            )
            plotted = finite_measure_rows(daily_for_country, metric)
            invalid_count = len(daily_for_country) - len(plotted)
            if plotted.empty:
                st.warning("No finite daily values for this measure and date window.")
            else:
                if invalid_count:
                    st.warning(
                        f"{invalid_count:,} missing or non-finite rows were excluded "
                        "from the selected measure."
                    )
                daily_fig = px.line(
                    plotted,
                    x="date",
                    y=metric,
                    title=(
                        f"{selected_code} — synthetic daily {metric}"
                        if is_demo_mode()
                        else f"{selected_code} — daily {metric} (unit not documented)"
                    ),
                    labels={
                        metric: (
                            "Synthetic illustrative value"
                            if is_demo_mode()
                            else "Archive value (unit unspecified)"
                        ),
                        "date": "Date",
                    },
                )
                daily_fig.update_layout(template="rane_corporate", height=330)
                st.plotly_chart(daily_fig, width="stretch")
        show_dataset_provenance("country_daily")
        st.caption(
            "The Parquet values are synthetic illustrative records."
            if is_demo_mode()
            else "Source rows in the Parquet file remain unchanged."
        )

elif view == "Global pressure":
    st.subheader("Global supply-chain pressure")
    frame = read("gscpi")
    selection = date_window(frame, "month", "risk_gscpi_range")
    if selection is None:
        st.stop()
    start, end = selection
    visible = filtered_dates(frame, "month", start, end)
    fig = px.line(
        visible,
        x="month",
        y="gscpi",
        title=(
            "Synthetic global supply-chain pressure index illustration"
            if is_demo_mode()
            else "GSCPI archive series (index values as supplied)"
        ),
        labels={"month": "Month", "gscpi": "Index value as stored"},
    )
    fig.update_layout(template="rane_corporate", height=400)
    st.plotly_chart(fig, width="stretch")
    if not visible.empty:
        last = visible.iloc[-1]
        st.metric(
            "Latest synthetic index value" if is_demo_mode() else "Latest archived value",
            f"{last['gscpi']:.4f}",
            last["month"].strftime("%Y-%m"),
        )
    show_dataset_provenance("gscpi")
    st.caption(
        "Synthetic values are not the official New York Fed GSCPI."
        if is_demo_mode()
        else "All 346 monthly values were matched to the New York Fed GSCPI workbook "
        "after normalizing dates to calendar months; maximum absolute value "
        "difference was below 1e-10. No risk class or live pressure alert is "
        "inferred from the index."
    )

elif view == "Events and industry exposure":
    section = st.sidebar.radio(
        "Synthetic examples" if is_demo_mode() else "Historical data",
        ["Disruption events", "Industry exposure"],
        key="risk_event_section",
    )
    if section == "Disruption events":
        st.subheader("Synthetic illustrative disruption events" if is_demo_mode() else "Historical disruption events")
        events = read("disruption_events")
        selection = date_window(events, "date", "risk_events_range")
        if selection is None:
            st.stop()
        start, end = selection
        visible = filtered_dates(events, "date", start, end)
        types = sorted(visible["disruption_type"].dropna().unique())
        chosen_types = st.multiselect(
            "Disruption type",
            types,
            default=types,
            key="risk_event_types",
        )
        visible = visible[visible["disruption_type"].isin(chosen_types)]
        severity = st.multiselect(
            "Recorded severity",
            sorted(visible["severity"].dropna().unique()),
            key="risk_event_severity",
        )
        if severity:
            visible = visible[visible["severity"].isin(severity)]
        st.dataframe(visible, hide_index=True, width="stretch")
        show_dataset_provenance("disruption_events")
        st.caption(
            "These are fictional illustrative scenarios, not actual or current events."
            if is_demo_mode()
            else "These are dated historical rows from the archive, not current alerts. "
            "Event selection and impact calculations are not independently sourced."
        )
    else:
        st.subheader("Synthetic illustrative industry exposure" if is_demo_mode() else "Industry exposure history")
        exposure = read("industry_exposure")
        industry = st.selectbox(
            "Industry",
            sorted(exposure["industry"].dropna().unique()),
            key="risk_industry_select",
        )
        measures = [
            "pandemic_exposure",
            "geopolitical_exposure",
            "natural_disaster_exposure",
            "tariff_exposure",
            "logistics_exposure",
            "energy_exposure",
            "labor_exposure",
            "cyber_exposure",
            "overall_vulnerability",
        ]
        measure = st.selectbox(
            "Recorded measure",
            measures,
            key="risk_industry_measure",
        )
        visible = exposure[exposure["industry"] == industry].sort_values("year")
        fig = px.line(
            visible,
            x="year",
            y=measure,
            title=f"{industry} — {measure} as stored",
            labels={"year": "Year", measure: "Value (scale not documented)"},
        )
        fig.update_layout(template="rane_corporate", height=380)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(visible, hide_index=True, width="stretch")
        show_dataset_provenance("industry_exposure")
        st.caption(
            "All indicators are generated for illustration; they do not represent "
            "actual industries, suppliers, or company operations."
            if is_demo_mode()
            else "The exposure/vulnerability scales and calculation are not documented. "
            "No new industry risk score is calculated."
        )

else:
    section = st.sidebar.radio(
        "Synthetic trade examples" if is_demo_mode() else "Country trade context",
        ["Tariff timeline", "Trade flows"],
        key="risk_trade_section",
    )
    if section == "Tariff timeline":
        st.subheader("Synthetic illustrative tariff scenarios" if is_demo_mode() else "Historical tariff timeline")
        tariffs = read("tariff_timeline")
        selection = date_window(tariffs, "date", "risk_tariff_range")
        if selection is None:
            st.stop()
        start, end = selection
        visible = filtered_dates(tariffs, "date", start, end)
        targets = sorted(visible["target_country"].dropna().unique())
        target = st.selectbox("Target", ["All"] + targets, key="risk_tariff_target")
        if target != "All":
            visible = visible[visible["target_country"] == target]
        st.dataframe(visible, hide_index=True, width="stretch")
        show_dataset_provenance("tariff_timeline")
        st.caption(
            "Fictional policy examples only; they do not describe actual laws or tariff actions."
            if is_demo_mode()
            else "Historical archive records only; no current tariff status is implied."
        )
    else:
        st.subheader("Synthetic illustrative trade flows" if is_demo_mode() else "Historical trade flows")
        flows = read("trade_flows")
        exporters = sorted(flows["exporter"].dropna().unique())
        exporter = st.selectbox("Exporter", exporters, key="risk_flow_exporter")
        selected = flows[flows["exporter"] == exporter]
        importers = sorted(selected["importer"].dropna().unique())
        importer = st.selectbox("Importer", importers, key="risk_flow_importer")
        selected = selected[selected["importer"] == importer].sort_values("year")
        fig = px.line(
            selected,
            x="year",
            y="trade_value_bn_usd",
            color="trade_category",
            title=f"{exporter} → {importer}: trade_value_bn_usd as supplied",
            labels={"year": "Year", "trade_value_bn_usd": "USD billions (field name)"},
        )
        fig.update_layout(template="rane_corporate", height=380)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(selected, hide_index=True, width="stretch")
        show_dataset_provenance("trade_flows")
        st.caption(
            "Values use synthetic demo country pairs and are not trade statistics."
            if is_demo_mode()
            else "Trade-value units are suggested by the field name but were not "
            "documented by a source or data dictionary."
        )

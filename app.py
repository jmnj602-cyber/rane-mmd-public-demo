"""Streamlit entry point for RANE Material Price Intelligence."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.app_ui import configure_page
from scripts.data_paths import get_data_mode, is_demo_mode
from scripts.material_price_intelligence import (
    MATERIAL_LABELS,
    annual_comparisons,
    filter_date_range,
    load_integrated_data,
    material_rows,
    missing_months,
    monthly_comparisons,
    observation_frequency,
    source_extraction_date,
)


configure_page("Material Price Intelligence", "📊")


@st.cache_data(show_spinner="Loading integrated market history...")
def load_data(mode: str) -> pd.DataFrame:
    return load_integrated_data(mode=mode)


def format_value(value: object, currency: str) -> str:
    if pd.isna(value):
        return "Not available"
    return f"{currency} {float(value):,.4f}"


def filtered_monthly_table(
    comparisons: pd.DataFrame, start: date, end: date
) -> pd.DataFrame:
    if comparisons.empty:
        return comparisons
    dates = pd.to_datetime(comparisons["observation_date"])
    return comparisons[
        dates.between(pd.Timestamp(start), pd.Timestamp(end), inclusive="both")
    ].copy()


st.title("Material Price Intelligence")
if is_demo_mode():
    st.caption("Synthetic illustrative series for demonstrating dashboard interactions.")
else:
    st.caption(
        "Historical source observations for management review. This is a static "
        "source snapshot, not a live market feed."
    )

try:
    integrated = load_data(get_data_mode())
except FileNotFoundError:
    st.error(
        f"The integrated market dataset is unavailable in `{get_data_mode()} "
        "mode`. Provision the selected data files; no fallback data is loaded."
    )
    st.stop()
except ValueError as error:
    st.error(f"Integrated market data failed validation: {error}")
    st.stop()

material = st.sidebar.selectbox(
    "Material",
    list(MATERIAL_LABELS),
    format_func=lambda key: MATERIAL_LABELS[key],
)
all_rows = material_rows(integrated, material)

if all_rows.empty:
    st.warning(
        "**No historical price series is available for Phenolic Resin.** "
        "No prices are estimated or substituted. Business Analytiq historical "
        "access is paid; UN Comtrade trade values/unit values are not market prices."
    )
    st.markdown(
        "Sources assessed: [Business Analytiq price index]"
        "(https://businessanalytiq.com/procurementanalytics/index/phenolic-resin-price-index/) · "
        "[UN Comtrade API (trade data, not a market-price series)]"
        "(https://comtradeapi.un.org/public/v1/preview/C/A/HS)"
    )
    st.caption(
        "A traceable source, resin grade, region, currency, unit, and observation "
        "date are required before a historical series can be added."
    )
    st.stop()

all_rows["date"] = pd.to_datetime(all_rows["date"])
data_start = all_rows["date"].min().date()
data_end = all_rows["date"].max().date()
date_range = st.sidebar.date_input(
    "Demo date range" if is_demo_mode() else "Observation date range",
    value=(data_start, data_end),
    min_value=data_start,
    max_value=data_end,
    key=f"date_range_{material}",
    help=(
        "Filters generated demo values. Missing dates are never filled."
        if is_demo_mode()
        else "Filters actual source observations. Missing dates are never filled."
    ),
)
if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
    st.info("Choose both a start and end date to filter the observations.")
    st.stop()

start_date, end_date = date_range
filtered = filter_date_range(all_rows, start_date, end_date)
frequency = observation_frequency(material)
quality_values = sorted(all_rows["data_quality"].dropna().unique())
currency_values = sorted(all_rows["currency"].dropna().astype(str).unique())
unit_values = sorted(all_rows["unit"].dropna().astype(str).unique())
source_values = sorted(all_rows["source"].dropna().astype(str).unique())
source_url_values = sorted(
    value
    for value in all_rows["source_url"].dropna().astype(str).unique()
    if value.strip()
)

st.subheader(MATERIAL_LABELS[material])
meta = st.columns(4)
meta[0].metric(
    "Synthetic records" if is_demo_mode() else "Available observations",
    f"{len(all_rows):,}",
)
meta[1].metric(
    "Illustrative date span" if is_demo_mode() else "Available coverage",
    f"{data_start:%Y-%m-%d} → {data_end:%Y-%m-%d}",
)
meta[2].metric("Illustrative frequency" if is_demo_mode() else "Source frequency", frequency)
meta[3].metric(
    "Demo generation date" if is_demo_mode() else "Source extraction date",
    source_extraction_date(all_rows),
)
st.caption(
    f"Currency: **{', '.join(currency_values)}** · "
    f"Source unit: **{', '.join(unit_values)}**"
)

if is_demo_mode():
    st.info("Every plotted value is synthetic and has no external market source.")
elif "LEGACY_SOURCE_PROVENANCE_UNVERIFIED" in quality_values:
    st.error(
        "Legacy Copper/Nickel/Aluminium provenance is unverified. The source "
        "vendor, grade, methodology, and original URL were not supplied; these "
        "values are preserved for continuity, not validated as authentic market prices."
    )
elif "APPROXIMATE_CHART_VALUE" in quality_values:
    st.warning(
        "These steel observations are approximate readings digitized from a "
        "published chart and rounded to Rs 100/tonne. They are not exact raw prices; "
        "any comparison derived from them is approximate too."
    )
if material == "Natural Rubber" and not is_demo_mode():
    st.warning(
        "The World Bank historical series changes grade: Malaysia RSS1 before "
        "2000, Singapore RSS1 during 2000–2003, and RSS3 from 2004. The full "
        "history is not one unchanged RSS3 grade."
    )

if not filtered.empty:
    latest = all_rows.iloc[-1]
    latest_filtered = filtered.iloc[-1]
    latest_cols = st.columns(4)
    latest_cols[0].metric(
        "Latest demo record" if is_demo_mode() else "Latest available observation",
        format_value(latest["value"], str(latest["currency"])),
        str(latest["date"].date()),
    )
    latest_cols[1].metric(
        "Latest in selected range (demo)" if is_demo_mode() else "Latest in selected range",
        format_value(latest_filtered["value"], str(latest_filtered["currency"])),
        str(latest_filtered["date"].date()),
    )
    latest_cols[2].metric("Selected observations", f"{len(filtered):,}")
    latest_cols[3].metric(
        "Selected range",
        f"{filtered.iloc[0]['date']:%Y-%m-%d} → "
        f"{filtered.iloc[-1]['date']:%Y-%m-%d}",
    )
else:
    st.warning(
        "No synthetic records fall within the selected date range."
        if is_demo_mode()
        else "No observations fall within the selected date range."
    )

quality_text = ", ".join(quality_values)
if not filtered.empty:
    chart_title = MATERIAL_LABELS[material]
    if is_demo_mode():
        chart_title += " — synthetic illustrative data"
    if "APPROXIMATE_CHART_VALUE" in quality_values:
        chart_title += " — approximate chart-derived observations"
    elif "LEGACY_SOURCE_PROVENANCE_UNVERIFIED" in quality_values:
        chart_title += " — legacy provenance unverified"
    figure = px.line(
        filtered,
        x="date",
        y="value",
        markers=frequency == "Monthly",
        custom_data=["data_quality", "source_series"],
        title=chart_title,
        labels={"date": "Observation date", "value": f"Value ({currency_values[0]})"},
    )
    figure.update_traces(
        hovertemplate=(
            "Date: %{x|%Y-%m-%d}<br>"
            "Value: %{y:,.4f}<br>"
            "Quality: %{customdata[0]}<br>"
            "Source series: %{customdata[1]}<extra></extra>"
        )
    )
    figure.update_layout(
        template="plotly_white",
        height=430,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        yaxis_title=f"Value ({currency_values[0]})",
        xaxis_title="Observation date",
    )
    st.plotly_chart(figure, width="stretch")
    st.caption(
        (
            "The chart plots only generated demo values. "
            "No conversion or interpolation is applied."
            if is_demo_mode()
            else "The chart plots only observations in the integrated dataset. "
            "No interpolation, currency conversion, or unit conversion is applied."
        )
    )

    gaps = missing_months(filtered)
    if gaps:
        st.warning(
            (
                "Missing generated calendar months within the selected span: "
                if is_demo_mode()
                else "Missing monthly source observations within the selected observed span: "
            )
            + f"{', '.join(gaps)}. No values were filled."
        )
    elif material in {"Steel HR", "Steel CR", "Natural Rubber"}:
        st.success(
            "No calendar months are missing from the generated demo series."
            if is_demo_mode()
            else "No missing calendar months were detected within the selected observed span."
        )
    else:
        st.info(
            (
                "Synthetic daily records use a generated business-day calendar."
                if is_demo_mode()
                else "Daily legacy rows are source observations, not a complete calendar. "
                "Because their trading calendar and vendor are unknown, absent dates "
                "cannot reliably be classified as missing market sessions."
            )
        )

monthly_all = monthly_comparisons(all_rows)
monthly_selected = filtered_monthly_table(monthly_all, start_date, end_date)

with st.expander("Monthly comparisons", expanded=True):
    st.caption(
        (
            "One generated value per calendar month. Daily demo series use the "
            "last generated value in the month. Comparisons do not fill gaps."
            if is_demo_mode()
            else "One observed value per calendar month. Daily series use the last actual "
            "source observation in that month; monthly series use the source value. "
            "MoM compares the immediately prior calendar month; YoY compares the same "
            "month in the prior year. Missing periods are not bridged."
        )
    )
    if monthly_selected.empty:
        st.info(
            "No monthly demo values are available for this date selection."
            if is_demo_mode()
            else "No monthly observations are available for this date selection."
        )
    else:
        st.dataframe(
            monthly_selected,
            hide_index=True,
            width="stretch",
            column_config={
                "value": st.column_config.NumberColumn(
                    "Synthetic value" if is_demo_mode() else "Observed value",
                    format="%.4f",
                ),
                "change_vs_previous_month": st.column_config.NumberColumn(
                    "Change vs prior month", format="%.4f"
                ),
                "pct_change_vs_previous_month": st.column_config.NumberColumn(
                    "MoM change (%)", format="%.2f%%"
                ),
                "change_vs_prior_year": st.column_config.NumberColumn(
                    "Change vs same month prior year", format="%.4f"
                ),
                "pct_change_vs_prior_year": st.column_config.NumberColumn(
                    "YoY change (%)", format="%.2f%%"
                ),
            },
        )

    st.markdown("#### Yearly synthetic comparison" if is_demo_mode() else "#### Yearly comparison")
    st.caption(
        (
            "Annual averages are averages of generated monthly snapshots, not daily averages. "
            if is_demo_mode()
            else "Annual averages are averages of monthly snapshots, not daily averages. "
        )
        + "Year-over-year comparison uses only calendar months present in both years; "
        "partial years are compared on their overlapping months."
    )
    yearly = annual_comparisons(monthly_all)
    selected_years = set(pd.to_datetime(monthly_selected["observation_date"]).dt.year) if not monthly_selected.empty else set()
    yearly = yearly[yearly["year"].isin(selected_years)]
    if yearly.empty:
        st.info("Yearly comparisons are unavailable for this date selection.")
    else:
        st.dataframe(
            yearly,
            hide_index=True,
            width="stretch",
            column_config={
                "observed_months": st.column_config.NumberColumn(
                    "Synthetic months" if is_demo_mode() else "Observed months",
                    format="%d",
                ),
                "average_of_observed_months": st.column_config.NumberColumn(
                    "Average of demo months" if is_demo_mode() else "Average of observed months",
                    format="%.4f",
                ),
                "prior_year_comparable_average": st.column_config.NumberColumn(
                    "Prior-year comparable average", format="%.4f"
                ),
                "change_vs_prior_year": st.column_config.NumberColumn(
                    "Change vs prior year", format="%.4f"
                ),
                "pct_change_vs_prior_year": st.column_config.NumberColumn(
                    "YoY change (%)", format="%.2f%%"
                ),
            },
        )

st.markdown("#### Source and quality")
source_cols = st.columns(2)
with source_cols[0]:
    st.write("**Source organisation**")
    st.write(", ".join(source_values))
    st.write("**Original source URL**")
    if source_url_values:
        for source_url in source_url_values:
            st.link_button("Open published source", source_url)
    elif is_demo_mode():
        st.write("None; the demo data are synthetic.")
    else:
        st.write("Not supplied with the legacy dataset.")
with source_cols[1]:
    st.write("**Data-quality classification**")
    st.code(quality_text)
    notes = sorted(all_rows["source_note"].dropna().astype(str).unique())
    for note in notes:
        st.caption(note)

st.markdown("#### Download filtered observations")
if filtered.empty:
    st.button("Download filtered observations CSV", disabled=True)
else:
    safe_name = re.sub(r"[^a-z0-9]+", "_", material.lower()).strip("_")
    filtered_csv = filtered.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")
    st.download_button(
        "Download filtered observations CSV",
        data=filtered_csv,
        file_name=f"{safe_name}_{start_date}_{end_date}.csv",
        mime="text/csv",
    )
    if not monthly_selected.empty:
        monthly_csv = monthly_selected.to_csv(
            index=False, date_format="%Y-%m-%d"
        ).encode("utf-8")
        st.download_button(
            "Download monthly comparison CSV",
            data=monthly_csv,
            file_name=f"{safe_name}_monthly_comparison_{start_date}_{end_date}.csv",
            mime="text/csv",
        )

st.divider()
st.caption(
    "Synthetic illustrative values only; not market observations or procurement quotations."
    if is_demo_mode()
    else "Historical snapshot only; not a live feed or procurement quotation. "
    "Values retain their source currency, unit, provenance, and quality labels. "
    "No cross-material ranking or cross-currency/unit comparison is performed."
)

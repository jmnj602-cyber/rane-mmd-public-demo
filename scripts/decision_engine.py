"""Explainable, historical decision-support indicators for management review."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from scripts.data_paths import is_demo_mode
from scripts.material_price_intelligence import (
    MATERIAL_LABELS,
    material_rows,
    monthly_comparisons,
)
from scripts.stage5_intelligence import (
    chokepoint_indicators,
    country_contraction_indicators,
    dataset_provenance,
)


MATERIAL_MOVE_THRESHOLD_PCT = 10.0
SHIPPING_MOVE_THRESHOLD_PCT = 10.0
CONGESTION_PERCENTILE = 0.90
CONGESTION_MINIMUM_OBSERVATIONS = 52
TRADE_CONCENTRATION_PERCENTILE = 0.75

INDICATOR_COLUMNS = [
    "indicator_group",
    "indicator",
    "status",
    "triggering_observation",
    "calculation_method",
    "threshold",
    "source_dataset",
    "source_url",
    "observation_date",
    "data_quality",
    "explanation",
    "recommendation",
]


def _finite(value: Any) -> bool:
    try:
        return value is not None and np.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def classify_absolute_change(change_pct: Any, threshold_pct: float) -> str:
    """Classify an absolute percent move without treating missing values as zero."""
    if threshold_pct < 0:
        raise ValueError("Change threshold must be non-negative")
    if not _finite(change_pct):
        return "Insufficient data"
    if abs(float(change_pct)) >= threshold_pct:
        return "Review threshold met"
    return "No threshold met"


def _row(**values: Any) -> dict[str, Any]:
    return {column: values.get(column) for column in INDICATOR_COLUMNS}


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(columns=INDICATOR_COLUMNS)


def _dataset_path(relative_path: str) -> str:
    root = "demo_data" if is_demo_mode() else "data"
    return f"{root}/{relative_path}"


def build_material_indicators(integrated: pd.DataFrame) -> pd.DataFrame:
    """Compare actual monthly snapshots to the immediately prior calendar month."""
    results: list[dict[str, Any]] = []
    for material, label in MATERIAL_LABELS.items():
        rows = material_rows(integrated, material)
        if rows.empty:
            results.append(
                _row(
                    indicator_group="Material market",
                    indicator=f"{label} monthly movement",
                    status="Insufficient data",
                    triggering_observation="No historical price observation is available.",
                    calculation_method=(
                        (
                            "Last generated value per calendar month; compare only "
                            "with the immediately prior calendar month. No gaps are filled."
                            if is_demo_mode()
                            else "Last actual observation per calendar month; compare only "
                            "with the immediately prior calendar month. No gaps are filled."
                        )
                    ),
                    threshold=f"Review if absolute MoM change >= {MATERIAL_MOVE_THRESHOLD_PCT:.1f}%",
                    source_dataset=_dataset_path(
                        "processed/material_market_data_integrated.csv"
                    ),
                    source_url=None,
                    observation_date=None,
                    data_quality="NO_MARKET_PRICE_DATA",
                    explanation=(
                        "No synthetic illustrative value exists for this material."
                        if is_demo_mode()
                        else "The integrated market dataset has no price rows for this "
                        "material; no estimate or substitute is used."
                    ),
                    recommendation=(
                        "No recommendation generated until a traceable market-price "
                        "series is available."
                    ),
                )
            )
            continue

        monthly = monthly_comparisons(rows)
        latest = monthly.iloc[-1]
        previous = latest["previous_month_value"]
        change_pct = latest["pct_change_vs_previous_month"]
        status = classify_absolute_change(change_pct, MATERIAL_MOVE_THRESHOLD_PCT)
        currency = str(latest["currency"])
        unit = str(latest["unit"])
        quality = str(latest["data_quality"])
        if _finite(change_pct):
            observation = (
                f"{latest['month']}: {float(latest['value']):,.4f} {currency}/{unit}; "
                f"prior calendar month: {float(previous):,.4f} {currency}/{unit}; "
                f"change {float(change_pct):+.2f}%"
            )
        else:
            observation = (
                f"{latest['month']}: {float(latest['value']):,.4f} {currency}/{unit}; "
                "no observation exists for the immediately prior calendar month."
            )
        if status == "Review threshold met":
            explanation = (
                f"The absolute observed month-over-month change is "
                f"{abs(float(change_pct)):.2f}%, meeting the project screening "
                f"threshold of {MATERIAL_MOVE_THRESHOLD_PCT:.1f}%. Source quality "
                f"remains {quality}."
            )
            recommendation = (
                "Investigate the movement against current, independently verified "
                "market quotations; do not infer a RANE purchase or supplier exposure."
            )
        elif status == "No threshold met":
            explanation = (
                f"The observed month-over-month change is below the "
                f"{MATERIAL_MOVE_THRESHOLD_PCT:.1f}% absolute screening threshold. "
                f"Source quality remains {quality}."
            )
            recommendation = "No threshold-based escalation is generated."
        else:
            explanation = (
                "The immediately prior calendar month is missing or unusable; "
                "a comparison is not calculated."
            )
            recommendation = "No movement recommendation is generated without a comparable month."
        if is_demo_mode():
            explanation = (
                f"The synthetic illustrative month-over-month movement is "
                f"{float(change_pct):.2f}% and demonstrates the configured screen; "
                "it is not a market signal."
                if _finite(change_pct)
                else "A synthetic demo comparison is unavailable for adjacent months."
            )
            recommendation = "No operational recommendation is generated from synthetic demo data."
        source = str(rows.iloc[-1]["source"])
        source_urls = rows["source_url"].dropna().astype(str)
        source_urls = source_urls[source_urls.str.strip().ne("")]
        results.append(
            _row(
                indicator_group="Material market",
                indicator=f"{label} monthly movement",
                status=status,
                triggering_observation=observation,
                calculation_method=(
                    "Monthly snapshot = last actual source observation in each "
                    "calendar month. MoM % = (current / prior calendar month - 1) "
                    "* 100. No interpolation, unit conversion, or currency conversion."
                ),
                threshold=f"Review if absolute MoM change >= {MATERIAL_MOVE_THRESHOLD_PCT:.1f}%",
                source_dataset=(
                    f"{_dataset_path('processed/material_market_data_integrated.csv')} · "
                    f"{source}"
                ),
                source_url=source_urls.iloc[-1] if not source_urls.empty else None,
                observation_date=latest["observation_date"],
                data_quality=quality,
                explanation=explanation,
                recommendation=recommendation,
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_gscpi_indicator(gscpi: pd.DataFrame) -> pd.DataFrame:
    """Expose the latest index record as context, without an alert rule."""
    if not {"month", "gscpi"}.issubset(gscpi.columns):
        missing = {"month", "gscpi"}.difference(gscpi.columns)
        raise ValueError(f"GSCPI data is missing columns: {sorted(missing)}")
    rows = gscpi.copy()
    rows["month"] = pd.to_datetime(rows["month"], errors="coerce")
    rows["gscpi"] = pd.to_numeric(rows["gscpi"], errors="coerce")
    rows = rows[np.isfinite(rows["gscpi"].to_numpy(dtype=float, na_value=np.nan))]
    rows = rows.dropna(subset=["month"]).sort_values("month")
    provenance = dataset_provenance("gscpi")
    if rows.empty:
        return pd.DataFrame(
            [
                _row(
                    indicator_group="Supply-chain pressure",
                    indicator="Global Supply Chain Pressure Index",
                    status="Insufficient data",
                    triggering_observation="No finite observation is available.",
                    calculation_method=(
                        "Latest synthetic monthly index value; no alert threshold."
                        if is_demo_mode()
                        else "Latest verified monthly GSCPI value; no alert threshold."
                    ),
                    threshold="None; context only",
                    source_dataset=_dataset_path("raw/stage_5/risk/gscpi.csv"),
                    source_url=provenance["original_source_url"] or None,
                    observation_date=None,
                    data_quality=provenance["data_quality"],
                    explanation=(
                        "No synthetic illustrative index value is present."
                        if is_demo_mode()
                        else "No usable GSCPI value is present."
                    ),
                    recommendation="No recommendation generated.",
                )
            ],
            columns=INDICATOR_COLUMNS,
        )

    latest = rows.iloc[-1]
    prior_period = latest["month"].to_period("M") - 1
    prior = rows[rows["month"].dt.to_period("M") == prior_period]
    delta = (
        float(latest["gscpi"] - prior.iloc[-1]["gscpi"])
        if not prior.empty
        else None
    )
    delta_text = "prior calendar month unavailable" if delta is None else f"change {delta:+.4f} index points"
    return pd.DataFrame(
        [
            _row(
                indicator_group="Supply-chain pressure",
                indicator="Global Supply Chain Pressure Index",
                status="Context only",
                triggering_observation=(
                    f"{latest['month']:%Y-%m}: {float(latest['gscpi']):.4f}; {delta_text}"
                ),
                calculation_method=(
                    (
                        "Show the latest synthetic illustrative monthly index and "
                        "its difference from the immediately prior calendar month."
                        if is_demo_mode()
                        else "Show the latest official-source-matched monthly index and "
                        "its difference from the immediately prior calendar month."
                    )
                ),
                threshold="None; no project alert threshold is applied",
                source_dataset=_dataset_path("raw/stage_5/risk/gscpi.csv"),
                source_url=provenance["original_source_url"] or None,
                observation_date=latest["month"],
                data_quality=provenance["data_quality"],
                explanation=(
                    "This synthetic index-shaped demo series is not the official "
                    "GSCPI or a real supply-chain pressure observation."
                    if is_demo_mode()
                    else "This verified global index is macro context only; it is not "
                    "a RANE-specific exposure or a live alert."
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "Use as context alongside current, company-specific evidence."
                ),
            )
        ],
        columns=INDICATOR_COLUMNS,
    )


def build_chokepoint_indicators(daily: pd.DataFrame) -> pd.DataFrame:
    """Convert existing historical transit screens into traceable decision rows."""
    calculated = chokepoint_indicators(daily)
    if calculated.empty:
        return _empty_result()
    results: list[dict[str, Any]] = []
    for _, item in calculated.iterrows():
        classification = str(item["classification"])
        flagged = classification in {
            "High historical decline threshold",
            "Watch historical decline threshold",
        }
        status = (
            "Review threshold met"
            if flagged
            else "Insufficient data"
            if classification == "Insufficient baseline"
            else "No threshold met"
        )
        change = item["change_vs_baseline_pct"]
        results.append(
            _row(
                indicator_group="Historical chokepoint",
                indicator=f"{item['chokepoint']} transit change",
                status=status,
                triggering_observation=(
                    f"{item['as_of']:%Y-%m-%d}: {item['latest_transits']:,.0f} "
                    f"transits vs prior baseline median "
                    f"{item['baseline_median_transits']:,.1f}; "
                    f"{change:+.2f}% ({item['baseline_observations']} baseline rows)"
                    if _finite(change)
                    else (
                        f"{item['as_of']:%Y-%m-%d}: {item['latest_transits']:,.0f} "
                        f"transits; only {item['baseline_observations']} usable "
                        "baseline rows."
                    )
                ),
                calculation_method=(
                    "Compare the latest daily `transits` count with the median "
                    "from the previous 28 calendar days (excluding the latest day); "
                    "require >=14 finite baseline rows and a positive median."
                ),
                threshold="High <= -25%; watch <= -10% and > -25%",
                source_dataset=_dataset_path("raw/stage_5/risk/chokepoint_daily.csv"),
                source_url=None,
                observation_date=item["as_of"],
                data_quality=item["data_quality"],
                explanation=(
                    f"{classification}. This synthetic example demonstrates the "
                    "historical screening calculation only."
                    if is_demo_mode()
                    else f"{classification}. This is an archive-derived historical "
                    "screen, not evidence of a current disruption."
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "Review the historical transit decline and confirm current "
                    "conditions with authoritative operational sources."
                    if flagged
                    else "No threshold-based escalation is generated."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_country_indicators(monthly: pd.DataFrame) -> pd.DataFrame:
    """Expose existing country trade-change screens with archive provenance."""
    calculated = country_contraction_indicators(monthly)
    if calculated.empty:
        return _empty_result()
    results: list[dict[str, Any]] = []
    for _, item in calculated.iterrows():
        classification = str(item["classification"])
        flagged = classification in {
            "High contraction threshold",
            "Watch contraction threshold",
        }
        results.append(
            _row(
                indicator_group="Country trade context",
                indicator=f"{item['country']} ({item['iso3']}) trade change",
                status="Review threshold met" if flagged else "No threshold met",
                triggering_observation=(
                    f"{item['month']:%Y-%m}: supplied trade_yoy_pct "
                    f"{float(item['trade_yoy_pct']):+.2f}%"
                ),
                calculation_method=(
                    "Use the latest finite source `trade_yoy_pct` for each "
                    "three-letter country code; aggregate codes are excluded."
                ),
                threshold="High <= -25%; watch <= -10% and > -25%",
                source_dataset=_dataset_path("raw/stage_5/risk/country_monthly.csv"),
                source_url=None,
                observation_date=item["month"],
                data_quality=item["data_quality"],
                explanation=(
                    f"{classification}. This synthetic example does not represent "
                    "actual country trade or RANE exposure."
                    if is_demo_mode()
                    else f"{classification}. Trade units and source calculation are "
                    "undocumented; this is not RANE trade or sourcing exposure."
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "If this geography is relevant to RANE, validate the signal "
                    "against official trade sources and company-specific records."
                    if flagged
                    else "No threshold-based escalation is generated."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_congestion_indicators(
    congestion: pd.DataFrame,
    percentile: float = CONGESTION_PERCENTILE,
    minimum_observations: int = CONGESTION_MINIMUM_OBSERVATIONS,
) -> pd.DataFrame:
    """Flag latest port index values at/above their own historical percentile."""
    required = {"port", "week_start", "congestion_index"}
    missing = required.difference(congestion.columns)
    if missing:
        raise ValueError(f"Port congestion data is missing columns: {sorted(missing)}")
    if not 0 < percentile < 1:
        raise ValueError("Congestion percentile must be between zero and one")
    if minimum_observations < 1:
        raise ValueError("Minimum congestion observations must be positive")

    rows = congestion.copy()
    rows["week_start"] = pd.to_datetime(rows["week_start"], errors="coerce")
    rows["congestion_index"] = pd.to_numeric(rows["congestion_index"], errors="coerce")
    rows = rows.dropna(subset=["week_start", "port"])
    rows = rows[np.isfinite(rows["congestion_index"].to_numpy(dtype=float, na_value=np.nan))]
    if rows.empty:
        return _empty_result()

    provenance = dataset_provenance("port_congestion")
    results: list[dict[str, Any]] = []
    for port, group in rows.groupby("port", sort=True):
        group = group.sort_values("week_start")
        latest = group.iloc[-1]
        count = len(group)
        historical_cutoff = float(group["congestion_index"].quantile(percentile))
        sufficient = count >= minimum_observations
        flagged = sufficient and float(latest["congestion_index"]) >= historical_cutoff
        status = (
            "Review threshold met"
            if flagged
            else "No threshold met"
            if sufficient
            else "Insufficient data"
        )
        results.append(
            _row(
                indicator_group="Historical port congestion",
                indicator=f"{port} congestion index",
                status=status,
                triggering_observation=(
                    f"{latest['week_start']:%Y-%m-%d}: "
                    f"congestion_index={latest['congestion_index']:,.2f}; "
                    f"historical P{percentile * 100:.0f}="
                    f"{historical_cutoff:,.2f}; {count} observations"
                ),
                calculation_method=(
                    f"Compare each port's latest finite value to its P{percentile * 100:.0f} "
                    "quantile over all available finite records; require at least "
                    f"{minimum_observations} observations."
                ),
                threshold=(
                    f"Latest value >= port-specific P{percentile * 100:.0f}; "
                    f"minimum {minimum_observations} observations"
                ),
                source_dataset=_dataset_path("raw/stage_5/logistics/port_congestion.csv"),
                source_url=None,
                observation_date=latest["week_start"],
                data_quality=provenance["data_quality"],
                explanation=(
                    "This synthetic example demonstrates the relative historical threshold."
                    if is_demo_mode() and flagged
                    else "Synthetic illustrative values; no actual port condition is represented."
                    if is_demo_mode()
                    else "The relative historical threshold is met. The archive's "
                    "congestion-index definition is undocumented and the result "
                    "is not a current congestion alert."
                    if flagged
                    else (
                        "The latest archived value is below the port-specific "
                        "historical percentile threshold; this does not establish "
                        "current port conditions."
                        if sufficient
                        else "Too few finite historical records for this screen."
                    )
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "Review the archived history and verify current port conditions "
                    "with an authoritative live source."
                    if flagged
                    else "No threshold-based escalation is generated."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_shipping_rate_indicators(
    shipping_rates: pd.DataFrame,
) -> pd.DataFrame:
    """Compare the two named monthly rate series with the immediately prior month."""
    required = {"date", "container_rate_usd_40ft", "air_cargo_rate_usd_kg"}
    missing = required.difference(shipping_rates.columns)
    if missing:
        raise ValueError(f"Shipping-rate data is missing columns: {sorted(missing)}")
    rates = shipping_rates.copy()
    rates["date"] = pd.to_datetime(rates["date"], errors="coerce")
    rates = rates.dropna(subset=["date"]).sort_values("date")
    provenance = dataset_provenance("shipping_rates")
    measures = {
        "container_rate_usd_40ft": "container rate USD/40ft (as named)",
        "air_cargo_rate_usd_kg": "air cargo rate USD/kg (as named)",
    }
    results: list[dict[str, Any]] = []
    for column, label in measures.items():
        values = pd.to_numeric(rates[column], errors="coerce")
        valid = rates.loc[np.isfinite(values.to_numpy(dtype=float, na_value=np.nan))].copy()
        valid[column] = pd.to_numeric(valid[column], errors="coerce")
        if valid.empty:
            results.append(
                _row(
                    indicator_group="Historical shipping rate",
                    indicator=label,
                    status="Insufficient data",
                    triggering_observation="No finite source observation is available.",
                    calculation_method="Compare latest month with immediately prior calendar month.",
                    threshold=f"Review if absolute MoM change >= {SHIPPING_MOVE_THRESHOLD_PCT:.1f}%",
                    source_dataset=_dataset_path("raw/stage_5/logistics/shipping_rates.csv"),
                    source_url=None,
                    observation_date=None,
                    data_quality=provenance["data_quality"],
                    explanation="No usable monthly source value is available.",
                    recommendation="No rate-movement recommendation is generated.",
                )
            )
            continue
        valid["_period"] = valid["date"].dt.to_period("M")
        latest = valid.iloc[-1]
        prior_period = latest["_period"] - 1
        prior = valid[valid["_period"] == prior_period]
        previous_value = float(prior.iloc[-1][column]) if not prior.empty else None
        current_value = float(latest[column])
        change_pct = (
            (current_value / previous_value - 1) * 100
            if previous_value not in (None, 0)
            else None
        )
        status = classify_absolute_change(change_pct, SHIPPING_MOVE_THRESHOLD_PCT)
        if _finite(change_pct):
            observation = (
                f"{latest['date']:%Y-%m}: {current_value:,.2f}; prior month "
                f"{previous_value:,.2f}; change {float(change_pct):+.2f}%"
            )
        else:
            observation = (
                f"{latest['date']:%Y-%m}: {current_value:,.2f}; no valid "
                "observation exists for the immediately prior calendar month."
            )
        results.append(
            _row(
                indicator_group="Historical shipping rate",
                indicator=label,
                status=status,
                triggering_observation=observation,
                calculation_method=(
                    "(latest monthly value / immediately prior calendar-month "
                    "value - 1) * 100; no missing month is bridged."
                ),
                threshold=f"Review if absolute MoM change >= {SHIPPING_MOVE_THRESHOLD_PCT:.1f}%",
                source_dataset=_dataset_path("raw/stage_5/logistics/shipping_rates.csv"),
                source_url=None,
                observation_date=latest["date"],
                data_quality=provenance["data_quality"],
                explanation=(
                    "Synthetic values demonstrate the configured heuristic; they "
                    "do not describe actual freight rates."
                    if is_demo_mode()
                    else f"The absolute month-over-month movement "
                    f"{'meets' if status == 'Review threshold met' else 'does not meet'} "
                    f"the {SHIPPING_MOVE_THRESHOLD_PCT:.1f}% heuristic. Unit labels "
                    "and source methodology remain unverified."
                    if status != "Insufficient data"
                    else "The prior calendar month is unavailable; no movement is calculated."
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "Review the archived rate movement against current carrier "
                    "quotes before any procurement decision."
                    if status == "Review threshold met"
                    else "No threshold-based escalation is generated."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_trade_flow_indicators(
    trade_flows: pd.DataFrame,
    percentile: float = TRADE_CONCENTRATION_PERCENTILE,
) -> pd.DataFrame:
    """Screen latest-year archive concentration values against their P75."""
    required = {
        "year",
        "exporter",
        "importer",
        "trade_category",
        "key_goods",
        "trade_value_bn_usd",
        "concentration_risk",
    }
    missing = required.difference(trade_flows.columns)
    if missing:
        raise ValueError(f"Trade-flow data is missing columns: {sorted(missing)}")
    if not 0 < percentile < 1:
        raise ValueError("Trade concentration percentile must be between zero and one")

    rows = trade_flows.copy()
    rows["year"] = pd.to_numeric(rows["year"], errors="coerce")
    rows["concentration_risk"] = pd.to_numeric(rows["concentration_risk"], errors="coerce")
    rows = rows.dropna(subset=["year"])
    rows = rows[np.isfinite(rows["concentration_risk"].to_numpy(dtype=float, na_value=np.nan))]
    if rows.empty:
        return _empty_result()
    latest_year = int(rows["year"].max())
    latest = rows[rows["year"] == latest_year].copy()
    if latest.empty:
        return _empty_result()
    cutoff = float(latest["concentration_risk"].quantile(percentile))
    provenance = dataset_provenance("trade_flows")
    results: list[dict[str, Any]] = []
    for _, item in latest.iterrows():
        value = float(item["concentration_risk"])
        flagged = value >= cutoff
        pair = f"{item['exporter']} -> {item['importer']} ({item['trade_category']})"
        results.append(
            _row(
                indicator_group="Country-pair trade context",
                indicator=f"{pair} concentration field",
                status="Review threshold met" if flagged else "No threshold met",
                triggering_observation=(
                    f"Reporting year {latest_year}: concentration_risk={value:.3f}; "
                    f"trade_value_bn_usd={item['trade_value_bn_usd']} as supplied; "
                    f"key_goods={item['key_goods']}"
                ),
                calculation_method=(
                    f"Compare the latest reported year's finite `concentration_risk` "
                    f"values with that year's P{percentile * 100:.0f} percentile."
                ),
                threshold=(
                    f"Review at or above latest-year P{percentile * 100:.0f} "
                    f"({cutoff:.3f}; {len(latest)} rows)"
                ),
                source_dataset=_dataset_path("raw/stage_5/risk/trade_flows.csv"),
                source_url=None,
                observation_date=str(latest_year),
                data_quality=provenance["data_quality"],
                explanation=(
                    "Synthetic country-pair values demonstrate the relative cutoff; "
                    "they are not customs statistics or RANE exposure."
                    if is_demo_mode() and flagged
                    else "Synthetic illustrative values; no real trade exposure is represented."
                    if is_demo_mode()
                    else "The archive value meets a relative screening cutoff. The "
                    "field scale/method and source authenticity are unverified; "
                    "this is not a RANE trade exposure."
                    if flagged
                    else "The archive value is below the latest-year relative cutoff."
                ),
                recommendation=(
                    "No operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "If this country pair or goods category is relevant to RANE, "
                    "validate it against official trade records and company-specific "
                    "sourcing data; no RANE exposure is established."
                    if flagged
                    else "No threshold-based escalation is generated."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_tariff_indicators(
    tariffs: pd.DataFrame,
    keyword: str = "",
    target_country: str | None = None,
) -> pd.DataFrame:
    """Filter historical tariff text; a text match is not legal applicability."""
    required = {
        "date",
        "target_country",
        "policy_name",
        "tariff_rate_pct",
        "description",
    }
    missing = required.difference(tariffs.columns)
    if missing:
        raise ValueError(f"Tariff timeline is missing columns: {sorted(missing)}")
    rows = tariffs.copy()
    rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
    rows = rows.dropna(subset=["date"])
    if target_country and target_country != "All":
        rows = rows[rows["target_country"].astype(str) == target_country]
    search = keyword.strip()
    if search:
        text = (
            rows["policy_name"].fillna("").astype(str)
            + " "
            + rows["description"].fillna("").astype(str)
        )
        rows = rows[text.str.contains(search, case=False, regex=False, na=False)]

    provenance = dataset_provenance("tariff_timeline")
    if rows.empty:
        return pd.DataFrame(
            [
                _row(
                    indicator_group="Historical tariff record",
                    indicator=(
                        "No matching demo row"
                        if is_demo_mode()
                        else "No matching archive row"
                    ),
                    status="No matching records",
                    triggering_observation=f"No tariff text matched {search!r}.",
                    calculation_method=(
                        "Optional case-insensitive substring filter over policy_name "
                        "and description; no category classifier is applied."
                    ),
                    threshold="No rate threshold",
                    source_dataset=_dataset_path("raw/stage_5/risk/tariff_timeline.csv"),
                    source_url=None,
                    observation_date=None,
                    data_quality=provenance["data_quality"],
                    explanation=(
                        "No synthetic illustrative row matched."
                        if is_demo_mode()
                        else "No matching historical archive row was found."
                    ),
                    recommendation="No recommendation generated.",
                )
            ],
            columns=INDICATOR_COLUMNS,
        )

    results: list[dict[str, Any]] = []
    for _, item in rows.sort_values("date", ascending=False).iterrows():
        matched_text = (
            f"Text match for {search!r} in policy_name/description."
            if search
            else (
                "Synthetic illustrative policy scenario; no real tariff is represented."
                if is_demo_mode()
                else "Historical archive record; no category text filter was applied."
            )
        )
        results.append(
            _row(
                indicator_group="Historical tariff record",
                indicator=str(item["policy_name"]),
                status=(
                    "Text match — verify applicability"
                    if search
                    else "Historical record — applicability unverified"
                ),
                triggering_observation=(
                    f"{item['date']:%Y-%m-%d}: target={item['target_country']}; "
                    f"tariff_rate_pct={item['tariff_rate_pct']} as supplied; "
                    f"description={item['description']}"
                ),
                calculation_method=(
                    "Historical record is shown as supplied. Optional keyword "
                    "filter searches policy_name and description only; it does "
                    "not determine legal scope or product classification."
                ),
                threshold="No rate threshold; text match is not a category determination",
                source_dataset=_dataset_path("raw/stage_5/risk/tariff_timeline.csv"),
                source_url=None,
                observation_date=item["date"],
                data_quality=provenance["data_quality"],
                explanation=(
                    f"{matched_text} Synthetic demo policy scenarios are fictional."
                    if is_demo_mode()
                    else f"{matched_text} Archive provenance and tariff methodology "
                    "are unverified; no RANE impact is established."
                ),
                recommendation=(
                    "No legal or operational recommendation is generated from synthetic demo data."
                    if is_demo_mode()
                    else "Verify current official tariff rules and whether the legal "
                    "scope applies to RANE products/counterparties before acting."
                ),
            )
        )
    return pd.DataFrame(results, columns=INDICATOR_COLUMNS)


def build_freshness_report(
    sources: dict[str, dict[str, Any]],
    as_of: date | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Summarize observed coverage and quality without implying a live feed."""
    reference = pd.Timestamp(as_of if as_of is not None else date.today()).normalize()
    results: list[dict[str, Any]] = []
    for name, metadata in sources.items():
        frame: pd.DataFrame = metadata["frame"]
        date_column: str | None = metadata.get("date_column")
        start = end = latest = None
        age_days = None
        if date_column and date_column in frame.columns and not frame.empty:
            if date_column == "year":
                years = pd.to_numeric(frame[date_column], errors="coerce").dropna()
                if not years.empty:
                    start = str(int(years.min()))
                    end = latest = str(int(years.max()))
            else:
                dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
                if not dates.empty:
                    start = dates.min().date().isoformat()
                    end = dates.max().date().isoformat()
                    latest_date = dates.max()
                    latest = latest_date.date().isoformat()
                    age_days = int((reference - latest_date.normalize()).days)
        if not date_column:
            freshness_note = "No observation date supplied"
        elif date_column == "year":
            freshness_note = "Annual reporting year; exact observation date not supplied"
        else:
            freshness_note = (
                "Historical snapshot; age is descriptive, not a live-feed status"
            )
        results.append(
            {
                "dataset": name,
                "coverage_start": start,
                "last_observation": latest,
                "coverage_end": end,
                "days_since_observation": age_days,
                "extraction_date": metadata.get("extraction_date", "Not supplied"),
                "data_quality": metadata.get("data_quality", "NOT CLASSIFIED"),
                "source": metadata.get("source", ""),
                "source_url": metadata.get("source_url"),
                "freshness_note": freshness_note,
            }
        )
    return pd.DataFrame(results)


def summarize_material_latest(integrated: pd.DataFrame) -> pd.DataFrame:
    """Return one observed latest value per material, preserving source units."""
    rows: list[dict[str, Any]] = []
    for material, label in MATERIAL_LABELS.items():
        material_data = material_rows(integrated, material)
        if material_data.empty:
            rows.append(
                {
                    "material": label,
                    "latest_value": None,
                    "currency": None,
                    "unit": None,
                    "observation_date": None,
                    "data_quality": "NO_MARKET_PRICE_DATA",
                    "source": "No price observations available",
                }
            )
            continue
        latest = material_data.iloc[-1]
        rows.append(
            {
                "material": label,
                "latest_value": float(latest["value"]),
                "currency": latest["currency"],
                "unit": latest["unit"],
                "observation_date": latest["date"],
                "data_quality": latest["data_quality"],
                "source": latest["source"],
            }
        )
    return pd.DataFrame(rows)


def route_benchmark_context(benchmarks: pd.DataFrame) -> pd.DataFrame:
    """Attach explicit archive quality to the one-date route snapshot."""
    required = {"as_of", "mode", "origin", "destination", "benchmark_usd", "unit"}
    missing = required.difference(benchmarks.columns)
    if missing:
        raise ValueError(f"Route benchmark is missing columns: {sorted(missing)}")
    result = benchmarks.copy()
    provenance = dataset_provenance("route_benchmark")
    result["data_quality"] = provenance["data_quality"]
    result["source_dataset"] = _dataset_path(
        "raw/stage_5/logistics/benchmark-2026-11.csv"
    )
    result["observation_note"] = (
        "Synthetic illustrative snapshot; no actual quote, change, or trend."
        if is_demo_mode()
        else "Single historical snapshot; no change or trend inferred."
    )
    return result

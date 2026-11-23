"""Read-only analytics for the integrated RANE material-market dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from scripts.data_paths import get_data_root

ROOT = Path(__file__).resolve().parents[1]
INTEGRATED_DATA = get_data_root() / "processed" / "material_market_data_integrated.csv"

REQUIRED_COLUMNS = {
    "date",
    "record_type",
    "material",
    "value",
    "currency",
    "unit",
    "source",
    "source_url",
    "extraction_date",
    "data_quality",
    "source_series",
    "source_period",
    "source_note",
}

MATERIAL_LABELS = {
    "Copper": "Copper",
    "Nickel": "Nickel",
    "Aluminium": "Aluminium",
    "Steel HR": "Steel HRC (HRC 2MM)",
    "Steel CR": "Steel CRC (CRC 0.63MM)",
    "Phenolic Resin": "Phenolic Resin",
    "Natural Rubber": "Natural Rubber (World Bank historical series)",
}

MONTHLY_MATERIALS = {"Steel HR", "Steel CR", "Natural Rubber"}
DAILY_MATERIALS = {"Copper", "Nickel", "Aluminium"}

MONTHLY_COMPARISON_COLUMNS = [
    "observation_date",
    "month",
    "value",
    "currency",
    "unit",
    "data_quality",
    "source",
    "source_url",
    "previous_month_value",
    "change_vs_previous_month",
    "pct_change_vs_previous_month",
    "prior_year_same_month_value",
    "change_vs_prior_year",
    "pct_change_vs_prior_year",
    "monthly_observation_basis",
]


def load_integrated_data(
    path: Path | None = None, *, mode: str | None = None
) -> pd.DataFrame:
    """Load and validate integrated rows without altering source values."""
    if path is None:
        path = get_data_root(mode) / "processed" / "material_market_data_integrated.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Integrated market data not found: {path}")
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Integrated data is missing columns: {sorted(missing_columns)}")

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    if data["date"].isna().any():
        raise ValueError("Integrated data contains an invalid date")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    if data["value"].isna().any():
        raise ValueError("Integrated data contains a missing or non-numeric value")

    material_prices = data[data["record_type"] == "material_price"]
    unexpected = set(material_prices["material"].dropna()).difference(MATERIAL_LABELS)
    if unexpected:
        raise ValueError(f"Integrated data contains unexpected materials: {sorted(unexpected)}")
    return data


def material_rows(data: pd.DataFrame, material: str) -> pd.DataFrame:
    """Return one material's observations; Phenolic Resin intentionally has none."""
    if material not in MATERIAL_LABELS:
        raise ValueError(f"Unsupported material: {material}")
    return data[
        (data["record_type"] == "material_price")
        & (data["material"] == material)
    ].copy().sort_values("date")


def filter_date_range(
    rows: pd.DataFrame, start: Any, end: Any
) -> pd.DataFrame:
    """Filter actual observations inclusively; do not fill absent dates."""
    start_date = pd.Timestamp(start)
    end_date = pd.Timestamp(end)
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date")
    return rows[
        rows["date"].between(start_date, end_date, inclusive="both")
    ].copy().sort_values("date")


def observation_frequency(material: str) -> str:
    if material in DAILY_MATERIALS:
        return "Daily source observations (legacy source)"
    if material in MONTHLY_MATERIALS:
        return "Monthly"
    return "No observations"


def monthly_comparisons(rows: pd.DataFrame) -> pd.DataFrame:
    """Build monthly snapshots and adjacent-month/same-month-prior-year changes.

    Daily series use their last actual observation within each calendar month.
    Monthly source observations are retained as supplied. No missing period or
    price is filled.
    """
    if rows.empty:
        return pd.DataFrame(columns=MONTHLY_COMPARISON_COLUMNS)

    pairs = rows[["currency", "unit"]].drop_duplicates()
    if len(pairs) != 1:
        raise ValueError("Cannot compare observations with mixed currencies or units")

    ordered = rows.sort_values("date").copy()
    ordered["_month"] = ordered["date"].dt.to_period("M")
    snapshots = (
        ordered.groupby("_month", sort=True, as_index=False)
        .tail(1)
        .sort_values("_month")
    )
    by_month = {
        row["_month"]: row
        for _, row in snapshots.iterrows()
    }

    output: list[dict[str, Any]] = []
    synthetic = (
        "data_quality" in ordered.columns
        and ordered["data_quality"].eq("SYNTHETIC_ILLUSTRATIVE_DATA").any()
    )
    daily_basis = (
        "Last generated demo value in month; no interpolation."
        if synthetic
        else "Last actual source observation in month; no interpolation."
    )
    monthly_basis = (
        "Synthetic generated monthly value; no interpolation."
        if synthetic
        else "Source monthly observation; no interpolation."
    )
    for _, row in snapshots.iterrows():
        month = row["_month"]
        previous = by_month.get(month - 1)
        prior_year = by_month.get(month - 12)
        previous_value = None if previous is None else float(previous["value"])
        prior_year_value = None if prior_year is None else float(prior_year["value"])
        value = float(row["value"])

        output.append(
            {
                "observation_date": row["date"],
                "month": str(month),
                "value": value,
                "currency": row["currency"],
                "unit": row["unit"],
                "data_quality": row["data_quality"],
                "source": row["source"],
                "source_url": row["source_url"],
                "previous_month_value": previous_value,
                "change_vs_previous_month": (
                    None if previous_value is None else value - previous_value
                ),
                "pct_change_vs_previous_month": _percentage_change(
                    value, previous_value
                ),
                "prior_year_same_month_value": prior_year_value,
                "change_vs_prior_year": (
                    None if prior_year_value is None else value - prior_year_value
                ),
                "pct_change_vs_prior_year": _percentage_change(
                    value, prior_year_value
                ),
                "monthly_observation_basis": (
                    daily_basis
                    if observation_frequency(str(row["material"])).startswith("Daily")
                    else monthly_basis
                ),
            }
        )
    return pd.DataFrame(output, columns=MONTHLY_COMPARISON_COLUMNS)


def annual_comparisons(monthly: pd.DataFrame) -> pd.DataFrame:
    """Summarize monthly snapshots and compare the same months year over year."""
    columns = [
        "year",
        "observed_months",
        "average_of_observed_months",
        "comparable_months",
        "prior_year_comparable_average",
        "change_vs_prior_year",
        "pct_change_vs_prior_year",
        "data_quality",
    ]
    if monthly.empty:
        return pd.DataFrame(columns=columns)

    monthly = monthly.copy()
    monthly["_period"] = pd.PeriodIndex(monthly["month"], freq="M")
    monthly["_year"] = monthly["_period"].map(lambda period: period.year)
    monthly["_month_number"] = monthly["_period"].map(lambda period: period.month)
    years = sorted(monthly["_year"].unique())
    groups = {
        year: group.set_index("_month_number")["value"]
        for year, group in monthly.groupby("_year", sort=True)
    }
    qualities = {
        year: ", ".join(sorted(group["data_quality"].dropna().unique()))
        for year, group in monthly.groupby("_year", sort=True)
    }

    output: list[dict[str, Any]] = []
    for year in years:
        current = groups[year]
        previous = groups.get(year - 1)
        common_months = (
            [] if previous is None else sorted(set(current.index) & set(previous.index))
        )
        current_comparable = None
        previous_comparable = None
        if common_months:
            current_comparable = float(current.loc[common_months].mean())
            previous_comparable = float(previous.loc[common_months].mean())
        output.append(
            {
                "year": year,
                "observed_months": int(current.size),
                "average_of_observed_months": float(current.mean()),
                "comparable_months": len(common_months),
                "prior_year_comparable_average": previous_comparable,
                "change_vs_prior_year": (
                    None
                    if current_comparable is None or previous_comparable is None
                    else current_comparable - previous_comparable
                ),
                "pct_change_vs_prior_year": _percentage_change(
                    current_comparable, previous_comparable
                ),
                "data_quality": qualities[year],
            }
        )
    return pd.DataFrame(output, columns=columns)


def missing_months(rows: pd.DataFrame) -> list[str]:
    """Return absent interior calendar months for a monthly source series."""
    if rows.empty or not rows["material"].iloc[0] in MONTHLY_MATERIALS:
        return []
    periods = rows["date"].dt.to_period("M").drop_duplicates().sort_values()
    if len(periods) < 2:
        return []
    expected = pd.period_range(periods.iloc[0], periods.iloc[-1], freq="M")
    return [str(period) for period in expected if period not in set(periods)]


def source_extraction_date(rows: pd.DataFrame) -> str:
    if rows.empty:
        return "Not recorded"
    extraction_dates = pd.to_datetime(rows["extraction_date"], errors="coerce").dropna()
    if extraction_dates.empty:
        return "Not recorded"
    return extraction_dates.max().date().isoformat()


def _percentage_change(value: float | None, base: float | None) -> float | None:
    if value is None or base is None or base == 0:
        return None
    return (value - base) / base * 100

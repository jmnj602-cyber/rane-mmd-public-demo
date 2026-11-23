"""Read-only helpers for the recovered Stage 5 archive datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.data_paths import DEMO_DATA_QUALITY, get_data_root, is_demo_mode

ROOT = Path(__file__).resolve().parents[1]
STAGE5_RAW = get_data_root() / "raw" / "stage_5"
ARCHIVE_SOURCE_UNVERIFIED = "ARCHIVE_SOURCE_UNVERIFIED"
OFFICIAL_SOURCE_MATCH_VERIFIED = "OFFICIAL_SOURCE_MATCH_VERIFIED"
SYNTHETIC_ILLUSTRATIVE_DATA = DEMO_DATA_QUALITY
GSCPI_SOURCE_URL = (
    "https://www.newyorkfed.org/medialibrary/research/interactives/"
    "gscpi/downloads/gscpi_data.csv"
)

DATASETS: dict[str, dict[str, Any]] = {
    "chokepoint_daily": {
        "path": STAGE5_RAW / "risk" / "chokepoint_daily.csv",
        "archive": "archive (1).zip",
        "member": "chokepoint_daily.csv",
        "date_column": "date",
        "required_columns": {"date", "chokepoint_id", "chokepoint", "transits"},
    },
    "chokepoint_monthly": {
        "path": STAGE5_RAW / "risk" / "chokepoint_monthly.csv",
        "archive": "archive (1).zip",
        "member": "chokepoint_monthly.csv",
        "date_column": "month",
        "required_columns": {"month", "chokepoint_id", "chokepoint", "transits_per_day"},
    },
    "country_monthly": {
        "path": STAGE5_RAW / "risk" / "country_monthly.csv",
        "archive": "archive (1).zip",
        "member": "country_monthly.csv",
        "date_column": "month",
        "required_columns": {"month", "iso3", "country", "trade_yoy_pct"},
    },
    "country_daily": {
        "path": STAGE5_RAW / "risk" / "country_daily.parquet",
        "archive": "archive (1).zip",
        "member": "country_daily.parquet",
        "date_column": "date",
        "required_columns": {
            "date",
            "iso3",
            "country",
            "is_aggregate",
            "shipment",
            "shipment_30ma_yoy",
        },
    },
    "gscpi": {
        "path": STAGE5_RAW / "risk" / "gscpi.csv",
        "archive": "archive (1).zip",
        "member": "gscpi.csv",
        "date_column": "month",
        "required_columns": {"month", "gscpi"},
    },
    "disruption_events": {
        "path": STAGE5_RAW / "risk" / "disruption_events.csv",
        "archive": "archive (2).zip",
        "member": "disruption_events.csv",
        "date_column": "date",
        "required_columns": {"date", "event_name", "disruption_type", "severity"},
    },
    "industry_exposure": {
        "path": STAGE5_RAW / "risk" / "industry_exposure.csv",
        "archive": "archive (2).zip",
        "member": "industry_exposure.csv",
        "required_columns": {"year", "industry", "overall_vulnerability"},
    },
    "tariff_timeline": {
        "path": STAGE5_RAW / "risk" / "tariff_timeline.csv",
        "archive": "archive (2).zip",
        "member": "tariff_timeline.csv",
        "date_column": "date",
        "required_columns": {"date", "imposing_country", "target_country", "tariff_rate_pct"},
    },
    "trade_flows": {
        "path": STAGE5_RAW / "risk" / "trade_flows.csv",
        "archive": "archive (2).zip",
        "member": "trade_flows.csv",
        "required_columns": {
            "year",
            "exporter",
            "importer",
            "trade_value_bn_usd",
            "concentration_risk",
        },
    },
    "ports": {
        "path": STAGE5_RAW / "logistics" / "ports.csv",
        "archive": "archive (1).zip",
        "member": "ports.csv",
        "required_columns": {
            "port_id",
            "port",
            "country",
            "continent",
            "latitude",
            "longitude",
        },
    },
    "port_congestion": {
        "path": STAGE5_RAW / "logistics" / "port_congestion.csv",
        "archive": "archive (2).zip",
        "member": "port_congestion.csv",
        "date_column": "week_start",
        "required_columns": {"week_start", "port", "country", "avg_wait_days", "congestion_index"},
    },
    "shipping_rates": {
        "path": STAGE5_RAW / "logistics" / "shipping_rates.csv",
        "archive": "archive (2).zip",
        "member": "shipping_rates.csv",
        "date_column": "date",
        "required_columns": {
            "date",
            "baltic_dry_index",
            "container_rate_usd_40ft",
            "air_cargo_rate_usd_kg",
        },
    },
    "route_benchmark": {
        "path": STAGE5_RAW / "logistics" / "benchmark-2026-11.csv",
        "archive": "archive.zip",
        "member": "benchmark-2026-11.csv",
        "date_column": "as_of",
        "required_columns": {
            "corridor_id",
            "origin",
            "destination",
            "mode",
            "benchmark_usd",
            "unit",
            "as_of",
        },
    },
}


def load_stage5_dataset(
    dataset_id: str, *, mode: str | None = None
) -> pd.DataFrame:
    """Load one selected-root dataset and parse its declared date field."""
    if dataset_id not in DATASETS:
        raise ValueError(f"Unknown Stage 5 dataset: {dataset_id}")
    metadata = DATASETS[dataset_id]
    configured_path: Path = Path(metadata["path"])
    relative_path: Path | None = None
    for root_name in ("demo_data", "data"):
        try:
            relative_path = configured_path.relative_to(ROOT / root_name)
            break
        except ValueError:
            continue
    if relative_path is None:
        path = configured_path
    else:
        path = get_data_root(mode) / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Stage 5 dataset not found: {path}")
    if path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path, low_memory=False)
    missing = metadata["required_columns"].difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {sorted(missing)}")
    date_column = metadata.get("date_column")
    if date_column:
        parsed = pd.to_datetime(frame[date_column], errors="coerce")
        if parsed.isna().any():
            invalid_count = int(parsed.isna().sum())
            raise ValueError(
                f"{path.name} has {invalid_count} invalid {date_column} values"
            )
        frame[date_column] = parsed
    return frame


def dataset_provenance(
    dataset_id: str, *, mode: str | None = None
) -> dict[str, str]:
    if dataset_id not in DATASETS:
        raise ValueError(f"Unknown Stage 5 dataset: {dataset_id}")
    metadata = DATASETS[dataset_id]
    if is_demo_mode(mode):
        return {
            "archive": "Synthetic demo data",
            "archive_member": metadata["member"],
            "source_organization": "Synthetic demo generator",
            "original_source_url": "",
            "data_quality": SYNTHETIC_ILLUSTRATIVE_DATA,
        }
    provenance = {
        "archive": metadata["archive"],
        "archive_member": metadata["member"],
        "source_organization": "Not supplied in the archive data",
        "original_source_url": "Not supplied in the archive data",
        "data_quality": (
            SYNTHETIC_ILLUSTRATIVE_DATA
            if is_demo_mode()
            else ARCHIVE_SOURCE_UNVERIFIED
        ),
    }
    if dataset_id == "gscpi":
        provenance.update(
            {
                "source_organization": "Federal Reserve Bank of New York",
                "original_source_url": GSCPI_SOURCE_URL,
                "data_quality": OFFICIAL_SOURCE_MATCH_VERIFIED,
            }
        )
    return provenance


def finite_measure_rows(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return a copy containing finite numeric values for a selected measure."""
    if column not in frame.columns:
        raise ValueError(f"Measure not found: {column}")
    numeric = pd.to_numeric(frame[column], errors="coerce")
    mask = np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))
    return frame.loc[mask].copy()


def classify_trade_contraction(change_pct: Any) -> str:
    """Classify a supplied year-over-year percent as an exploratory indicator."""
    if pd.isna(change_pct) or not np.isfinite(float(change_pct)):
        return "Insufficient or invalid data"
    value = float(change_pct)
    if value <= -25:
        return "High contraction threshold"
    if value <= -10:
        return "Watch contraction threshold"
    return "No contraction threshold triggered"


def _classification_rank(value: str) -> int:
    return {
        "High historical decline threshold": 0,
        "High contraction threshold": 0,
        "Watch historical decline threshold": 1,
        "Watch contraction threshold": 1,
        "No decline threshold triggered": 2,
        "No contraction threshold triggered": 2,
        "Insufficient baseline": 3,
        "Insufficient or invalid data": 3,
    }.get(value, 4)


def chokepoint_indicators(
    daily: pd.DataFrame,
    as_of: Any | None = None,
    baseline_days: int = 28,
    minimum_baseline_rows: int = 14,
) -> pd.DataFrame:
    """Compare each chokepoint's latest daily transit count to prior 28-day median.

    Thresholds are deliberately described as exploratory: <= -25% is high,
    <= -10% is watch, and otherwise no decline threshold is triggered.
    """
    required = {"date", "chokepoint_id", "chokepoint", "transits"}
    missing = required.difference(daily.columns)
    if missing:
        raise ValueError(f"Daily chokepoint data is missing columns: {sorted(missing)}")
    if baseline_days < 1 or minimum_baseline_rows < 1:
        raise ValueError("Baseline window and minimum rows must be positive")

    rows = daily.copy()
    rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
    rows["transits"] = pd.to_numeric(rows["transits"], errors="coerce")
    rows = finite_measure_rows(rows, "transits")
    rows = rows.dropna(subset=["date", "chokepoint_id", "chokepoint"])
    result_columns = [
        "chokepoint_id",
        "chokepoint",
        "as_of",
        "latest_transits",
        "baseline_median_transits",
        "baseline_observations",
        "change_vs_baseline_pct",
        "classification",
        "data_quality",
    ]
    if rows.empty:
        return pd.DataFrame(columns=result_columns)
    cutoff = pd.Timestamp(as_of) if as_of is not None else rows["date"].max()
    rows = rows[rows["date"] <= cutoff]

    results: list[dict[str, Any]] = []
    for _, group in rows.groupby(["chokepoint_id", "chokepoint"], sort=True):
        group = group.sort_values("date")
        if group.empty:
            continue
        latest = group.iloc[-1]
        latest_date = latest["date"]
        baseline_start = latest_date - pd.Timedelta(days=baseline_days)
        baseline = group[
            (group["date"] >= baseline_start) & (group["date"] < latest_date)
        ]["transits"]
        baseline_count = int(baseline.size)
        baseline_median = float(baseline.median()) if baseline_count else np.nan
        current = float(latest["transits"])
        change_pct = (
            (current / baseline_median - 1) * 100
            if baseline_count >= minimum_baseline_rows and baseline_median > 0
            else np.nan
        )
        if pd.isna(change_pct):
            classification = "Insufficient baseline"
        elif change_pct <= -25:
            classification = "High historical decline threshold"
        elif change_pct <= -10:
            classification = "Watch historical decline threshold"
        else:
            classification = "No decline threshold triggered"
        results.append(
            {
                "chokepoint_id": latest["chokepoint_id"],
                "chokepoint": latest["chokepoint"],
                "as_of": latest_date,
                "latest_transits": current,
                "baseline_median_transits": baseline_median,
                "baseline_observations": baseline_count,
                "change_vs_baseline_pct": change_pct,
                "classification": classification,
                "data_quality": ARCHIVE_SOURCE_UNVERIFIED,
            }
        )
    if not results:
        return pd.DataFrame(columns=result_columns)
    result = pd.DataFrame(results, columns=result_columns)
    result["_classification_rank"] = result["classification"].map(_classification_rank)
    return result.sort_values(
        ["_classification_rank", "chokepoint"], kind="stable"
    ).drop(columns="_classification_rank").reset_index(drop=True)


def country_contraction_indicators(monthly: pd.DataFrame) -> pd.DataFrame:
    """Return each country-code entity's latest finite monthly trade change.

    Numeric aggregate geography codes are excluded; only three-letter alphabetic
    codes are included. The source does not document these codes or trade units.
    """
    required = {"month", "iso3", "country", "trade_yoy_pct"}
    missing = required.difference(monthly.columns)
    if missing:
        raise ValueError(f"Country monthly data is missing columns: {sorted(missing)}")
    rows = monthly.copy()
    rows["month"] = pd.to_datetime(rows["month"], errors="coerce")
    rows["trade_yoy_pct"] = pd.to_numeric(rows["trade_yoy_pct"], errors="coerce")
    rows = rows[rows["iso3"].astype(str).str.fullmatch(r"[A-Z]{3}", na=False)]
    rows = finite_measure_rows(rows, "trade_yoy_pct")
    rows = rows.dropna(subset=["month"]).sort_values("month")
    if rows.empty:
        return pd.DataFrame(
            columns=["iso3", "country", "month", "trade_yoy_pct", "classification", "data_quality"]
        )
    latest = rows.groupby("iso3", sort=True).tail(1).copy()
    latest["classification"] = latest["trade_yoy_pct"].map(classify_trade_contraction)
    latest["data_quality"] = (
        SYNTHETIC_ILLUSTRATIVE_DATA
        if is_demo_mode()
        else ARCHIVE_SOURCE_UNVERIFIED
    )
    result = latest[
        ["iso3", "country", "month", "trade_yoy_pct", "classification", "data_quality"]
    ].copy()
    result["_classification_rank"] = result["classification"].map(_classification_rank)
    return result.sort_values(
        ["_classification_rank", "country"], kind="stable"
    ).drop(columns="_classification_rank").reset_index(drop=True)


def add_provenance_for_export(frame: pd.DataFrame, dataset_id: str) -> pd.DataFrame:
    """Add explicit archive provenance to an export without changing source files."""
    provenance = dataset_provenance(dataset_id)
    exported = frame.copy()
    exported["archive_source"] = (
        ""
        if is_demo_mode()
        else f"{provenance['archive']}::{provenance['archive_member']}"
    )
    exported["source"] = provenance["source_organization"]
    exported["original_source_url"] = provenance["original_source_url"]
    exported["data_quality"] = provenance["data_quality"]
    return exported

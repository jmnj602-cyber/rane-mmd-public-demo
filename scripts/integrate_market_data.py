"""Build a provenance-preserving, non-converting market-data integration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "external"
OUTPUT = ROOT / "data" / "processed" / "material_market_data_integrated.csv"

COMMON_COLUMNS = [
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
]

LEGACY_MATERIALS = {
    "Copper": "Copper",
    "Nickel": "Nickel",
    "Aluminum": "Aluminium",
}

LEGACY_SOURCE = (
    "Provided archive member: archive (2).zip::commodity_prices_supply_chain.csv "
    "(underlying source attribution absent)"
)
LEGACY_NOTE = (
    "Original archive values, dates, currency, and unit retained. The source "
    "file does not identify a vendor, methodology, grade, or source URL; "
    "not validated as an authentic market-price series."
)


def _read_csv(name: str, required_columns: set[str]) -> pd.DataFrame:
    path = RAW / name
    if not path.is_file():
        raise FileNotFoundError(f"Required source dataset not found: {path}")
    frame = pd.read_csv(path)
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"{name} is missing columns: {sorted(missing_columns)}")
    return frame


def _standardize_legacy_prices() -> pd.DataFrame:
    legacy = _read_csv(
        "commodity_prices_supply_chain.csv",
        {"date", "commodity", "unit", "currency", "price"},
    )
    legacy = legacy[legacy["commodity"].isin(LEGACY_MATERIALS)].copy()
    if legacy.empty:
        raise ValueError("No legacy Copper, Nickel, or Aluminum rows were found")
    if legacy[["date", "commodity", "price", "unit", "currency"]].isna().any().any():
        raise ValueError("Legacy source has missing required values")

    return pd.DataFrame(
        {
            "date": legacy["date"].astype(str),
            "record_type": "material_price",
            "material": legacy["commodity"].map(LEGACY_MATERIALS),
            "value": legacy["price"],
            "currency": legacy["currency"],
            "unit": legacy["unit"],
            "source": LEGACY_SOURCE,
            "source_url": "",
            "extraction_date": "",
            "data_quality": "LEGACY_SOURCE_PROVENANCE_UNVERIFIED",
            "source_series": legacy["commodity"],
            "source_period": legacy["date"].astype(str),
            "source_note": LEGACY_NOTE,
        }
    )


def _standardize_rubber() -> pd.DataFrame:
    rubber = _read_csv(
        "natural_rubber_rss3.csv",
        {
            "date",
            "value",
            "currency",
            "unit",
            "source",
            "source_url",
            "extraction_date",
            "data_quality",
            "source_period",
            "series",
            "source_note",
        },
    )
    return pd.DataFrame(
        {
            "date": rubber["date"],
            "record_type": "material_price",
            "material": "Natural Rubber",
            "value": rubber["value"],
            "currency": rubber["currency"],
            "unit": rubber["unit"],
            "source": rubber["source"],
            "source_url": rubber["source_url"],
            "extraction_date": rubber["extraction_date"],
            "data_quality": rubber["data_quality"],
            "source_series": rubber["series"],
            "source_period": rubber["source_period"],
            "source_note": rubber["source_note"],
        }
    )


def _standardize_steel() -> pd.DataFrame:
    steel = _read_csv(
        "steel_hrc_crc.csv",
        {
            "date",
            "value",
            "currency",
            "unit",
            "source",
            "source_url",
            "extraction_date",
            "data_quality",
            "material",
            "digitization_note",
        },
    )
    material_mapping = {
        "Steel HRC 2MM": "Steel HR",
        "Steel CRC 0.63MM": "Steel CR",
    }
    unexpected = set(steel["material"].dropna()).difference(material_mapping)
    if unexpected:
        raise ValueError(f"Unexpected steel chart series: {sorted(unexpected)}")
    if set(steel["data_quality"].dropna()) != {"APPROXIMATE_CHART_VALUE"}:
        raise ValueError("Every steel chart value must be marked approximate")

    return pd.DataFrame(
        {
            "date": steel["date"],
            "record_type": "material_price",
            "material": steel["material"].map(material_mapping),
            "value": steel["value"],
            "currency": steel["currency"],
            "unit": steel["unit"],
            "source": steel["source"],
            "source_url": steel["source_url"],
            "extraction_date": steel["extraction_date"],
            "data_quality": steel["data_quality"],
            "source_series": steel["material"],
            "source_period": steel["date"],
            "source_note": steel["digitization_note"],
        }
    )


def _standardize_fx() -> pd.DataFrame:
    rates = _read_csv(
        "usd_inr.csv",
        {
            "date",
            "value",
            "currency",
            "unit",
            "source",
            "source_url",
            "extraction_date",
            "data_quality",
            "rate",
        },
    )
    return pd.DataFrame(
        {
            "date": rates["date"],
            "record_type": "reference_rate",
            "material": "USD/INR Reference Rate",
            "value": rates["value"],
            "currency": rates["currency"],
            "unit": rates["unit"],
            "source": rates["source"],
            "source_url": rates["source_url"],
            "extraction_date": rates["extraction_date"],
            "data_quality": rates["data_quality"],
            "source_series": rates["rate"],
            "source_period": rates["date"],
            "source_note": (
                "Official RBI USD reference-rate observation; no price "
                "conversion or interpolation performed."
            ),
        }
    )


def build_integrated_data() -> pd.DataFrame:
    """Stack source series while retaining source units, currency, and quality."""
    frames = [
        _standardize_legacy_prices(),
        _standardize_rubber(),
        _standardize_steel(),
        _standardize_fx(),
    ]
    integrated = pd.concat(frames, ignore_index=True)
    integrated = integrated[COMMON_COLUMNS].sort_values(
        ["record_type", "material", "date"], kind="stable"
    )
    key = ["record_type", "material", "date", "source_series"]
    if integrated.duplicated(key).any():
        raise ValueError("Integrated data contains duplicate series/date rows")
    if integrated["value"].isna().any():
        raise ValueError("Integrated data contains missing values")
    return integrated.reset_index(drop=True)


def write_integrated_data() -> Path:
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {OUTPUT}")
    integrated = build_integrated_data()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    integrated.to_csv(OUTPUT, index=False)
    return OUTPUT


if __name__ == "__main__":
    print(f"Wrote {write_integrated_data()}")

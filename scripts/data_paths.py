"""Resolve the selected local or public-demo data root."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_MODE_ENV = "RANE_DATA_MODE"
DEMO_DATA_QUALITY = "SYNTHETIC_ILLUSTRATIVE_DATA"


def get_data_mode(mode: str | None = None) -> str:
    selected = (mode or os.environ.get(DATA_MODE_ENV, "demo")).strip().lower()
    if selected not in {"demo", "private"}:
        raise ValueError(
            f"{DATA_MODE_ENV} must be 'demo' or 'private'; got {selected!r}"
        )
    return selected


def get_data_root(mode: str | None = None) -> Path:
    selected = get_data_mode(mode)
    return ROOT / ("demo_data" if selected == "demo" else "data")


def resolve_data_path(*parts: str, mode: str | None = None) -> Path:
    if any(Path(part).is_absolute() or ".." in Path(part).parts for part in parts):
        raise ValueError("Data paths must stay within the selected project data root")
    return get_data_root(mode).joinpath(*parts)


def is_demo_mode(mode: str | None = None) -> bool:
    return get_data_mode(mode) == "demo"


def data_quality_for_mode(mode: str | None = None) -> str:
    return DEMO_DATA_QUALITY if is_demo_mode(mode) else "ARCHIVE_SOURCE_UNVERIFIED"

"""Exact-name coordinate joins for the Stage 6 historical control-tower map."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from scripts.data_paths import data_quality_for_mode


ROUTE_COLUMNS = [
    "corridor_id",
    "mode",
    "origin",
    "destination",
    "origin_code",
    "destination_code",
    "group",
    "benchmark_usd",
    "unit",
    "low_usd",
    "high_usd",
    "error_band_pct",
    "basis_grade",
    "transit_min_days",
    "transit_max_days",
    "as_of",
    "origin_country",
    "origin_continent",
    "origin_latitude",
    "origin_longitude",
    "destination_country",
    "destination_continent",
    "destination_latitude",
    "destination_longitude",
    "coordinate_match",
    "data_quality",
]

CONGESTION_COLUMNS = [
    "week_start",
    "port",
    "country",
    "port_country",
    "region",
    "throughput_teu_mn",
    "vessels_at_anchor",
    "avg_wait_days",
    "congestion_index",
    "port_utilization_pct",
    "berth_delay_hrs",
    "port_id",
    "continent",
    "locode",
    "latitude",
    "longitude",
    "data_quality",
]


def exact_unique_port_lookup(ports: pd.DataFrame) -> dict[str, pd.Series]:
    """Map exact normalized port names to unique rows with valid coordinates."""
    required = {"port", "latitude", "longitude"}
    missing = required.difference(ports.columns)
    if missing:
        raise ValueError(f"Port master is missing columns: {sorted(missing)}")

    frame = ports.copy()
    frame = frame[frame["port"].notna()].copy()
    frame["_normalized_name"] = frame["port"].astype(str).str.strip().str.casefold()
    frame = frame[
        frame["_normalized_name"].ne("")
        & ~frame["_normalized_name"].duplicated(keep=False)
    ].copy()
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    valid_coordinates = (
        np.isfinite(frame["latitude"])
        & np.isfinite(frame["longitude"])
        & frame["latitude"].between(-90, 90)
        & frame["longitude"].between(-180, 180)
    )
    frame = frame[valid_coordinates]
    return {
        row["_normalized_name"]: row
        for _, row in frame.iterrows()
    }


def match_ocean_route_endpoints(
    ports: pd.DataFrame, benchmarks: pd.DataFrame
) -> pd.DataFrame:
    """Resolve Ocean benchmark endpoints using exact, unique port-name matches.

    No fuzzy matching, geocoding, or route interpolation is performed. The
    benchmark and port data remain archive-source-unverified.
    """
    required = {
        "corridor_id",
        "mode",
        "origin",
        "destination",
        "benchmark_usd",
        "unit",
        "as_of",
    }
    missing = required.difference(benchmarks.columns)
    if missing:
        raise ValueError(f"Route benchmark is missing columns: {sorted(missing)}")

    lookup = exact_unique_port_lookup(ports)
    result: list[dict[str, Any]] = []
    ocean_routes = benchmarks[benchmarks["mode"].astype(str).str.casefold() == "ocean"]
    for _, route in ocean_routes.iterrows():
        origin_key = str(route["origin"]).strip().casefold()
        destination_key = str(route["destination"]).strip().casefold()
        origin = lookup.get(origin_key)
        destination = lookup.get(destination_key)
        if origin is None or destination is None:
            continue
        record = route.to_dict()
        record.update(
            {
                "origin_country": origin.get("country"),
                "origin_continent": origin.get("continent"),
                "origin_latitude": float(origin["latitude"]),
                "origin_longitude": float(origin["longitude"]),
                "destination_country": destination.get("country"),
                "destination_continent": destination.get("continent"),
                "destination_latitude": float(destination["latitude"]),
                "destination_longitude": float(destination["longitude"]),
                "coordinate_match": "Exact unique port-name match; source unverified",
                "data_quality": data_quality_for_mode(),
            }
        )
        result.append(record)
    return pd.DataFrame(result, columns=ROUTE_COLUMNS)


def match_congestion_to_ports(
    ports: pd.DataFrame, congestion: pd.DataFrame
) -> pd.DataFrame:
    """Attach coordinates only where congestion and a unique port name match."""
    required = {"week_start", "port", "country", "region"}
    missing = required.difference(congestion.columns)
    if missing:
        raise ValueError(f"Port congestion is missing columns: {sorted(missing)}")

    lookup = exact_unique_port_lookup(ports)
    result: list[dict[str, Any]] = []
    for _, observation in congestion.iterrows():
        key = str(observation["port"]).strip().casefold()
        port = lookup.get(key)
        if port is None:
            continue
        record = observation.to_dict()
        record.update(
            {
                "port_id": port.get("port_id"),
                "port_country": port.get("country"),
                "continent": port.get("continent"),
                "locode": port.get("locode"),
                "latitude": float(port["latitude"]),
                "longitude": float(port["longitude"]),
                "data_quality": data_quality_for_mode(),
            }
        )
        result.append(record)
    return pd.DataFrame(result, columns=CONGESTION_COLUMNS)

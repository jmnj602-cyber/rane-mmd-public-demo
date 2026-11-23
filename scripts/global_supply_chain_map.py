"""Exact-name coordinate joins for the Stage 6 historical control-tower map."""

from __future__ import annotations

import math
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

PORT_REGION_COLORS = {
    "Asia & Pacific": "#2c6782",
    "Europe": "#4b8297",
    "North America": "#3d7c78",
    "South America": "#8292a4",
    "Africa": "#6f9ea4",
}


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


def highlighted_port_ids(
    ports: pd.DataFrame,
    selected_continent: str | None = None,
    selected_port_id: str | None = None,
) -> set[str]:
    """Return port IDs emphasized by the current map focus."""
    if selected_port_id is not None:
        return {
            str(port_id)
            for port_id in ports["port_id"].dropna()
            if str(port_id) == str(selected_port_id)
        }
    if selected_continent in (None, "All continents"):
        return set(ports["port_id"].dropna().astype(str))
    return set(
        ports.loc[ports["continent"].eq(selected_continent), "port_id"]
        .dropna()
        .astype(str)
    )


def port_id_from_map_click(
    tooltip: object,
    clicked_location: object,
    zoom: object,
    ports: pd.DataFrame,
) -> str | None:
    """Resolve a Folium click to a visible port using its ID or map coordinates."""
    visible_port_ids = set(ports["port_id"].dropna().astype(str))
    if isinstance(tooltip, str):
        for port_id in visible_port_ids:
            if tooltip.endswith(f"[{port_id}]"):
                return port_id

    if not isinstance(clicked_location, dict):
        return None
    try:
        clicked_latitude = float(clicked_location["lat"])
        clicked_longitude = float(clicked_location["lng"])
        zoom_level = float(zoom)
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not math.isfinite(clicked_latitude)
        or not math.isfinite(clicked_longitude)
        or not math.isfinite(zoom_level)
        or not 0 <= zoom_level <= 22
    ):
        return None

    world_size = 256 * (2**zoom_level)

    def mercator_y(latitude: float) -> float:
        latitude = min(max(latitude, -85.05112878), 85.05112878)
        radians = math.radians(latitude)
        return (1 - math.asinh(math.tan(radians)) / math.pi) / 2

    matches: list[tuple[str, float]] = []
    for row in ports.itertuples(index=False):
        latitude = float(row.latitude)
        longitude = float(row.longitude)
        longitude_delta = abs(longitude - clicked_longitude) % 360
        longitude_delta = min(longitude_delta, 360 - longitude_delta)
        x_distance = longitude_delta / 360 * world_size
        y_distance = abs(mercator_y(latitude) - mercator_y(clicked_latitude)) * world_size
        pixel_distance = math.hypot(x_distance, y_distance)
        if pixel_distance <= 10:
            matches.append((str(row.port_id), pixel_distance))

    if not matches:
        return None
    nearest_distance = min(distance for _, distance in matches)
    nearest_ids = {
        port_id
        for port_id, distance in matches
        if math.isclose(distance, nearest_distance, abs_tol=0.25)
    }
    return next(iter(nearest_ids)) if len(nearest_ids) == 1 else None


def port_marker_styles(
    ports: pd.DataFrame,
    selected_continent: str | None = None,
    selected_port_id: str | None = None,
) -> dict[str, list[object]]:
    """Build muted or highlighted marker styles without changing port records."""
    focused = selected_port_id is not None or selected_continent not in (
        None,
        "All continents",
    )
    highlighted = highlighted_port_ids(
        ports,
        selected_continent=selected_continent,
        selected_port_id=selected_port_id,
    )
    colors: list[str] = []
    sizes: list[int] = []
    opacities: list[float] = []
    for row in ports.itertuples(index=False):
        is_highlighted = str(row.port_id) in highlighted
        if not focused:
            colors.append(PORT_REGION_COLORS.get(row.continent, "#8292a4"))
            sizes.append(7)
            opacities.append(0.78)
        elif is_highlighted and selected_port_id is not None:
            colors.append("#1f7a83")
            sizes.append(14)
            opacities.append(1.0)
        elif is_highlighted:
            colors.append("#2c6782")
            sizes.append(9)
            opacities.append(0.96)
        else:
            colors.append("#aebac5")
            sizes.append(4)
            opacities.append(0.12)
    return {"color": colors, "size": sizes, "opacity": opacities}


def filter_routes_for_focus(
    routes: pd.DataFrame,
    selected_continent: str | None = None,
    selected_port_name: str | None = None,
) -> pd.DataFrame:
    """Keep routes connected to the selected port or continent, if any."""
    if selected_port_name:
        port_key = selected_port_name.strip().casefold()
        mask = (
            routes["origin"].astype(str).str.strip().str.casefold().eq(port_key)
            | routes["destination"].astype(str).str.strip().str.casefold().eq(port_key)
        )
        return routes.loc[mask].copy()
    if selected_continent not in (None, "All continents"):
        mask = routes["origin_continent"].eq(selected_continent) | routes[
            "destination_continent"
        ].eq(selected_continent)
        return routes.loc[mask].copy()
    return routes.copy()


def filter_congestion_for_port(
    congestion: pd.DataFrame, selected_port_id: str | None
) -> pd.DataFrame:
    """Return a single port's congestion series when a port is selected."""
    if selected_port_id is None:
        return congestion.copy()
    return congestion.loc[
        congestion["port_id"].astype(str).eq(str(selected_port_id))
    ].copy()


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

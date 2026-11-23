"""Generate deterministic, fictional datasets for the public demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "demo_data"
SEED = 20261123
AS_OF = "2026-11-23"
QUALITY = "SYNTHETIC_ILLUSTRATIVE_DATA"
SYNTHETIC_SOURCE = "Synthetic illustrative demo generator"
SYNTHETIC_NOTE = (
    "Fictional deterministic demo record; not an observed market, trade, "
    "supplier, port, event, or RANE operational record."
)

COUNTRIES = [
    {"name": "Demo Republic A", "iso3": "DRA", "continent": "Asia & Pacific", "lat": 18.2, "lon": 116.8},
    {"name": "Demo Republic B", "iso3": "DRB", "continent": "Asia & Pacific", "lat": 29.4, "lon": 105.6},
    {"name": "Demo Republic C", "iso3": "DRC", "continent": "Europe", "lat": 53.1, "lon": 16.7},
    {"name": "Demo Republic D", "iso3": "DRD", "continent": "North America", "lat": 38.6, "lon": -102.4},
    {"name": "Demo Republic E", "iso3": "DRE", "continent": "South America", "lat": -18.3, "lon": -55.2},
    {"name": "Demo Republic F", "iso3": "DRF", "continent": "Africa", "lat": 4.7, "lon": 23.8},
]
REGIONS = [country["continent"] for country in COUNTRIES]
INDUSTRIES = [
    "Illustrative automotive",
    "Illustrative electronics",
    "Illustrative machinery",
    "Illustrative construction",
    "Illustrative chemicals",
    "Illustrative consumer goods",
    "Illustrative transport",
    "Illustrative manufacturing",
]
MATERIAL_COLUMNS = [
    "date", "record_type", "material", "value", "currency", "unit", "source",
    "source_url", "extraction_date", "data_quality", "source_series",
    "source_period", "source_note",
]


def _walk(
    rng: np.random.Generator,
    count: int,
    base: float,
    drift: float,
    noise: float,
) -> np.ndarray:
    changes = rng.normal(drift, noise, count)
    values = base * np.exp(np.cumsum(changes))
    return np.maximum(values, base * 0.1)


def _material_market(rng: np.random.Generator) -> pd.DataFrame:
    records: list[dict[str, Any]] = []

    def append_series(
        material: str,
        dates: pd.DatetimeIndex,
        base: float,
        currency: str,
        unit: str,
        frequency: str,
    ) -> None:
        values = _walk(rng, len(dates), base, 0.0007, 0.012 if frequency == "daily" else 0.035)
        for date_value, value in zip(dates, values):
            date_text = date_value.date().isoformat()
            records.append(
                {
                    "date": date_text,
                    "record_type": "material_price",
                    "material": material,
                    "value": round(float(value), 4),
                    "currency": currency,
                    "unit": unit,
                    "source": SYNTHETIC_SOURCE,
                    "source_url": "",
                    "extraction_date": AS_OF,
                    "data_quality": QUALITY,
                    "source_series": f"synthetic_{frequency}",
                    "source_period": date_text,
                    "source_note": SYNTHETIC_NOTE,
                }
            )

    daily_dates = pd.bdate_range("2024-01-01", AS_OF)
    for material, base in (("Copper", 8500), ("Nickel", 16500), ("Aluminium", 2350)):
        append_series(material, daily_dates, base, "USD", "USD/tonne", "daily")

    monthly_dates = pd.date_range("2019-01-01", AS_OF, freq="MS")
    for material, base, currency, unit in (
        ("Steel HR", 52000, "INR", "INR/tonne"),
        ("Steel CR", 61000, "INR", "INR/tonne"),
        ("Phenolic Resin", 1850, "USD", "USD/tonne"),
        ("Natural Rubber", 1.8, "USD", "USD/kg"),
    ):
        append_series(material, monthly_dates, base, currency, unit, "monthly")

    fx_dates = pd.bdate_range("2024-01-01", AS_OF)
    fx_values = _walk(rng, len(fx_dates), 83.0, 0.00012, 0.0015)
    for date_value, value in zip(fx_dates, fx_values):
        date_text = date_value.date().isoformat()
        records.append(
            {
                "date": date_text,
                "record_type": "reference_rate",
                "material": "USD/INR Reference Rate",
                "value": round(float(value), 4),
                "currency": "INR",
                "unit": "INR / 1 USD",
                "source": SYNTHETIC_SOURCE,
                "source_url": "",
                "extraction_date": AS_OF,
                "data_quality": QUALITY,
                "source_series": "synthetic_USD_INR",
                "source_period": date_text,
                "source_note": SYNTHETIC_NOTE,
            }
        )

    return (
        pd.DataFrame(records, columns=MATERIAL_COLUMNS)
        .sort_values(["record_type", "material", "date"], kind="stable")
        .reset_index(drop=True)
    )


def _chokepoints(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    chokepoints = [
        ("DEMO-CP-01", "Demo Strait Alpha", 42),
        ("DEMO-CP-02", "Demo Passage Bravo", 31),
        ("DEMO-CP-03", "Demo Channel Charlie", 24),
    ]
    dates = pd.date_range("2019-01-01", "2026-11-15", freq="D")
    daily_records: list[dict[str, Any]] = []
    for point_id, point, base in chokepoints:
        container = rng.poisson(base * 0.36, len(dates))
        bulk = rng.poisson(base * 0.24, len(dates))
        general = rng.poisson(base * 0.15, len(dates))
        roro = rng.poisson(base * 0.08, len(dates))
        tanker = rng.poisson(base * 0.17, len(dates))
        total = container + bulk + general + roro + tanker
        cap_container = np.full(len(dates), base * 0.6)
        cap_bulk = np.full(len(dates), base * 0.42)
        cap_general = np.full(len(dates), base * 0.26)
        cap_roro = np.full(len(dates), base * 0.15)
        cap_tanker = np.full(len(dates), base * 0.3)
        cap_total = cap_container + cap_bulk + cap_general + cap_roro + cap_tanker
        for i, date_value in enumerate(dates):
            daily_records.append(
                {
                    "date": date_value.date().isoformat(),
                    "chokepoint_id": point_id,
                    "chokepoint": point,
                    "transits_container": int(container[i]),
                    "transits_dry_bulk": int(bulk[i]),
                    "transits_general_cargo": int(general[i]),
                    "transits_roro": int(roro[i]),
                    "transits_tanker": int(tanker[i]),
                    "transits_cargo": int(total[i]),
                    "transits": int(total[i]),
                    "capacity_container": cap_container[i],
                    "capacity_dry_bulk": cap_bulk[i],
                    "capacity_general_cargo": cap_general[i],
                    "capacity_roro": cap_roro[i],
                    "capacity_tanker": cap_tanker[i],
                    "capacity_cargo": cap_total[i],
                    "capacity": cap_total[i],
                }
            )
    daily = pd.DataFrame(daily_records)
    daily["date"] = pd.to_datetime(daily["date"])
    daily["_month"] = daily["date"].dt.to_period("M")
    monthly = (
        daily.groupby(["_month", "chokepoint_id", "chokepoint"], as_index=False)
        .agg(
            days=("date", "nunique"),
            transits_per_day=("transits", "mean"),
            container_transits_per_day=("transits_container", "mean"),
            tanker_transits_per_day=("transits_tanker", "mean"),
            capacity_per_day=("capacity", "mean"),
        )
        .sort_values(["chokepoint_id", "_month"])
    )
    monthly["month"] = monthly["_month"].dt.to_timestamp()
    monthly["transits_yoy_pct"] = (
        monthly.groupby("chokepoint_id")["transits_per_day"].pct_change(12) * 100
    )
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily = daily.drop(columns="_month")
    monthly["month"] = monthly["month"].dt.strftime("%Y-%m-%d")
    monthly = monthly[
        [
            "month", "chokepoint_id", "chokepoint", "days", "transits_per_day",
            "container_transits_per_day", "tanker_transits_per_day",
            "capacity_per_day", "transits_yoy_pct",
        ]
    ]
    return daily, monthly


def _country_monthly(rng: np.random.Generator) -> pd.DataFrame:
    months = pd.date_range("2019-01-01", "2026-10-01", freq="MS")
    records: list[dict[str, Any]] = []
    entities = [*COUNTRIES, {"name": "Demo Aggregate", "iso3": "1"}]
    for entity in entities:
        n = len(months)
        portcalls = rng.poisson(550 + rng.random() * 500, n)
        trade = _walk(rng, n, 300, 0.0005, 0.025)
        yoy = pd.Series(trade).pct_change(12).to_numpy() * 100
        for i, month in enumerate(months):
            records.append(
                {
                    "month": month.date().isoformat(),
                    "iso3": entity["iso3"],
                    "country": entity["name"],
                    "days": month.days_in_month,
                    "portcalls": int(portcalls[i]),
                    "portcalls_container": int(portcalls[i] * 0.54),
                    "import": float(trade[i] * 0.52),
                    "export": float(trade[i] * 0.48),
                    "import_container": float(trade[i] * 0.28),
                    "export_container": float(trade[i] * 0.25),
                    "trade_yoy_pct": float(yoy[i]) if np.isfinite(yoy[i]) else np.nan,
                }
            )
    return pd.DataFrame(records)


def _country_daily(rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", AS_OF, freq="D")
    records: list[pd.DataFrame] = []
    entities = [*COUNTRIES, {"name": "Demo Aggregate", "iso3": "1", "continent": "Synthetic"}]
    for entity_index, entity in enumerate(entities):
        n = len(dates)
        container = rng.poisson(16 + entity_index * 3, n)
        dry_bulk = rng.poisson(8 + entity_index, n)
        general = rng.poisson(6 + entity_index, n)
        roro = rng.poisson(4 + entity_index, n)
        tanker = rng.poisson(5 + entity_index, n)
        portcalls = container + dry_bulk + general + roro + tanker
        imports = np.maximum(0, rng.normal(150, 25, n))
        exports = np.maximum(0, rng.normal(140, 23, n))
        shipment = imports + exports
        container_ma = pd.Series(container, dtype=float).rolling(30, min_periods=30).mean()
        shipment_ma = pd.Series(shipment).rolling(30, min_periods=30).mean()
        container_yoy = container_ma.pct_change(365) * 100
        shipment_yoy = shipment_ma.pct_change(365) * 100
        frame = pd.DataFrame(
            {
                "date": dates,
                "iso3": entity["iso3"],
                "country": entity["name"],
                "is_aggregate": entity["iso3"] == "1",
                "portcalls_container": container,
                "portcalls_dry_bulk": dry_bulk,
                "portcalls_general_cargo": general,
                "portcalls_roro": roro,
                "portcalls_tanker": tanker,
                "portcalls_cargo": portcalls,
                "portcalls": portcalls,
                "import_container": imports * 0.52,
                "import_dry_bulk": imports * 0.2,
                "import_general_cargo": imports * 0.11,
                "import_roro": imports * 0.07,
                "import_tanker": imports * 0.1,
                "import_cargo": imports,
                "import": imports,
                "export_container": exports * 0.5,
                "export_dry_bulk": exports * 0.21,
                "export_general_cargo": exports * 0.12,
                "export_roro": exports * 0.07,
                "export_tanker": exports * 0.1,
                "export_cargo": exports,
                "export": exports,
                "shipment": shipment,
                "portcalls_container_30ma": container_ma,
                "portcalls_container_30ma_yoy": container_yoy,
                "shipment_30ma": shipment_ma,
                "shipment_30ma_yoy": shipment_yoy,
            }
        )
        records.append(frame)
    return pd.concat(records, ignore_index=True)


def _gscpi(rng: np.random.Generator) -> pd.DataFrame:
    months = pd.date_range("1998-01-01", "2026-10-01", freq="MS")
    values = 0.1 + np.sin(np.arange(len(months)) / 13) * 0.7
    values += rng.normal(0, 0.18, len(months))
    return pd.DataFrame(
        {"month": months.strftime("%Y-%m-%d"), "gscpi": np.round(values, 4)}
    )


def _disruption_events(rng: np.random.Generator) -> pd.DataFrame:
    kinds = ["logistics", "labor", "geopolitical", "natural", "energy"]
    records = []
    for i in range(36):
        date_value = pd.Timestamp("2019-01-01") + pd.DateOffset(months=i * 2 + 1)
        kind = kinds[i % len(kinds)]
        records.append(
            {
                "date": date_value.date().isoformat(),
                "year": date_value.year,
                "event_name": f"Demo {kind.title()} Event {i + 1:02d}",
                "disruption_type": kind,
                "region_affected": REGIONS[i % len(REGIONS)],
                "duration_days": int(rng.integers(3, 80)),
                "bdi_shock_pct": int(rng.integers(-25, 45)),
                "freight_rate_shock_pct": int(rng.integers(-20, 55)),
                "severity": ["Low", "Moderate", "High"][i % 3],
                "gdp_impact_pct": round(float(rng.uniform(-1.5, 0.5)), 3),
                "trade_volume_impact_pct": round(float(rng.uniform(-25, 5)), 3),
                "recovery_months": int(rng.integers(1, 16)),
                "is_pandemic": int(kind == "natural" and i % 4 == 0),
                "is_geopolitical": int(kind == "geopolitical"),
                "is_natural": int(kind == "natural"),
                "is_financial": int(kind == "energy" and i % 2 == 0),
                "straits_affected": int(kind == "logistics" and i % 2 == 0),
                "port_closure": int(kind == "logistics" and i % 3 == 0),
            }
        )
    return pd.DataFrame(records)


def _industry_exposure(rng: np.random.Generator) -> pd.DataFrame:
    records = []
    for industry in INDUSTRIES:
        for year in range(2017, 2027):
            factors = rng.uniform(0.08, 0.88, 8)
            records.append(
                {
                    "year": year,
                    "industry": industry,
                    "pandemic_exposure": factors[0],
                    "geopolitical_exposure": factors[1],
                    "natural_disaster_exposure": factors[2],
                    "tariff_exposure": factors[3],
                    "logistics_exposure": factors[4],
                    "energy_exposure": factors[5],
                    "labor_exposure": factors[6],
                    "cyber_exposure": factors[7],
                    "overall_vulnerability": float(factors.mean()),
                    "inventory_days": int(rng.integers(8, 95)),
                    "supplier_concentration_hhi": round(float(rng.uniform(0.08, 0.52)), 3),
                    "just_in_time_dependency": round(float(rng.uniform(0.1, 0.95)), 3),
                    "nearshoring_score_2024": round(float(rng.uniform(0.1, 0.9)), 3),
                }
            )
    return pd.DataFrame(records)


def _tariff_timeline(rng: np.random.Generator) -> pd.DataFrame:
    records = []
    for i in range(42):
        date_value = pd.Timestamp("2019-03-01") + pd.DateOffset(months=i * 2)
        imposing = COUNTRIES[i % len(COUNTRIES)]["name"]
        target = COUNTRIES[(i + 1) % len(COUNTRIES)]["name"]
        kind = i % 4
        records.append(
            {
                "tariff_id": f"DEMO-TARIFF-{i + 1:03d}",
                "date": date_value.date().isoformat(),
                "year": date_value.year,
                "month": date_value.month,
                "imposing_country": imposing,
                "target_country": target,
                "policy_name": f"Illustrative tariff scenario {i + 1:02d}",
                "tariff_rate_pct": round(float(rng.uniform(1, 28)), 2),
                "estimated_value_usd_bn": round(float(rng.uniform(0.1, 22)), 3),
                "description": "Synthetic policy example; no real law or jurisdiction is represented.",
                "is_trump_1_0": 0,
                "is_biden": 0,
                "is_trump_2_0": 0,
                "is_retaliation": int(kind == 1),
                "is_section_232": 0,
                "is_section_301": 0,
                "is_ieepa": 0,
            }
        )
    return pd.DataFrame(records)


def _trade_flows(rng: np.random.Generator) -> pd.DataFrame:
    categories = [
        ("Illustrative materials", "synthetic industrial inputs"),
        ("Illustrative components", "fictional machine components"),
        ("Illustrative consumer goods", "demo consumer products"),
    ]
    records = []
    for year in range(2019, 2027):
        for i, exporter in enumerate(COUNTRIES):
            for j, importer in enumerate(COUNTRIES):
                if i == j:
                    continue
                for category_index, (category, goods) in enumerate(categories):
                    records.append(
                        {
                            "year": year,
                            "exporter": exporter["name"],
                            "importer": importer["name"],
                            "trade_category": category,
                            "key_goods": goods,
                            "trade_value_bn_usd": round(float(rng.uniform(0.2, 45)), 3),
                            "yoy_growth_pct": (
                                np.nan if year == 2019 else round(float(rng.normal(2, 11)), 2)
                            ),
                            "effective_tariff_rate_pct": round(float(rng.uniform(0, 18)), 2),
                            "trade_active": 1,
                            "supply_chain_integrated": int((i + j + category_index) % 2 == 0),
                            "concentration_risk": round(float(rng.uniform(0.05, 0.95)), 3),
                        }
                    )
    return pd.DataFrame(records)


def _ports(rng: np.random.Generator) -> pd.DataFrame:
    records = []
    for country_index, country in enumerate(COUNTRIES):
        for port_index in range(2):
            lat_offset = (-1 if port_index == 0 else 1) * float(rng.uniform(1.0, 5.0))
            lon_offset = (-1 if port_index == 0 else 1) * float(rng.uniform(1.0, 5.0))
            counts = rng.integers(15, 160, 5)
            records.append(
                {
                    "port_id": f"DEMO-PORT-{country_index + 1:02d}-{port_index + 1}",
                    "port": f"Demo {chr(65 + country_index)} Harbor {port_index + 1}",
                    "country": country["name"],
                    "iso3": country["iso3"],
                    "continent": country["continent"],
                    "locode": f"DEMO{country_index + 1:02d}{port_index + 1}",
                    "latitude": country["lat"] + lat_offset,
                    "longitude": country["lon"] + lon_offset,
                    "vessels_total": int(counts.sum()),
                    "vessels_container": int(counts[0]),
                    "vessels_dry_bulk": int(counts[1]),
                    "vessels_general_cargo": int(counts[2]),
                    "vessels_roro": int(counts[3]),
                    "vessels_tanker": int(counts[4]),
                    "industry_1": INDUSTRIES[country_index % len(INDUSTRIES)],
                    "industry_2": INDUSTRIES[(country_index + 1) % len(INDUSTRIES)],
                    "industry_3": INDUSTRIES[(country_index + 2) % len(INDUSTRIES)],
                    "share_of_country_imports": round(float(rng.uniform(0.03, 0.32)), 3),
                    "share_of_country_exports": round(float(rng.uniform(0.03, 0.32)), 3),
                }
            )
    return pd.DataFrame(records)


def _port_congestion(rng: np.random.Generator, ports: pd.DataFrame) -> pd.DataFrame:
    weeks = pd.date_range("2019-01-07", "2026-11-16", freq="W-MON")
    records = []
    for port in ports.itertuples(index=False):
        baseline = float(rng.uniform(0.4, 1.2))
        for i, week in enumerate(weeks):
            index = float(np.clip(1.0 + 0.3 * np.sin(i / 9) + rng.normal(0, 0.15), 0.2, 2.2))
            records.append(
                {
                    "week_start": week.date().isoformat(),
                    "year": week.year,
                    "port": port.port,
                    "country": port.country,
                    "region": port.continent,
                    "throughput_teu_mn": int(rng.integers(10, 300)),
                    "vessels_at_anchor": int(rng.integers(0, 45)),
                    "avg_wait_days": round(baseline * index, 2),
                    "congestion_index": round(index * 100, 2),
                    "port_utilization_pct": round(float(np.clip(0.55 + index / 5 + rng.normal(0, 0.03), 0.4, 0.99)), 3),
                    "berth_delay_hrs": round(float(rng.uniform(0, 35) * index), 2),
                }
            )
    return pd.DataFrame(records)


def _shipping_rates(rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range("2019-01-01", AS_OF, freq="MS")
    bdi = _walk(rng, len(dates), 1150, 0.002, 0.08)
    container = _walk(rng, len(dates), 1800, 0.001, 0.06)
    air = _walk(rng, len(dates), 4.2, 0.0005, 0.025)
    tanker = _walk(rng, len(dates), 22000, 0.0006, 0.05)
    bulk = _walk(rng, len(dates), 12000, 0.0008, 0.05)
    pressure = 0.3 + np.sin(np.arange(len(dates)) / 8) * 0.4 + rng.normal(0, 0.08, len(dates))
    on_time = np.clip(rng.normal(0.91, 0.035, len(dates)), 0.68, 0.98)
    frame = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "baltic_dry_index": np.round(bdi).astype(int),
            "container_rate_usd_40ft": np.round(container).astype(int),
            "air_cargo_rate_usd_kg": np.round(air, 2),
            "bdi_mom_change_pct": pd.Series(bdi).pct_change().to_numpy() * 100,
            "container_yoy_pct": pd.Series(container).pct_change(12).to_numpy() * 100,
            "tanker_rate_aframax_usd_day": np.round(tanker).astype(int),
            "bulk_carrier_handysize_usd_day": np.round(bulk).astype(int),
            "supply_chain_pressure_index": np.round(pressure, 4),
            "on_time_delivery_pct": np.round(on_time, 3),
        }
    )
    return frame


def _route_benchmark(rng: np.random.Generator, ports: pd.DataFrame) -> pd.DataFrame:
    port_names = ports["port"].tolist()
    records = []
    routes: list[tuple[str, str, str, str]] = []
    for i in range(12):
        routes.append(
            (
                "Ocean",
                port_names[i],
                port_names[(i + 5) % len(port_names)],
                f"Demo Ocean Group {i % 3 + 1}",
            )
        )
    for i in range(6):
        routes.append(
            (
                "Air",
                f"Demo Air Hub {i + 1}",
                f"Demo Air Hub {((i + 2) % 6) + 1}",
                "Illustrative air corridors",
            )
        )
    for i in range(6):
        routes.append(
            (
                "Truck",
                f"Demo Inland Hub {i + 1}",
                f"Demo Inland Hub {((i + 3) % 6) + 1}",
                "Illustrative land corridors",
            )
        )
    for i, (mode, origin, destination, group) in enumerate(routes):
        benchmark = float(rng.uniform(500, 9000))
        records.append(
            {
                "corridor_id": f"DEMO-CORRIDOR-{i + 1:03d}",
                "mode": mode,
                "origin_code": f"DEMO-O-{i + 1:03d}",
                "origin": origin,
                "destination_code": f"DEMO-D-{i + 1:03d}",
                "destination": destination,
                "group": group,
                "benchmark_usd": round(benchmark, 2),
                "unit": ["USD per illustrative 40ft container", "USD per illustrative tonne"][i % 2],
                "low_usd": round(benchmark * 0.85, 2),
                "high_usd": round(benchmark * 1.15, 2),
                "error_band_pct": 15,
                "basis_grade": "Synthetic illustration only",
                "transit_min_days": int(rng.integers(3, 18)),
                "transit_max_days": int(rng.integers(20, 55)),
                "as_of": AS_OF,
            }
        )
    return pd.DataFrame(records)


def _metadata(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    descriptions = {
        "processed/material_market_data_integrated.csv": (
            "Synthetic material observations and a synthetic FX reference series."
        ),
        "raw/stage_5/risk/chokepoint_daily.csv": "Synthetic daily transit and capacity records.",
        "raw/stage_5/risk/chokepoint_monthly.csv": "Synthetic monthly chokepoint aggregates.",
        "raw/stage_5/risk/country_monthly.csv": "Synthetic country-level monthly measures.",
        "raw/stage_5/risk/country_daily.parquet": "Synthetic daily country measures; aggregate row uses code 1.",
        "raw/stage_5/risk/gscpi.csv": "Synthetic index-shaped series; not the official GSCPI.",
        "raw/stage_5/risk/disruption_events.csv": "Fictional disruption scenarios, not recorded events.",
        "raw/stage_5/risk/industry_exposure.csv": "Fictional industry-level illustrative indicators.",
        "raw/stage_5/risk/tariff_timeline.csv": "Fictional policy scenarios, not actual tariff actions.",
        "raw/stage_5/risk/trade_flows.csv": "Fictional country-pair/category values, not customs records.",
        "raw/stage_5/logistics/ports.csv": "Fictional ports and generated coordinates.",
        "raw/stage_5/logistics/port_congestion.csv": "Fictional weekly port measures.",
        "raw/stage_5/logistics/shipping_rates.csv": "Fictional monthly shipping indices and rates.",
        "raw/stage_5/logistics/benchmark-2026-11.csv": "Fictional one-date route benchmark snapshot.",
    }
    datasets: dict[str, Any] = {}
    for filename, frame in frames.items():
        date_columns = [
            column for column in ("date", "month", "week_start", "as_of")
            if column in frame.columns
        ]
        date_range = {}
        for column in date_columns:
            dates = pd.to_datetime(frame[column], errors="coerce").dropna()
            date_range[column] = {
                "start": dates.min().date().isoformat(),
                "end": dates.max().date().isoformat(),
            }
        datasets[filename] = {
            "description": descriptions[filename],
            "records": len(frame),
            "columns": [
                {"name": column, "dtype": str(frame[column].dtype)}
                for column in frame.columns
            ],
            "date_ranges": date_range,
            "relationships": (
                "Demo country codes/names and port names join exactly across the "
                "generated country, port, congestion, and route files."
            ),
        }
    return {
        "synthetic": True,
        "data_quality": QUALITY,
        "notice": (
            "Every record in this directory is synthetic and illustrative. "
            "No original workspace dataset or private RANE record was read or copied. "
            "No value represents an actual market observation, supplier, transaction, "
            "country statistic, event, port condition, route quote, or live intelligence."
        ),
        "seed": SEED,
        "scenario_as_of_date": AS_OF,
        "generated_by": "scripts/generate_demo_data.py",
        "datasets": datasets,
    }


def generate(force: bool = False) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    chokepoint_daily, chokepoint_monthly = _chokepoints(rng)
    ports = _ports(rng)
    frames = {
        "processed/material_market_data_integrated.csv": _material_market(rng),
        "raw/stage_5/risk/chokepoint_daily.csv": chokepoint_daily,
        "raw/stage_5/risk/chokepoint_monthly.csv": chokepoint_monthly,
        "raw/stage_5/risk/country_monthly.csv": _country_monthly(rng),
        "raw/stage_5/risk/country_daily.parquet": _country_daily(rng),
        "raw/stage_5/risk/gscpi.csv": _gscpi(rng),
        "raw/stage_5/risk/disruption_events.csv": _disruption_events(rng),
        "raw/stage_5/risk/industry_exposure.csv": _industry_exposure(rng),
        "raw/stage_5/risk/tariff_timeline.csv": _tariff_timeline(rng),
        "raw/stage_5/risk/trade_flows.csv": _trade_flows(rng),
        "raw/stage_5/logistics/ports.csv": ports,
        "raw/stage_5/logistics/port_congestion.csv": _port_congestion(rng, ports),
        "raw/stage_5/logistics/shipping_rates.csv": _shipping_rates(rng),
        "raw/stage_5/logistics/benchmark-2026-11.csv": _route_benchmark(rng, ports),
    }
    existing = [OUTPUT / name for name in frames if (OUTPUT / name).exists()]
    metadata_path = OUTPUT / "metadata.json"
    if metadata_path.exists():
        existing.append(metadata_path)
    if existing and not force:
        raise FileExistsError(
            "Refusing to overwrite existing demo files; pass --force to regenerate."
        )

    for name, frame in frames.items():
        path = OUTPUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".parquet":
            parquet_frame = frame.copy()
            parquet_frame["iso3"] = parquet_frame["iso3"].astype("string")
            parquet_frame["country"] = parquet_frame["country"].astype("string")
            parquet_frame.to_parquet(path, index=False)
            frames[name] = parquet_frame
        else:
            frame.to_csv(path, index=False, date_format="%Y-%m-%d")

    metadata = _metadata(frames)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readme = OUTPUT / "README.md"
    readme.write_text(
        "# Public demo data\n\n"
        "Every file in this directory is synthetic and illustrative. "
        "It contains no actual RANE or source-market records. See "
        "`metadata.json` for schemas, record counts, date spans, seed, and "
        "cross-file relationships. Rebuild deterministically with "
        "`python -m scripts.generate_demo_data`; existing files are protected "
        "from overwrite unless `--force` is explicitly supplied.\n",
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace the specifically named synthetic demo files.",
    )
    args = parser.parse_args()
    metadata = generate(force=args.force)
    print(f"Generated {len(metadata['datasets'])} synthetic datasets under {OUTPUT}")
    for filename, dataset in metadata["datasets"].items():
        print(f"{filename}: {dataset['records']} rows")


if __name__ == "__main__":
    main()

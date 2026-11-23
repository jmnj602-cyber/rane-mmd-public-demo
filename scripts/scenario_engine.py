"""Transparent case-study scenario calculations for the management simulator.

All operational allocations in this module are editable demonstration assumptions.
The financial starting values are the user-supplied FY25 case-study baseline.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd


MATERIALS = (
    "Copper",
    "Nickel",
    "Aluminium",
    "Steel HR",
    "Steel CR",
    "Phenolic Resin",
    "Natural Rubber",
)

CASE_STUDY_BASELINE = {
    "revenue_cr": 3421.0,
    "ebitda_cr": 297.7,
    "ebitda_margin_pct": 8.7,
    "pat_cr": 37.6,
    "raw_material_spend_cr": 1223.0,
    "oem_cost_pass_through_pct": 50.0,
    "container_rate_usd_40ft": 2172.0,
    "annual_inbound_ocean_freight_cr": 25.0,
}

DEFAULT_MATERIAL_MIX_PCT = {
    "Copper": 20.0,
    "Nickel": 10.0,
    "Aluminium": 15.0,
    "Steel HR": 15.0,
    "Steel CR": 10.0,
    "Phenolic Resin": 15.0,
    "Natural Rubber": 15.0,
}

DEFAULT_DIVISION_ALLOCATION_PCT = {
    "Illustrative division 1": 40.0,
    "Illustrative division 2": 35.0,
    "Illustrative division 3": 25.0,
}

DEFAULT_USD_LINKED_SHARE = {
    "Copper": 0.85,
    "Nickel": 0.80,
    "Aluminium": 0.80,
    "Steel HR": 0.25,
    "Steel CR": 0.25,
    "Phenolic Resin": 0.55,
    "Natural Rubber": 0.75,
}

DEFAULT_TARIFF_EXPOSURE = {
    "Copper": 0.75,
    "Nickel": 0.80,
    "Aluminium": 0.75,
    "Steel HR": 0.20,
    "Steel CR": 0.20,
    "Phenolic Resin": 0.70,
    "Natural Rubber": 0.65,
}

DEFAULT_REFERENCE_INR_PER_TONNE = {
    "Copper": 820000.0,
    "Nickel": 1450000.0,
    "Aluminium": 235000.0,
    "Steel HR": 68000.0,
    "Steel CR": 76000.0,
    "Phenolic Resin": 190000.0,
    "Natural Rubber": 185000.0,
}

SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "Base Case": {
        "material_shocks_pct": {material: 0.0 for material in MATERIALS},
        "freight_shock_pct": 0.0,
        "fx_shock_pct": 0.0,
        "tariff_shock_pct": 0.0,
        "demand_change_pct": 0.0,
        "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    },
    "Red Sea / Hormuz Crisis": {
        "material_shocks_pct": {material: 0.0 for material in MATERIALS},
        "freight_shock_pct": 35.0,
        "fx_shock_pct": 5.0,
        "tariff_shock_pct": 0.0,
        "demand_change_pct": 0.0,
        "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    },
    "Metal Shock": {
        "material_shocks_pct": {
            "Copper": 18.0,
            "Nickel": 22.0,
            "Aluminium": 15.0,
            "Steel HR": 12.0,
            "Steel CR": 12.0,
            "Phenolic Resin": 0.0,
            "Natural Rubber": 0.0,
        },
        "freight_shock_pct": 8.0,
        "fx_shock_pct": 3.0,
        "tariff_shock_pct": 0.0,
        "demand_change_pct": 0.0,
        "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    },
    "Tariff and FX Escalation": {
        "material_shocks_pct": {material: 0.0 for material in MATERIALS},
        "freight_shock_pct": 5.0,
        "fx_shock_pct": 8.0,
        "tariff_shock_pct": 12.0,
        "demand_change_pct": 0.0,
        "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    },
    "Demand Recession": {
        "material_shocks_pct": {material: 0.0 for material in MATERIALS},
        "freight_shock_pct": -10.0,
        "fx_shock_pct": 2.0,
        "tariff_shock_pct": 0.0,
        "demand_change_pct": -15.0,
        "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    },
}

DEFAULT_ACTION_ASSUMPTIONS = {
    "Expedite critical materials": {
        "mitigation_pct": 25.0,
        "implementation_cost_cr": 0.75,
        "exposure": "Editable inventory-disruption exposure",
        "functions": "MMD / Procurement; Production; Logistics; Finance",
    },
    "Increase safety stock": {
        "mitigation_pct": 15.0,
        "implementation_cost_cr": 1.0,
        "exposure": "Editable inventory-disruption exposure",
        "functions": "MMD / Procurement; Finance; Production; Warehousing",
    },
    "Change shipment mode": {
        "mitigation_pct": 20.0,
        "implementation_cost_cr": 0.5,
        "exposure": "Positive freight cost increase",
        "functions": "Logistics and Exports; Production; Finance; Quality",
    },
    "Consolidate container shipments": {
        "mitigation_pct": 8.0,
        "implementation_cost_cr": 0.25,
        "exposure": "Scenario annual freight cost",
        "functions": "MMD / Procurement; Logistics and Exports; Finance",
    },
    "Explore alternate suppliers": {
        "mitigation_pct": 12.0,
        "implementation_cost_cr": 0.8,
        "exposure": "Largest positive material cost increase",
        "functions": "MMD / Procurement; Quality; Production; Finance",
    },
    "Negotiate OEM cost pass-through": {
        "mitigation_pct": 25.0,
        "implementation_cost_cr": 0.2,
        "exposure": "Unrecovered positive cost pressure",
        "functions": "Sales; Finance; MMD / Procurement; Legal",
    },
    "Adjust procurement timing": {
        "mitigation_pct": 10.0,
        "implementation_cost_cr": 0.15,
        "exposure": "Positive raw-material cost increase",
        "functions": "MMD / Procurement; Finance; Production; Sales",
    },
    "Review affected production schedules": {
        "mitigation_pct": 10.0,
        "implementation_cost_cr": 0.3,
        "exposure": "Positive raw-material cost increase",
        "functions": "Production; Sales; HR; Quality; Finance",
    },
}


def _finite_number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not np.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _ratio(value: Any, name: str) -> float:
    result = _finite_number(value, name)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return result


def _positive(value: Any, name: str) -> float:
    result = _finite_number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _shock_fraction(value_pct: Any, name: str) -> float:
    result = _finite_number(value_pct, name)
    if result <= -100:
        raise ValueError(f"{name} must be greater than -100 percent")
    return result / 100


def normalized_mix(mix_pct: Mapping[str, Any]) -> dict[str, float]:
    """Normalize positive editable relative weights to shares summing to one."""
    weights = {}
    for material in MATERIALS:
        weight = _finite_number(
            mix_pct.get(material, 0), f"{material} mix weight"
        )
        if weight < 0:
            raise ValueError(f"{material} mix weight cannot be negative")
        weights[material] = weight
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("At least one material mix weight must be positive")
    return {material: weight / total for material, weight in weights.items()}


def calculate_scenario(
    *,
    material_mix_pct: Mapping[str, Any] | None = None,
    usd_linked_share: Mapping[str, Any] | None = None,
    tariff_exposure: Mapping[str, Any] | None = None,
    reference_inr_per_tonne: Mapping[str, Any] | None = None,
    material_shocks_pct: Mapping[str, Any] | None = None,
    tariff_shock_pct: float = 0,
    fx_shock_pct: float = 0,
    freight_shock_pct: float = 0,
    demand_change_pct: float = 0,
    oem_pass_through_pct: float = 50,
    tax_rate_pct: float = 25,
    base_usd_inr: float = 83.5,
) -> dict[str, Any]:
    """Calculate scenario costs from the case-study baseline and visible inputs."""
    mix_input = (
        DEFAULT_MATERIAL_MIX_PCT
        if material_mix_pct is None
        else material_mix_pct
    )
    usd_input = (
        DEFAULT_USD_LINKED_SHARE
        if usd_linked_share is None
        else usd_linked_share
    )
    tariff_input = (
        DEFAULT_TARIFF_EXPOSURE
        if tariff_exposure is None
        else tariff_exposure
    )
    price_input = (
        DEFAULT_REFERENCE_INR_PER_TONNE
        if reference_inr_per_tonne is None
        else reference_inr_per_tonne
    )
    shock_input = {} if material_shocks_pct is None else material_shocks_pct

    shares = normalized_mix(mix_input)
    usd_shares = {
        material: _ratio(usd_input.get(material, 0), f"{material} USD-linked share")
        for material in MATERIALS
    }
    tariff_shares = {
        material: _ratio(tariff_input.get(material, 0), f"{material} tariff exposure")
        for material in MATERIALS
    }
    reference_prices = {
        material: _positive(
            price_input.get(material, 0), f"{material} reference cost per tonne"
        )
        for material in MATERIALS
    }
    price_shocks = {
        material: _shock_fraction(
            shock_input.get(material, 0), f"{material} price shock"
        )
        for material in MATERIALS
    }
    tariff_shock = _shock_fraction(tariff_shock_pct, "Tariff shock")
    fx_shock = _shock_fraction(fx_shock_pct, "USD/INR shock")
    freight_shock = _shock_fraction(freight_shock_pct, "Freight shock")
    demand_change = _shock_fraction(demand_change_pct, "Demand change")
    pass_through = _ratio(
        _finite_number(oem_pass_through_pct, "OEM pass-through") / 100,
        "OEM pass-through",
    )
    tax_rate = _ratio(
        _finite_number(tax_rate_pct, "Tax rate") / 100,
        "Tax rate",
    )
    base_usd_inr = _positive(base_usd_inr, "Base USD/INR rate")
    scenario_usd_inr = base_usd_inr * (1 + fx_shock)
    volume_factor = 1 + demand_change
    baseline_spend = CASE_STUDY_BASELINE["raw_material_spend_cr"]

    per_material: list[dict[str, Any]] = []
    stage_volume = 0.0
    stage_price = 0.0
    stage_tariff = 0.0
    stage_fx = 0.0
    baseline_tonnage = 0.0
    for material in MATERIALS:
        budget_cr = baseline_spend * shares[material]
        base_price = reference_prices[material]
        budget_tonnage = budget_cr * 10_000_000 / base_price
        baseline_tonnage += budget_tonnage

        volume_spend = budget_cr * volume_factor
        material_spend = volume_spend * (1 + price_shocks[material])
        tariff_spend = material_spend * (
            1 + tariff_shock * tariff_shares[material]
        )
        fx_factor = (
            1
            + fx_shock * usd_shares[material]
        )
        final_spend = tariff_spend * fx_factor
        stage_volume += volume_spend
        stage_price += material_spend
        stage_tariff += tariff_spend
        stage_fx += final_spend

        local_fx_factor = (1 - usd_shares[material]) + (
            usd_shares[material] * scenario_usd_inr / base_usd_inr
        )
        material_cost_per_tonne = (
            base_price
            * (1 + price_shocks[material])
            * (1 + tariff_shock * tariff_shares[material])
            * local_fx_factor
        )
        per_material.append(
            {
                "material": material,
                "mix_weight_pct": shares[material] * 100,
                "baseline_spend_cr": budget_cr,
                "reference_cost_inr_per_tonne": base_price,
                "baseline_tonnage_assumption": budget_tonnage,
                "material_price_shock_pct": price_shocks[material] * 100,
                "usd_linked_share_pct": usd_shares[material] * 100,
                "tariff_exposure_pct": tariff_shares[material] * 100,
                "scenario_material_cost_inr_per_tonne": material_cost_per_tonne,
                "scenario_material_spend_cr": final_spend,
            }
        )

    annual_freight = CASE_STUDY_BASELINE["annual_inbound_ocean_freight_cr"]
    freight_after_volume = annual_freight * volume_factor
    freight_after_rate = freight_after_volume * (1 + freight_shock)
    scenario_freight = freight_after_rate * (1 + fx_shock)
    freight_per_tonne = (
        annual_freight * 10_000_000 / baseline_tonnage
        if baseline_tonnage > 0
        else 0.0
    )
    scenario_freight_per_tonne = (
        freight_per_tonne * (1 + freight_shock) * (1 + fx_shock)
    )
    for row in per_material:
        row["allocated_freight_inr_per_tonne"] = scenario_freight_per_tonne
        row["scenario_landed_cost_inr_per_tonne"] = (
            row["scenario_material_cost_inr_per_tonne"]
            + scenario_freight_per_tonne
        )

    material_delta = stage_fx - baseline_spend
    freight_delta = scenario_freight - annual_freight
    gross_cost_pressure = material_delta + freight_delta
    oem_recovery = max(0.0, gross_cost_pressure) * pass_through
    unrecovered_cost = gross_cost_pressure - oem_recovery

    revenue = CASE_STUDY_BASELINE["revenue_cr"] * volume_factor
    revenue_change = revenue - CASE_STUDY_BASELINE["revenue_cr"]
    contribution_margin_before_materials_and_freight = (
        CASE_STUDY_BASELINE["ebitda_cr"]
        + CASE_STUDY_BASELINE["raw_material_spend_cr"]
        + annual_freight
    ) / CASE_STUDY_BASELINE["revenue_cr"]
    demand_ebitda_effect = (
        revenue_change * contribution_margin_before_materials_and_freight
    )
    revised_ebitda = (
        CASE_STUDY_BASELINE["ebitda_cr"]
        + demand_ebitda_effect
        - unrecovered_cost
    )
    ebitda_change = revised_ebitda - CASE_STUDY_BASELINE["ebitda_cr"]
    revised_margin = (revised_ebitda / revenue * 100) if revenue else np.nan
    revised_pat = CASE_STUDY_BASELINE["pat_cr"] + ebitda_change * (1 - tax_rate)

    bridge = pd.DataFrame(
        [
            {"component": "Demand / volume effect", "change_cr": stage_volume - baseline_spend},
            {"component": "Material price shock", "change_cr": stage_price - stage_volume},
            {"component": "Tariff effect", "change_cr": stage_tariff - stage_price},
            {"component": "USD/INR effect on materials", "change_cr": stage_fx - stage_tariff},
            {"component": "Freight volume effect", "change_cr": freight_after_volume - annual_freight},
            {"component": "Freight rate effect", "change_cr": freight_after_rate - freight_after_volume},
            {"component": "Freight FX effect", "change_cr": scenario_freight - freight_after_rate},
        ]
    )
    financial = {
        "revenue_cr": revenue,
        "raw_material_spend_cr": stage_fx,
        "incremental_material_cost_cr": material_delta,
        "annual_freight_cr": scenario_freight,
        "incremental_freight_cost_cr": freight_delta,
        "tariff_impact_cr": stage_tariff - stage_price,
        "fx_material_impact_cr": stage_fx - stage_tariff,
        "gross_cost_pressure_cr": gross_cost_pressure,
        "oem_cost_recovery_cr": oem_recovery,
        "unrecovered_cost_cr": unrecovered_cost,
        "demand_ebitda_effect_cr": demand_ebitda_effect,
        "demand_contribution_margin_pct": (
            contribution_margin_before_materials_and_freight * 100
        ),
        "ebitda_cr": revised_ebitda,
        "ebitda_change_cr": ebitda_change,
        "ebitda_margin_pct": revised_margin,
        "pat_cr": revised_pat,
        "scenario_usd_inr": scenario_usd_inr,
        "normalized_material_mix_pct": {
            material: share * 100 for material, share in shares.items()
        },
        "oem_cost_pass_through_pct": pass_through * 100,
        "tax_rate_pct": tax_rate * 100,
    }
    return {
        "baseline": CASE_STUDY_BASELINE.copy(),
        "financial": financial,
        "material_costs": pd.DataFrame(per_material),
        "cost_bridge": bridge,
        "baseline_tonnage_assumption": baseline_tonnage,
        "baseline_freight_per_tonne_inr": freight_per_tonne,
        "scenario_freight_per_tonne_inr": scenario_freight_per_tonne,
        "baseline_material_stage_cr": baseline_spend,
    }


def allocate_division_costs(
    scenario: Mapping[str, Any],
    division_allocation_pct: Mapping[str, Any] | pd.DataFrame,
) -> pd.DataFrame:
    """Allocate case-study cost changes across editable illustrative divisions."""
    if isinstance(division_allocation_pct, pd.DataFrame):
        required = {"Division / line", "Allocation weight (%)"}
        missing = required.difference(division_allocation_pct.columns)
        if missing:
            raise ValueError(
                f"Division allocation is missing columns: {sorted(missing)}"
            )
        raw_names = division_allocation_pct["Division / line"].astype(str).str.strip()
        raw_weights = pd.to_numeric(
            division_allocation_pct["Allocation weight (%)"], errors="coerce"
        )
        if raw_names.duplicated().any():
            raise ValueError("Illustrative division/line names must be unique")
        division_allocation_pct = dict(zip(raw_names, raw_weights))
    if not division_allocation_pct:
        raise ValueError("At least one illustrative division allocation is required")
    shares: dict[str, float] = {}
    for label, raw_weight in division_allocation_pct.items():
        name = str(label).strip()
        if not name:
            raise ValueError("Illustrative division/line names cannot be blank")
        if name in shares:
            raise ValueError(f"Duplicate illustrative division/line: {name}")
        weight = _finite_number(raw_weight, f"{name} allocation")
        if weight < 0:
            raise ValueError(f"{name} allocation cannot be negative")
        shares[name] = weight
    total = sum(shares.values())
    if total <= 0:
        raise ValueError("At least one illustrative division allocation must be positive")

    financial = scenario["financial"]
    baseline_material = CASE_STUDY_BASELINE["raw_material_spend_cr"]
    baseline_freight = CASE_STUDY_BASELINE["annual_inbound_ocean_freight_cr"]
    rows = []
    for division, weight in shares.items():
        share = weight / total
        baseline_cost = (baseline_material + baseline_freight) * share
        scenario_cost = (
            float(financial["raw_material_spend_cr"])
            + float(financial["annual_freight_cr"])
        ) * share
        rows.append(
            {
                "division_or_line": division,
                "normalized_allocation_pct": share * 100,
                "baseline_material_spend_cr": baseline_material * share,
                "scenario_material_spend_cr": (
                    float(financial["raw_material_spend_cr"]) * share
                ),
                "incremental_material_cost_cr": (
                    float(financial["incremental_material_cost_cr"]) * share
                ),
                "baseline_freight_cr": baseline_freight * share,
                "scenario_freight_cr": float(financial["annual_freight_cr"]) * share,
                "incremental_freight_cost_cr": (
                    float(financial["incremental_freight_cost_cr"]) * share
                ),
                "baseline_combined_cost_cr": baseline_cost,
                "scenario_combined_cost_cr": scenario_cost,
                "incremental_combined_cost_cr": scenario_cost - baseline_cost,
                "data_quality": "SYNTHETIC_ILLUSTRATIVE_ASSUMPTION",
            }
        )
    return pd.DataFrame(rows)


def calculate_inventory_runway(
    scenario: Mapping[str, Any],
    *,
    inventory_days: float,
    supplier_lead_time_days: float,
    safety_stock_days: float,
    demand_change_pct: float = 0,
) -> dict[str, float | str]:
    """Calculate illustrative inventory cover from an editable days-on-hand input."""
    stock_days = _finite_number(inventory_days, "Inventory days")
    lead_days = _finite_number(supplier_lead_time_days, "Supplier lead time")
    safety_days = _finite_number(safety_stock_days, "Safety stock")
    if min(stock_days, lead_days, safety_days) < 0:
        raise ValueError("Inventory, lead-time, and safety-stock days cannot be negative")
    demand_factor = 1 + _shock_fraction(demand_change_pct, "Demand change")
    if demand_factor <= 0:
        raise ValueError("Demand-adjusted daily consumption must be positive")

    annual_tonnage = float(scenario["baseline_tonnage_assumption"])
    daily_baseline = annual_tonnage / 365
    current_stock = daily_baseline * stock_days
    daily_scenario = daily_baseline * demand_factor
    cover = current_stock / daily_scenario if daily_scenario else np.inf
    runway_buffer = cover - lead_days - safety_days
    if cover <= lead_days:
        status = "Reorder review: cover is at or below lead time"
    elif runway_buffer < 0:
        status = "Below lead time plus safety-stock buffer"
    else:
        status = "Within configured inventory buffer"
    average_cost = (
        float(scenario["baseline"]["raw_material_spend_cr"])
        * 10_000_000
        / annual_tonnage
        if annual_tonnage > 0
        else 0
    )
    return {
        "daily_consumption_tonnes": daily_scenario,
        "current_inventory_tonnes": current_stock,
        "days_of_cover": cover,
        "supplier_lead_time_days": lead_days,
        "safety_stock_days": safety_days,
        "days_until_potential_stockout": cover,
        "buffer_after_lead_and_safety_days": runway_buffer,
        "inventory_value_cr_illustrative": current_stock * average_cost / 10_000_000,
        "status": status,
    }


def calculate_container_model(
    scenario: Mapping[str, Any],
    *,
    base_usd_inr: float,
    freight_shock_pct: float,
    fx_shock_pct: float,
    share_40ft_pct: float = 70,
    cost_20ft_ratio: float = 75,
    payload_20ft_tonnes: float = 24,
    payload_40ft_tonnes: float = 26,
    payload_utilization_pct: float = 75,
) -> dict[str, Any]:
    """Estimate container-equivalents and payload from the case-study freight spend."""
    rate_40ft = CASE_STUDY_BASELINE["container_rate_usd_40ft"] * (
        1 + _shock_fraction(freight_shock_pct, "Freight shock")
    )
    rate_20ft = rate_40ft * _ratio(
        _finite_number(cost_20ft_ratio, "20-foot cost ratio") / 100,
        "20-foot cost ratio",
    )
    share_40ft = _ratio(
        _finite_number(share_40ft_pct, "40-foot container share") / 100,
        "40-foot container share",
    )
    utilization = _ratio(
        _finite_number(payload_utilization_pct, "Payload utilization") / 100,
        "Payload utilization",
    )
    capacity_20 = _positive(payload_20ft_tonnes, "20-foot payload capacity")
    capacity_40 = _positive(payload_40ft_tonnes, "40-foot payload capacity")
    fx_rate = _positive(base_usd_inr, "Base USD/INR rate") * (
        1 + _shock_fraction(fx_shock_pct, "USD/INR shock")
    )
    blended_cost_inr = (
        (1 - share_40ft) * rate_20ft + share_40ft * rate_40ft
    ) * fx_rate
    annual_freight_cr = float(scenario["financial"]["annual_freight_cr"])
    total_count = annual_freight_cr * 10_000_000 / blended_cost_inr
    count_20 = total_count * (1 - share_40ft)
    count_40 = total_count * share_40ft
    payload_20 = capacity_20 * utilization
    payload_40 = capacity_40 * utilization
    tonnes_20 = count_20 * payload_20
    tonnes_40 = count_40 * payload_40
    total_tonnes = tonnes_20 + tonnes_40
    rows = pd.DataFrame(
        [
            {
                "container_type": "20-foot",
                "container_count_equivalent": count_20,
                "payload_capacity_tonnes": capacity_20,
                "actual_payload_tonnes": payload_20,
                "utilization_pct": utilization * 100,
                "freight_cost_inr_per_container": rate_20ft * fx_rate,
                "freight_cost_inr_per_tonne": (
                    rate_20ft * fx_rate / payload_20 if payload_20 else np.nan
                ),
                "material_transported_tonnes": tonnes_20,
            },
            {
                "container_type": "40-foot",
                "container_count_equivalent": count_40,
                "payload_capacity_tonnes": capacity_40,
                "actual_payload_tonnes": payload_40,
                "utilization_pct": utilization * 100,
                "freight_cost_inr_per_container": rate_40ft * fx_rate,
                "freight_cost_inr_per_tonne": (
                    rate_40ft * fx_rate / payload_40 if payload_40 else np.nan
                ),
                "material_transported_tonnes": tonnes_40,
            },
        ]
    )
    mix = scenario["financial"]["normalized_material_mix_pct"]
    material_transport = pd.DataFrame(
        [
            {
                "material": material,
                "illustrative_mix_pct": mix[material],
                "material_transported_tonnes": total_tonnes * mix[material] / 100,
            }
            for material in MATERIALS
        ]
    )
    return {
        "containers": rows,
        "material_transport": material_transport,
        "container_count_equivalent": total_count,
        "material_transported_tonnes": total_tonnes,
        "weighted_freight_cost_inr_per_tonne": (
            annual_freight_cr * 10_000_000 / total_tonnes
            if total_tonnes
            else np.nan
        ),
        "data_quality": "SYNTHETIC_ILLUSTRATIVE_ASSUMPTION",
    }


def rank_management_actions(
    scenario: Mapping[str, Any],
    inventory: Mapping[str, Any],
    action_assumptions: Mapping[str, Mapping[str, Any]] | None = None,
    inventory_disruption_exposure_cr: float = 0,
) -> pd.DataFrame:
    """Rank review actions using explicitly supplied mitigation and cost inputs."""
    assumptions = action_assumptions or DEFAULT_ACTION_ASSUMPTIONS
    financial = scenario["financial"]
    positive_material = max(0.0, float(financial["incremental_material_cost_cr"]))
    positive_freight = max(0.0, float(financial["incremental_freight_cost_cr"]))
    gross_pressure = max(0.0, float(financial["gross_cost_pressure_cr"]))
    inventory_disruption_exposure = max(
        0.0,
        _finite_number(
            inventory_disruption_exposure_cr,
            "Inventory-disruption exposure",
        ),
    )
    remaining_pass_through = max(
        0.0, 100 - float(financial["oem_cost_pass_through_pct"])
    ) / 100
    rows: list[dict[str, Any]] = []
    for action, config in DEFAULT_ACTION_ASSUMPTIONS.items():
        supplied = assumptions.get(action, config)
        mitigation = _ratio(
            _finite_number(supplied.get("mitigation_pct", 0), f"{action} mitigation")
            / 100,
            f"{action} mitigation",
        )
        cost = _finite_number(
            supplied.get("implementation_cost_cr", 0), f"{action} cost"
        )
        if cost < 0:
            raise ValueError(f"{action} cost cannot be negative")

        exposure = config["exposure"]
        if action in {"Expedite critical materials", "Increase safety stock"}:
            exposure_cr = inventory_disruption_exposure
        elif action in {
            "Adjust procurement timing",
            "Review affected production schedules",
        }:
            exposure_cr = positive_material
        elif action == "Change shipment mode":
            exposure_cr = positive_freight
        elif action == "Consolidate container shipments":
            exposure_cr = max(
                0.0, float(financial["annual_freight_cr"])
            )
        elif action == "Explore alternate suppliers":
            exposure_cr = max(
                float(scenario["material_costs"]["scenario_material_spend_cr"].sub(
                    scenario["material_costs"]["baseline_spend_cr"]
                ).max()),
                0.0,
            )
        else:
            exposure_cr = gross_pressure * remaining_pass_through

        inventory_risk = (
            float(inventory["buffer_after_lead_and_safety_days"]) < 0
        )
        if action in {"Expedite critical materials", "Increase safety stock"}:
            if not inventory_risk or inventory_disruption_exposure <= 0:
                exposure_cr = 0.0
        elif action == "Review affected production schedules":
            if not inventory_risk and positive_material == 0:
                exposure_cr = 0.0

        benefit = exposure_cr * mitigation
        net = benefit - cost
        before = exposure_cr
        after = max(0.0, exposure_cr - benefit)
        rows.append(
            {
                "action": action,
                "triggering_risk": (
                    f"{exposure}: ₹{exposure_cr:.2f} Cr; "
                    f"inventory status: {inventory['status']}"
                ),
                "exposure_before_cr": before,
                "estimated_benefit_cr": benefit,
                "estimated_implementation_cost_cr": cost,
                "net_impact_cr_illustrative": net,
                "exposure_after_cr": after,
                "before_after_comparison": f"₹{before:.2f} Cr → ₹{after:.2f} Cr",
                "mitigation_assumption_pct": mitigation * 100,
                "priority_ranking_basis": (
                    "Ranked by illustrative net impact; ties retain action order"
                ),
                "suppliers_affected": "Not supplied",
                "functions_affected": config["functions"],
                "data_quality": "SYNTHETIC_ILLUSTRATIVE_ASSUMPTION",
            }
        )
    result = pd.DataFrame(rows)
    return (
        result.sort_values(
            "net_impact_cr_illustrative", ascending=False, kind="stable"
        )
        .reset_index(drop=True)
        .assign(priority_rank=lambda frame: np.arange(1, len(frame) + 1))
    )


def build_forecast_or_scenario(
    history: pd.DataFrame,
    *,
    value_column: str,
    date_column: str,
    data_quality: str,
    horizon_months: int,
    scenario_shock_pct: float,
    scenario_range_pct: float = 8.0,
) -> dict[str, Any]:
    """Forecast only verified monthly series; otherwise return an indexed scenario."""
    if horizon_months not in {3, 6, 12}:
        raise ValueError("Forecast horizon must be 3, 6, or 12 months")
    scenario_range = _shock_fraction(scenario_range_pct, "Scenario range")
    if scenario_range < 0:
        raise ValueError("Scenario range cannot be negative")
    quality = str(data_quality)
    rows = history.copy()
    if not rows.empty and {date_column, value_column}.issubset(rows.columns):
        rows[date_column] = pd.to_datetime(rows[date_column], errors="coerce")
        rows[value_column] = pd.to_numeric(rows[value_column], errors="coerce")
        rows = rows.dropna(subset=[date_column, value_column]).sort_values(date_column)
        rows = rows.drop_duplicates(subset=[date_column], keep="last")
    else:
        rows = pd.DataFrame(columns=[date_column, value_column])

    trusted_source = quality in {
        "OFFICIAL_SOURCE_MATCH_VERIFIED",
        "OFFICIAL_SOURCE_VALUE",
    } and not rows.empty
    if trusted_source:
        monthly = rows.set_index(date_column)[value_column].resample("MS").last().dropna()
        complete_index = pd.date_range(monthly.index.min(), monthly.index.max(), freq="MS")
        trusted_source = monthly.index.equals(complete_index)
    if trusted_source and len(monthly) >= 36:
        values = monthly.to_numpy(dtype=float)
        residuals = values[12:] - values[:-12]
        residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
        latest = float(values[-1])
        latest_date = monthly.index[-1]
        forecast_rows = []
        for step in range(1, horizon_months + 1):
            point = float(values[-12 + ((step - 1) % 12)])
            half_width = 1.96 * residual_std * np.sqrt(step)
            forecast_rows.append(
                {
                    "date": latest_date + pd.offsets.MonthBegin(step),
                    "value": point,
                    "lower": max(0.0, point - half_width),
                    "upper": point + half_width,
                }
            )
        historical = pd.DataFrame(
            {"date": monthly.index, "value": values}
        )
        forecast = pd.DataFrame(forecast_rows)
        method = "Seasonal naive (12-month lag); 95% residual interval"
        rationale = (
            "At least 36 contiguous official monthly observations are available, "
            "so a repeating annual seasonal baseline can be estimated."
        )
        projection_type = "STATISTICAL_FORECAST"
    elif trusted_source and len(monthly) >= 12:
        values = monthly.to_numpy(dtype=float)
        alpha = 0.3
        level = float(values[0])
        one_step_errors = []
        for observed in values[1:]:
            one_step_errors.append(float(observed) - level)
            level = alpha * float(observed) + (1 - alpha) * level
        residual_std = (
            float(np.std(one_step_errors, ddof=1))
            if len(one_step_errors) > 1
            else 0.0
        )
        latest_date = monthly.index[-1]
        forecast_rows = []
        for step in range(1, horizon_months + 1):
            half_width = 1.96 * residual_std * np.sqrt(step)
            forecast_rows.append(
                {
                    "date": latest_date + pd.offsets.MonthBegin(step),
                    "value": level,
                    "lower": max(0.0, level - half_width),
                    "upper": max(0.0, level + half_width),
                }
            )
        historical = pd.DataFrame(
            {"date": monthly.index, "value": values}
        )
        forecast = pd.DataFrame(forecast_rows)
        method = "Simple exponential smoothing (alpha=0.30); 95% residual interval"
        rationale = (
            "There are 12–35 contiguous official months; the series is long enough "
            "to smooth its level but too short for a stable annual seasonal estimate."
        )
        projection_type = "STATISTICAL_FORECAST"
    elif trusted_source and len(monthly) >= 6:
        values = monthly.to_numpy(dtype=float)
        time = np.arange(len(values), dtype=float)
        slope, intercept = np.polyfit(time, values, 1)
        fitted = intercept + slope * time
        residual_std = float(np.sqrt(np.sum((values - fitted) ** 2) / max(1, len(values) - 2)))
        centered_sum_squares = float(np.sum((time - time.mean()) ** 2))
        latest_date = monthly.index[-1]
        forecast_rows = []
        for step in range(1, horizon_months + 1):
            future_time = float(len(values) + step - 1)
            point = max(0.0, float(intercept + slope * future_time))
            leverage = (
                1 + 1 / len(values)
                + (future_time - float(time.mean())) ** 2
                / centered_sum_squares
                if centered_sum_squares > 0
                else 1 + 1 / len(values)
            )
            half_width = 1.96 * residual_std * np.sqrt(leverage)
            forecast_rows.append(
                {
                    "date": latest_date + pd.offsets.MonthBegin(step),
                    "value": point,
                    "lower": max(0.0, point - half_width),
                    "upper": max(0.0, point + half_width),
                }
            )
        historical = pd.DataFrame(
            {"date": monthly.index, "value": values}
        )
        forecast = pd.DataFrame(forecast_rows)
        method = "Linear trend OLS; 95% residual-based prediction interval"
        rationale = (
            "There are 6–11 contiguous official months; only an exploratory linear "
            "level/trend fit is used, with no seasonal pattern inferred."
        )
        projection_type = "STATISTICAL_FORECAST"
    else:
        historical = pd.DataFrame(
            {
                "date": rows[date_column].to_numpy(),
                "value": rows[value_column].to_numpy(dtype=float),
            }
        ) if not rows.empty else pd.DataFrame(columns=["date", "value"])
        last_date = (
            pd.Timestamp(historical["date"].max())
            if not historical.empty
            else pd.Timestamp.today().normalize().replace(day=1)
        )
        scenario_change = _shock_fraction(
            scenario_shock_pct, "Scenario shock"
        )
        shock_index = 100 * (1 + scenario_change)
        forecast_rows = []
        for step in range(1, horizon_months + 1):
            half_width = max(0.0, scenario_range) * np.sqrt(step / 12)
            forecast_rows.append(
                {
                    "date": last_date + pd.offsets.MonthBegin(step),
                    "value": shock_index,
                    "lower": max(0.0, shock_index * (1 - half_width)),
                    "upper": shock_index * (1 + half_width),
                }
            )
        forecast = pd.DataFrame(forecast_rows)
        method = (
            "Illustrative scenario projection; base index 100, selected shock held constant"
        )
        rationale = (
            "The source quality or history length does not support a statistical "
            "market forecast; the output is a user-controlled scenario, not an estimate."
        )
        projection_type = "ILLUSTRATIVE_SCENARIO_NOT_A_FORECAST"

    if not historical.empty:
        anchor = float(historical["value"].iloc[-1])
        if anchor != 0:
            historical["index_100"] = historical["value"] / anchor * 100
        else:
            historical["index_100"] = np.nan
    else:
        historical["index_100"] = pd.Series(dtype=float)
    if projection_type == "STATISTICAL_FORECAST":
        anchor = float(historical["value"].iloc[-1])
        if anchor != 0:
            for column in ("value", "lower", "upper"):
                forecast[f"{column}_index_100"] = forecast[column] / anchor * 100
        else:
            forecast[["value_index_100", "lower_index_100", "upper_index_100"]] = np.nan
    else:
        forecast["value_index_100"] = forecast["value"]
        forecast["lower_index_100"] = forecast["lower"]
        forecast["upper_index_100"] = forecast["upper"]
    return {
        "historical": historical,
        "projection": forecast,
        "method": method,
        "method_rationale": rationale,
        "projection_type": projection_type,
        "data_quality": quality,
        "horizon_months": horizon_months,
        "chart_unit": "Index (latest historical value = 100)",
    }

"""Streamlit interface for the explainable FY25 management case-study simulator."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts.data_paths import is_demo_mode
from scripts.material_price_intelligence import MATERIAL_LABELS, material_rows
from scripts.scenario_engine import (
    CASE_STUDY_BASELINE,
    DEFAULT_ACTION_ASSUMPTIONS,
    DEFAULT_DIVISION_ALLOCATION_PCT,
    DEFAULT_MATERIAL_MIX_PCT,
    DEFAULT_REFERENCE_INR_PER_TONNE,
    DEFAULT_TARIFF_EXPOSURE,
    DEFAULT_USD_LINKED_SHARE,
    MATERIALS,
    SCENARIO_PRESETS,
    build_forecast_or_scenario,
    allocate_division_costs,
    calculate_container_model,
    calculate_inventory_runway,
    calculate_scenario,
    rank_management_actions,
)


_SLIDER_DEFAULTS = {
    "freight_shock_pct": 0.0,
    "fx_shock_pct": 0.0,
    "tariff_shock_pct": 0.0,
    "demand_change_pct": 0.0,
    "oem_pass_through_pct": CASE_STUDY_BASELINE["oem_cost_pass_through_pct"],
    "tax_rate_pct": 25.0,
    "base_usd_inr": 83.5,
    "inventory_days": 30.0,
    "supplier_lead_time_days": 45.0,
    "safety_stock_days": 15.0,
    "scenario_range_pct": 8.0,
}

_MATERIAL_SHOCK_KEYS = {
    material: f"scenario_material_shock_{index}"
    for index, material in enumerate(MATERIALS)
}


def _apply_preset() -> None:
    preset = SCENARIO_PRESETS[st.session_state["scenario_preset_select"]]
    for material, key in _MATERIAL_SHOCK_KEYS.items():
        st.session_state[key] = preset["material_shocks_pct"][material]
    for name in (
        "freight_shock_pct",
        "fx_shock_pct",
        "tariff_shock_pct",
        "demand_change_pct",
    ):
        st.session_state[f"scenario_{name}"] = preset[name]
    st.session_state["scenario_oem_pass_through_pct"] = preset[
        "oem_pass_through_pct"
    ]


def _reset_to_base_case() -> None:
    st.session_state["scenario_preset_select"] = "Base Case"
    for key in _MATERIAL_SHOCK_KEYS.values():
        st.session_state[key] = 0.0
    for name in (
        "freight_shock_pct",
        "fx_shock_pct",
        "tariff_shock_pct",
        "demand_change_pct",
    ):
        st.session_state[f"scenario_{name}"] = 0.0
    st.session_state["scenario_oem_pass_through_pct"] = (
        CASE_STUDY_BASELINE["oem_cost_pass_through_pct"]
    )


def _initialize_controls() -> None:
    st.session_state.setdefault("scenario_preset_select", "Base Case")
    for material, key in _MATERIAL_SHOCK_KEYS.items():
        st.session_state.setdefault(key, 0.0)
    for name, value in _SLIDER_DEFAULTS.items():
        state_key = f"scenario_{name}"
        st.session_state.setdefault(state_key, value)


def _material_configuration() -> pd.DataFrame:
    rows = []
    for material in MATERIALS:
        rows.append(
            {
                "Material": material,
                "Mix weight (%)": DEFAULT_MATERIAL_MIX_PCT[material],
                "USD-linked share (%)": DEFAULT_USD_LINKED_SHARE[material] * 100,
                "Tariff exposure (%)": DEFAULT_TARIFF_EXPOSURE[material] * 100,
                "Reference cost (INR/tonne)": DEFAULT_REFERENCE_INR_PER_TONNE[
                    material
                ],
            }
        )
    return pd.DataFrame(rows)


def _edit_action_assumptions() -> tuple[dict[str, dict[str, float]], float]:
    action_frame = pd.DataFrame(
        [
            {
                "Action": action,
                "Mitigation assumption (%)": config["mitigation_pct"],
                "Implementation cost (₹ Cr)": config["implementation_cost_cr"],
            }
            for action, config in DEFAULT_ACTION_ASSUMPTIONS.items()
        ]
    )
    with st.expander("Action mitigation and implementation-cost assumptions"):
        st.caption(
            "All benefits and costs are editable illustrative assumptions, not "
            "validated savings or actual project estimates."
        )
        st.session_state.setdefault("scenario_inventory_disruption_exposure", 0.0)
        inventory_disruption_exposure = st.number_input(
            "Potential inventory-disruption exposure (₹ Cr)",
            min_value=0.0,
            step=0.5,
            key="scenario_inventory_disruption_exposure",
            help=(
                "Defaults to zero because no RANE stock-out loss or disruption "
                "exposure evidence was supplied."
            ),
        )
        edited_actions = st.data_editor(
            action_frame,
            key="scenario_action_assumptions",
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            column_config={
                "Action": st.column_config.TextColumn(disabled=True),
                "Mitigation assumption (%)": st.column_config.NumberColumn(
                    min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
                ),
                "Implementation cost (₹ Cr)": st.column_config.NumberColumn(
                    min_value=0.0, step=0.1, format="₹%.2f"
                ),
            },
        )
    return (
        {
            str(row["Action"]): {
                "mitigation_pct": float(row["Mitigation assumption (%)"]),
                "implementation_cost_cr": float(row["Implementation cost (₹ Cr)"]),
            }
            for _, row in edited_actions.iterrows()
        },
        float(inventory_disruption_exposure),
    )


def _edit_assumptions() -> tuple[pd.DataFrame, dict[str, object]]:
    st.markdown("#### Editable material cost assumptions")
    st.caption(
        "All material mix, currency exposure, tariff exposure, and reference-cost "
        "values below are SYNTHETIC / ILLUSTRATIVE. Mix weights are normalized to "
        "100% in calculations; these are not RANE procurement shares or market prices."
    )
    config = st.data_editor(
        _material_configuration(),
        key="scenario_material_configuration",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_config={
            "Material": st.column_config.TextColumn(disabled=True),
            "Mix weight (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
            ),
            "USD-linked share (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
            ),
            "Tariff exposure (%)": st.column_config.NumberColumn(
                min_value=0.0, max_value=100.0, step=1.0, format="%.1f"
            ),
            "Reference cost (INR/tonne)": st.column_config.NumberColumn(
                min_value=1.0, step=1000.0, format="₹%.0f"
            ),
        },
    )
    mix = dict(zip(config["Material"], config["Mix weight (%)"]))
    usd_share = {
        row["Material"]: float(row["USD-linked share (%)"]) / 100
        for _, row in config.iterrows()
    }
    tariff_exposure = {
        row["Material"]: float(row["Tariff exposure (%)"]) / 100
        for _, row in config.iterrows()
    }
    reference_cost = {
        row["Material"]: float(row["Reference cost (INR/tonne)"])
        for _, row in config.iterrows()
    }
    division_config = pd.DataFrame(
        [
            {"Division / line": label, "Allocation weight (%)": weight}
            for label, weight in DEFAULT_DIVISION_ALLOCATION_PCT.items()
        ]
    )
    st.markdown("#### Illustrative division / line allocation")
    st.caption(
        "No division-level consumption data was supplied. These generic labels "
        "and editable weights allocate case-study totals only; they are not RANE divisions."
    )
    division_config = st.data_editor(
        division_config,
        key="scenario_division_allocation",
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Division / line": st.column_config.TextColumn(),
            "Allocation weight (%)": st.column_config.NumberColumn(
                min_value=0.0, step=1.0, format="%.1f"
            ),
        },
    )
    return config, {
        "mix": mix,
        "usd_share": usd_share,
        "tariff_exposure": tariff_exposure,
        "reference_cost": reference_cost,
        "division_allocation": division_config,
    }


def _render_inputs() -> tuple[dict[str, object], pd.DataFrame]:
    _initialize_controls()
    st.subheader("Scenario assumptions")
    st.caption(
        "Select a preset to populate its starting assumptions, then adjust any "
        "control. Presets are fictional stress cases, not predictions or live alerts."
    )
    top = st.columns([2, 1])
    top[0].selectbox(
        "Scenario preset",
        list(SCENARIO_PRESETS),
        key="scenario_preset_select",
        on_change=_apply_preset,
    )
    top[1].button(
        "Reset to baseline",
        key="scenario_reset_to_base",
        on_click=_reset_to_base_case,
        use_container_width=True,
        help="Clears shocks and restores the FY25 case-study assumptions.",
    )

    st.markdown("##### Price and cost shocks")
    shock_columns = st.columns(4)
    material_shocks: dict[str, float] = {}
    for index, material in enumerate(MATERIALS):
        column = shock_columns[index % len(shock_columns)]
        material_shocks[material] = column.slider(
            f"{material} price shock (%)",
            min_value=-90.0,
            max_value=150.0,
            step=1.0,
            key=_MATERIAL_SHOCK_KEYS[material],
        )
    scalar_columns = st.columns(4)
    scalar_values: dict[str, float] = {}
    slider_specs = (
        ("freight_shock_pct", "40-foot freight shock (%)", -80.0, 200.0),
        ("fx_shock_pct", "USD/INR change (%)", -50.0, 100.0),
        ("tariff_shock_pct", "Tariff shock (%)", -90.0, 200.0),
        ("demand_change_pct", "Demand change (%)", -50.0, 50.0),
        ("oem_pass_through_pct", "OEM cost pass-through (%)", 0.0, 100.0),
        ("tax_rate_pct", "Tax assumption (%)", 0.0, 50.0),
    )
    for index, (name, label, lower, upper) in enumerate(slider_specs):
        scalar_values[name] = scalar_columns[index % len(scalar_columns)].slider(
            label,
            min_value=lower,
            max_value=upper,
            step=1.0,
            key=f"scenario_{name}",
        )

    with st.expander("Material mix and per-tonne assumptions", expanded=False):
        config, assumptions = _edit_assumptions()
    base_usd_inr = st.number_input(
        "Illustrative base USD/INR rate",
        min_value=1.0,
        max_value=500.0,
        step=0.1,
        key="scenario_base_usd_inr",
        help="An editable calculation assumption; not a new FX observation.",
    )
    scalar_values["tax_rate_pct"] = float(
        st.session_state["scenario_tax_rate_pct"]
    )
    scalar_values["oem_pass_through_pct"] = float(
        st.session_state["scenario_oem_pass_through_pct"]
    )
    scalar_values["base_usd_inr"] = float(base_usd_inr)
    scenario_inputs: dict[str, object] = {
        "material_mix_pct": assumptions["mix"],
        "usd_linked_share": assumptions["usd_share"],
        "tariff_exposure": assumptions["tariff_exposure"],
        "reference_inr_per_tonne": assumptions["reference_cost"],
        "division_allocation": assumptions["division_allocation"],
        "material_shocks_pct": material_shocks,
        **scalar_values,
    }
    return scenario_inputs, config


def _render_forecast(
    integrated: pd.DataFrame,
    shipping_rates: pd.DataFrame,
    scenario_inputs: Mapping[str, object],
    config: pd.DataFrame,
    horizon_months: int,
    scenario_range_pct: float,
) -> None:
    st.subheader("Price and freight outlook")
    st.caption(
        "Statistical forecasts are restricted to sufficiently long, verified "
        "monthly source series. Other histories are shown with an explicitly "
        "illustrative scenario projection, not a market forecast."
    )
    options = [*MATERIALS, "Global container freight (40-foot)"]
    selected = st.selectbox("Series", options, key="scenario_projection_series")
    if selected == "Global container freight (40-foot)":
        rows = shipping_rates[["date", "container_rate_usd_40ft"]].copy()
        quality = (
            "SYNTHETIC_ILLUSTRATIVE_DATA"
            if is_demo_mode()
            else "ARCHIVE_SOURCE_UNVERIFIED"
        )
        value_column = "container_rate_usd_40ft"
        display_name = "Container benchmark (USD per 40-foot container)"
        shock_pct = (
            (1 + float(st.session_state["scenario_freight_shock_pct"]) / 100)
            * (1 + float(st.session_state["scenario_fx_shock_pct"]) / 100)
            - 1
        ) * 100
    else:
        rows = material_rows(integrated, selected)
        if selected == "Natural Rubber" and not is_demo_mode() and not rows.empty:
            rows = rows[pd.to_datetime(rows["date"]).dt.year >= 2004].copy()
        quality_values = (
            sorted(rows["data_quality"].dropna().astype(str).unique())
            if not rows.empty
            else []
        )
        quality = (
            quality_values[0]
            if len(quality_values) == 1
            else ", ".join(quality_values)
            if quality_values
            else "NO_MARKET_PRICE_DATA"
        )
        value_column = "value"
        display_name = MATERIAL_LABELS[selected]
        shock_pct = float(scenario_inputs["material_shocks_pct"].get(selected, 0.0))
        row = config.loc[config["Material"] == selected].iloc[0]
        price_shock = 1 + shock_pct / 100
        tariff_factor = 1 + (
            float(st.session_state["scenario_tariff_shock_pct"])
            / 100
            * float(row["Tariff exposure (%)"])
            / 100
        )
        fx_factor = 1 + (
            float(st.session_state["scenario_fx_shock_pct"])
            / 100
            * float(row["USD-linked share (%)"])
            / 100
        )
        shock_pct = (price_shock * tariff_factor * fx_factor - 1) * 100
    projection = build_forecast_or_scenario(
        rows,
        value_column=value_column,
        date_column="date",
        data_quality=quality,
        horizon_months=horizon_months,
        scenario_shock_pct=shock_pct,
        scenario_range_pct=scenario_range_pct,
    )
    st.markdown(f"**{display_name}** · `{projection['data_quality']}`")
    st.info(
        f"Method: {projection['method']}. {projection['method_rationale']} "
        + (
            "The historical source is plotted as an index (latest historical "
            "value = 100). Bands are residual-based intervals, not a guarantee."
            if projection["projection_type"] == "STATISTICAL_FORECAST"
            else "The selected scenario is an illustrative indexed path; its band "
            "is a user-controlled assumption range, not a confidence interval."
        )
    )

    figure = go.Figure()
    historical = projection["historical"]
    forecast = projection["projection"]
    if not historical.empty:
        figure.add_trace(
            go.Scatter(
                x=historical["date"],
                y=historical["index_100"],
                name=(
                    "Synthetic history"
                    if "SYNTHETIC" in quality
                    else "Observed history (quality as labelled)"
                ),
                mode="lines",
                line={"color": "#2c6782", "width": 2},
                customdata=historical["value"],
                hovertemplate=(
                    "Date: %{x|%Y-%m}<br>Index: %{y:.1f}"
                    "<br>Original value: %{customdata:,.4f}<extra></extra>"
                ),
            )
        )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["value_index_100"],
            name=(
                "Seasonal-naive forecast"
                if projection["projection_type"] == "STATISTICAL_FORECAST"
                else "Illustrative scenario projection"
            ),
            mode="lines+markers",
            line={"color": "#1f7a83", "width": 2, "dash": "dash"},
            hovertemplate="Date: %{x|%Y-%m}<br>Index: %{y:.1f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["upper_index_100"],
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=forecast["date"],
            y=forecast["lower_index_100"],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(61,124,120,0.16)",
            name=(
                "95% residual interval"
                if projection["projection_type"] == "STATISTICAL_FORECAST"
                else "Illustrative assumption range"
            ),
            hoverinfo="skip",
        )
    )
    figure.update_layout(
        template="rane_corporate",
        title=f"{display_name} — indexed history and {horizon_months}-month outlook",
        xaxis_title="Month",
        yaxis_title=projection["chart_unit"],
        height=420,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
    )
    st.plotly_chart(figure, width="stretch")
    st.dataframe(
        forecast[
            [
                "date",
                "value_index_100",
                "lower_index_100",
                "upper_index_100",
            ]
        ].rename(
            columns={
                "date": "Period",
                "value_index_100": "Projection index",
                "lower_index_100": "Range low",
                "upper_index_100": "Range high",
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Period": st.column_config.DateColumn("Projection month"),
            "Projection index": st.column_config.NumberColumn(format="%.2f"),
            "Range low": st.column_config.NumberColumn(format="%.2f"),
            "Range high": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def render_scenario_dashboard(
    integrated: pd.DataFrame, shipping_rates: pd.DataFrame
) -> None:
    """Render the five case-study modules inside the existing management page."""
    scenario_inputs, material_config = _render_inputs()
    inventory_columns = st.columns(3)
    for column, (name, label, default, upper) in zip(
        inventory_columns,
        (
            ("inventory_days", "Illustrative inventory on hand (days)", 30.0, 365.0),
            ("supplier_lead_time_days", "Illustrative supplier lead time (days)", 45.0, 365.0),
            ("safety_stock_days", "Illustrative safety-stock buffer (days)", 15.0, 180.0),
        ),
    ):
        scenario_inputs[name] = column.number_input(
            label,
            min_value=0.0,
            max_value=upper,
            step=1.0,
            key=f"scenario_{name}",
        )
    scenario_inputs["scenario_range_pct"] = st.slider(
        "Illustrative projection range (± %)",
        min_value=0.0,
        max_value=50.0,
        step=1.0,
        key="scenario_scenario_range_pct",
    )
    with st.expander("Container planning assumptions", expanded=False):
        container_columns = st.columns(3)
        share_40ft_pct = container_columns[0].number_input(
            "40-foot share of container count (%)",
            min_value=0.0,
            max_value=100.0,
            value=70.0,
            step=1.0,
            key="scenario_share_40ft_pct",
        )
        cost_20ft_ratio = container_columns[1].number_input(
            "20-foot freight cost relative to 40-foot (%)",
            min_value=1.0,
            max_value=100.0,
            value=75.0,
            step=1.0,
            key="scenario_cost_20ft_ratio",
        )
        payload_utilization_pct = container_columns[2].number_input(
            "Payload utilisation (%)",
            min_value=1.0,
            max_value=100.0,
            value=75.0,
            step=1.0,
            key="scenario_payload_utilization",
        )
        capacity_columns = st.columns(2)
        payload_20ft_tonnes = capacity_columns[0].number_input(
            "20-foot payload capacity (tonnes)",
            min_value=1.0,
            max_value=100.0,
            value=24.0,
            step=1.0,
            key="scenario_payload_20ft",
        )
        payload_40ft_tonnes = capacity_columns[1].number_input(
            "40-foot payload capacity (tonnes)",
            min_value=1.0,
            max_value=100.0,
            value=26.0,
            step=1.0,
            key="scenario_payload_40ft",
        )

    st.warning(
        "SYNTHETIC / ILLUSTRATIVE CASE-STUDY CALCULATIONS. The FY25 values below "
        "are the supplied case-study baseline; material mix, per-tonne costs, FX, "
        "inventory, lead time, container payload, mitigation, and action costs are "
        "editable assumptions—not actual RANE records, supplier terms, or savings."
    )
    try:
        scenario = calculate_scenario(
            material_mix_pct=scenario_inputs["material_mix_pct"],
            usd_linked_share=scenario_inputs["usd_linked_share"],
            tariff_exposure=scenario_inputs["tariff_exposure"],
            reference_inr_per_tonne=scenario_inputs["reference_inr_per_tonne"],
            material_shocks_pct=scenario_inputs["material_shocks_pct"],
            tariff_shock_pct=float(scenario_inputs["tariff_shock_pct"]),
            fx_shock_pct=float(scenario_inputs["fx_shock_pct"]),
            freight_shock_pct=float(scenario_inputs["freight_shock_pct"]),
            demand_change_pct=float(scenario_inputs["demand_change_pct"]),
            oem_pass_through_pct=float(scenario_inputs["oem_pass_through_pct"]),
            tax_rate_pct=float(scenario_inputs["tax_rate_pct"]),
            base_usd_inr=float(scenario_inputs["base_usd_inr"]),
        )
        inventory = calculate_inventory_runway(
            scenario,
            inventory_days=float(scenario_inputs["inventory_days"]),
            supplier_lead_time_days=float(scenario_inputs["supplier_lead_time_days"]),
            safety_stock_days=float(scenario_inputs["safety_stock_days"]),
            demand_change_pct=float(scenario_inputs["demand_change_pct"]),
        )
        container = calculate_container_model(
            scenario,
            base_usd_inr=float(scenario_inputs["base_usd_inr"]),
            freight_shock_pct=float(scenario_inputs["freight_shock_pct"]),
            fx_shock_pct=float(scenario_inputs["fx_shock_pct"]),
            share_40ft_pct=float(share_40ft_pct),
            cost_20ft_ratio=float(cost_20ft_ratio),
            payload_20ft_tonnes=float(payload_20ft_tonnes),
            payload_40ft_tonnes=float(payload_40ft_tonnes),
            payload_utilization_pct=float(payload_utilization_pct),
        )
        division_costs = allocate_division_costs(
            scenario,
            scenario_inputs["division_allocation"],
        )
        action_inputs, disruption_exposure = _edit_action_assumptions()
        ranked_actions = rank_management_actions(
            scenario,
            inventory,
            action_inputs,
            inventory_disruption_exposure_cr=disruption_exposure,
        )
    except (ValueError, KeyError) as error:
        st.error(f"Scenario assumptions are invalid: {error}")
        return

    financial = scenario["financial"]
    summary, forecast, inventory_tab, actions = st.tabs(
        [
            "Financial recalculation",
            "Price and freight outlook",
            "Inventory and containers",
            "Prescriptive action matrix",
        ]
    )
    with summary:
        st.subheader("FY25 case-study management overview")
        st.caption(
            f"Selected preset: {st.session_state['scenario_preset_select']} · "
            f"Tax assumption: {financial['tax_rate_pct']:.1f}% · "
            f"OEM pass-through: {financial['oem_cost_pass_through_pct']:.1f}%"
        )
        top_metrics = st.columns(4)
        top_metrics[0].metric(
            "FY25 baseline EBITDA",
            f"₹{CASE_STUDY_BASELINE['ebitda_cr']:,.1f} Cr",
        )
        top_metrics[1].metric(
            "Scenario EBITDA",
            f"₹{financial['ebitda_cr']:,.1f} Cr",
            f"₹{financial['ebitda_change_cr']:+,.1f} Cr",
        )
        top_metrics[2].metric(
            "Scenario PAT",
            f"₹{financial['pat_cr']:,.1f} Cr",
            f"vs baseline ₹{CASE_STUDY_BASELINE['pat_cr']:,.1f} Cr",
        )
        top_metrics[3].metric(
            "EBITDA margin",
            f"{financial['ebitda_margin_pct']:.2f}%",
            f"Revenue ₹{financial['revenue_cr']:,.1f} Cr",
        )
        material_impacts = scenario["material_costs"].copy()
        material_impacts["incremental_cost_cr"] = (
            material_impacts["scenario_material_spend_cr"]
            - material_impacts["baseline_spend_cr"]
        )
        largest_exposure = material_impacts.sort_values(
            "incremental_cost_cr", ascending=False
        ).iloc[0]
        largest_exposure_value = float(largest_exposure["incremental_cost_cr"])
        second_metrics = st.columns(5)
        second_metrics[0].metric(
            "Largest material cost increase",
            (
                str(largest_exposure["material"])
                if largest_exposure_value > 0
                else "None"
            ),
            (
                f"₹{largest_exposure_value:+,.2f} Cr"
                if largest_exposure_value > 0
                else "No positive modeled increase"
            ),
        )
        second_metrics[1].metric(
            "Incremental material cost",
            f"₹{financial['incremental_material_cost_cr']:+,.2f} Cr",
        )
        second_metrics[2].metric(
            "Freight exposure change",
            f"₹{financial['incremental_freight_cost_cr']:+,.2f} Cr",
        )
        second_metrics[3].metric(
            "Unrecovered cost pressure",
            f"₹{financial['unrecovered_cost_cr']:+,.2f} Cr",
        )
        second_metrics[4].metric(
            "Inventory cover",
            f"{inventory['days_of_cover']:.1f} days",
            inventory["status"],
        )
        st.info(
            f"Top-ranked action to review: **{ranked_actions.iloc[0]['action']}** "
            f"(illustrative net impact ₹"
            f"{ranked_actions.iloc[0]['net_impact_cr_illustrative']:+,.2f} Cr). "
            "See the action matrix for its editable assumptions and evidence."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Measure": "Revenue",
                        "Baseline": CASE_STUDY_BASELINE["revenue_cr"],
                        "Scenario": financial["revenue_cr"],
                        "Change": financial["revenue_cr"] - CASE_STUDY_BASELINE["revenue_cr"],
                        "Unit": "₹ Cr",
                    },
                    {
                        "Measure": "EBITDA",
                        "Baseline": CASE_STUDY_BASELINE["ebitda_cr"],
                        "Scenario": financial["ebitda_cr"],
                        "Change": financial["ebitda_change_cr"],
                        "Unit": "₹ Cr",
                    },
                    {
                        "Measure": "EBITDA margin",
                        "Baseline": CASE_STUDY_BASELINE["ebitda_margin_pct"],
                        "Scenario": financial["ebitda_margin_pct"],
                        "Change": financial["ebitda_margin_pct"] - CASE_STUDY_BASELINE["ebitda_margin_pct"],
                        "Unit": "%",
                    },
                    {
                        "Measure": "PAT",
                        "Baseline": CASE_STUDY_BASELINE["pat_cr"],
                        "Scenario": financial["pat_cr"],
                        "Change": financial["pat_cr"] - CASE_STUDY_BASELINE["pat_cr"],
                        "Unit": "₹ Cr",
                    },
                    {
                        "Measure": "Raw-material spend",
                        "Baseline": CASE_STUDY_BASELINE["raw_material_spend_cr"],
                        "Scenario": financial["raw_material_spend_cr"],
                        "Change": financial["incremental_material_cost_cr"],
                        "Unit": "₹ Cr",
                    },
                    {
                        "Measure": "Annual inbound ocean freight",
                        "Baseline": CASE_STUDY_BASELINE["annual_inbound_ocean_freight_cr"],
                        "Scenario": financial["annual_freight_cr"],
                        "Change": financial["incremental_freight_cost_cr"],
                        "Unit": "₹ Cr",
                    },
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Baseline": st.column_config.NumberColumn(format="%.2f"),
                "Scenario": st.column_config.NumberColumn(format="%.2f"),
                "Change": st.column_config.NumberColumn(format="%+.2f"),
            },
        )
        st.markdown("#### Transparent cost bridge (₹ Cr)")
        st.dataframe(
            scenario["cost_bridge"],
            hide_index=True,
            width="stretch",
            column_config={
                "change_cr": st.column_config.NumberColumn(
                    "Change (₹ Cr)", format="₹%.2f"
                )
            },
        )
        st.caption(
            "Bridge order: volume → material price → tariff → material FX → "
            "freight volume → freight rate → freight FX. Each effect is applied "
            "once. OEM recovery is applied only to positive combined cost pressure."
        )
        st.markdown("#### Landed material cost per tonne")
        st.caption(
            "Editable reference costs are INR/tonne assumptions. A normalized "
            "USD-linked share receives the FX shock; applicable tariff exposure "
            "is applied once. Allocated freight is added separately per tonne."
        )
        st.dataframe(
            scenario["material_costs"][
                [
                    "material",
                    "mix_weight_pct",
                    "baseline_spend_cr",
                    "reference_cost_inr_per_tonne",
                    "scenario_material_cost_inr_per_tonne",
                    "allocated_freight_inr_per_tonne",
                    "scenario_landed_cost_inr_per_tonne",
                    "scenario_material_spend_cr",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "mix_weight_pct": st.column_config.NumberColumn("Normalized mix (%)", format="%.1f%%"),
                "baseline_spend_cr": st.column_config.NumberColumn("Baseline spend (₹ Cr)", format="₹%.2f"),
                "reference_cost_inr_per_tonne": st.column_config.NumberColumn("Illustrative base (₹/t)", format="₹%.0f"),
                "scenario_material_cost_inr_per_tonne": st.column_config.NumberColumn("Scenario material (₹/t)", format="₹%.0f"),
                "allocated_freight_inr_per_tonne": st.column_config.NumberColumn("Allocated freight (₹/t)", format="₹%.0f"),
                "scenario_landed_cost_inr_per_tonne": st.column_config.NumberColumn("Landed scenario (₹/t)", format="₹%.0f"),
                "scenario_material_spend_cr": st.column_config.NumberColumn("Scenario spend (₹ Cr)", format="₹%.2f"),
            },
        )
        st.markdown("#### Illustrative division / line cost allocation")
        st.caption(
            "Editable allocation weights are normalized to 100%; these are "
            "scenario allocations, not actual division-level consumption."
        )
        st.dataframe(
            division_costs,
            hide_index=True,
            width="stretch",
            column_config={
                "normalized_allocation_pct": st.column_config.NumberColumn(
                    "Normalized allocation (%)", format="%.1f%%"
                ),
                "baseline_material_spend_cr": st.column_config.NumberColumn(
                    "Baseline material spend (₹ Cr)", format="₹%.2f"
                ),
                "scenario_material_spend_cr": st.column_config.NumberColumn(
                    "Scenario material spend (₹ Cr)", format="₹%.2f"
                ),
                "incremental_material_cost_cr": st.column_config.NumberColumn(
                    "Material cost change (₹ Cr)", format="₹%.2f"
                ),
                "baseline_freight_cr": st.column_config.NumberColumn(
                    "Baseline freight (₹ Cr)", format="₹%.2f"
                ),
                "scenario_freight_cr": st.column_config.NumberColumn(
                    "Scenario freight (₹ Cr)", format="₹%.2f"
                ),
                "incremental_freight_cost_cr": st.column_config.NumberColumn(
                    "Freight change (₹ Cr)", format="₹%.2f"
                ),
                "baseline_combined_cost_cr": st.column_config.NumberColumn(
                    "Baseline combined cost (₹ Cr)", format="₹%.2f"
                ),
                "scenario_combined_cost_cr": st.column_config.NumberColumn(
                    "Scenario combined cost (₹ Cr)", format="₹%.2f"
                ),
                "incremental_combined_cost_cr": st.column_config.NumberColumn(
                    "Combined cost change (₹ Cr)", format="₹%.2f"
                ),
            },
        )
        st.markdown("#### Full EBITDA and PAT calculation trace")
        trace = pd.DataFrame(
            [
                {"Step": "FY25 baseline EBITDA", "Amount (₹ Cr)": 297.7},
                {
                    "Step": "Demand-related EBITDA effect",
                    "Amount (₹ Cr)": financial["demand_ebitda_effect_cr"],
                },
                {
                    "Step": "Incremental material cost",
                    "Amount (₹ Cr)": -financial["incremental_material_cost_cr"],
                },
                {
                    "Step": "Incremental freight cost",
                    "Amount (₹ Cr)": -financial["incremental_freight_cost_cr"],
                },
                {
                    "Step": "OEM cost recovery",
                    "Amount (₹ Cr)": financial["oem_cost_recovery_cr"],
                },
                {
                    "Step": "Revised EBITDA",
                    "Amount (₹ Cr)": financial["ebitda_cr"],
                },
                {
                    "Step": "EBITDA change vs baseline",
                    "Amount (₹ Cr)": financial["ebitda_change_cr"],
                },
                {"Step": "FY25 baseline PAT", "Amount (₹ Cr)": 37.6},
                {
                    "Step": "After-tax EBITDA change",
                    "Amount (₹ Cr)": financial["pat_cr"] - 37.6,
                },
                {"Step": "Revised PAT", "Amount (₹ Cr)": financial["pat_cr"]},
            ]
        )
        st.caption(
            f"PAT bridge applies the editable {financial['tax_rate_pct']:.1f}% "
            "tax assumption to the EBITDA change; other non-operating items are held constant."
        )
        st.dataframe(
            trace,
            hide_index=True,
            width="stretch",
            column_config={
                "Amount (₹ Cr)": st.column_config.NumberColumn(format="₹%.2f")
            },
        )
        with st.expander("Calculation and tax methodology"):
            st.markdown(
                """
                - Material spend is the ₹1,223 Cr case-study baseline distributed by the editable relative mix, normalized to 100%.
                - Per material, spend is scaled by demand, material shock, tariff shock times editable tariff exposure, then USD/INR shock times editable USD-linked share.
                - Freight is modeled separately from material spend: ₹25 Cr × demand factor × freight-rate factor × USD/INR factor. It is not tariffed or added twice.
                - Revenue changes by the demand slider. The pre-material/pre-freight contribution proxy is (₹297.7 Cr EBITDA + ₹1,223 Cr raw materials + ₹25 Cr freight) ÷ ₹3,421 Cr revenue; material and freight volume savings are then subtracted once.
                - OEM recovery = positive combined cost pressure × pass-through rate. Negative cost changes are not treated as an OEM recovery.
                - Revised EBITDA = ₹297.7 Cr + demand effect − unrecovered cost pressure.
                - Revised PAT = ₹37.6 Cr + change in EBITDA × (1 − editable tax assumption). Depreciation, financing, and other non-operating items are assumed unchanged.
                - Landed ₹/tonne uses editable illustrative unit-cost references plus a separately allocated freight-per-tonne estimate. It is not actual procurement pricing.
                """
            )

    with forecast:
        _render_forecast(
            integrated,
            shipping_rates,
            scenario_inputs,
            material_config,
            horizon_months=st.selectbox(
                "Projection horizon (months)",
                [3, 6, 12],
                index=2,
                key="scenario_projection_horizon",
            ),
            scenario_range_pct=float(scenario_inputs["scenario_range_pct"]),
        )

    with inventory_tab:
        st.subheader("Inventory runway")
        st.caption(
            "Inventory quantity is derived from the editable days-on-hand "
            "assumption and case-study spend. No RANE stock ledger, purchase order, "
            "or supplier lead-time record is supplied."
        )
        inv_metrics = st.columns(4)
        inv_metrics[0].metric(
            "Illustrative daily consumption",
            f"{inventory['daily_consumption_tonnes']:,.1f} t/day",
        )
        inv_metrics[1].metric(
            "Illustrative current inventory",
            f"{inventory['current_inventory_tonnes']:,.0f} t",
        )
        inv_metrics[2].metric(
            "Potential stock-out runway",
            f"{inventory['days_until_potential_stockout']:.1f} days",
        )
        inv_metrics[3].metric(
            "Runway status",
            inventory["status"],
        )
        inventory_detail = pd.DataFrame(
            [
                {"Measure": "Inventory cover", "Value": f"{inventory['days_of_cover']:.1f} days"},
                {"Measure": "Supplier lead time (illustrative)", "Value": f"{inventory['supplier_lead_time_days']:.1f} days"},
                {"Measure": "Safety stock buffer (illustrative)", "Value": f"{inventory['safety_stock_days']:.1f} days"},
                {"Measure": "Cover after lead time and safety stock", "Value": f"{inventory['buffer_after_lead_and_safety_days']:+.1f} days"},
                {"Measure": "Inventory value (illustrative)", "Value": f"₹{inventory['inventory_value_cr_illustrative']:.2f} Cr"},
            ]
        )
        st.dataframe(inventory_detail, hide_index=True, width="stretch")
        st.markdown("#### Container-equivalent planning model")
        st.caption(
            f"Uses the case-study USD {CASE_STUDY_BASELINE['container_rate_usd_40ft']:,.0f} "
            "40-foot baseline and ₹25 Cr annual freight. Counts and payload are "
            "scenario estimates, not actual shipments or carrier quotes."
        )
        container_metrics = st.columns(3)
        container_metrics[0].metric(
            "Estimated container equivalents",
            f"{container['container_count_equivalent']:,.0f}",
        )
        container_metrics[1].metric(
            "Estimated payload",
            f"{container['material_transported_tonnes']:,.0f} tonnes",
        )
        container_metrics[2].metric(
            "Freight per payload tonne",
            f"₹{container['weighted_freight_cost_inr_per_tonne']:,.0f}/t",
        )
        st.dataframe(
            container["containers"],
            hide_index=True,
            width="stretch",
            column_config={
                "container_count_equivalent": st.column_config.NumberColumn("Container count (equivalent)", format="%.1f"),
                "payload_capacity_tonnes": st.column_config.NumberColumn("Capacity (t)", format="%.1f"),
                "actual_payload_tonnes": st.column_config.NumberColumn("Payload at utilisation (t/container)", format="%.1f"),
                "utilization_pct": st.column_config.NumberColumn("Payload utilisation (%)", format="%.1f%%"),
                "freight_cost_inr_per_container": st.column_config.NumberColumn("Freight (₹/container)", format="₹%.0f"),
                "freight_cost_inr_per_tonne": st.column_config.NumberColumn("Freight (₹/payload tonne)", format="₹%.0f"),
                "material_transported_tonnes": st.column_config.NumberColumn("Estimated annual material (t)", format="%.0f"),
            },
        )
        st.dataframe(
            container["material_transport"],
            hide_index=True,
            width="stretch",
            column_config={
                "illustrative_mix_pct": st.column_config.NumberColumn("Illustrative mix (%)", format="%.1f%%"),
                "material_transported_tonnes": st.column_config.NumberColumn("Illustrative material tonnes", format="%.0f"),
            },
        )

    with actions:
        st.subheader("Prescriptive action matrix")
        st.caption(
            "Priorities are ranked by illustrative net impact = assumed mitigated "
            "exposure minus editable implementation cost. Benefits are not "
            "validated savings; suppliers affected are not supplied."
        )
        st.dataframe(
            ranked_actions[
                [
                    "priority_rank",
                    "action",
                    "triggering_risk",
                    "estimated_benefit_cr",
                    "estimated_implementation_cost_cr",
                    "net_impact_cr_illustrative",
                    "before_after_comparison",
                    "suppliers_affected",
                    "functions_affected",
                    "data_quality",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "priority_rank": st.column_config.NumberColumn("Priority", format="%d"),
                "estimated_benefit_cr": st.column_config.NumberColumn("Assumed benefit (₹ Cr)", format="₹%.2f"),
                "estimated_implementation_cost_cr": st.column_config.NumberColumn("Assumed cost (₹ Cr)", format="₹%.2f"),
                "net_impact_cr_illustrative": st.column_config.NumberColumn("Illustrative net impact (₹ Cr)", format="₹%.2f"),
            },
        )
        st.info(
            "Action suggestions are prompts for management review only. The model "
            "does not execute procurement, create supplier relationships, or "
            "establish production exposure."
        )

# Scenario simulator data trace

## Public-demo mode

All files under `demo_data/` are deterministic synthetic examples. The
application displays the public-demo disclaimer on every page. These values
are not actual RANE records, live conditions, or market observations.

| Dataset / input | Source and status | Use in the simulator |
|---|---|---|
| `demo_data/processed/material_market_data_integrated.csv` | Synthetic demo generator; `SYNTHETIC_ILLUSTRATIVE_DATA` | Historical indexed series in the outlook module only. Does not feed the FY25 spend calculation. |
| `demo_data/raw/stage_5/logistics/shipping_rates.csv` | Synthetic demo generator; `SYNTHETIC_ILLUSTRATIVE_DATA` | Historical 40-foot freight series for the indexed outlook only. |
| Case-study financial baseline | Supplied directly in the task | Starts the revenue, EBITDA, PAT, raw-material spend, and annual freight calculations. |
| Material mix, reference costs, USD/tariff exposures | Editable synthetic assumptions | Distributes the raw-material baseline and calculates illustrative INR/tonne outputs. |
| Inventory, lead-time, safety-stock, division allocation, container payload, mitigation, and action costs | Editable synthetic assumptions | Drives illustrative inventory, division allocation, container, and action-matrix calculations. |

## Private-development source data

Private mode reads the existing `data/` environment. The simulator does not
copy, alter, upload, or publish those files.

| Dataset / series | Source-quality status in the existing application | Simulator use and limitation |
|---|---|---|
| Copper, Nickel, Aluminium | `LEGACY_SOURCE_PROVENANCE_UNVERIFIED` | Existing histories may be shown, but are not used as verified forecasts or as unit-cost assumptions. |
| Steel HR and Steel CR | `APPROXIMATE_CHART_VALUE` | Chart-derived observations remain approximate; they are not treated as exact forecasts. |
| Natural Rubber | World Bank Group, Commodity Markets (Pink Sheet); `OFFICIAL_SOURCE_VALUE` | Official monthly history is eligible for a statistical method after restricting the grade-changing series to RSS3-era observations from 2004. It remains a static snapshot, not a live feed. |
| Phenolic Resin | No market-price rows supplied | No price series or market forecast is fabricated. Only an editable scenario assumption is available. |
| USD/INR and other market records | Existing integrated data retains source, unit, currency, dates, and quality labels | Not used to silently convert or combine incompatible material series. The simulator's base FX input is editable and clearly labeled as an assumption. |
| `data/raw/stage_5/logistics/shipping_rates.csv` | `ARCHIVE_SOURCE_UNVERIFIED` | Historical values may be displayed; no statistical forecast is presented from this archive-only quality. The finance calculation uses the supplied case-study freight baseline instead. |
| Stage 5 risk, port, and congestion datasets | Existing provenance labels are preserved by their pages | Not inputs to the case-study financial calculations. The simulator does not convert global indicators into RANE-specific exposure. |

## Non-data assumptions

The default percentages and unit costs in the material-configuration table are
fictional starting values intended to make the interface interactive. Editable
action mitigation and implementation costs are also illustrative; potential
inventory-disruption exposure defaults to zero because no loss evidence was
supplied. These values must be replaced with approved, traceable RANE inputs
before operational use. The division/line table uses generic labels and
normalized editable weights; it does not claim actual division consumption.
The material mix is normalized to 100%; USD linkage and tariff exposure are
applied per the visible configuration. No suppliers, contracts, inventory
quantities, purchase orders, shipments, production volumes, or division-level
consumption are present.

Public deployment must use `RANE_DATA_MODE=demo` and include only the approved
synthetic demo environment. Do not publish private `data/`, local backups, or
unapproved reports.


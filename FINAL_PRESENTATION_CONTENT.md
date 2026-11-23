# RANE MMD Decision Engine — 15-minute presentation

## Slide 1 — The management problem (1 minute)

- Manufacturing decisions are exposed to material, freight, foreign-exchange,
  tariff, and demand uncertainty.
- Data quality and operational-data gaps make unsupported precision risky.
- Objective: provide a transparent review tool, not automated procurement.

**Speaker note:** This public demonstration uses synthetic records and an
explicit FY25 case-study baseline. It is not live RANE intelligence.

## Slide 2 — What the application brings together (1 minute)

- Material Price Intelligence.
- Supply-Chain Risk.
- Logistics Intelligence.
- Global Supply-Chain Map.
- Management Decision Support and its Case-study simulator.

**Speaker note:** Existing pages, source-quality labels, historical context,
filters, and map disclaimers remain separate from the scenario assumptions.

## Slide 3 — Data and trust boundaries (1.5 minutes)

- Synthetic demo records are visibly labeled and kept separate from private
  source data.
- Steel chart readings remain approximate; archive-only datasets remain
  unverified.
- Phenolic Resin has no authenticated market-price history in the supplied
  dataset.
- No suppliers, inventory ledger, orders, shipments, or division consumption
  have been supplied.

**Speaker note:** The simulator does not fill those gaps with fake operational
records. The editable assumptions are clearly marked illustrative.

## Slide 4 — Five simulator modules (1 minute)

1. Price and freight outlook.
2. Five what-if presets.
3. Live landed-cost and financial recalculation.
4. Inventory and container-equivalent planning.
5. Ranked action matrix with visible assumptions.

## Slide 5 — Scenario presets and controls (2 minutes)

- Base Case.
- Red Sea / Hormuz Crisis.
- Metal Shock.
- Tariff and FX Escalation.
- Demand Recession.
- Independent sliders allow a preset to be modified; reset restores baseline.

**Demo:** Select the freight crisis preset, then adjust the freight, USD/INR,
and OEM pass-through sliders.

## Slide 6 — Cost bridge and financial recalculation (2 minutes)

- FY25 case baseline: Revenue ₹3,421 Cr; EBITDA ₹297.7 Cr; PAT ₹37.6 Cr.
- Raw-material spend: ₹1,223 Cr; annual ocean freight: ₹25 Cr.
- Sequential bridge separates demand, material price, tariff, FX, freight rate,
  and freight FX effects.
- OEM cost recovery and tax assumptions are shown.

**Demo:** Apply a copper price shock and review revised EBITDA, margin, PAT,
landed ₹/tonne, and the cost bridge.

## Slide 7 — Forecast versus scenario projection (1.5 minutes)

- Statistical methods are limited to long, contiguous, officially labeled
  monthly series.
- Seasonal naive, exponential smoothing, or OLS trend is selected by history
  length.
- Other series show clearly labeled indexed scenario paths with assumption
  bands, not fabricated price forecasts.

**Demo:** Inspect Natural Rubber in private mode, then inspect Phenolic Resin
or container freight in the synthetic public demo.

## Slide 8 — Inventory and container planning (1.5 minutes)

- Editable days-on-hand, lead time, and safety-stock assumptions drive runway
  and reorder review status.
- The model presents 20-foot and 40-foot annualized equivalents, payload,
  utilisation, and freight per payload tonne.

**Speaker note:** These are planning calculations, not actual RANE stock or
shipment data.

## Slide 9 — Cross-functional action review (1 minute)

- The action matrix ranks actions by assumed mitigated exposure minus editable
  implementation cost.
- It identifies generic functions and explicitly states that affected suppliers
  are not supplied.
- Benefits are illustrative sensitivity estimates, not savings commitments.

## Slide 10 — Value, limitations, and roadmap (2.5 minutes)

**Demonstration value**

- Makes assumptions, source quality, and calculation traces visible.
- Allows consistent comparison of a small set of explicit stress cases.
- Creates a structured management conversation across Procurement, Finance,
  Production, Logistics, Quality, Sales, and HR.

**Limitations**

- No verified procurement mix, supplier terms, inventory, shipment, or
  production data.
- No validated forecast backtest or predictive model.
- No verified cost-benefit estimates or automated procurement decisions.

**Implementation roadmap**

1. Approve private data governance and access controls.
2. Supply validated supplier, inventory, purchase-order, and production inputs.
3. Reconcile mix, tax, lead-time, and freight assumptions with Finance and
   Procurement.
4. Backtest forecasts and review calculations with business owners.
5. Deploy privately if approved operational data is introduced.

**Closing:** Treat outputs as traceable decision support and scenario analysis;
management review and source validation remain essential.


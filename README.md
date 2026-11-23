# RANE MMD Decision Engine — Public Demo

Streamlit demonstration of material-price, supply-chain, logistics, mapping,
historical management screening, and an interactive FY25 case-study simulator.
The management page's **Case-study simulator** tab contains five modules:

1. Price and freight outlook.
2. What-if scenarios with five presets and editable shocks.
3. Live recalculation of landed cost, raw-material exposure, EBITDA, and PAT.
4. Inventory runway, illustrative division/line cost allocation, and
   20-foot / 40-foot container planning.
5. A ranked, assumption-based management action matrix.

**Every page displays:**

> PUBLIC DEMO | SYNTHETIC ILLUSTRATIVE DATA | NOT ACTUAL RANE OR LIVE MARKET DATA

All 14 runtime datasets under `demo_data/` are deterministic fictional examples.
They contain no actual market observations, source archive records, RANE
operational data, real ports, live conditions, or procurement quotations. See
[`demo_data/README.md`](demo_data/README.md) and
[`demo_data/metadata.json`](demo_data/metadata.json) for the generator seed,
schemas, date spans, and relationships.

The simulator uses the supplied FY25 case-study baseline (Revenue ₹3,421 Cr,
EBITDA ₹297.7 Cr, PAT ₹37.6 Cr, raw materials ₹1,223 Cr, annual ocean freight
₹25 Cr, and USD 2,172 per 40-foot container). All material mix, per-tonne
reference costs, tariff/currency exposure, inventory, lead-time, payload,
mitigation, and implementation-cost inputs are synthetic and editable. They
are not RANE procurement, stock, supplier, production, or shipment records.
The simulator does not execute purchasing decisions or promise savings. See
[`FORMULA_README.md`](FORMULA_README.md) and [`DATA_TRACE.md`](DATA_TRACE.md).

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The application defaults to `demo_data/` and never falls back to `data/` when
a demo file is missing. For private local development only, explicitly set
`RANE_DATA_MODE=private` before running Streamlit. **Do not set private mode in
a public deployment.**

To operate the simulator, open **Management Decision Support → Case-study
simulator**, select one of the five presets, and adjust the displayed sliders
and editable assumptions. Use **Reset to baseline** to clear the shocks.
Scenario paths and action benefits are illustrative; forecast methods and
source-quality labels are shown beside their outputs.

## Run tests

```powershell
$env:RANE_DATA_MODE = "private"
python -m unittest discover -s tests -v
```

## Streamlit Community Cloud

1. Publish the reviewed project allowlist to the public repository
   `jmnj602-cyber/rane-mmd-public-demo`.
2. In Community Cloud, create an app from that repository and branch `main`.
3. Set the main file path to `app.py` and deploy.
4. Test the public app URL and verify the synthetic-data banner appears on all
   five pages.

No secrets or private data are required for this demo. The public deployment
must use the default demo mode and the committed `demo_data/` files.
Do not upload `data/`, actual source datasets, local backups, or unapproved
reports. No changes are published automatically by the application.

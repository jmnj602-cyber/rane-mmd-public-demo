# RANE MMD Decision Engine — Public Demo

Streamlit demonstration of material-price, supply-chain, logistics, mapping,
and management-screening pages. **Every page displays:**

> PUBLIC DEMO | SYNTHETIC ILLUSTRATIVE DATA | NOT ACTUAL RANE OR LIVE MARKET DATA

All 14 runtime datasets under `demo_data/` are deterministic fictional examples.
They contain no actual market observations, source archive records, RANE
operational data, real ports, live conditions, or procurement quotations. See
[`demo_data/README.md`](demo_data/README.md) and
[`demo_data/metadata.json`](demo_data/metadata.json) for the generator seed,
schemas, date spans, and relationships.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The application defaults to `demo_data/` and never falls back to `data/` when
a demo file is missing. For private local development only, explicitly set
`RANE_DATA_MODE=private` before running Streamlit. **Do not set private mode in
a public deployment.**

## Streamlit Community Cloud

1. Publish the reviewed project allowlist to the public repository
   `jmnj602-cyber/rane-mmd-public-demo`.
2. In Community Cloud, create an app from that repository and branch `main`.
3. Set the main file path to `app.py` and deploy.
4. Test the public app URL and verify the synthetic-data banner appears on all
   five pages.

No secrets or private data are required for this demo. The public deployment
must use the default demo mode and the committed `demo_data/` files.

# Indian Options Research Workbench (IORW)

A personal-use, research-only starter for Indian equities and index derivatives. It does **not** place orders and does not scrape NSE/BSE websites.

## What is included
- Streamlit dashboard with an explicitly synthetic sample option chain.
- CSV import for data you are authorized to use.
- Black–Scholes price/Greeks/IV helper calculations for European-style options.
- Strike-level gamma exposure proxy, PCR, OI changes, IV and volume summaries.
- A small unit-test suite.
- Data adapter boundary for adding a licensed broker/vendor feed later.

## Important limitations
- The bundled sample data is fabricated for software demonstration and is not current market data.
- The GEX output is a **proxy**, not observed dealer positioning. The dashboard assumes an optional dealer-sign convention; open interest alone cannot reveal whether dealers are net long or short gamma.
- Black–Scholes is an analytical reference, not a guarantee of exchange/vendor Greeks. Indian index options may have exercise/settlement and market conventions that require additional validation.
- The app is analytics/research only: no broker credentials, order entry, or execution module.
- Do not scrape NSE/BSE pages or reuse exchange data unless your use is permitted by the relevant terms and data licence. See https://www.nseindia.com/static/market-data/nse-data-policy and https://www.nseindia.com/option-chain.

## Quick start (Windows)
1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/ and tick **Add Python to PATH**.
2. Extract the ZIP.
3. Open the extracted folder, click the address bar, type `cmd`, press Enter.
4. Run:
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. A browser tab opens. Choose **Demo data** or upload a CSV you are licensed to use.

## macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## CSV format
Required columns:
`symbol, expiry, option_type, strike, spot, option_price, iv, oi, oi_change, volume, lot_size, risk_free_rate`

- `expiry`: `YYYY-MM-DD`
- `option_type`: `CE`/`PE` or `CALL`/`PUT`
- `iv`: decimal volatility (e.g. `0.18` = 18%). If blank/zero, IV can be estimated from `option_price` when the inputs are valid.
- `oi`: open interest in contracts.
- `lot_size`: exchange contract multiplier for that instrument/expiry; do not hard-code old lot sizes.
- `risk_free_rate`: annual decimal (e.g. `0.065` = 6.5%).
- Prices and quantities should match your licensed source's units.

See `data/sample/demo_option_chain.csv` for a synthetic example.

## REA use
REA is an optional local research assistant for software you own or are authorized to inspect. The upstream repository describes REA as MIT-licensed for REA-authored code, while third-party tools/materials keep their own terms: https://github.com/morluto/rea. REA is not a market-data provider or quant engine. This project does not bundle REA or copy code from commercial analytics platforms.

## Project layout
- `app.py` — dashboard
- `src/quant.py` — independent quantitative calculations
- `src/adapters.py` — licensed CSV adapter and provider interface placeholder
- `tests/test_quant.py` — basic calculation tests
- `data/sample/` — synthetic demo data
- `data/imports/` — place your own authorized CSV files here (not included in source control)

## Roadmap
1. Validate calculations against trusted reference cases.
2. Add a provider adapter only after confirming API terms and entitlements.
3. Add historical replay and backtesting using timestamped licensed data.
4. Add alerts and paper portfolio only after the analytics are tested.

Not investment advice. This is a research tool; validate outputs independently before relying on them.

## FYERS API v3 integration (v0.2)

This version adds a FYERS data source for option-chain and quote snapshots. It does not place orders and does not implement continuous WebSocket streaming yet.

1. In Streamlit Community Cloud, open the deployed app's menu and find **Settings / Secrets**.
2. Add the following TOML entries, replacing the placeholders inside Streamlit only:

   ```toml
   FYERS_APP_ID = "YOUR_APP_ID"
   FYERS_ACCESS_TOKEN = "YOUR_CURRENT_ACCESS_TOKEN"
   ```

3. Save the secrets. Never put access tokens, app secrets or passwords into GitHub files or chat.
4. Upload the updated project files from this ZIP to the same GitHub repository, replacing the old `app.py` and adding `src/fyers_adapter.py`; update `requirements.txt`. Commit the changes. Streamlit should redeploy automatically.
5. Select **FYERS live snapshot** in the app's Data source menu. Choose NIFTY or BANKNIFTY, select an expiry and refresh when you want a new snapshot.

The app uses the FYERS API v3 SDK. If FYERS returns an authentication or permission error, confirm that the access token is active and that the API app has market-data permissions. Token renewal/re-authentication is not automated in this starter version. Option-chain results depend on FYERS API availability, permissions and applicable rate limits.

The quote panel shows latest REST snapshots, not a continuous live ticker. WebSocket streaming can be added as a later step. The GEX proxy lot-size input defaults to 1 because the option-chain response does not include the contract lot size; enter the current official lot size if you want the proxy scaled by lots.

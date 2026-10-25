from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from src.adapters import load_chain_csv
from src.fyers_adapter import (
    DEFAULT_QUOTE_SYMBOLS, INDEX_SYMBOLS, get_option_chain,
    get_option_expiries, get_quotes, make_fyers_client,
)
from src.quant import enrich_chain, summarize_chain

BASE = Path(__file__).parent
DEMO = BASE / "data" / "sample" / "demo_option_chain.csv"

st.set_page_config(page_title="Indian Options Research Workbench", page_icon="📈", layout="wide")
st.title("Indian Options Research Workbench")
st.caption("Personal research prototype · India F&O · No live trading or order placement")

with st.sidebar:
    st.header("Data source")
    source = st.radio("Choose data source", ["FYERS live snapshot", "Synthetic demo data", "Upload licensed CSV"])
    st.markdown("---")
    st.markdown("**Research assumptions**")
    sign = st.selectbox("Dealer gamma sign assumption", ["No sign assumption (gross proxy)", "Assume dealers short gamma", "Assume dealers long gamma"])
    st.caption("Open interest alone does not reveal dealer positioning. The signed gamma view is illustrative only.")

if source == "FYERS live snapshot":
    st.info("FYERS data is requested when this page runs. Use Refresh data to request a new snapshot. This is not a continuous WebSocket ticker.")
    if st.button("🔄 Refresh data", type="primary"):
        st.rerun()
    try:
        app_id = st.secrets.get("FYERS_APP_ID", "")
        access_token = st.secrets.get("FYERS_ACCESS_TOKEN", "")
    except Exception:
        app_id, access_token = "", ""
    if not app_id or not access_token:
        st.error("FYERS credentials are not configured. Open Streamlit app settings → Secrets and add FYERS_APP_ID and FYERS_ACCESS_TOKEN.")
        st.code('FYERS_APP_ID = "YOUR_APP_ID"\nFYERS_ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"', language="toml")
        st.stop()
    try:
        client = make_fyers_client(str(app_id), str(access_token))
        st.subheader("Live price snapshots")
        quote_input = st.text_input("Quote symbols (comma-separated)", value=",".join(DEFAULT_QUOTE_SYMBOLS), help="Use FYERS symbol format, e.g. NSE:SBIN-EQ. Up to 50 symbols per request.")
        if st.button("Fetch quote snapshots"):
            st.session_state["fyers_quote_symbols"] = quote_input
        symbols_for_quotes = st.session_state.get("fyers_quote_symbols", quote_input)
        quote_df = get_quotes(client, [x.strip() for x in symbols_for_quotes.split(",")])
        if not quote_df.empty:
            st.dataframe(quote_df.drop(columns=["FYERS timestamp"], errors="ignore"), use_container_width=True, hide_index=True)
            st.caption("Quotes are latest API snapshots. Prices can be unavailable outside market hours or if the symbol/permission is unsupported.")
        else:
            st.warning("FYERS returned no quote rows for these symbols.")

        st.subheader("NIFTY / BANKNIFTY option-chain analytics")
        underlying_label = st.selectbox("Underlying index", list(INDEX_SYMBOLS.keys()))
        underlying_symbol = INDEX_SYMBOLS[underlying_label]
        strike_count = st.slider("Strikes on each side of ATM", min_value=1, max_value=20, value=10)
        expiries = get_option_expiries(client, underlying_symbol, strike_count=min(strike_count, 5))
        expiry_labels = [f"{item.get('date', item.get('expiry'))} ({'weekly' if item.get('expiry_flag') == 'W' else 'monthly/other'})" for item in expiries]
        selected_idx = st.selectbox("Expiry", list(range(len(expiries))), format_func=lambda i: expiry_labels[i])
        selected_expiry = expiries[selected_idx]
        chain_df, meta = get_option_chain(client, underlying_symbol, str(selected_expiry["expiry"]), strike_count=strike_count)
        lot_size = st.number_input("Contract lot size for gamma-exposure proxy", min_value=1, max_value=10000, value=1, step=1, help="FYERS option-chain response does not provide lot size per row. Enter the current exchange contract lot size if you want this proxy scaled by lots. Default 1 avoids assuming a possibly outdated lot size.")
        chain_df["lot_size"] = float(lot_size)
        st.caption(f"Source: FYERS API · {meta['underlying_symbol']} · Expiry {meta['expiry_text']} · Spot from response: {meta['spot']:,.2f}")
        if meta.get("india_vix") is not None:
            st.metric("India VIX (FYERS response)", f"{float(meta['india_vix']):.2f}")
        st.session_state["live_chain"] = chain_df
        st.session_state["live_chain_meta"] = meta
        raw = chain_df
        valuation_date = pd.Timestamp.now().date()
    except Exception as exc:
        st.error(f"Could not retrieve FYERS data: {exc}")
        st.info("Check the access token, API app permissions, symbol format, plan/rate limits and whether FYERS is returning market data. Do not paste credentials into chat or GitHub.")
        st.stop()
else:
    with st.sidebar:
        valuation_date = st.date_input("Valuation date", value=pd.Timestamp.now().date())
        uploaded = st.file_uploader("Upload your authorized option-chain CSV", type=["csv"]) if source == "Upload licensed CSV" else None
    try:
        if source == "Synthetic demo data":
            st.warning("Demo values are synthetic, not current market prices.")
            raw = load_chain_csv(DEMO)
        elif uploaded is not None:
            raw = load_chain_csv(uploaded)
        else:
            st.info("Upload a CSV to begin, or choose Synthetic demo data.")
            st.stop()
    except Exception as exc:
        st.error(f"Could not load data: {exc}")
        st.stop()

if source == "FYERS live snapshot":
    # The live API rows contain individual option-contract symbols, so do not offer those as underlying selectors.
    symbol = underlying_label
    df = raw.copy()
    expiry = str(df.expiry.iloc[0])
    # Keep the vendor-supplied Greeks visible for comparison; the workbench independently calculates reference Greeks too.
    st.caption("FYERS-provided Greeks are retained in the downloaded data when returned. The dashboard also computes independent Black–Scholes reference Greeks.")
else:
    symbols = sorted(raw.symbol.astype(str).unique())
    symbol = st.selectbox("Underlying / data symbol", symbols)
    df = raw[raw.symbol.astype(str) == symbol].copy()
    expiry_values = sorted(df.expiry.astype(str).unique())
    expiry = st.selectbox("Expiry", expiry_values)
    df = df[df.expiry.astype(str) == expiry].copy()

try:
    enriched = enrich_chain(df, valuation_date=valuation_date)
    summary = summarize_chain(enriched)
except Exception as exc:
    st.error(f"Could not calculate analytics: {exc}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
spot = float(df.spot.iloc[0])
c1.metric("Underlying spot", f"{spot:,.2f}")
c2.metric("Call OI", f"{summary['call_oi']:,.0f}")
c3.metric("Put OI", f"{summary['put_oi']:,.0f}")
c4.metric("Put/Call OI ratio", "N/A" if pd.isna(summary["pcr"]) else f"{summary['pcr']:.3f}")

st.subheader("Strike map")
by = summary["by_strike"].sort_values("strike")
fig = px.bar(by, x="strike", y=["call_oi", "put_oi"], barmode="group",
             title="Open interest by strike", labels={"value":"OI (contracts)", "strike":"Strike", "variable":"Option side"})
fig.add_vline(x=spot, line_dash="dash", annotation_text="Spot")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Gamma exposure proxy by strike")
gex = by[["strike","call_gamma_proxy","put_gamma_proxy","gross_gamma_proxy"]].melt(
    id_vars="strike", var_name="series", value_name="exposure")
if sign == "Assume dealers short gamma":
    gex["exposure"] = -gex["exposure"]
elif sign == "Assume dealers long gamma":
    gex["exposure"] = gex["exposure"]
fig2 = px.bar(gex, x="strike", y="exposure", color="series", barmode="relative",
              title="Modelled gamma exposure proxy (not dealer positions)",
              labels={"exposure":"Exposure proxy (currency units; model convention)", "strike":"Strike"})
fig2.add_vline(x=spot, line_dash="dash", annotation_text="Spot")
st.plotly_chart(fig2, use_container_width=True)
st.caption("Proxy convention: gamma × OI × entered lot size × spot² × 1%. Sign assumptions are illustrative. This is not observed dealer inventory.")

st.subheader("Options table")
show_cols = ["symbol","expiry","option_type","strike","spot","option_price","iv","iv_calc","oi","oi_change","volume","delta","gamma","vega_1pt","theta_per_day","gamma_exposure_proxy"]
extra_cols = [c for c in ["bid", "ask", "fyers_iv_percent", "fyers_delta", "fyers_gamma", "fyers_theta", "fyers_vega", "ltp_change", "oi_change_percent"] if c in enriched.columns]
st.dataframe(enriched[[c for c in show_cols + extra_cols if c in enriched.columns]].sort_values(["strike","option_type"]), use_container_width=True, hide_index=True)

csv_bytes = enriched.to_csv(index=False).encode("utf-8")
st.download_button("Download enriched CSV", data=csv_bytes, file_name=f"{symbol.replace(':','_')}_{expiry}_enriched.csv", mime="text/csv")

with st.expander("Calculation notes and limitations"):
    st.markdown("""
    - FYERS option-chain/quote results are API snapshots, not a continuously updating WebSocket ticker in this version.
    - Access depends on your FYERS app permissions, active token, API plan/rate limits, market hours and supported symbols.
    - FYERS IV is converted from percent to a fraction for the internal Black–Scholes reference model.
    - Greeks use a Black–Scholes European-option reference model with calendar-day time-to-expiry; they may differ from vendor Greeks.
    - The GEX proxy requires a correct current contract lot size. Default lot size is 1 because the option-chain payload does not supply it per row.
    - Open interest alone does not reveal dealer positions or dealer gamma sign.
    - This is a personal quantitative research tool, not investment advice or a trading recommendation. It cannot place orders.
    """)

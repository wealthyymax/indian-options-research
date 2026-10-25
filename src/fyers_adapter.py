"""FYERS API v3 market-data adapter. Never store credentials in source code."""
from __future__ import annotations

from datetime import datetime
from typing import Any
import pandas as pd

INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}
DEFAULT_QUOTE_SYMBOLS = [
    "NSE:NIFTY50-INDEX",
    "NSE:NIFTYBANK-INDEX",
    "NSE:INDIAVIX-INDEX",
]


def make_fyers_client(app_id: str, access_token: str):
    """Create the official FYERS API v3 SDK client from Streamlit secrets."""
    if not app_id or not access_token:
        raise ValueError("FYERS App ID and access token are required.")
    try:
        from fyers_apiv3 import fyersModel
    except ImportError as exc:
        raise RuntimeError(
            "FYERS SDK is not installed. Check requirements.txt and redeploy the app."
        ) from exc
    return fyersModel.FyersModel(
        client_id=app_id.strip(), token=access_token.strip(),
        is_async=False, log_path=""
    )


def _check_response(response: Any, operation: str) -> dict:
    if not isinstance(response, dict):
        raise RuntimeError(f"FYERS returned an unexpected response for {operation}.")
    status = str(response.get("s", "")).lower()
    code = response.get("code")
    if status == "error" or (code is not None and int(code) >= 400):
        # Do not dump headers, credentials, or complete response into the UI.
        message = response.get("message") or "FYERS rejected the request."
        raise RuntimeError(f"FYERS {operation} failed (code {code}): {message}")
    return response


def get_quotes(client, symbols: list[str]) -> pd.DataFrame:
    """Fetch a latest quote snapshot for up to 50 comma-separated symbols."""
    cleaned = list(dict.fromkeys(s.strip() for s in symbols if s.strip()))
    if not cleaned:
        raise ValueError("Enter at least one FYERS symbol.")
    if len(cleaned) > 50:
        raise ValueError("FYERS Quotes supports up to 50 symbols per request.")
    response = _check_response(client.quotes(data={"symbols": ",".join(cleaned)}), "quotes")
    rows = []
    for item in response.get("d", []):
        values = item.get("v") or {}
        rows.append({
            "Symbol": item.get("n", ""),
            "Status": item.get("s", ""),
            "Last price": values.get("lp"),
            "Change": values.get("ch"),
            "Change %": values.get("chp"),
            "Open": values.get("open_price"),
            "High": values.get("high_price"),
            "Low": values.get("low_price"),
            "Previous close": values.get("prev_close_price"),
            "Volume": values.get("volume"),
            "Bid": values.get("bid"),
            "Ask": values.get("ask"),
            "FYERS timestamp": values.get("tt"),
        })
    return pd.DataFrame(rows)


def get_option_expiries(client, underlying_symbol: str, strike_count: int = 5) -> list[dict]:
    """Fetch the available expiry list for an index's option chain."""
    response = _check_response(client.optionchain(data={
        "symbol": underlying_symbol,
        "strikecount": int(strike_count),
        "timestamp": "",
        "greeks": "1",
    }), "option chain")
    data = response.get("data") or {}
    expiries = data.get("expiryData") or []
    if not expiries:
        raise RuntimeError("FYERS returned no option expiries. Check symbol, permissions and market availability.")
    return expiries


def get_option_chain(client, underlying_symbol: str, expiry_epoch: str, strike_count: int = 10) -> tuple[pd.DataFrame, dict]:
    """Fetch a selected expiry and normalize it to the app's research schema."""
    response = _check_response(client.optionchain(data={
        "symbol": underlying_symbol,
        "strikecount": int(strike_count),
        "timestamp": str(expiry_epoch),
        "greeks": "1",
    }), "option chain")
    data = response.get("data") or {}
    chain = data.get("optionsChain") or []
    underlying = next((x for x in chain if x.get("option_type") == "" or x.get("strike_price") == -1), {})
    spot = underlying.get("ltp") or underlying.get("fp")
    if not spot:
        raise RuntimeError("FYERS did not return an underlying price for this option chain.")
    expiry_item = next((x for x in data.get("expiryData", []) if str(x.get("expiry")) == str(expiry_epoch)), None)
    expiry_text = (expiry_item or {}).get("date")
    if expiry_text:
        expiry_date = pd.to_datetime(expiry_text, dayfirst=True, errors="raise").date()
    else:
        expiry_date = datetime.fromtimestamp(int(expiry_epoch)).date()

    rows = []
    for item in chain:
        option_type = str(item.get("option_type", "")).upper()
        if option_type not in ("CE", "PE"):
            continue
        try:
            strike = float(item.get("strike_price"))
            option_price = float(item.get("ltp") or 0)
            oi = float(item.get("oi") or 0)
            volume = float(item.get("volume") or 0)
            # The FYERS chain returns IV in percent; the internal quant engine expects a fraction.
            greeks = item.get("greeks") or {}
            iv_pct = float(greeks.get("iv") or 0)
        except (TypeError, ValueError):
            continue
        if strike <= 0 or option_price <= 0:
            continue
        rows.append({
            "symbol": str(item.get("symbol") or underlying_symbol),
            "expiry": expiry_date,
            "option_type": option_type,
            "strike": strike,
            "spot": float(spot),
            "option_price": option_price,
            "iv": iv_pct / 100.0 if iv_pct > 0 else 0.0,
            "oi": oi,
            "oi_change": float(item.get("oich") or 0),
            "volume": volume,
            # FYERS option-chain response doesn't provide contract lot size in each row.
            # User-configured value defaults to 1 to avoid silently assuming an outdated lot size.
            "lot_size": 1.0,
            "risk_free_rate": 0.06,
            "fyers_iv_percent": iv_pct,
            "fyers_delta": greeks.get("delta"),
            "fyers_gamma": greeks.get("gamma"),
            "fyers_theta": greeks.get("theta"),
            "fyers_vega": greeks.get("vega"),
            "bid": item.get("bid"),
            "ask": item.get("ask"),
            "ltp_change": item.get("ltpch"),
            "oi_change_percent": item.get("oichp"),
        })
    if not rows:
        raise RuntimeError("No option contracts with usable prices were returned. Try during market hours or check expiry/access.")
    meta = {
        "spot": float(spot),
        "call_oi": data.get("callOi"),
        "put_oi": data.get("putOi"),
        "india_vix": (data.get("indiavixData") or {}).get("ltp"),
        "expiry_text": expiry_text or str(expiry_date),
        "underlying_symbol": underlying_symbol,
    }
    return pd.DataFrame(rows), meta

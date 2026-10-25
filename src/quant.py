"""Independent reference calculations for European options research.

GEX convention used here:
gamma_notional_proxy = gamma * OI * lot_size * spot^2 * 0.01
This estimates dollar-equivalent exposure for a 1% spot move per option side,
before any dealer-position sign assumption. It is not actual dealer GEX.
"""
from math import exp, log, sqrt
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq

def _validate(spot, strike, t, rate, sigma):
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive")
    if t <= 0:
        raise ValueError("time to expiry must be positive")
    if sigma <= 0:
        raise ValueError("volatility must be positive")

def bs_price(spot, strike, t, rate, sigma, option_type):
    _validate(spot, strike, t, rate, sigma)
    typ = option_type.upper()
    d1 = (log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    if typ in ("CE", "CALL", "C"):
        return spot * norm.cdf(d1) - strike * exp(-rate*t) * norm.cdf(d2)
    if typ in ("PE", "PUT", "P"):
        return strike * exp(-rate*t) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    raise ValueError("option_type must be CE/CALL/C or PE/PUT/P")

def bs_greeks(spot, strike, t, rate, sigma, option_type):
    _validate(spot, strike, t, rate, sigma)
    typ = option_type.upper()
    d1 = (log(spot / strike) + (rate + 0.5 * sigma * sigma) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    delta_call = norm.cdf(d1)
    delta = delta_call if typ in ("CE", "CALL", "C") else delta_call - 1.0
    gamma = norm.pdf(d1) / (spot * sigma * sqrt(t))
    vega_per_1vol_point = spot * norm.pdf(d1) * sqrt(t) * 0.01
    theta_annual = -(spot * norm.pdf(d1) * sigma) / (2 * sqrt(t))
    if typ in ("CE", "CALL", "C"):
        theta_annual -= rate * strike * exp(-rate*t) * norm.cdf(d2)
    elif typ in ("PE", "PUT", "P"):
        theta_annual += rate * strike * exp(-rate*t) * norm.cdf(-d2)
    else:
        raise ValueError("option_type must be CE/CALL/C or PE/PUT/P")
    return {"delta": float(delta), "gamma": float(gamma),
            "vega_1pt": float(vega_per_1vol_point),
            "theta_per_day": float(theta_annual / 365.0)}

def implied_volatility(price, spot, strike, t, rate, option_type):
    if price <= 0:
        return np.nan
    try:
        intrinsic = max(spot-strike, 0) if option_type.upper() in ("CE","CALL","C") else max(strike-spot, 0)
        if price < intrinsic * 0.999:
            return np.nan
        return float(brentq(lambda vol: bs_price(spot, strike, t, rate, vol, option_type)-price,
                            1e-4, 5.0, maxiter=200))
    except (ValueError, RuntimeError, OverflowError):
        return np.nan

def enrich_chain(df, valuation_date=None):
    """Add IV and Greeks. Expiry uses calendar days; no exchange holiday logic."""
    import pandas as pd
    out = df.copy()
    today = pd.Timestamp(valuation_date or pd.Timestamp.now().date()).date()
    ivs, deltas, gammas, vegas, thetas = [], [], [], [], []
    for row in out.itertuples():
        days = max((row.expiry - today).days, 0)
        t = max(days / 365.0, 1/36500)
        sigma = float(row.iv) if row.iv and row.iv > 0 else implied_volatility(
            row.option_price, row.spot, row.strike, t, row.risk_free_rate, row.option_type)
        if not np.isfinite(sigma) or sigma <= 0:
            sigma = np.nan
            greeks = {"delta":np.nan,"gamma":np.nan,"vega_1pt":np.nan,"theta_per_day":np.nan}
        else:
            greeks = bs_greeks(row.spot, row.strike, t, row.risk_free_rate, sigma, row.option_type)
        ivs.append(sigma)
        deltas.append(greeks["delta"]); gammas.append(greeks["gamma"])
        vegas.append(greeks["vega_1pt"]); thetas.append(greeks["theta_per_day"])
    out["iv_calc"] = ivs
    out["delta"] = deltas
    out["gamma"] = gammas
    out["vega_1pt"] = vegas
    out["theta_per_day"] = thetas
    out["gamma_exposure_proxy"] = out["gamma"] * out["oi"] * out["lot_size"] * out["spot"]**2 * 0.01
    out["delta_exposure_proxy"] = out["delta"] * out["oi"] * out["lot_size"] * out["spot"]
    return out

def summarize_chain(enriched):
    import pandas as pd
    calls = enriched[enriched.option_type == "CE"]
    puts = enriched[enriched.option_type == "PE"]
    call_oi = float(calls.oi.sum())
    put_oi = float(puts.oi.sum())
    pcr = put_oi / call_oi if call_oi else np.nan
    by_strike = enriched.groupby("strike", as_index=False).agg(
        call_oi=("oi", lambda s: float(s[enriched.loc[s.index, "option_type"].eq("CE")].sum())),
        put_oi=("oi", lambda s: float(s[enriched.loc[s.index, "option_type"].eq("PE")].sum())),
        call_gamma_proxy=("gamma_exposure_proxy", lambda s: float(s[enriched.loc[s.index, "option_type"].eq("CE")].sum())),
        put_gamma_proxy=("gamma_exposure_proxy", lambda s: float(s[enriched.loc[s.index, "option_type"].eq("PE")].sum())),
        total_volume=("volume", "sum"),
    )
    by_strike["gross_gamma_proxy"] = by_strike["call_gamma_proxy"] + by_strike["put_gamma_proxy"]
    return {"call_oi": call_oi, "put_oi": put_oi, "pcr": pcr, "by_strike": by_strike}

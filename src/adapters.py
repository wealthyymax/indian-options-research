"""Data adapters. Only load files/data that you are authorized to use."""
from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = [
    "symbol", "expiry", "option_type", "strike", "spot", "option_price",
    "iv", "oi", "oi_change", "volume", "lot_size", "risk_free_rate"
]

def load_chain_csv(file_or_path) -> pd.DataFrame:
    """Load and normalize a licensed CSV export into the internal schema."""
    df = pd.read_csv(file_or_path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(missing))
    df = df.copy()
    df["expiry"] = pd.to_datetime(df["expiry"], errors="raise").dt.date
    df["option_type"] = df["option_type"].astype(str).str.upper().replace(
        {"CALL": "CE", "PUT": "PE"}
    )
    if not df["option_type"].isin(["CE", "PE"]).all():
        raise ValueError("option_type must be CE/PE or CALL/PUT")
    numeric = ["strike", "spot", "option_price", "iv", "oi", "oi_change",
               "volume", "lot_size", "risk_free_rate"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[numeric].isna().any().any():
        raise ValueError("Numeric fields contain blank or invalid values.")
    if (df[["strike", "spot", "option_price", "lot_size"]] <= 0).any().any():
        raise ValueError("strike, spot, option_price and lot_size must be positive.")
    if (df["oi"] < 0).any() or (df["volume"] < 0).any():
        raise ValueError("oi and volume cannot be negative.")
    return df

from src.fyers_adapter import get_option_chain, get_option_expiries, get_quotes

class FakeFyers:
    def optionchain(self, data):
        if not data.get("timestamp"):
            return {"s": "ok", "code": 200, "data": {"expiryData": [{"date": "29-10-2026", "expiry": "1793232000", "expiry_flag": "W"}]}}
        return {"s": "ok", "code": 200, "data": {
            "expiryData": [{"date": "29-10-2026", "expiry": "1793232000", "expiry_flag": "W"}],
            "optionsChain": [
                {"symbol": "NSE:NIFTY50-INDEX", "option_type": "", "strike_price": -1, "ltp": 25000},
                {"symbol": "NSE:NIFTY2612925000CE", "option_type": "CE", "strike_price": 25000, "ltp": 120, "oi": 1000, "oich": 50, "volume": 5000, "greeks": {"iv": 20.0, "delta": 0.5}},
                {"symbol": "NSE:NIFTY2612925000PE", "option_type": "PE", "strike_price": 25000, "ltp": 110, "oi": 900, "oich": -20, "volume": 4500, "greeks": {"iv": 21.0, "delta": -0.5}},
            ], "callOi": 1000, "putOi": 900, "indiavixData": {"ltp": 14.2}
        }}

    def quotes(self, data):
        return {"s": "ok", "code": 200, "d": [{"n": "NSE:NIFTY50-INDEX", "s": "ok", "v": {"lp": 25000, "ch": 10, "chp": 0.04}}]}

def test_option_expiry_and_chain_normalization():
    client = FakeFyers()
    expiries = get_option_expiries(client, "NSE:NIFTY50-INDEX", 3)
    assert expiries[0]["expiry_flag"] == "W"
    df, meta = get_option_chain(client, "NSE:NIFTY50-INDEX", "1793232000", 3)
    assert len(df) == 2
    assert set(df.option_type) == {"CE", "PE"}
    assert df.loc[df.option_type == "CE", "iv"].iloc[0] == 0.20
    assert meta["spot"] == 25000

def test_quotes_normalization():
    df = get_quotes(FakeFyers(), ["NSE:NIFTY50-INDEX"])
    assert df.iloc[0]["Last price"] == 25000

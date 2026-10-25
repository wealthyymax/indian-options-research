import math
import pytest
from src.quant import bs_price, bs_greeks, implied_volatility

def test_call_put_prices_positive_and_put_call_parity():
    s, k, t, r, vol = 22000, 22000, 30/365, 0.06, 0.18
    call = bs_price(s,k,t,r,vol,"CE")
    put = bs_price(s,k,t,r,vol,"PE")
    assert call > 0 and put > 0
    assert abs((call-put) - (s-k*math.exp(-r*t))) < 1e-7

def test_gamma_positive_and_call_delta_range():
    g = bs_greeks(22000,22000,30/365,0.06,0.18,"CE")
    assert g["gamma"] > 0
    assert 0 < g["delta"] < 1

def test_iv_round_trip():
    args = (22000, 22000, 30/365, 0.06, 0.22, "CE")
    p = bs_price(*args)
    iv = implied_volatility(p, 22000, 22000, 30/365, 0.06, "CE")
    assert abs(iv-0.22) < 1e-5

def test_bad_spot_rejected():
    with pytest.raises(ValueError):
        bs_price(0, 22000, 0.1, 0.06, 0.2, "CE")

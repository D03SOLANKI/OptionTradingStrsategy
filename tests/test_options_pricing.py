"""
Unit Tests for Black-Scholes-Merton Pricing, Greeks, and Implied Volatility.
"""

import pytest
import math
from datetime import date
from src.options.pricing_engine import BlackScholesEngine
from src.options.strike_selector import StrikeSelector

def test_black_scholes_call_put_parity():
    """
    Verifies that C - P = S * exp(-q * T) - K * exp(-r * T) holds.
    """
    spot = 2500.0
    strike = 2500.0
    t = 30.0 / 365.0
    r = 0.065
    q = 0.012
    sigma = 0.22

    call_price = BlackScholesEngine.price_option(spot, strike, t, r, sigma, "CE", q)
    put_price = BlackScholesEngine.price_option(spot, strike, t, r, sigma, "PE", q)

    lhs = call_price - put_price
    rhs = spot * math.exp(-q * t) - strike * math.exp(-r * t)
    assert abs(lhs - rhs) < 0.01, f"Call-Put parity violated: {lhs} vs {rhs}"

def test_greeks_properties():
    """
    Verifies standard mathematical boundaries on Option Greeks.
    """
    spot = 2500.0
    strike = 2500.0
    t = 20.0 / 365.0
    r = 0.065
    q = 0.012
    sigma = 0.20

    call_greeks = BlackScholesEngine.calculate_greeks(spot, strike, t, r, sigma, "CE", q)
    put_greeks = BlackScholesEngine.calculate_greeks(spot, strike, t, r, sigma, "PE", q)

    # Call delta in (0, 1), Put delta in (-1, 0)
    assert 0.40 < call_greeks["delta"] < 0.60
    assert -0.60 < put_greeks["delta"] < -0.40

    # Gamma must be positive and identical for call and put
    assert call_greeks["gamma"] > 0
    assert abs(call_greeks["gamma"] - put_greeks["gamma"]) < 1e-6

    # Theta daily should be negative (time decay hurts long buyers)
    assert call_greeks["theta_daily"] < 0
    assert put_greeks["theta_daily"] < 0

    # Vega should be positive
    assert call_greeks["vega_1pct"] > 0

def test_implied_volatility_solver():
    """
    Verifies that IV solver recovers the input volatility accurately.
    """
    spot = 1200.0
    strike = 1200.0
    t = 15.0 / 365.0
    r = 0.065
    target_vol = 0.28

    market_price = BlackScholesEngine.price_option(spot, strike, t, r, target_vol, "CE")
    solved_iv = BlackScholesEngine.implied_volatility(market_price, spot, strike, t, r, "CE")

    assert solved_iv is not None
    assert abs(solved_iv - target_vol) < 0.001

def test_nse_last_thursday_expiry():
    """
    Verifies calculation of NSE monthly expiry (last Thursday).
    """
    # October 2026: 31 days. Oct 31, 2026 is a Saturday.
    # Thursdays in Oct 2026: Oct 1, 8, 15, 22, 29. Last Thursday is Oct 29.
    expiry_oct_2026 = StrikeSelector.get_last_thursday_of_month(2026, 10)
    assert expiry_oct_2026.year == 2026
    assert expiry_oct_2026.month == 10
    assert expiry_oct_2026.day == 29
    assert expiry_oct_2026.weekday() == 3 # Thursday

"""
Black-Scholes-Merton Option Pricing, Greeks, and Implied Volatility Engine.
Includes continuous dividend yield, robust numerical root-finding, and Greeks computation.
"""

import math
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from typing import Dict, Any, Tuple, Optional, Literal

class BlackScholesEngine:
    """
    Institutional Black-Scholes-Merton Analytical Engine for European Options.
    NSE Stock Options are European style (settled at expiry in cash/physical).
    """

    @staticmethod
    def calculate_d1_d2(
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> Tuple[float, float]:
        """
        Calculates d1 and d2 parameters with numerical safety checks.
        """
        if spot <= 0 or strike <= 0:
            raise ValueError(f"Spot ({spot}) and Strike ({strike}) must be strictly positive.")
        if time_to_expiry <= 1e-6:
            time_to_expiry = 1e-6
        if volatility <= 1e-5:
            volatility = 1e-5

        vol_sqrt_t = volatility * math.sqrt(time_to_expiry)
        numerator = math.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        d1 = numerator / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return d1, d2

    @classmethod
    def price_option(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: Literal["CE", "PE"],
        dividend_yield: float = 0.0
    ) -> float:
        """
        Calculates Black-Scholes theoretical option price.
        time_to_expiry is in years (e.g. 10 days = 10 / 365).
        """
        if time_to_expiry <= 1e-6:
            # Intrinsic value at expiration
            if option_type == "CE":
                return max(0.0, spot - strike)
            else:
                return max(0.0, strike - spot)

        d1, d2 = cls.calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        df_div = math.exp(-dividend_yield * time_to_expiry)
        df_rate = math.exp(-rate * time_to_expiry)

        if option_type == "CE":
            price = spot * df_div * norm.cdf(d1) - strike * df_rate * norm.cdf(d2)
        elif option_type == "PE":
            price = strike * df_rate * norm.cdf(-d2) - spot * df_div * norm.cdf(-d1)
        else:
            raise ValueError(f"Invalid option type: {option_type}. Must be 'CE' or 'PE'.")

        return max(0.0, float(price))

    @classmethod
    def calculate_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: Literal["CE", "PE"],
        dividend_yield: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculates Delta, Gamma, Theta (per calendar day), Vega (per 1% IV), and Rho.
        """
        if time_to_expiry <= 1e-6:
            is_itm = (spot > strike) if option_type == "CE" else (spot < strike)
            return {
                "delta": 1.0 if (option_type == "CE" and is_itm) else (-1.0 if (option_type == "PE" and is_itm) else 0.0),
                "gamma": 0.0,
                "theta_daily": 0.0,
                "vega_1pct": 0.0,
                "rho": 0.0,
            }

        d1, d2 = cls.calculate_d1_d2(spot, strike, time_to_expiry, rate, volatility, dividend_yield)
        df_div = math.exp(-dividend_yield * time_to_expiry)
        df_rate = math.exp(-rate * time_to_expiry)
        sqrt_t = math.sqrt(time_to_expiry)
        pdf_d1 = norm.pdf(d1)

        # Delta
        if option_type == "CE":
            delta = df_div * norm.cdf(d1)
        else:
            delta = -df_div * norm.cdf(-d1)

        # Gamma (identical for Call and Put)
        gamma = (df_div * pdf_d1) / (spot * volatility * sqrt_t) if (spot * volatility * sqrt_t) > 0 else 0.0

        # Vega (per 1% volatility change, i.e., 0.01 in sigma)
        vega_total = spot * df_div * sqrt_t * pdf_d1
        vega_1pct = vega_total * 0.01

        # Theta (per year converted to per calendar day = / 365)
        term1 = -(spot * df_div * pdf_d1 * volatility) / (2.0 * sqrt_t)
        if option_type == "CE":
            term2 = -rate * strike * df_rate * norm.cdf(d2) + dividend_yield * spot * df_div * norm.cdf(d1)
        else:
            term2 = rate * strike * df_rate * norm.cdf(-d2) - dividend_yield * spot * df_div * norm.cdf(-d1)

        theta_annual = term1 + term2
        theta_daily = theta_annual / 365.0

        # Rho (per 1% interest rate change = * 0.01)
        if option_type == "CE":
            rho = strike * time_to_expiry * df_rate * norm.cdf(d2) * 0.01
        else:
            rho = -strike * time_to_expiry * df_rate * norm.cdf(-d2) * 0.01

        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "theta_daily": float(theta_daily),
            "vega_1pct": float(vega_1pct),
            "rho": float(rho),
        }

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        option_type: Literal["CE", "PE"],
        dividend_yield: float = 0.0,
        initial_vol_guess: float = 0.25,
        max_iter: int = 100,
        tol: float = 1e-5
    ) -> Optional[float]:
        """
        Solves for implied volatility using robust Newton-Raphson with Brent's method fallback.
        Returns None if market price violates arbitrage bounds or cannot converge.
        """
        if market_price <= 0 or time_to_expiry <= 1e-6:
            return None

        # Check intrinsic lower bound
        df_rate = math.exp(-rate * time_to_expiry)
        df_div = math.exp(-dividend_yield * time_to_expiry)
        intrinsic = max(0.0, spot * df_div - strike * df_rate) if option_type == "CE" else max(0.0, strike * df_rate - spot * df_div)
        if market_price < intrinsic - 1e-4:
            return None

        # Newton-Raphson iteration
        vol = max(0.05, min(initial_vol_guess, 2.0))
        for _ in range(max_iter):
            price = cls.price_option(spot, strike, time_to_expiry, rate, vol, option_type, dividend_yield)
            diff = price - market_price
            if abs(diff) < tol:
                return float(vol)

            d1, _ = cls.calculate_d1_d2(spot, strike, time_to_expiry, rate, vol, dividend_yield)
            vega = spot * df_div * math.sqrt(time_to_expiry) * norm.pdf(d1)
            if vega < 1e-8:
                break
            vol_step = diff / vega
            vol -= vol_step
            if vol <= 0.001 or vol > 5.0:
                break

        # Fallback to Brent's method bracket search
        def objective(sigma: float) -> float:
            return cls.price_option(spot, strike, time_to_expiry, rate, sigma, option_type, dividend_yield) - market_price

        try:
            low_vol, high_vol = 0.01, 4.0
            p_low = objective(low_vol)
            p_high = objective(high_vol)
            if p_low * p_high <= 0:
                return float(brentq(objective, low_vol, high_vol, xtol=tol, maxiter=100))
        except Exception:
            pass

        return None

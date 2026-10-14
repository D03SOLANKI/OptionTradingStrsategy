"""
Option Strike and Expiry Selection Module for NSE Derivatives.
Implements NSE last-Thursday monthly expiry calculations, strike grid rounding,
and dynamic strike selection based on ATM, ITM, OTM, or Target Delta.
"""

import math
import calendar
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass

from src.config.nse_symbols import get_symbol_spec, SymbolSpec
from src.options.pricing_engine import BlackScholesEngine

@dataclass
class OptionContract:
    symbol: str
    underlying_symbol: str
    expiry_date: date
    strike: float
    option_type: Literal["CE", "PE"]
    lot_size: int
    dte_days: int
    dte_years: float
    spot_price: float
    theoretical_price: float
    bid_price: float
    ask_price: float
    delta: float
    gamma: float
    theta_daily: float
    vega_1pct: float
    implied_volatility: float
    spread_pct: float

class StrikeSelector:
    """
    Intelligent Strike and Expiry Selector for Indian Equity Options.
    """

    @staticmethod
    def get_last_thursday_of_month(year: int, month: int) -> date:
        """
        Calculates the last Thursday of the specified month and year (standard NSE expiry).
        """
        _, last_day = calendar.monthrange(year, month)
        d = date(year, month, last_day)
        # weekday(): Monday is 0, Thursday is 3
        offset = (d.weekday() - 3) % 7
        last_thursday = d - timedelta(days=offset)
        return last_thursday

    @classmethod
    def get_valid_expiry_dates(
        cls,
        current_date: date,
        min_dte: int = 2,
        max_dte: int = 40,
        num_expiries: int = 3
    ) -> List[date]:
        """
        Finds valid monthly expiry dates within [min_dte, max_dte] range from current_date.
        """
        expiries = []
        year = current_date.year
        month = current_date.month

        for _ in range(num_expiries + 2):
            expiry = cls.get_last_thursday_of_month(year, month)
            dte = (expiry - current_date).days
            if dte >= min_dte and dte <= max_dte:
                expiries.append(expiry)

            # Move to next month
            month += 1
            if month > 12:
                month = 1
                year += 1

        expiries.sort()
        return expiries[:num_expiries]

    @staticmethod
    def round_to_strike(price: float, strike_step: float) -> float:
        """
        Rounds price to nearest valid NSE strike price.
        """
        return round(price / strike_step) * strike_step

    @classmethod
    def generate_strike_chain(
        cls,
        spot_price: float,
        strike_step: float,
        num_strikes_each_side: int = 4
    ) -> List[float]:
        """
        Generates symmetric grid of strikes around current spot price.
        """
        atm_strike = cls.round_to_strike(spot_price, strike_step)
        strikes = []
        for i in range(-num_strikes_each_side, num_strikes_each_side + 1):
            strikes.append(round(atm_strike + i * strike_step, 2))
        return sorted(strikes)

    @classmethod
    def select_best_contract(
        cls,
        symbol: str,
        current_datetime: datetime,
        spot_price: float,
        option_type: Literal["CE", "PE"],
        volatility: float,
        mode: Literal["ATM", "ITM1", "OTM1", "DELTA_TARGET"] = "ATM",
        target_delta: float = 0.50,
        min_dte: int = 2,
        max_dte: int = 35,
        risk_free_rate: float = 0.065,
        dividend_yield: float = 0.012,
        max_spread_pct: float = 0.035
    ) -> Optional[OptionContract]:
        """
        Dynamically selects the optimal option contract based on liquidity,
        moneyness/delta, expiry horizon, and Greeks profile.
        """
        spec: SymbolSpec = get_symbol_spec(symbol)
        curr_date = current_datetime.date() if isinstance(current_datetime, datetime) else current_datetime
        valid_expiries = cls.get_valid_expiry_dates(curr_date, min_dte=min_dte, max_dte=max_dte)

        if not valid_expiries:
            return None

        # Prefer nearest valid expiry that satisfies min_dte
        chosen_expiry = valid_expiries[0]
        dte_days = (chosen_expiry - curr_date).days
        dte_years = max(1e-5, dte_days / 365.0)

        strikes = cls.generate_strike_chain(spot_price, spec.strike_step, num_strikes_each_side=5)
        atm_strike = cls.round_to_strike(spot_price, spec.strike_step)

        # Build candidate contracts
        candidate_contracts: List[OptionContract] = []
        for k in strikes:
            price = BlackScholesEngine.price_option(
                spot=spot_price,
                strike=k,
                time_to_expiry=dte_years,
                rate=risk_free_rate,
                volatility=volatility,
                option_type=option_type,
                dividend_yield=dividend_yield
            )
            greeks = BlackScholesEngine.calculate_greeks(
                spot=spot_price,
                strike=k,
                time_to_expiry=dte_years,
                rate=risk_free_rate,
                volatility=volatility,
                option_type=option_type,
                dividend_yield=dividend_yield
            )

            # Realistic simulated market bid-ask spread
            # In liquid NSE options, spread is roughly 0.5% - 2.0% for ATM, wider for deep OTM
            moneyness = abs(math.log(spot_price / k))
            base_spread_pct = min(0.04, 0.008 + 0.03 * moneyness)
            half_spread = price * (base_spread_pct / 2.0)
            bid = max(0.05, round((price - half_spread) / 0.05) * 0.05)
            ask = max(0.05, round((price + half_spread) / 0.05) * 0.05)
            spread_pct = (ask - bid) / price if price > 0 else 1.0

            contract = OptionContract(
                symbol=f"{symbol}{chosen_expiry.strftime('%y%b').upper()}{int(k)}{option_type}",
                underlying_symbol=symbol,
                expiry_date=chosen_expiry,
                strike=k,
                option_type=option_type,
                lot_size=spec.lot_size,
                dte_days=dte_days,
                dte_years=dte_years,
                spot_price=spot_price,
                theoretical_price=round(price, 2),
                bid_price=round(bid, 2),
                ask_price=round(ask, 2),
                delta=round(greeks["delta"], 4),
                gamma=round(greeks["gamma"], 6),
                theta_daily=round(greeks["theta_daily"], 3),
                vega_1pct=round(greeks["vega_1pct"], 3),
                implied_volatility=round(volatility, 4),
                spread_pct=round(spread_pct, 4)
            )
            candidate_contracts.append(contract)

        # Select strike according to mode
        if mode == "ATM":
            chosen = min(candidate_contracts, key=lambda c: abs(c.strike - atm_strike))
        elif mode == "ITM1":
            if option_type == "CE":
                target_k = atm_strike - spec.strike_step
            else:
                target_k = atm_strike + spec.strike_step
            chosen = min(candidate_contracts, key=lambda c: abs(c.strike - target_k))
        elif mode == "OTM1":
            if option_type == "CE":
                target_k = atm_strike + spec.strike_step
            else:
                target_k = atm_strike - spec.strike_step
            chosen = min(candidate_contracts, key=lambda c: abs(c.strike - target_k))
        elif mode == "DELTA_TARGET":
            # For CE: target_delta ~ 0.50; For PE: abs(delta) ~ 0.50
            chosen = min(candidate_contracts, key=lambda c: abs(abs(c.delta) - abs(target_delta)))
        else:
            chosen = min(candidate_contracts, key=lambda c: abs(c.strike - atm_strike))

        # Check spread filter
        if chosen.spread_pct > max_spread_pct:
            # Check if ATM meets spread filter as fallback
            atm_contract = min(candidate_contracts, key=lambda c: abs(c.strike - atm_strike))
            if atm_contract.spread_pct <= max_spread_pct:
                return atm_contract

        return chosen

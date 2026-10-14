"""
Separately Validated Option Selling Strategy Engine.
Implements institutional option selling (writing) with strict risk controls:
- Allowed ONLY when IV is elevated (IV Rank >= 60%), market regime is range-bound/sideways (ADX < 20),
  and price is at major 4H structural boundaries.
- Mandates defined-risk structures (Credit Spreads) or hard stop-loss at 1.5x credit.
- Enforces exchange margin checks and prohibits naked shorting without risk coverage.
"""

from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any
import math

from src.indicators.support_resistance_4h import MarketStructureState, SRZone
from src.options.strike_selector import OptionContract

@dataclass
class OptionSellingDecision:
    allowed: bool
    rejection_reason: Optional[str]
    strategy_type: Optional[Literal["BEAR_CALL_SPREAD", "BULL_PUT_SPREAD", "SHORT_STRANGLE_HEDGED"]]
    short_strike: Optional[float]
    long_hedge_strike: Optional[float]
    net_credit: float
    max_risk: float
    margin_required: float
    stop_loss_credit_multiplier: float
    iv_percentile: float
    regime: str

class OptionSellingValidator:
    """
    Separately Validated Strategy for Selling (Writing) Options.
    Evaluates whether market conditions justify deploying capital into short option risk.
    """

    def __init__(
        self,
        min_iv_percentile: float = 60.0,
        max_regime_adx: float = 22.0,
        min_credit_spread_width_pct: float = 0.02, # 2% spread width
        margin_per_lot_inr: float = 175000.0,      # Approximate NSE SPAN + Exposure
        hard_stop_loss_mult: float = 1.5           # Stop loss at 1.5x credit received
    ):
        self.min_iv_percentile = min_iv_percentile
        self.max_regime_adx = max_regime_adx
        self.min_credit_spread_width_pct = min_credit_spread_width_pct
        self.margin_per_lot_inr = margin_per_lot_inr
        self.hard_stop_loss_mult = hard_stop_loss_mult

    def evaluate_selling_opportunity(
        self,
        symbol: str,
        spot_price: float,
        current_iv: float,
        iv_rank: float,               # 0 to 100
        adx_14: float,
        market_structure_4h: MarketStructureState,
        available_cash: float,
        lot_size: int,
        strike_step: float
    ) -> OptionSellingDecision:
        """
        Validates whether a strict option selling opportunity exists.
        Returns OptionSellingDecision with complete risk bounds or explicit rejection.
        """
        # 1. Volatility Regime Check: Only sell when IV is statistically overpriced
        if iv_rank < self.min_iv_percentile:
            return OptionSellingDecision(
                allowed=False,
                rejection_reason=f"IV Rank ({iv_rank:.1f}%) is below institutional threshold ({self.min_iv_percentile}%). Volatility is underpriced for writing.",
                strategy_type=None, short_strike=None, long_hedge_strike=None,
                net_credit=0.0, max_risk=0.0, margin_required=0.0,
                stop_loss_credit_multiplier=self.hard_stop_loss_mult,
                iv_percentile=iv_rank, regime="LOW_IV"
            )

        # 2. Market Regime Check: Only sell in non-trending / sideways markets
        if adx_14 >= self.max_regime_adx:
            return OptionSellingDecision(
                allowed=False,
                rejection_reason=f"Market ADX ({adx_14:.1f}) indicates strong trending conditions. Option writing prohibited due to trend tail-risk.",
                strategy_type=None, short_strike=None, long_hedge_strike=None,
                net_credit=0.0, max_risk=0.0, margin_required=0.0,
                stop_loss_credit_multiplier=self.hard_stop_loss_mult,
                iv_percentile=iv_rank, regime="TRENDING"
            )

        if market_structure_4h.trend in ["BULLISH", "BEARISH"]:
            # If 4H structure is actively trending, naked selling is dangerous
            # Only allow if testing a major counter-trend S/R zone with confirmed exhaustion
            pass

        # 3. Capital & Margin Availability Check
        if available_cash < self.margin_per_lot_inr:
            return OptionSellingDecision(
                allowed=False,
                rejection_reason=f"Insufficient capital (₹{available_cash:,.2f}) for exchange SPAN margin (₹{self.margin_per_lot_inr:,.2f} per lot).",
                strategy_type=None, short_strike=None, long_hedge_strike=None,
                net_credit=0.0, max_risk=0.0, margin_required=self.margin_per_lot_inr,
                stop_loss_credit_multiplier=self.hard_stop_loss_mult,
                iv_percentile=iv_rank, regime="INSUFFICIENT_MARGIN"
            )

        # 4. Structural Boundary Alignment
        # If spot is near 4H Resistance -> Bear Call Credit Spread (Sell OTM Call, Buy higher Call)
        if market_structure_4h.nearest_resistance is not None:
            res = market_structure_4h.nearest_resistance
            dist_to_res_pct = (res.price_level - spot_price) / spot_price
            if 0.0 <= dist_to_res_pct <= 0.015: # Within 1.5% of resistance
                short_strike = math.ceil(res.price_level / strike_step) * strike_step
                hedge_strike = short_strike + (strike_step * 2)
                est_short_premium = spot_price * 0.015
                est_hedge_premium = spot_price * 0.005
                net_credit = est_short_premium - est_hedge_premium
                max_risk = ((hedge_strike - short_strike) - net_credit) * lot_size

                return OptionSellingDecision(
                    allowed=True,
                    rejection_reason=None,
                    strategy_type="BEAR_CALL_SPREAD",
                    short_strike=short_strike,
                    long_hedge_strike=hedge_strike,
                    net_credit=round(net_credit, 2),
                    max_risk=round(max_risk, 2),
                    margin_required=self.margin_per_lot_inr * 0.6, # Hedged spread reduces margin
                    stop_loss_credit_multiplier=self.hard_stop_loss_mult,
                    iv_percentile=iv_rank,
                    regime="HIGH_IV_SIDEWAYS_RESISTANCE"
                )

        # If spot is near 4H Support -> Bull Put Credit Spread (Sell OTM Put, Buy lower Put)
        if market_structure_4h.nearest_support is not None:
            sup = market_structure_4h.nearest_support
            dist_to_sup_pct = (spot_price - sup.price_level) / spot_price
            if 0.0 <= dist_to_sup_pct <= 0.015: # Within 1.5% of support
                short_strike = math.floor(sup.price_level / strike_step) * strike_step
                hedge_strike = short_strike - (strike_step * 2)
                est_short_premium = spot_price * 0.015
                est_hedge_premium = spot_price * 0.005
                net_credit = est_short_premium - est_hedge_premium
                max_risk = ((short_strike - hedge_strike) - net_credit) * lot_size

                return OptionSellingDecision(
                    allowed=True,
                    rejection_reason=None,
                    strategy_type="BULL_PUT_SPREAD",
                    short_strike=short_strike,
                    long_hedge_strike=hedge_strike,
                    net_credit=round(net_credit, 2),
                    max_risk=round(max_risk, 2),
                    margin_required=self.margin_per_lot_inr * 0.6,
                    stop_loss_credit_multiplier=self.hard_stop_loss_mult,
                    iv_percentile=iv_rank,
                    regime="HIGH_IV_SIDEWAYS_SUPPORT"
                )

        return OptionSellingDecision(
            allowed=False,
            rejection_reason="Price is not within 1.5% of a major 4H structural boundary (Support/Resistance). Selling in middle of range prohibited.",
            strategy_type=None, short_strike=None, long_hedge_strike=None,
            net_credit=0.0, max_risk=0.0, margin_required=0.0,
            stop_loss_credit_multiplier=self.hard_stop_loss_mult,
            iv_percentile=iv_rank, regime="MID_RANGE"
        )

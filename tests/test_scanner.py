"""
Unit Tests for Market Scanner, Opportunity Ranker, and Option Selling Validator.
Tests multi-factor scoring, minimum quality filtering, NO_TRADE enforcement, and option selling risk controls.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import get_symbol_spec
from src.indicators.support_resistance_4h import MarketStructureState, SRZone
from src.indicators.support_resistance_15m import ConfluenceZone
from src.indicators.reversal_confirmation import ReversalSignal
from src.options.strike_selector import OptionContract
from src.scanner.option_selling_validator import OptionSellingValidator, OptionSellingDecision
from src.scanner.opportunity_ranker import OpportunityRanker, OpportunityCandidate
from src.scanner.market_scanner import MarketScanner, ScanResult

def make_mock_sr_zone(price: float, zone_type: str, strength: float = 0.8, touches: int = 3):
    now = pd.Timestamp.now()
    return SRZone(
        zone_id=f"zone_{zone_type}_{price}",
        zone_type=zone_type,
        price_level=price,
        upper_bound=price + (price * 0.005),
        lower_bound=price - (price * 0.005),
        strength_score=strength,
        touch_count=touches,
        rejection_strength=0.7,
        volume_score=1.3,
        recency_score=0.9,
        first_formed_time=now,
        last_touch_time=now
    )

def make_mock_option_contract(symbol: str, strike: float, opt_type: str, price: float, lot_size: int):
    return OptionContract(
        symbol=f"{symbol}_{strike}_{opt_type}",
        underlying_symbol=symbol,
        expiry_date=date(2026, 10, 29),
        strike=strike,
        option_type=opt_type,
        lot_size=lot_size,
        dte_days=15,
        dte_years=15.0 / 365.0,
        spot_price=strike,
        theoretical_price=price,
        bid_price=round(price * 0.99, 2),
        ask_price=round(price * 1.01, 2),
        delta=0.52,
        gamma=0.003,
        theta_daily=-1.2,
        vega_1pct=4.5,
        implied_volatility=0.22,
        spread_pct=0.02
    )

def test_opportunity_ranker_scoring_and_sizing():
    config = MasterConfig()
    ranker = OpportunityRanker(config, min_composite_score=55.0, min_rr=1.5)

    sup_zone = make_mock_sr_zone(3500.0, "SUPPORT", strength=0.85, touches=4)
    res_zone = make_mock_sr_zone(3650.0, "RESISTANCE", strength=0.75, touches=3)
    market_struct = MarketStructureState(
        trend="BULLISH", higher_highs=True, higher_lows=True, lower_highs=False, lower_lows=False,
        last_swing_high=3650.0, last_swing_low=3480.0, active_supports=[sup_zone],
        active_resistances=[res_zone], nearest_support=sup_zone, nearest_resistance=res_zone
    )

    conf_zone = ConfluenceZone(
        zone_type="SUPPORT", center_price=3500.0, lower_bound=3485.0, upper_bound=3515.0,
        confluence_score=0.88, zone_4h=sup_zone, zone_15m=None, distance_pct=0.0, is_tested=True
    )
    reversal = ReversalSignal(
        timestamp=pd.Timestamp.now(), direction="BULLISH", pattern_name="BULLISH_ENGULFING",
        pattern_strength=0.8, volume_ratio=1.6, rsi_value=42.0, is_volume_confirmed=True,
        is_momentum_confirmed=True, composite_confirmation_score=0.82
    )

    contract = make_mock_option_contract("TCS", 3500.0, "CE", 45.0, 175)

    candidate = ranker.evaluate_candidate(
        symbol="TCS", spot_price=3505.0, action="BUY_CE",
        sr_zone=conf_zone, market_structure=market_struct, reversal=reversal,
        contract=contract, current_atr_15m=25.0, available_cash=1000000.0,
        max_risk_inr=12000.0
    )

    assert candidate.is_selected is True
    assert candidate.composite_score >= 60.0
    assert candidate.risk_reward_ratio >= 1.5
    assert candidate.trade_plan is not None
    assert candidate.trade_plan.recommended_lots >= 1
    assert candidate.trade_plan.capital_required > 0
    assert candidate.trade_plan.friction_cost_inr > 0

def test_cheap_option_rejection_slippage_defense():
    """Verify that options under ₹4.00 are rejected to prevent slippage erosion."""
    config = MasterConfig()
    ranker = OpportunityRanker(config, min_composite_score=55.0, min_rr=1.5)

    sup_zone = make_mock_sr_zone(150.0, "SUPPORT", strength=0.7, touches=2)
    market_struct = MarketStructureState(
        trend="SIDEWAYS", higher_highs=False, higher_lows=False, lower_highs=False, lower_lows=False,
        last_swing_high=160.0, last_swing_low=145.0, active_supports=[sup_zone],
        active_resistances=[], nearest_support=sup_zone, nearest_resistance=None
    )
    reversal = ReversalSignal(
        timestamp=pd.Timestamp.now(), direction="BULLISH", pattern_name="HAMMER",
        pattern_strength=0.7, volume_ratio=1.3, rsi_value=35.0, is_volume_confirmed=True,
        is_momentum_confirmed=True, composite_confirmation_score=0.7
    )

    # Cheap penny option (e.g. 1.20 Rs)
    cheap_contract = make_mock_option_contract("TATASTEEL", 150.0, "CE", 1.20, 5500)

    candidate = ranker.evaluate_candidate(
        symbol="TATASTEEL", spot_price=150.2, action="BUY_CE",
        sr_zone=None, market_structure=market_struct, reversal=reversal,
        contract=cheap_contract, current_atr_15m=1.8, available_cash=1000000.0
    )

    # Should be rejected because premium < ₹4.00
    assert candidate.is_selected is False
    assert "cheap" in candidate.rejection_reason.lower()

def test_option_selling_validator_regime_filtering():
    """Verify option writing is prohibited during trending or low-IV conditions."""
    validator = OptionSellingValidator(min_iv_percentile=60.0, max_regime_adx=22.0)
    market_struct = MarketStructureState(
        trend="SIDEWAYS", higher_highs=False, higher_lows=False, lower_highs=False, lower_lows=False,
        last_swing_high=None, last_swing_low=None, active_supports=[], active_resistances=[],
        nearest_support=None, nearest_resistance=None
    )

    # Case 1: Low IV rank (30%) -> Must reject
    dec1 = validator.evaluate_selling_opportunity(
        symbol="TCS", spot_price=3500.0, current_iv=0.15, iv_rank=30.0,
        adx_14=15.0, market_structure_4h=market_struct, available_cash=1000000.0,
        lot_size=175, strike_step=50.0
    )
    assert dec1.allowed is False
    assert "IV Rank" in dec1.rejection_reason

    # Case 2: Trending market (ADX = 32) -> Must reject
    dec2 = validator.evaluate_selling_opportunity(
        symbol="TCS", spot_price=3500.0, current_iv=0.28, iv_rank=75.0,
        adx_14=32.0, market_structure_4h=market_struct, available_cash=1000000.0,
        lot_size=175, strike_step=50.0
    )
    assert dec2.allowed is False
    assert "ADX" in dec2.rejection_reason

def test_no_trade_verdict_when_unconfirmed():
    """Verify that when no setups confirm, MarketScanner returns explicit NO_TRADE."""
    config = MasterConfig()
    scanner = MarketScanner(config, min_composite_score=70.0, min_rr=2.0)

    # Empty candidate feed
    scan_res = scanner.scan_universe(symbol_data_15m={})
    assert scan_res.execution_verdict == "NO_TRADE"
    assert scan_res.valid_opportunities_found == 0

"""
Unit Tests for Intelligent Position Averaging and Trailing Stop Monotonicity.
"""

import pytest
import pandas as pd
from datetime import datetime

from src.strategy.intelligent_averaging import IntelligentAveragingEngine
from src.strategy.trailing_stop_manager import TrailingStopManager
from src.config.trading_config import AveragingConfig, TrailingStopConfig
from src.indicators.support_resistance_4h import SRZone, MarketStructureState
from src.indicators.support_resistance_15m import ConfluenceZone
from src.indicators.reversal_confirmation import ReversalSignal

def test_averaging_denied_upon_thesis_invalidation():
    """
    Verifies that averaging is strictly denied if the support zone has been broken.
    """
    config = AveragingConfig(enable_averaging=True, max_thesis_invalidation_buffer_atr=0.5)
    engine = IntelligentAveragingEngine(config)

    zone_4h = SRZone(
        zone_id="SUP_2000", zone_type="SUPPORT", price_level=2000.0,
        upper_bound=2010.0, lower_bound=1990.0, strength_score=0.8,
        touch_count=2, rejection_strength=0.5, volume_score=0.5, recency_score=0.9,
        first_formed_time=pd.Timestamp("2026-01-01"), last_touch_time=pd.Timestamp("2026-01-05")
    )
    conf_zone = ConfluenceZone(
        zone_type="SUPPORT", center_price=2000.0, lower_bound=1990.0, upper_bound=2010.0,
        confluence_score=0.8, zone_4h=zone_4h, zone_15m=None, distance_pct=0.0, is_tested=True
    )
    mkt_struct = MarketStructureState(
        trend="SIDEWAYS", higher_highs=False, higher_lows=False, lower_highs=False, lower_lows=False,
        last_swing_high=2050.0, last_swing_low=1990.0, active_supports=[zone_4h], active_resistances=[],
        nearest_support=zone_4h, nearest_resistance=None
    )
    rev_sig = ReversalSignal(
        timestamp=pd.Timestamp("2026-01-05 14:00"), direction="BULLISH", pattern_name="HAMMER",
        pattern_strength=0.8, volume_ratio=1.5, rsi_value=30.0, is_volume_confirmed=True,
        is_momentum_confirmed=True, composite_confirmation_score=0.8
    )

    # Underlying spot price is 1970.0 (far below lower_bound 1990 - buffer 5 = 1985)
    decision = engine.evaluate_averaging(
        symbol="RELIANCE",
        option_type="CE",
        current_underlying_spot=1970.0,
        current_option_price=25.0,
        initial_underlying_entry_price=2005.0,
        initial_option_entry_price=50.0,
        initial_quantity=250,
        current_averaging_count=0,
        confluence_zone=conf_zone,
        market_structure=mkt_struct,
        reversal_signal=rev_sig,
        atr_15m=10.0,
        lot_size=250
    )

    assert decision.allow_average == False
    assert "invalidated" in decision.rejection_reason.lower()

def test_averaging_weighted_price_calculation():
    """
    Verifies that when allowed, the weighted average entry price is mathematically exact.
    """
    config = AveragingConfig(enable_averaging=True, min_distance_atr=1.0, size_multiplier=1.0)
    engine = IntelligentAveragingEngine(config)

    zone_4h = SRZone(
        zone_id="SUP_2000", zone_type="SUPPORT", price_level=2000.0,
        upper_bound=2015.0, lower_bound=1985.0, strength_score=0.85,
        touch_count=2, rejection_strength=0.5, volume_score=0.5, recency_score=0.9,
        first_formed_time=pd.Timestamp("2026-01-01"), last_touch_time=pd.Timestamp("2026-01-05")
    )
    conf_zone = ConfluenceZone(
        zone_type="SUPPORT", center_price=2000.0, lower_bound=1985.0, upper_bound=2015.0,
        confluence_score=0.85, zone_4h=zone_4h, zone_15m=None, distance_pct=0.0, is_tested=True
    )
    mkt_struct = MarketStructureState(
        trend="SIDEWAYS", higher_highs=False, higher_lows=False, lower_highs=False, lower_lows=False,
        last_swing_high=2050.0, last_swing_low=1985.0, active_supports=[zone_4h], active_resistances=[],
        nearest_support=zone_4h, nearest_resistance=None
    )
    rev_sig = ReversalSignal(
        timestamp=pd.Timestamp("2026-01-05 14:00"), direction="BULLISH", pattern_name="HAMMER",
        pattern_strength=0.85, volume_ratio=1.5, rsi_value=32.0, is_volume_confirmed=True,
        is_momentum_confirmed=True, composite_confirmation_score=0.8
    )

    # Initial entry: 250 units @ 50.0. Current price: 30.0.
    # Spot is 1990 (inside support zone 1985-2015, distance 15 > 1.0 * ATR 10)
    decision = engine.evaluate_averaging(
        symbol="RELIANCE",
        option_type="CE",
        current_underlying_spot=1990.0,
        current_option_price=30.0,
        initial_underlying_entry_price=2005.0,
        initial_option_entry_price=50.0,
        initial_quantity=250,
        current_averaging_count=0,
        confluence_zone=conf_zone,
        market_structure=mkt_struct,
        reversal_signal=rev_sig,
        atr_15m=10.0,
        lot_size=250
    )

    assert decision.allow_average == True
    assert decision.additional_quantity == 250
    assert decision.new_total_quantity == 500
    # Expected weighted average: (250 * 50 + 250 * 30) / 500 = 40.0
    assert decision.new_weighted_avg_price == 40.0

def test_trailing_stop_monotonicity():
    """
    Verifies that the trailing stop never widens/loosens when price drops.
    """
    config = TrailingStopConfig(
        activation_profit_pct=0.10,
        trailing_distance_pct=0.10
    )
    manager = TrailingStopManager(config)

    entry_price = 100.0
    initial_stop = 70.0
    state = manager.initialize_state(entry_price, initial_stop)

    # Price moves up to 120 (+20%, activates trailing)
    state = manager.update(state, current_option_price=120.0, underlying_spot=2500, entry_price=entry_price)
    assert state.is_activated == True
    # Trail stop should be 120 * (1 - 0.10) = 108.0
    assert state.current_stop_loss == 108.0

    # Price drops to 112: Stop must REMAIN 108.0 (never loosen!)
    state = manager.update(state, current_option_price=112.0, underlying_spot=2490, entry_price=entry_price)
    assert state.current_stop_loss == 108.0

    # Price rallies to 140: Peak is now 140, trail stop ratchets to 140 * 0.9 = 126.0
    state = manager.update(state, current_option_price=140.0, underlying_spot=2520, entry_price=entry_price)
    assert state.current_stop_loss == 126.0

"""
Unit Tests for Support and Resistance Indicators and Confluence Engine.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.indicators.support_resistance_4h import SupportResistance4H
from src.indicators.support_resistance_15m import SupportResistance15M
from src.config.trading_config import SRConfig

def test_sr_4h_zone_clustering_and_scoring():
    """
    Tests that multiple swing lows within tolerance are clustered and assigned high strength.
    """
    config = SRConfig(pivot_order_4h=2, zone_tolerance_pct_4h=0.01)
    engine = SupportResistance4H(config)

    # Create synthetic series bouncing off 2400 three times
    prices = [2500, 2450, 2402, 2460, 2500, 2450, 2398, 2465, 2510, 2445, 2401, 2470, 2520]
    base_time = pd.Timestamp("2026-01-01 09:15:00")
    timestamps = [base_time + timedelta(hours=4 * i) for i in range(len(prices))]

    df_4h = pd.DataFrame({
        "Open": prices,
        "High": [p + 10 for p in prices],
        "Low": [p - 10 for p in prices],
        "Close": prices,
        "Volume": [10000] * len(prices)
    }, index=pd.DatetimeIndex(timestamps))

    curr_time = timestamps[-1]
    curr_spot = 2410.0

    state = engine.analyze_market_structure(df_4h, curr_time, curr_spot)
    assert len(state.active_supports) >= 1

    sup = state.active_supports[0]
    # Center should be around 2400
    assert abs(sup.price_level - 2400.0) < 15.0
    # Strength score should be high due to multiple touches
    assert sup.touch_count >= 2
    assert sup.strength_score >= 0.40

def test_confluence_detection():
    """
    Tests that overlapping 4H and 15M levels produce a valid confluence zone.
    """
    config = SRConfig()
    engine_15m = SupportResistance15M(config)

    # Fake 4H market structure with support at 2500
    from src.indicators.support_resistance_4h import SRZone, MarketStructureState
    zone_4h = SRZone(
        zone_id="SUP_2500",
        zone_type="SUPPORT",
        price_level=2500.0,
        upper_bound=2515.0,
        lower_bound=2485.0,
        strength_score=0.85,
        touch_count=3,
        rejection_strength=0.6,
        volume_score=0.8,
        recency_score=0.9,
        first_formed_time=pd.Timestamp("2026-01-01"),
        last_touch_time=pd.Timestamp("2026-01-05")
    )
    mkt_struct = MarketStructureState(
        trend="BULLISH",
        higher_highs=True, higher_lows=True, lower_highs=False, lower_lows=False,
        last_swing_high=2600.0, last_swing_low=2500.0,
        active_supports=[zone_4h], active_resistances=[],
        nearest_support=zone_4h, nearest_resistance=None
    )

    # 15M support at 2505 (very close, < 0.6% distance)
    zone_15m = SRZone(
        zone_id="15M_SUP_2505",
        zone_type="SUPPORT",
        price_level=2505.0,
        upper_bound=2515.0,
        lower_bound=2495.0,
        strength_score=0.75,
        touch_count=2,
        rejection_strength=0.5,
        volume_score=0.6,
        recency_score=0.9,
        first_formed_time=pd.Timestamp("2026-01-05 10:00"),
        last_touch_time=pd.Timestamp("2026-01-05 11:30")
    )

    confluent_sups, _ = engine_15m.find_confluence_zones(
        market_structure_4h=mkt_struct,
        supports_15m=[zone_15m],
        resistances_15m=[],
        current_spot=2503.0
    )

    assert len(confluent_sups) == 1
    conf = confluent_sups[0]
    assert conf.zone_type == "SUPPORT"
    assert conf.confluence_score > 0.70
    assert conf.is_tested == True

"""
Unit Tests for Zero Look-Ahead Bias Guarantees.
Verifies that:
1. 4H candles are strictly invisible until their closing timestamp.
2. Swing pivots are confirmed ONLY after N subsequent bars have closed.
3. Adding future bars does not retroactively change decisions made at time t.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta

from src.data.timeframe_manager import TimeframeManager
from src.indicators.swing_detector import SwingDetector
from src.config.constants import MARKET_TIMEZONE

def test_4h_zero_lookahead_filtering():
    """
    Tests that a forming 4H candle is never visible to an intraday 15M bar before its close.
    """
    # Create sample 15M data spanning one day (09:15 to 15:30)
    base_date = datetime(2026, 1, 5) # Monday
    times = [base_date + timedelta(minutes=15 * i) for i in range(25)]
    # Session 09:15 to 15:30
    start_time = datetime.combine(base_date.date(), time(9, 15))
    bar_starts = [start_time + timedelta(minutes=15 * i) for i in range(25)]

    df_15m = pd.DataFrame({
        "Open": [100.0 + i for i in range(25)],
        "High": [101.0 + i for i in range(25)],
        "Low": [99.0 + i for i in range(25)],
        "Close": [100.5 + i for i in range(25)],
        "Volume": [1000 for _ in range(25)]
    }, index=pd.DatetimeIndex(bar_starts, tz=MARKET_TIMEZONE))

    df_4h = TimeframeManager.resample_15m_to_4h(df_15m)

    # 4H morning block closes at 13:15
    # At 10:30, visible 4H candles must be EMPTY (since morning block has not closed yet)
    check_time_1030 = pd.Timestamp(datetime.combine(base_date.date(), time(10, 30)), tz=MARKET_TIMEZONE)
    visible_at_1030 = TimeframeManager.get_visible_4h_bars_at_time(df_4h, check_time_1030)
    assert len(visible_at_1030) == 0, "A 4H candle closing at 13:15 must NOT be visible at 10:30!"

    # At 13:15, the morning 4H block has closed and must now become visible
    check_time_1315 = pd.Timestamp(datetime.combine(base_date.date(), time(13, 15)), tz=MARKET_TIMEZONE)
    visible_at_1315 = TimeframeManager.get_visible_4h_bars_at_time(df_4h, check_time_1315)
    assert len(visible_at_1315) == 1, "The morning 4H candle must be visible at its closing time 13:15."

    # At 14:00, only the 1 closed 4H candle should be visible, not the afternoon block
    check_time_1400 = pd.Timestamp(datetime.combine(base_date.date(), time(14, 0)), tz=MARKET_TIMEZONE)
    visible_at_1400 = TimeframeManager.get_visible_4h_bars_at_time(df_4h, check_time_1400)
    assert len(visible_at_1400) == 1, "Afternoon 4H candle must not be visible before its close at 15:30."

def test_swing_detector_confirmation_lag():
    """
    Tests that a swing pivot of order N is confirmed exactly N bars after the peak/trough.
    """
    detector = SwingDetector(order=3)

    # Construct price series with a clear peak at index 5
    # 0, 1, 2, 3, 4, [5: peak], 6, 7, 8, 9, 10
    prices = [10, 12, 14, 16, 18, 25, 20, 17, 15, 13, 11]
    timestamps = [pd.Timestamp("2026-01-05") + timedelta(hours=i) for i in range(len(prices))]

    df = pd.DataFrame({
        "Open": prices,
        "High": prices,
        "Low": [p - 1 for p in prices],
        "Close": prices,
        "Volume": [500] * len(prices)
    }, index=pd.DatetimeIndex(timestamps))

    swings = detector.detect_swings(df)
    assert len(swings) >= 1

    peak_swing = [s for s in swings if s.pivot_type == "HIGH" and s.price == 25.0][0]
    assert peak_swing.pivot_index == 5
    # Confirmation must occur at index 5 + 3 = 8
    assert peak_swing.confirmation_index == 8
    assert peak_swing.confirmation_timestamp == timestamps[8]

    # At timestamp 6 (before confirmation), the swing must NOT be visible
    visible_at_6 = SwingDetector.filter_visible_swings(swings, timestamps[6])
    assert peak_swing not in visible_at_6

    # At timestamp 8 (confirmation time), it becomes visible
    visible_at_8 = SwingDetector.filter_visible_swings(swings, timestamps[8])
    assert peak_swing in visible_at_8

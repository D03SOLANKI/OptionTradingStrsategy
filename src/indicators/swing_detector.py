"""
Point-in-Time Swing High and Swing Low Detector with Guaranteed Zero Look-Ahead Bias.
A pivot at bar i is strictly confirmed only at bar (i + order), when the future confirmation bars have closed.
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import numpy as np

@dataclass
class SwingPoint:
    pivot_index: int               # Integer index where the peak/trough occurred
    confirmation_index: int        # Integer index when the pivot was strictly confirmed (pivot_index + order)
    pivot_timestamp: pd.Timestamp  # Timestamp of the peak/trough bar
    confirmation_timestamp: pd.Timestamp # Timestamp when confirmed and visible
    price: float                   # Peak or Trough price level
    pivot_type: str                # 'HIGH' or 'LOW'
    volume: float                  # Volume at the pivot bar
    wick_ratio: float              # Wick size / bar range ratio (measure of rejection)

class SwingDetector:
    """
    Detects structural swing highs and lows strictly point-in-time.
    """

    def __init__(self, order: int = 3):
        self.order = order

    def detect_swings(self, df: pd.DataFrame) -> List[SwingPoint]:
        """
        Scans OHLCV series and returns list of confirmed SwingPoints.
        Strict guarantee: confirmation_index = pivot_index + order.
        Any trading system at bar t can only observe swings with confirmation_index <= t.
        """
        if len(df) < 2 * self.order + 1:
            return []

        highs = df["High"].values
        lows = df["Low"].values
        opens = df["Open"].values
        closes = df["Close"].values
        volumes = df["Volume"].values if "Volume" in df.columns else np.zeros(len(df))
        timestamps = df.index

        swings: List[SwingPoint] = []
        n = len(df)

        for i in range(self.order, n - self.order):
            # Check Swing High
            is_high = True
            current_high = highs[i]
            for k in range(1, self.order + 1):
                if highs[i - k] >= current_high or highs[i + k] >= current_high:
                    is_high = False
                    break

            if is_high:
                bar_range = max(1e-4, highs[i] - lows[i])
                body_top = max(opens[i], closes[i])
                upper_wick = highs[i] - body_top
                wick_ratio = upper_wick / bar_range

                swings.append(SwingPoint(
                    pivot_index=i,
                    confirmation_index=i + self.order,
                    pivot_timestamp=timestamps[i],
                    confirmation_timestamp=timestamps[i + self.order],
                    price=float(current_high),
                    pivot_type="HIGH",
                    volume=float(volumes[i]),
                    wick_ratio=float(wick_ratio)
                ))

            # Check Swing Low
            is_low = True
            current_low = lows[i]
            for k in range(1, self.order + 1):
                if lows[i - k] <= current_low or lows[i + k] <= current_low:
                    is_low = False
                    break

            if is_low:
                bar_range = max(1e-4, highs[i] - lows[i])
                body_bottom = min(opens[i], closes[i])
                lower_wick = body_bottom - lows[i]
                wick_ratio = lower_wick / bar_range

                swings.append(SwingPoint(
                    pivot_index=i,
                    confirmation_index=i + self.order,
                    pivot_timestamp=timestamps[i],
                    confirmation_timestamp=timestamps[i + self.order],
                    price=float(current_low),
                    pivot_type="LOW",
                    volume=float(volumes[i]),
                    wick_ratio=float(wick_ratio)
                ))

        swings.sort(key=lambda s: s.confirmation_index)
        return swings

    @staticmethod
    def filter_visible_swings(swings: List[SwingPoint], current_time: pd.Timestamp) -> List[SwingPoint]:
        """
        Filters swings so that only those confirmed at or before current_time are visible.
        """
        return [s for s in swings if s.confirmation_timestamp <= current_time]

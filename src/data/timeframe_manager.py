"""
Session-Aware Multi-Timeframe Resampler with Strict Zero Look-Ahead Bias Guarantees.
Converts 15-Minute NSE intraday bars into 4-Hour structural candles.
Ensures that at any 15M decision time t, only fully CLOSED 4H candles prior to t are visible.
"""

import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Optional
from datetime import datetime, time

class TimeframeManager:
    """
    Session-aware Multi-Timeframe Resampling & Alignment Engine.
    NSE Session: 09:15 to 15:30 (375 minutes, 25 x 15M bars per day).
    """

    @staticmethod
    def resample_15m_to_4h(df_15m: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregates 15M OHLCV data into 4-Hour (240-minute) candles aligned to trading sessions.
        Each trading day (09:15-15:30) is split into:
        - Session 1: 09:15 to 13:15 (16 bars x 15m = 240 mins)
        - Session 2: 13:15 to 15:30 (9 bars x 15m = 135 mins, session remainder)

        Each 4H candle is timestamped at its CLOSING time, strictly enforcing
        that it is never visible before that exact closing timestamp.
        """
        df = df_15m.copy()
        if "Datetime" in df.columns:
            df = df.set_index("Datetime")

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        df = df.sort_index()

        # Identify trading dates
        df["date"] = df.index.date
        df["time"] = df.index.time

        records = []
        for d, day_group in df.groupby("date"):
            # Morning 4H block: 09:15 to 13:15 (15m bars starting at 09:15 up to 13:00, closing at 13:15)
            # Afternoon block: 13:15 to 15:30 (15m bars starting at 13:15 up to 15:15, closing at 15:30)
            morning = day_group[day_group["time"] < time(13, 15)]
            afternoon = day_group[day_group["time"] >= time(13, 15)]

            for block_name, block in [("morning", morning), ("afternoon", afternoon)]:
                if block.empty:
                    continue

                open_price = float(block["Open"].iloc[0])
                high_price = float(block["High"].max())
                low_price = float(block["Low"].min())
                close_price = float(block["Close"].iloc[-1])
                volume = float(block["Volume"].sum())

                # Closing timestamp is the close of the last 15M candle in the block (+15 mins from bar start)
                last_bar_start = block.index[-1]
                close_time = last_bar_start + pd.Timedelta(minutes=15)

                records.append({
                    "open_time": block.index[0],
                    "close_time": close_time,
                    "Open": open_price,
                    "High": high_price,
                    "Low": low_price,
                    "Close": close_price,
                    "Volume": volume,
                    "bar_count": len(block)
                })

        df_4h = pd.DataFrame(records)
        if not df_4h.empty:
            df_4h = df_4h.set_index("close_time").sort_index()

        return df_4h

    @staticmethod
    def get_visible_4h_bars_at_time(
        df_4h: pd.DataFrame,
        current_15m_timestamp: pd.Timestamp
    ) -> pd.DataFrame:
        """
        CRITICAL ZERO LOOK-AHEAD FILTER:
        Returns only the 4H candles whose close_time <= current_15m_timestamp.
        The currently forming 4H candle is STRICTLY EXCLUDED.
        """
        return df_4h[df_4h.index <= current_15m_timestamp].copy()

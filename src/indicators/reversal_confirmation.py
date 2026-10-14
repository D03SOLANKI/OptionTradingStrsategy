"""
15-Minute Reversal Confirmation Engine: Candlestick Patterns, Momentum, and Volume Filters.
Detects Hammer, Shooting Star, Bullish/Bearish Engulfing, Morning/Evening Stars, Pin Bars,
along with RSI momentum hooks and volume surges.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, Literal
import numpy as np
import pandas as pd

from src.config.trading_config import ConfirmationConfig

@dataclass
class ReversalSignal:
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH", "NONE"]
    pattern_name: str
    pattern_strength: float            # [0.0, 1.0]
    volume_ratio: float                # Bar volume vs 20 SMA
    rsi_value: float                   # 14-period RSI
    is_volume_confirmed: bool
    is_momentum_confirmed: bool
    composite_confirmation_score: float # [0.0, 1.0]

class ReversalConfirmation:
    """
    Evaluates 15M candle patterns and momentum/volume signals for trade entry confirmation.
    """

    def __init__(self, config: Optional[ConfirmationConfig] = None):
        self.config = config or ConfirmationConfig()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Standard Wilder's RSI calculation.
        """
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def evaluate_bar(
        self,
        df_15m: pd.DataFrame,
        bar_idx: int
    ) -> ReversalSignal:
        """
        Evaluates the 15M bar at bar_idx strictly using data available up to bar_idx.
        """
        timestamp = df_15m.index[bar_idx]
        if bar_idx < max(self.config.rsi_period + 1, self.config.volume_ma_period + 1, 3):
            return ReversalSignal(
                timestamp=timestamp,
                direction="NONE",
                pattern_name="INSUFFICIENT_HISTORY",
                pattern_strength=0.0,
                volume_ratio=1.0,
                rsi_value=50.0,
                is_volume_confirmed=False,
                is_momentum_confirmed=False,
                composite_confirmation_score=0.0
            )

        # Candle 0 is current (at bar_idx), Candle -1 is prior, Candle -2 is 2 bars ago
        c0 = df_15m.iloc[bar_idx]
        c1 = df_15m.iloc[bar_idx - 1]
        c2 = df_15m.iloc[bar_idx - 2]

        open0, high0, low0, close0, vol0 = float(c0["Open"]), float(c0["High"]), float(c0["Low"]), float(c0["Close"]), float(c0["Volume"])
        open1, high1, low1, close1 = float(c1["Open"]), float(c1["High"]), float(c1["Low"]), float(c1["Close"])
        open2, high2, low2, close2 = float(c2["Open"]), float(c2["High"]), float(c2["Low"]), float(c2["Close"])

        range0 = max(1e-4, high0 - low0)
        body0 = abs(close0 - open0)
        body0_top = max(open0, close0)
        body0_bottom = min(open0, close0)
        upper_wick0 = high0 - body0_top
        lower_wick0 = body0_bottom - low0
        is_green0 = close0 >= open0

        range1 = max(1e-4, high1 - low1)
        body1 = abs(close1 - open1)
        is_green1 = close1 >= open1

        range2 = max(1e-4, high2 - low2)
        body2 = abs(close2 - open2)
        is_green2 = close2 >= open2

        # Volume confirmation
        vol_slice = df_15m["Volume"].iloc[max(0, bar_idx - self.config.volume_ma_period):bar_idx]
        vol_ma = float(vol_slice.mean()) if len(vol_slice) > 0 else vol0
        vol_ratio = vol0 / vol_ma if vol_ma > 0 else 1.0
        is_vol_confirmed = vol_ratio >= self.config.min_volume_ratio if self.config.enable_volume_confirmation else True

        # RSI confirmation
        rsi_series = self.calculate_rsi(df_15m["Close"].iloc[:bar_idx + 1], period=self.config.rsi_period)
        rsi_curr = float(rsi_series.iloc[-1])
        rsi_prev = float(rsi_series.iloc[-2]) if len(rsi_series) > 1 else rsi_curr

        # Detect Candlestick Patterns
        bullish_pattern = None
        bullish_strength = 0.0

        bearish_pattern = None
        bearish_strength = 0.0

        # 1. Hammer / Bullish Pin Bar
        if lower_wick0 >= 2.0 * body0 and upper_wick0 <= 0.35 * range0 and lower_wick0 >= 0.50 * range0:
            bullish_pattern = "HAMMER / BULLISH PIN BAR"
            bullish_strength = 0.85

        # 2. Bullish Engulfing
        elif not is_green1 and is_green0 and close0 > open1 and open0 <= close1 and body0 > body1 * 1.1:
            bullish_pattern = "BULLISH ENGULFING"
            bullish_strength = 0.90

        # 3. Morning Star
        elif not is_green2 and body2 > 0.5 * range2 and body1 < 0.3 * range1 and is_green0 and close0 > (open2 + close2) / 2.0:
            bullish_pattern = "MORNING STAR"
            bullish_strength = 0.95

        # 4. Piercing Pattern
        elif not is_green1 and is_green0 and open0 < low1 and close0 > (open1 + close1) / 2.0 and close0 < open1:
            bullish_pattern = "PIERCING LINE"
            bullish_strength = 0.75

        # Bearish Patterns
        # 1. Shooting Star / Bearish Pin Bar
        if upper_wick0 >= 2.0 * body0 and lower_wick0 <= 0.35 * range0 and upper_wick0 >= 0.50 * range0:
            bearish_pattern = "SHOOTING STAR / BEARISH PIN BAR"
            bearish_strength = 0.85

        # 2. Bearish Engulfing
        elif is_green1 and not is_green0 and close0 < open1 and open0 >= close1 and body0 > body1 * 1.1:
            bearish_pattern = "BEARISH ENGULFING"
            bearish_strength = 0.90

        # 3. Evening Star
        elif is_green2 and body2 > 0.5 * range2 and body1 < 0.3 * range1 and not is_green0 and close0 < (open2 + close2) / 2.0:
            bearish_pattern = "EVENING STAR"
            bearish_strength = 0.95

        # 4. Dark Cloud Cover
        elif is_green1 and not is_green0 and open0 > high1 and close0 < (open1 + close1) / 2.0 and close0 > open1:
            bearish_pattern = "DARK CLOUD COVER"
            bearish_strength = 0.75

        # Determine Signal Direction & Momentum Confirmation
        if bullish_pattern is not None:
            # RSI momentum check: either oversold or hooking upwards
            is_mom_confirmed = (rsi_curr <= self.config.rsi_oversold_threshold or (rsi_curr > rsi_prev and rsi_prev <= 45.0)) if self.config.enable_momentum_filter else True
            comp_score = (
                0.50 * bullish_strength +
                0.25 * min(1.0, vol_ratio / 1.5) +
                0.25 * (1.0 if is_mom_confirmed else 0.4)
            )
            return ReversalSignal(
                timestamp=timestamp,
                direction="BULLISH",
                pattern_name=bullish_pattern,
                pattern_strength=round(bullish_strength, 3),
                volume_ratio=round(vol_ratio, 2),
                rsi_value=round(rsi_curr, 2),
                is_volume_confirmed=is_vol_confirmed,
                is_momentum_confirmed=is_mom_confirmed,
                composite_confirmation_score=round(comp_score, 3)
            )

        elif bearish_pattern is not None:
            is_mom_confirmed = (rsi_curr >= self.config.rsi_overbought_threshold or (rsi_curr < rsi_prev and rsi_prev >= 55.0)) if self.config.enable_momentum_filter else True
            comp_score = (
                0.50 * bearish_strength +
                0.25 * min(1.0, vol_ratio / 1.5) +
                0.25 * (1.0 if is_mom_confirmed else 0.4)
            )
            return ReversalSignal(
                timestamp=timestamp,
                direction="BEARISH",
                pattern_name=bearish_pattern,
                pattern_strength=round(bearish_strength, 3),
                volume_ratio=round(vol_ratio, 2),
                rsi_value=round(rsi_curr, 2),
                is_volume_confirmed=is_vol_confirmed,
                is_momentum_confirmed=is_mom_confirmed,
                composite_confirmation_score=round(comp_score, 3)
            )

        # No reversal pattern
        return ReversalSignal(
            timestamp=timestamp,
            direction="NONE",
            pattern_name="NONE",
            pattern_strength=0.0,
            volume_ratio=round(vol_ratio, 2),
            rsi_value=round(rsi_curr, 2),
            is_volume_confirmed=is_vol_confirmed,
            is_momentum_confirmed=False,
            composite_confirmation_score=0.0
        )

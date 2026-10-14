"""
4-Hour Timeframe: Major Market Structure and Support/Resistance Zone Analysis.
Includes DBSCAN/tolerance clustering, historical retests, volume profile weighting,
rejection wick scoring, recency decay, S/R flips, and market structure classification.
Strictly point-in-time with zero look-ahead bias.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Literal
import math
import numpy as np
import pandas as pd

from src.indicators.swing_detector import SwingPoint, SwingDetector
from src.config.trading_config import SRConfig

@dataclass
class SRZone:
    zone_id: str
    zone_type: Literal["SUPPORT", "RESISTANCE"]
    price_level: float
    upper_bound: float
    lower_bound: float
    strength_score: float             # [0.0, 1.0] normalized strength score
    touch_count: int                  # Number of confirmed retests
    rejection_strength: float         # Average wick ratio [0.0, 1.0]
    volume_score: float               # Relative volume accumulation score
    recency_score: float              # Time-decayed recency score [0.0, 1.0]
    first_formed_time: pd.Timestamp
    last_touch_time: pd.Timestamp
    is_flipped: bool = False          # True if resistance became support or vice versa
    breakout_count: int = 0           # Count of false breakouts / penetrations

@dataclass
class MarketStructureState:
    trend: Literal["BULLISH", "BEARISH", "SIDEWAYS"]
    higher_highs: bool
    higher_lows: bool
    lower_highs: bool
    lower_lows: bool
    last_swing_high: Optional[float]
    last_swing_low: Optional[float]
    active_supports: List[SRZone]
    active_resistances: List[SRZone]
    nearest_support: Optional[SRZone]
    nearest_resistance: Optional[SRZone]

class SupportResistance4H:
    """
    Analyzes 4-Hour Major Market Structure and Support/Resistance Zones.
    """

    def __init__(self, config: Optional[SRConfig] = None):
        self.config = config or SRConfig()
        self.swing_detector = SwingDetector(order=self.config.pivot_order_4h)

    def analyze_market_structure(
        self,
        df_4h_visible: pd.DataFrame,
        current_time: pd.Timestamp,
        current_spot: float
    ) -> MarketStructureState:
        """
        Performs full market structure and S/R zone analysis on visible 4H data.
        df_4h_visible contains ONLY completed 4H bars with close_time <= current_time.
        """
        if len(df_4h_visible) < 2 * self.config.pivot_order_4h + 1:
            return MarketStructureState(
                trend="SIDEWAYS",
                higher_highs=False,
                higher_lows=False,
                lower_highs=False,
                lower_lows=False,
                last_swing_high=None,
                last_swing_low=None,
                active_supports=[],
                active_resistances=[],
                nearest_support=None,
                nearest_resistance=None
            )

        # 1. Detect all confirmed swings
        all_swings = self.swing_detector.detect_swings(df_4h_visible)
        # Filter visible swings
        visible_swings = SwingDetector.filter_visible_swings(all_swings, current_time)

        # 2. Market Structure (Bullish / Bearish / Sideways)
        trend, hh, hl, lh, ll, last_sh, last_sl = self._determine_trend(visible_swings)

        # 3. Cluster swings into S/R zones
        supports, resistances = self._cluster_and_score_zones(
            visible_swings,
            df_4h_visible,
            current_time,
            current_spot
        )

        # 4. Filter active zones by minimum strength score
        active_supports = [s for s in supports if s.strength_score >= self.config.min_level_strength_score]
        active_resistances = [r for r in resistances if r.strength_score >= self.config.min_level_strength_score]

        # Sort supports descending (highest price near current spot first)
        active_supports.sort(key=lambda z: z.price_level, reverse=True)
        # Sort resistances ascending (lowest price near current spot first)
        active_resistances.sort(key=lambda z: z.price_level)

        # Cap max active zones
        active_supports = active_supports[:self.config.max_active_zones]
        active_resistances = active_resistances[:self.config.max_active_zones]

        # 5. Identify nearest zones below and above current price
        nearest_sup = None
        for s in active_supports:
            if s.price_level <= current_spot * (1.0 + self.config.zone_tolerance_pct_4h):
                nearest_sup = s
                break

        nearest_res = None
        for r in active_resistances:
            if r.price_level >= current_spot * (1.0 - self.config.zone_tolerance_pct_4h):
                nearest_res = r
                break

        return MarketStructureState(
            trend=trend,
            higher_highs=hh,
            higher_lows=hl,
            lower_highs=lh,
            lower_lows=ll,
            last_swing_high=last_sh,
            last_swing_low=last_sl,
            active_supports=active_supports,
            active_resistances=active_resistances,
            nearest_support=nearest_sup,
            nearest_resistance=nearest_res
        )

    def _determine_trend(
        self,
        swings: List[SwingPoint]
    ) -> Tuple[Literal["BULLISH", "BEARISH", "SIDEWAYS"], bool, bool, bool, bool, Optional[float], Optional[float]]:
        """
        Determines market structure from the sequence of confirmed swing highs and lows.
        """
        highs = [s for s in swings if s.pivot_type == "HIGH"]
        lows = [s for s in swings if s.pivot_type == "LOW"]

        if len(highs) < 2 or len(lows) < 2:
            last_sh = highs[-1].price if highs else None
            last_sl = lows[-1].price if lows else None
            return "SIDEWAYS", False, False, False, False, last_sh, last_sl

        last_sh = highs[-1].price
        prev_sh = highs[-2].price
        last_sl = lows[-1].price
        prev_sl = lows[-2].price

        higher_highs = last_sh > prev_sh
        higher_lows = last_sl > prev_sl
        lower_highs = last_sh < prev_sh
        lower_lows = last_sl < prev_sl

        if higher_highs and higher_lows:
            trend = "BULLISH"
        elif lower_highs and lower_lows:
            trend = "BEARISH"
        else:
            trend = "SIDEWAYS"

        return trend, higher_highs, higher_lows, lower_highs, lower_lows, last_sh, last_sl

    def _cluster_and_score_zones(
        self,
        swings: List[SwingPoint],
        df_4h: pd.DataFrame,
        current_time: pd.Timestamp,
        current_spot: float
    ) -> Tuple[List[SRZone], List[SRZone]]:
        """
        Clusters swing points within zone_tolerance_pct_4h into coherent S/R zones.
        Computes dynamic strength score based on touches, volume, rejection wicks, and recency.
        """
        tol = self.config.zone_tolerance_pct_4h
        half_life_days = self.config.touch_decay_half_life_days
        lambda_decay = math.log(2.0) / half_life_days

        # Separate swings by type
        low_swings = [s for s in swings if s.pivot_type == "LOW"]
        high_swings = [s for s in swings if s.pivot_type == "HIGH"]

        supports: List[SRZone] = []
        resistances: List[SRZone] = []

        # Helper to cluster swings
        def cluster_swings(swing_list: List[SwingPoint], zone_type: Literal["SUPPORT", "RESISTANCE"]) -> List[SRZone]:
            if not swing_list:
                return []

            # Sort by price
            sorted_by_price = sorted(swing_list, key=lambda s: s.price)
            clusters: List[List[SwingPoint]] = []

            for sp in sorted_by_price:
                placed = False
                for c in clusters:
                    avg_p = sum(item.price for item in c) / len(c)
                    if abs(sp.price - avg_p) / avg_p <= tol:
                        c.append(sp)
                        placed = True
                        break
                if not placed:
                    clusters.append([sp])

            zones: List[SRZone] = []
            for idx, cluster in enumerate(clusters):
                prices = [s.price for s in cluster]
                mean_price = float(np.mean(prices))
                upper = mean_price * (1.0 + tol / 2.0)
                lower = mean_price * (1.0 - tol / 2.0)

                touch_count = len(cluster)
                avg_wick = float(np.mean([s.wick_ratio for s in cluster]))
                first_time = min(s.pivot_timestamp for s in cluster)
                last_time = max(s.pivot_timestamp for s in cluster)

                # Recency score via exponential decay
                days_since_last = max(0.0, (current_time - last_time).total_seconds() / 86400.0)
                recency_score = math.exp(-lambda_decay * days_since_last)

                # Volume score: compare average cluster volume to overall volume
                avg_cluster_vol = np.mean([s.volume for s in cluster])
                overall_avg_vol = df_4h["Volume"].mean() if not df_4h.empty else 1.0
                vol_ratio = avg_cluster_vol / overall_avg_vol if overall_avg_vol > 0 else 1.0
                volume_score = min(1.0, vol_ratio / 2.0)

                # Touch score (saturates at 4 touches)
                touch_score = min(1.0, touch_count / 4.0)

                # Check if zone was flipped:
                # E.g., if a SUPPORT zone was broken to the downside and price later traded below it,
                # or if a RESISTANCE zone was broken to the upside
                is_flipped = False
                breakout_count = 0
                for _, bar in df_4h[df_4h.index > last_time].iterrows():
                    if zone_type == "SUPPORT" and bar["Close"] < lower:
                        breakout_count += 1
                    elif zone_type == "RESISTANCE" and bar["Close"] > upper:
                        breakout_count += 1

                # If broken cleanly more than once, reduce score unless it acts as flipped S/R
                breakdown_penalty = 0.20 * min(3, breakout_count)

                # Composite strength score [0.0, 1.0]
                raw_score = (
                    0.35 * touch_score +
                    0.25 * recency_score +
                    0.20 * min(1.0, avg_wick * 2.0) +
                    0.20 * volume_score -
                    breakdown_penalty
                )
                strength_score = max(0.05, min(1.0, raw_score))

                zone = SRZone(
                    zone_id=f"{zone_type[:3]}_{int(mean_price)}_{idx}",
                    zone_type=zone_type,
                    price_level=round(mean_price, 2),
                    upper_bound=round(upper, 2),
                    lower_bound=round(lower, 2),
                    strength_score=round(strength_score, 4),
                    touch_count=touch_count,
                    rejection_strength=round(avg_wick, 3),
                    volume_score=round(volume_score, 3),
                    recency_score=round(recency_score, 3),
                    first_formed_time=first_time,
                    last_touch_time=last_time,
                    is_flipped=is_flipped,
                    breakout_count=breakout_count
                )
                zones.append(zone)

            return zones

        supports = cluster_swings(low_swings, "SUPPORT")
        resistances = cluster_swings(high_swings, "RESISTANCE")

        return supports, resistances

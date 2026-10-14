"""
15-Minute Timeframe: Short-Term S/R Detection and Multi-Timeframe Confluence Engine.
Identifies confluence zones where 4H and 15M support/resistance levels overlap.
Prioritizes high-confluence setups and avoids low-quality entries in the middle of a range.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal
import math
import numpy as np
import pandas as pd

from src.indicators.swing_detector import SwingPoint, SwingDetector
from src.indicators.support_resistance_4h import SRZone, MarketStructureState
from src.config.trading_config import SRConfig

@dataclass
class ConfluenceZone:
    zone_type: Literal["SUPPORT", "RESISTANCE"]
    center_price: float
    lower_bound: float
    upper_bound: float
    confluence_score: float             # [0.0, 1.0] composite strength score
    zone_4h: SRZone
    zone_15m: Optional[SRZone]
    distance_pct: float                 # Percentage distance between 4H and 15M centers
    is_tested: bool                     # True if current price is inside the confluence zone

class SupportResistance15M:
    """
    15-Minute Short-term S/R and Multi-Timeframe Confluence Engine.
    """

    def __init__(self, config: Optional[SRConfig] = None):
        self.config = config or SRConfig()
        self.swing_detector = SwingDetector(order=self.config.pivot_order_15m)

    def detect_15m_zones(
        self,
        df_15m_visible: pd.DataFrame,
        current_time: pd.Timestamp
    ) -> Tuple[List[SRZone], List[SRZone]]:
        """
        Detects short-term 15M support and resistance zones from visible 15M bars.
        """
        if len(df_15m_visible) < 2 * self.config.pivot_order_15m + 1:
            return [], []

        all_swings = self.swing_detector.detect_swings(df_15m_visible)
        visible_swings = SwingDetector.filter_visible_swings(all_swings, current_time)

        tol = self.config.zone_tolerance_pct_15m
        low_swings = [s for s in visible_swings if s.pivot_type == "LOW"]
        high_swings = [s for s in visible_swings if s.pivot_type == "HIGH"]

        def cluster_15m(swings: List[SwingPoint], z_type: Literal["SUPPORT", "RESISTANCE"]) -> List[SRZone]:
            if not swings:
                return []
            sorted_swings = sorted(swings, key=lambda s: s.price)
            clusters: List[List[SwingPoint]] = []
            for sp in sorted_swings:
                placed = False
                for c in clusters:
                    avg_p = sum(x.price for x in c) / len(c)
                    if abs(sp.price - avg_p) / avg_p <= tol:
                        c.append(sp)
                        placed = True
                        break
                if not placed:
                    clusters.append([sp])

            zones = []
            for idx, c in enumerate(clusters):
                prices = [s.price for s in c]
                mean_p = float(np.mean(prices))
                upper = mean_p * (1.0 + tol / 2.0)
                lower = mean_p * (1.0 - tol / 2.0)
                touch_count = len(c)
                avg_wick = float(np.mean([s.wick_ratio for s in c]))
                first_t = min(s.pivot_timestamp for s in c)
                last_t = max(s.pivot_timestamp for s in c)

                # 15M strength score (touches, recency, wicks)
                days_since = max(0.0, (current_time - last_t).total_seconds() / 86400.0)
                recency = math.exp(-0.15 * days_since)
                raw_score = 0.40 * min(1.0, touch_count / 3.0) + 0.35 * recency + 0.25 * min(1.0, avg_wick * 2.0)

                zone = SRZone(
                    zone_id=f"15M_{z_type[:3]}_{int(mean_p)}_{idx}",
                    zone_type=z_type,
                    price_level=round(mean_p, 2),
                    upper_bound=round(upper, 2),
                    lower_bound=round(lower, 2),
                    strength_score=round(raw_score, 4),
                    touch_count=touch_count,
                    rejection_strength=round(avg_wick, 3),
                    volume_score=0.5,
                    recency_score=round(recency, 3),
                    first_formed_time=first_t,
                    last_touch_time=last_t
                )
                zones.append(zone)
            return zones

        supports_15m = cluster_15m(low_swings, "SUPPORT")
        resistances_15m = cluster_15m(high_swings, "RESISTANCE")
        return supports_15m, resistances_15m

    def find_confluence_zones(
        self,
        market_structure_4h: MarketStructureState,
        supports_15m: List[SRZone],
        resistances_15m: List[SRZone],
        current_spot: float
    ) -> Tuple[List[ConfluenceZone], List[ConfluenceZone]]:
        """
        Cross-matches 4H major zones with 15M short-term zones.
        Computes composite confluence score and boundaries.
        """
        conf_dist = self.config.confluence_distance_pct
        w_4h = self.config.confluence_weight_4h
        w_15m = self.config.confluence_weight_15m

        confluent_supports: List[ConfluenceZone] = []
        confluent_resistances: List[ConfluenceZone] = []

        # 1. Match Supports
        for s_4h in market_structure_4h.active_supports:
            best_match: Optional[SRZone] = None
            min_dist = float("inf")

            for s_15m in supports_15m:
                dist_pct = abs(s_4h.price_level - s_15m.price_level) / s_4h.price_level
                if dist_pct <= conf_dist and dist_pct < min_dist:
                    min_dist = dist_pct
                    best_match = s_15m

            if best_match is not None:
                # Both 4H and 15M present -> High Confluence
                conf_score = w_4h * s_4h.strength_score + w_15m * best_match.strength_score
                center = (s_4h.price_level + best_match.price_level) / 2.0
                lower = min(s_4h.lower_bound, best_match.lower_bound)
                upper = max(s_4h.upper_bound, best_match.upper_bound)
                dist = min_dist
            else:
                # Standalone 4H major zone
                conf_score = w_4h * s_4h.strength_score * 0.85 # Slight discount if no 15M confluence
                center = s_4h.price_level
                lower = s_4h.lower_bound
                upper = s_4h.upper_bound
                dist = 0.0

            if conf_score >= self.config.min_confluence_score:
                is_tested = (lower <= current_spot <= upper * 1.002)
                confluent_supports.append(ConfluenceZone(
                    zone_type="SUPPORT",
                    center_price=round(center, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                    confluence_score=round(conf_score, 4),
                    zone_4h=s_4h,
                    zone_15m=best_match,
                    distance_pct=round(dist, 4),
                    is_tested=is_tested
                ))

        # 2. Match Resistances
        for r_4h in market_structure_4h.active_resistances:
            best_match: Optional[SRZone] = None
            min_dist = float("inf")

            for r_15m in resistances_15m:
                dist_pct = abs(r_4h.price_level - r_15m.price_level) / r_4h.price_level
                if dist_pct <= conf_dist and dist_pct < min_dist:
                    min_dist = dist_pct
                    best_match = r_15m

            if best_match is not None:
                conf_score = w_4h * r_4h.strength_score + w_15m * best_match.strength_score
                center = (r_4h.price_level + best_match.price_level) / 2.0
                lower = min(r_4h.lower_bound, best_match.lower_bound)
                upper = max(r_4h.upper_bound, best_match.upper_bound)
                dist = min_dist
            else:
                conf_score = w_4h * r_4h.strength_score * 0.85
                center = r_4h.price_level
                lower = r_4h.lower_bound
                upper = r_4h.upper_bound
                dist = 0.0

            if conf_score >= self.config.min_confluence_score:
                is_tested = (lower * 0.998 <= current_spot <= upper)
                confluent_resistances.append(ConfluenceZone(
                    zone_type="RESISTANCE",
                    center_price=round(center, 2),
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                    confluence_score=round(conf_score, 4),
                    zone_4h=r_4h,
                    zone_15m=best_match,
                    distance_pct=round(dist, 4),
                    is_tested=is_tested
                ))

        # Sort supports descending (closest to spot first)
        confluent_supports.sort(key=lambda z: z.center_price, reverse=True)
        # Sort resistances ascending (closest to spot first)
        confluent_resistances.sort(key=lambda z: z.center_price)

        return confluent_supports, confluent_resistances

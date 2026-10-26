"""
Agent 2: Support & Resistance Agent.
Analyzes 4H and 15M charts for every shortlisted stock.
Identifies major 4H market structure, support and resistance zones, swing pivots, touches, volume accumulation, and rejection wicks.
Detects 15M short-term levels, determines MTF confluence zones, and evaluates price reactions.
Sends high-conviction structural maps to Agent 3 (Technical Analysis Agent).
"""

from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentReport
from src.agents.transparency_bus import TransparencyBus
from src.config.trading_config import MasterConfig
from src.data.timeframe_manager import TimeframeManager
from src.indicators.support_resistance_4h import SupportResistance4H, MarketStructureState, SRZone
from src.indicators.support_resistance_15m import SupportResistance15M, ConfluenceZone

class SupportResistanceAgent(BaseAgent):
    """
    Support & Resistance Agent.
    Specializes in institutional multi-timeframe structural mapping (4H Macro + 15M Micro).
    """

    def __init__(self, bus: TransparencyBus, config: Optional[MasterConfig] = None):
        super().__init__(
            agent_id="AGENT_2_SUPPORT_RESISTANCE",
            agent_name="Support & Resistance Agent",
            bus=bus
        )
        self.config = config or MasterConfig()
        self.sr_4h_engine = SupportResistance4H(self.config.sr)
        self.sr_15m_engine = SupportResistance15M(self.config.sr)
        self.mapped_structures: Dict[str, Dict[str, Any]] = {}
        self.input_summary: str = ""

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
        - 'universe_data': Dict[str, pd.DataFrame] (symbol -> 15M dataframe)
        - 'agent_1_handoff': Dict[str, Any] (from MarketScanningAgent)
        - 'timestamp': Optional[pd.Timestamp]
        """
        task = "4H & 15M Structural Support/Resistance Analysis"
        self.start_execution(task=task, stage="Structural Ingestion")

        universe_data: Dict[str, pd.DataFrame] = inputs.get("universe_data", {})
        agent_1_handoff: Dict[str, Any] = inputs.get("agent_1_handoff", {})
        evaluation_time = inputs.get("timestamp", None)

        shortlisted_symbols = agent_1_handoff.get("shortlisted_symbols", list(universe_data.keys()))
        self.input_summary = f"Received {len(shortlisted_symbols)} candidate stocks from Agent 1. Target time: {evaluation_time or 'Latest'}."

        if not shortlisted_symbols:
            self.record_warning("No shortlisted stocks received from Market Scanning Agent.")
            self.complete_execution(task=task, summary="No stocks to analyze.")
            return {"structural_candidates": {}}

        structural_candidates: Dict[str, Any] = {}
        total = len(shortlisted_symbols)

        for idx, sym in enumerate(shortlisted_symbols):
            pct = 10.0 + (idx / total) * 80.0
            df_15m = universe_data.get(sym)
            if df_15m is None or df_15m.empty:
                self.record_decision(
                    symbol=sym, task=task, stage="Data Validation", progress_pct=round(pct, 1),
                    verdict="REJECTED", rationale="15M price history is missing or corrupted.",
                    criteria={"data_available": False}
                )
                continue

            # Determine point-in-time slice
            if evaluation_time is not None and evaluation_time in df_15m.index:
                bar_idx = df_15m.index.get_loc(evaluation_time)
                df_15m_visible = df_15m.iloc[:bar_idx + 1]
            else:
                df_15m_visible = df_15m

            current_time = df_15m_visible.index[-1]
            latest_bar = df_15m_visible.iloc[-1]
            spot_close = float(latest_bar["Close"])
            current_atr = float(latest_bar.get("ATR_14", spot_close * 0.01))

            self.update_progress(
                task=task, stage="4H Resampling & S/R Mapping", progress_pct=round(pct, 1),
                message=f"Constructing 4H structure and detecting confluence zones for {sym}...", symbol=sym
            )

            # 1. 4H Point-in-time Resampling (Strict Zero Look-Ahead Bias)
            df_4h = TimeframeManager.resample_15m_to_4h(df_15m_visible)
            visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, current_time)

            if len(visible_4h) < self.config.timeframe.warmup_bars_4h:
                self.record_decision(
                    symbol=sym, task=task, stage="4H Warmup Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED", rationale=f"Only {len(visible_4h)} closed 4H bars available (minimum required: {self.config.timeframe.warmup_bars_4h}).",
                    criteria={"4h_bars": len(visible_4h), "min_required": self.config.timeframe.warmup_bars_4h}
                )
                continue

            # 2. 4H Market Structure Analysis
            market_structure_4h = self.sr_4h_engine.analyze_market_structure(
                df_4h_visible=visible_4h,
                current_time=current_time,
                current_spot=spot_close
            )

            # 3. 15M S/R Zone Detection
            supports_15m, resistances_15m = self.sr_15m_engine.detect_15m_zones(
                df_15m_visible=df_15m_visible,
                current_time=current_time
            )

            # 4. Multi-Timeframe Confluence Detection
            confluent_supports, confluent_resistances = self.sr_15m_engine.find_confluence_zones(
                market_structure_4h=market_structure_4h,
                supports_15m=supports_15m,
                resistances_15m=resistances_15m,
                current_spot=spot_close
            )

            # 5. Price Reaction & Boundary Proximity Checks
            nearest_sup = confluent_supports[0] if confluent_supports else None
            nearest_res = confluent_resistances[0] if confluent_resistances else None

            # Fallback to nearest 4H levels if no confluence zone directly at spot
            if nearest_sup is None and market_structure_4h.nearest_support:
                ns = market_structure_4h.nearest_support
                nearest_sup = ConfluenceZone(
                    zone_type="SUPPORT", center_price=ns.price_level, lower_bound=ns.lower_bound,
                    upper_bound=ns.upper_bound, confluence_score=ns.strength_score * 0.8,
                    zone_4h=ns, zone_15m=None, distance_pct=abs(spot_close - ns.price_level) / spot_close,
                    is_tested=True
                )
            if nearest_res is None and market_structure_4h.nearest_resistance:
                nr = market_structure_4h.nearest_resistance
                nearest_res = ConfluenceZone(
                    zone_type="RESISTANCE", center_price=nr.price_level, lower_bound=nr.lower_bound,
                    upper_bound=nr.upper_bound, confluence_score=nr.strength_score * 0.8,
                    zone_4h=nr, zone_15m=None, distance_pct=abs(spot_close - nr.price_level) / spot_close,
                    is_tested=True
                )

            # Distance calculations
            dist_to_sup_pct = (spot_close - nearest_sup.center_price) / spot_close if nearest_sup else 999.0
            dist_to_res_pct = (nearest_res.center_price - spot_close) / spot_close if nearest_res else 999.0

            self.record_calculation(
                symbol=sym, task=task, stage="Proximity Calculation", progress_pct=round(pct, 1),
                formula="Dist_Support_Pct = (Spot - Sup_Level) / Spot; Dist_Res_Pct = (Res_Level - Spot) / Spot",
                inputs={"Spot": spot_close, "Nearest_Sup": nearest_sup.center_price if nearest_sup else None, "Nearest_Res": nearest_res.center_price if nearest_res else None},
                result={"dist_to_sup_pct": round(dist_to_sup_pct * 100.0, 2), "dist_to_res_pct": round(dist_to_res_pct * 100.0, 2)},
                interpretation=f"Price is {dist_to_sup_pct*100:.2f}% above Support, {dist_to_res_pct*100:.2f}% below Resistance."
            )

            # Rejection / Acceptance Logic
            # Must be within 1.5% of either Support (Potential BUY) or Resistance (Potential SELL / Short)
            testing_support = (-0.005 <= dist_to_sup_pct <= 0.015)
            testing_resistance = (-0.005 <= dist_to_res_pct <= 0.015)

            if not testing_support and not testing_resistance:
                self.record_decision(
                    symbol=sym, task=task, stage="Zone Proximity Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Stock is floating in mid-range ({dist_to_sup_pct*100:.1f}% from support, {dist_to_res_pct*100:.1f}% from resistance). Entering in the middle of a range violates risk-reward.",
                    criteria={"dist_to_sup_pct": dist_to_sup_pct, "dist_to_res_pct": dist_to_res_pct, "max_allowed_dist": 0.015}
                )
                continue

            # Determine setup bias
            setup_bias = "BULLISH_SUPPORT_TEST" if testing_support else "BEARISH_RESISTANCE_TEST"
            active_zone = nearest_sup if testing_support else nearest_res
            strength_score = active_zone.confluence_score if active_zone else 0.5

            if strength_score < 0.50:
                self.record_decision(
                    symbol=sym, task=task, stage="Zone Strength Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Zone strength score ({strength_score:.2f}) is below minimum institutional threshold (0.50). Insufficient retests.",
                    criteria={"strength_score": strength_score, "min_required": 0.50}
                )
                continue

            # Passed S/R validation!
            self.record_decision(
                symbol=sym, task=task, stage="Zone Selection", progress_pct=round(pct, 1),
                verdict="SELECTED",
                rationale=f"Confirmed {setup_bias} at ₹{active_zone.center_price:,.2f} with strength score {strength_score*100:.1f}%. 4H trend: {market_structure_4h.trend}.",
                criteria={"setup_bias": setup_bias, "zone_level": active_zone.center_price, "strength_score": strength_score, "trend_4h": market_structure_4h.trend}
            )

            candidate_info = {
                "symbol": sym,
                "spot_close": spot_close,
                "current_atr_15m": current_atr,
                "setup_bias": setup_bias, # "BULLISH_SUPPORT_TEST" or "BEARISH_RESISTANCE_TEST"
                "active_zone": active_zone,
                "nearest_support": nearest_sup,
                "nearest_resistance": nearest_res,
                "market_structure_4h": market_structure_4h,
                "confluent_supports": confluent_supports,
                "confluent_resistances": confluent_resistances,
                "zone_strength_score": strength_score
            }
            structural_candidates[sym] = candidate_info
            self.mapped_structures[sym] = candidate_info

        # Inter-Agent Handoff to Agent 3 (Technical Analysis Agent)
        self.update_progress(task=task, stage="Dispatch to Agent 3", progress_pct=95.0, message="Handoff structural candidate maps to Technical Analysis Agent...")
        handoff_payload = {
            "structural_candidates": structural_candidates,
            "mapped_count": len(structural_candidates)
        }

        self.send_message(
            recipient_agent="AGENT_3_TECHNICAL_ANALYSIS",
            message_type="STRUCTURAL_ZONES_AND_CONFLUENCE_MAPS",
            payload_summary=f"Transferred {len(structural_candidates)} confirmed S/R zone setups for 15M reversal confirmation.",
            payload=handoff_payload,
            impact_on_recipient="Provides Agent 3 with verified 4H structural levels, zone boundaries, and macro market direction for indicator alignment."
        )

        self.complete_execution(
            task=task,
            summary=f"Mapped 4H/15M structure for {total} stocks; confirmed {len(structural_candidates)} actionable S/R setups."
        )

        return handoff_payload

    def generate_report(self) -> AgentReport:
        elapsed = round((self.end_perf_time - self.start_perf_time) * 1000.0, 2) if self.start_perf_time and self.end_perf_time else 0.0
        confidence = 0.88 if len(self.selected_stocks) > 0 else 0.40
        limitations = [
            "4H levels require at least 3 confirmed pivot retests to achieve high conviction.",
            "Wick rejections can occasionally be distorted during high-volatility market open spikes (09:15 - 09:30 IST)."
        ]
        return AgentReport(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            objective="Identify major 4H and 15M support & resistance zones, test touch counts, and verify price boundary proximity.",
            timestamp=datetime.now(),
            input_data_summary=self.input_summary,
            methodology="Session-aware 15M to 4H resampling, swing pivot clustering with N-bar lag, volume weighting, and confluence zone matching.",
            calculations_performed=self.calculations,
            findings=[
                {"metric": "Actionable Setups Identified", "value": len(self.selected_stocks)},
                {"metric": "Rejected Floating Mid-Range", "value": len(self.rejected_stocks)}
            ],
            selected_stocks=self.selected_stocks,
            rejected_stocks=self.rejected_stocks,
            output_summary=f"Passed {len(self.selected_stocks)} structurally validated stocks to Technical Analysis Agent.",
            output_payload={"candidate_symbols": self.selected_stocks},
            confidence_assessment=confidence,
            limitations_identified=limitations,
            execution_status="Completed" if self.selected_stocks else "No Setups Near S/R",
            processing_time_ms=elapsed,
            errors_and_warnings=self.warnings_and_errors
        )

"""
Agent 3: Technical Analysis & Stock Selection Agent.
Evaluates 15M price action, candlestick reversal patterns, volume surges, momentum (RSI), and trend structure (EMAs).
Calculates Risk-to-Reward ratios against opposing 4H levels, scores multi-factor conviction, and rank-orders the strongest opportunities.
Sends prioritized candidate trade setups to Agent 4 (Risk Management Agent).
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentReport
from src.agents.transparency_bus import TransparencyBus
from src.config.trading_config import MasterConfig
from src.indicators.reversal_confirmation import ReversalConfirmation, ReversalSignal

class TechnicalAnalysisAgent(BaseAgent):
    """
    Technical Analysis & Stock Selection Agent.
    Evaluates micro price action, volume confirmation, oscillator momentum, and R:R ratios.
    """

    def __init__(self, bus: TransparencyBus, config: Optional[MasterConfig] = None, min_rr: float = 1.5, min_score: float = 55.0):
        super().__init__(
            agent_id="AGENT_3_TECHNICAL_ANALYSIS",
            agent_name="Technical Analysis & Stock Selection Agent",
            bus=bus
        )
        self.config = config or MasterConfig()
        self.min_rr = min_rr
        self.min_score = min_score
        self.reversal_engine = ReversalConfirmation(self.config.confirmation)
        self.ranked_opportunities: List[Dict[str, Any]] = []
        self.input_summary: str = ""

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
        - 'universe_data': Dict[str, pd.DataFrame] (symbol -> 15M dataframe)
        - 'agent_2_handoff': Dict[str, Any] (from SupportResistanceAgent)
        - 'timestamp': Optional[pd.Timestamp]
        """
        task = "15M Technical Reversal, Volume, Momentum & R:R Ranking"
        self.start_execution(task=task, stage="Technical Evaluation")

        universe_data: Dict[str, pd.DataFrame] = inputs.get("universe_data", {})
        agent_2_handoff: Dict[str, Any] = inputs.get("agent_2_handoff", {})
        structural_candidates: Dict[str, Any] = agent_2_handoff.get("structural_candidates", {})
        evaluation_time = inputs.get("timestamp", None)

        self.input_summary = f"Received {len(structural_candidates)} structurally validated stocks from Agent 2. Time: {evaluation_time or 'Latest'}."

        if not structural_candidates:
            self.record_warning("No structural candidates provided by Agent 2 to analyze.")
            self.complete_execution(task=task, summary="No candidates passed S/R validation.")
            return {"ranked_setups": []}

        scored_candidates: List[Dict[str, Any]] = []
        total = len(structural_candidates)

        for idx, (sym, struct_info) in enumerate(structural_candidates.items()):
            pct = 10.0 + (idx / total) * 80.0
            df_15m = universe_data.get(sym)
            if df_15m is None or df_15m.empty:
                continue

            if evaluation_time is not None and evaluation_time in df_15m.index:
                bar_idx = df_15m.index.get_loc(evaluation_time)
                df_sub = df_15m.iloc[:bar_idx + 1]
            else:
                bar_idx = len(df_15m) - 1
                df_sub = df_15m

            latest_bar = df_sub.iloc[-1]
            spot_close = float(latest_bar["Close"])
            setup_bias = struct_info["setup_bias"] # "BULLISH_SUPPORT_TEST" or "BEARISH_RESISTANCE_TEST"
            current_atr = struct_info["current_atr_15m"]

            self.update_progress(
                task=task, stage="Pattern & Momentum Detection", progress_pct=round(pct, 1),
                message=f"Evaluating 15M candle patterns, volume surge, and RSI momentum for {sym}...", symbol=sym
            )

            # 1. Evaluate 15M Reversal Candlestick Patterns
            reversal: ReversalSignal = self.reversal_engine.evaluate_bar(df_sub, len(df_sub) - 1)

            # 2. EMA Trend Alignment (20 EMA vs 50 EMA on 15M)
            ema_20 = float(df_sub["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
            ema_50 = float(df_sub["Close"].ewm(span=50, adjust=False).mean().iloc[-1])
            ema_trend = "BULLISH" if ema_20 >= ema_50 else "BEARISH"

            # 3. Volume Surge Ratio
            vol_ratio = reversal.volume_ratio

            # 4. Pattern Alignment Check
            expected_dir = "BULLISH" if setup_bias == "BULLISH_SUPPORT_TEST" else "BEARISH"
            is_pattern_aligned = (reversal.direction == expected_dir)

            self.record_calculation(
                symbol=sym, task=task, stage="Indicator Calculations", progress_pct=round(pct, 1),
                formula="Volume_Ratio = Bar_Vol / 20_SMA_Vol; EMA_Trend = EMA20 >= EMA50",
                inputs={"Pattern": reversal.pattern_name, "Direction": reversal.direction, "RSI_14": round(reversal.rsi_value, 1), "Vol_Ratio": round(vol_ratio, 2), "EMA20": round(ema_20, 2), "EMA50": round(ema_50, 2)},
                result={"aligned": is_pattern_aligned, "composite_conf_score": round(reversal.composite_confirmation_score, 2)},
                interpretation=f"Detected {reversal.pattern_name} ({reversal.direction}). Volume {vol_ratio:.1f}x SMA, RSI {reversal.rsi_value:.1f}."
            )

            if not is_pattern_aligned or reversal.composite_confirmation_score < 0.35:
                self.record_decision(
                    symbol=sym, task=task, stage="Reversal Confirmation Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Reversal pattern not confirmed. Expected {expected_dir} at S/R zone, but 15M candle shows {reversal.direction} ({reversal.pattern_name}) with low score ({reversal.composite_confirmation_score:.2f}).",
                    criteria={"pattern_name": reversal.pattern_name, "direction": reversal.direction, "score": reversal.composite_confirmation_score}
                )
                continue

            # 5. Risk-to-Reward Ratio (R:R) Calculation
            # Stop loss placed beyond zone boundary + ATR buffer
            if expected_dir == "BULLISH":
                zone_low = struct_info["active_zone"].lower_bound
                stop_loss = round(zone_low - (1.2 * current_atr), 2)
                # Target is opposing 4H resistance level
                opposing_target = struct_info["nearest_resistance"].center_price if struct_info.get("nearest_resistance") else (spot_close + 3.0 * current_atr)
                opposing_target = round(opposing_target, 2)
            else: # BEARISH
                zone_high = struct_info["active_zone"].upper_bound
                stop_loss = round(zone_high + (1.2 * current_atr), 2)
                # Target is opposing 4H support level
                opposing_target = struct_info["nearest_support"].center_price if struct_info.get("nearest_support") else (spot_close - 3.0 * current_atr)
                opposing_target = round(opposing_target, 2)

            risk_per_share = abs(spot_close - stop_loss)
            reward_per_share = abs(opposing_target - spot_close)
            rr_ratio = round(reward_per_share / max(0.01, risk_per_share), 2)

            self.record_calculation(
                symbol=sym, task=task, stage="Risk-Reward Math", progress_pct=round(pct, 1),
                formula="R:R = (Opposing_Target - Spot) / (Spot - Stop_Loss)",
                inputs={"Spot": spot_close, "StopLoss": stop_loss, "Target": opposing_target, "Risk": round(risk_per_share, 2), "Reward": round(reward_per_share, 2)},
                result=rr_ratio,
                interpretation=f"Risk ₹{risk_per_share:.2f} to make ₹{reward_per_share:.2f} (R:R = {rr_ratio}:1)."
            )

            # Strict R:R Gate
            if rr_ratio < self.min_rr:
                self.record_decision(
                    symbol=sym, task=task, stage="Risk-Reward Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Risk-to-Reward ratio ({rr_ratio}:1) is below institutional minimum ({self.min_rr}:1). Opposing 4H level is too close to entry.",
                    criteria={"rr_ratio": rr_ratio, "min_required": self.min_rr, "opposing_target": opposing_target}
                )
                continue

            # 6. Multi-Factor Conviction Scoring (0 to 100)
            # 35% S/R Strength + 30% Confirmation Pattern + 20% R:R + 15% Volume Surge
            sr_part = struct_info["zone_strength_score"] * 35.0
            conf_part = reversal.composite_confirmation_score * 30.0
            rr_part = min(20.0, (rr_ratio / 3.0) * 20.0)
            vol_part = min(15.0, (vol_ratio / 1.5) * 15.0)
            composite_score = round(sr_part + conf_part + rr_part + vol_part, 1)

            if composite_score < self.min_score:
                self.record_decision(
                    symbol=sym, task=task, stage="Composite Conviction Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Composite technical score ({composite_score:.1f}) is below threshold ({self.min_score:.1f}).",
                    criteria={"composite_score": composite_score, "min_score": self.min_score}
                )
                continue

            # Accepted & Qualified!
            self.record_decision(
                symbol=sym, task=task, stage="Candidate Qualification", progress_pct=round(pct, 1),
                verdict="SELECTED",
                rationale=f"Qualified {expected_dir} setup! Pattern: {reversal.pattern_name}, Volume: {vol_ratio:.1f}x, R:R: {rr_ratio}:1, Conviction: {composite_score}/100.",
                criteria={"score": composite_score, "rr_ratio": rr_ratio, "pattern": reversal.pattern_name, "volume_ratio": vol_ratio}
            )

            setup_payload = {
                "symbol": sym,
                "direction": "BUY" if expected_dir == "BULLISH" else "SELL", # Cash market action
                "spot_entry": spot_close,
                "stop_loss": stop_loss,
                "opposing_target": opposing_target,
                "risk_per_share": risk_per_share,
                "reward_per_share": reward_per_share,
                "rr_ratio": rr_ratio,
                "pattern_name": reversal.pattern_name,
                "volume_ratio": vol_ratio,
                "rsi_value": reversal.rsi_value,
                "composite_score": composite_score,
                "struct_info": struct_info
            }
            scored_candidates.append(setup_payload)

        # Rank-order by composite score descending
        scored_candidates.sort(key=lambda x: x["composite_score"], reverse=True)
        for r_idx, c in enumerate(scored_candidates):
            c["rank"] = r_idx + 1

        self.ranked_opportunities = scored_candidates

        # Inter-Agent Handoff to Agent 4 (Risk Management Agent)
        self.update_progress(task=task, stage="Dispatch to Agent 4", progress_pct=95.0, message="Handoff ranked candidates to Risk Management Agent...")
        handoff_payload = {
            "ranked_setups": scored_candidates,
            "qualified_count": len(scored_candidates)
        }

        self.send_message(
            recipient_agent="AGENT_4_RISK_MANAGEMENT",
            message_type="RANKED_TECHNICAL_CANDIDATES",
            payload_summary=f"Transferred {len(scored_candidates)} prioritized technical setups with verified R:R and pattern confirmations.",
            payload=handoff_payload,
            impact_on_recipient="Supplies Agent 4 with validated entry, structural stop-loss, target, and conviction scores for cash position sizing."
        )

        self.complete_execution(
            task=task,
            summary=f"Evaluated {total} structural candidates; ranked {len(scored_candidates)} high-probability setups with R:R >= {self.min_rr}:1."
        )

        return handoff_payload

    def generate_report(self) -> AgentReport:
        elapsed = round((self.end_perf_time - self.start_perf_time) * 1000.0, 2) if self.start_perf_time and self.end_perf_time else 0.0
        confidence = 0.85 if len(self.selected_stocks) > 0 else 0.45
        limitations = [
            "Candlestick patterns require volume expansion to distinguish institutional accumulation from retail noise.",
            "R:R ratios are bounded by the nearest opposing 4H zone; in compressed ranges, valid patterns must be rejected if R:R < 1.5."
        ]
        return AgentReport(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            objective="Evaluate 15M reversal patterns, volume surges, RSI momentum, and R:R ratios to rank top opportunities.",
            timestamp=datetime.now(),
            input_data_summary=self.input_summary,
            methodology="Rule-based candlestick classification (Hammer, Engulfing), volume surge ratio (>=1.2x SMA), and opposing structural target R:R math.",
            calculations_performed=self.calculations,
            findings=[
                {"metric": "Qualified Technical Setups", "value": len(self.selected_stocks)},
                {"metric": "Rejected Low R:R or Unconfirmed", "value": len(self.rejected_stocks)}
            ],
            selected_stocks=self.selected_stocks,
            rejected_stocks=self.rejected_stocks,
            output_summary=f"Passed {len(self.selected_stocks)} rank-ordered technical setups to Risk Management Agent.",
            output_payload={"ranked_count": len(self.selected_stocks)},
            confidence_assessment=confidence,
            limitations_identified=limitations,
            execution_status="Completed" if self.selected_stocks else "No Setups Confirmed",
            processing_time_ms=elapsed,
            errors_and_warnings=self.warnings_and_errors
        )

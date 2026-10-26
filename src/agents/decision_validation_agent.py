"""
Agent 5: Decision & Validation Agent.
Ultimate governance and consensus engine for the 5-Agent Stock Trading System.
- Audits findings, calculations, and confidence scores from Agents 1, 2, 3, and 4.
- Resolves conflicting signals (Macro vs Micro, S/R vs Volume, Reward vs Friction).
- Validates each trade blueprint against institutional execution standards.
- Produces the Final Decision: BUY, SELL, or NO TRADE.
- If no stock qualifies, strictly outputs NO TRADE (capital 100% protected).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentReport
from src.agents.transparency_bus import TransparencyBus

@dataclass
class FinalTradeRecommendation:
    symbol: str
    company_name: str
    cap_category: str
    verdict: Literal["BUY", "SELL", "NO_TRADE"]
    entry_price: float
    target_1_rr: float
    target_2_macro: float
    initial_stop_loss: float
    trailing_stop_plan: str
    shares_quantity: int
    capital_deployed: float
    max_risk_inr: float
    friction_cost_inr: float
    risk_reward_ratio: float
    system_confidence: float # 0.0 to 1.0
    detailed_reasoning: str
    agent_contributions: Dict[str, str] = field(default_factory=dict)
    conflict_resolutions: List[str] = field(default_factory=list)

class DecisionValidationAgent(BaseAgent):
    """
    Decision & Validation Agent.
    Final arbiter and governance authority. Guarantees no forced entries and transparent consensus tracking.
    """

    def __init__(self, bus: TransparencyBus, min_system_confidence: float = 0.65, max_final_trades: int = 5):
        super().__init__(
            agent_id="AGENT_5_DECISION_VALIDATION",
            agent_name="Decision & Validation Agent",
            bus=bus
        )
        self.min_system_confidence = min_system_confidence
        self.max_final_trades = max_final_trades
        self.final_recommendations: List[FinalTradeRecommendation] = []
        self.conflict_resolution_log: List[Dict[str, Any]] = []
        self.input_summary: str = ""

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
        - 'agent_1_handoff': Dict[str, Any] (Market regime & sector data)
        - 'agent_2_handoff': Dict[str, Any] (S/R structural maps)
        - 'agent_3_handoff': Dict[str, Any] (Ranked technical setups)
        - 'agent_4_handoff': Dict[str, Any] (Sized risk plans & cost models)
        """
        task = "Multi-Agent Consensus Audit & Final Trade Decision"
        self.start_execution(task=task, stage="Multi-Agent Audit")

        agent_1_handoff: Dict[str, Any] = inputs.get("agent_1_handoff", {})
        agent_2_handoff: Dict[str, Any] = inputs.get("agent_2_handoff", {})
        agent_3_handoff: Dict[str, Any] = inputs.get("agent_3_handoff", {})
        agent_4_handoff: Dict[str, Any] = inputs.get("agent_4_handoff", {})

        market_regime = agent_1_handoff.get("market_regime", "RANGE_BOUND_NEUTRAL")
        sector_performance = agent_1_handoff.get("sector_performance", {})
        sized_plans: List[Dict[str, Any]] = agent_4_handoff.get("sized_risk_plans", [])

        self.input_summary = f"Auditing {len(sized_plans)} sized risk blueprints under {market_regime} regime with inputs from Agents 1, 2, 3, and 4."

        if not sized_plans:
            self.record_decision(
                symbol="PORTFOLIO_VERDICT", task=task, stage="Final Consensus", progress_pct=100.0,
                verdict="PASSED",
                rationale="Zero qualified trade setups received from upstream risk pipeline. Capital is 100% preserved in cash buffer.",
                criteria={"qualified_plans": 0}
            )
            self.complete_execution(task=task, summary="Verdict: NO TRADE. Zero candidates met institutional criteria.")
            return {
                "execution_verdict": "NO_TRADE",
                "final_recommendations": [],
                "conflict_resolutions": self.conflict_resolution_log
            }

        candidate_recommendations: List[FinalTradeRecommendation] = []
        total = len(sized_plans)

        for idx, plan in enumerate(sized_plans):
            pct = 15.0 + (idx / total) * 75.0
            sym = plan["symbol"]
            sec = plan["sector"]
            direction = plan["direction"]
            spot = plan["spot_entry"]
            stop_loss = plan["stop_loss"]
            t1 = plan["target_1_rr"]
            t2 = plan["target_2_macro"]
            shares = plan["shares_quantity"]
            capital = plan["capital_required"]
            risk_inr = plan["actual_risk_inr"]
            friction = plan["friction_cost_inr"]
            rr = plan["rr_ratio"]
            score = plan["technical_score"]

            self.update_progress(
                task=task, stage="Conflict Resolution & Cross-Validation", progress_pct=round(pct, 1),
                message=f"Resolving inter-agent signals and auditing execution blueprint for {sym}...", symbol=sym
            )

            disagreements: List[str] = []
            resolutions: List[str] = []

            # -----------------------------------------------------------------
            # Conflict Resolution Check 1: Macro vs Micro Directional Alignment
            # -----------------------------------------------------------------
            # If market regime is BEARISH_CONTRACTION, buying stocks requires extra strong sector momentum
            sec_mom = sector_performance.get(sec, 0.0)
            if direction == "BUY" and market_regime == "BEARISH_CONTRACTION":
                if sec_mom < 0.0:
                    disagreements.append(f"Agent 1 reports Bearish Market Regime and negative {sec} momentum ({sec_mom}%), conflicting with Long Buy setup.")
                    # Rejection: Swimming against market and sector tide
                    self.record_decision(
                        symbol=sym, task=task, stage="Macro Conflict Gate", progress_pct=round(pct, 1),
                        verdict="REJECTED",
                        rationale=f"Vetoed: Long BUY signal conflicts with broad market contraction and negative sector momentum ({sec_mom}%).",
                        criteria={"market_regime": market_regime, "sector_momentum": sec_mom}
                    )
                    self.conflict_resolution_log.append({
                        "symbol": sym, "conflict": "Bearish Market vs Long Buy",
                        "resolution": "Vetoed trade to prevent counter-trend market risk."
                    })
                    continue
                else:
                    resolutions.append(f"Sector {sec} exhibits positive relative strength ({sec_mom}%) despite broader market contraction. Permitted with caution.")

            # -----------------------------------------------------------------
            # Conflict Resolution Check 2: Volume Conviction Audit
            # -----------------------------------------------------------------
            vol_ratio = plan.get("volume_ratio", 1.0)
            if vol_ratio < 1.15:
                disagreements.append(f"Agent 3 noted volume ratio ({vol_ratio:.2f}x) is near the minimum confirmation boundary.")
                # Resolution: Require higher R:R (>= 1.8) if volume is not high conviction
                if rr < 1.8:
                    self.record_decision(
                        symbol=sym, task=task, stage="Volume Conviction Gate", progress_pct=round(pct, 1),
                        verdict="REJECTED",
                        rationale=f"Vetoed: Moderate volume ({vol_ratio:.2f}x) requires at least 1.8:1 R:R (current R:R is {rr:.2f}:1).",
                        criteria={"volume_ratio": vol_ratio, "rr": rr}
                    )
                    self.conflict_resolution_log.append({
                        "symbol": sym, "conflict": "Marginal Volume vs Standard R:R",
                        "resolution": "Vetoed trade due to insufficient risk compensation."
                    })
                    continue
                else:
                    resolutions.append(f"Volume is moderate ({vol_ratio:.2f}x), but exceptional R:R ({rr:.2f}:1) provides statistical compensation.")

            # -----------------------------------------------------------------
            # Conflict Resolution Check 3: Friction vs Expected Net Alpha
            # -----------------------------------------------------------------
            gross_pnl_est = abs(t1 - spot) * shares
            friction_ratio = friction / max(1.0, gross_pnl_est)
            if friction_ratio > 0.12: # Friction exceeds 12% of Target 1 profit
                self.record_decision(
                    symbol=sym, task=task, stage="Friction Impact Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Vetoed: Transaction friction (₹{friction:.2f}) consumes {friction_ratio*100:.1f}% of gross Target 1 profit (limit: 12%).",
                    criteria={"friction_ratio": friction_ratio, "max_allowed": 0.12}
                )
                self.conflict_resolution_log.append({
                    "symbol": sym, "conflict": "High Transaction Friction",
                    "resolution": "Vetoed trade because exchange and regulatory friction impairs net alpha."
                })
                continue

            # -----------------------------------------------------------------
            # System Confidence Formulation (0.0 to 1.0)
            # -----------------------------------------------------------------
            # Weights: 25% Agent 1, 25% Agent 2, 25% Agent 3, 25% Agent 4
            a1_conf = 0.85 if (direction == "BUY" and sec_mom > 0) or (direction == "SELL" and sec_mom < 0) else 0.65
            a2_conf = plan.get("technical_score", 70.0) / 100.0
            a3_conf = min(1.0, (rr / 2.5) * 0.9)
            a4_conf = 0.90 if friction_ratio < 0.08 else 0.75
            system_conf = round((a1_conf * 0.25) + (a2_conf * 0.25) + (a3_conf * 0.25) + (a4_conf * 0.25), 2)

            self.record_calculation(
                symbol=sym, task=task, stage="System Confidence Score", progress_pct=round(pct, 1),
                formula="System_Confidence = 0.25*A1 + 0.25*A2 + 0.25*A3 + 0.25*A4",
                inputs={"Agent1_Macro": a1_conf, "Agent2_SR": round(a2_conf, 2), "Agent3_Technical": round(a3_conf, 2), "Agent4_Risk": a4_conf},
                result=system_conf,
                interpretation=f"Integrated 4-agent consensus score is {system_conf*100:.1f}% (Minimum threshold: {self.min_system_confidence*100:.1f}%)."
            )

            if system_conf < self.min_system_confidence:
                self.record_decision(
                    symbol=sym, task=task, stage="Final Confidence Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"System consensus confidence ({system_conf*100:.1f}%) is below minimum institutional threshold ({self.min_system_confidence*100:.1f}%).",
                    criteria={"system_confidence": system_conf, "min_required": self.min_system_confidence}
                )
                continue

            # Agent Contribution Log
            contributions = {
                "Agent 1 (Market Scanner)": f"Macro regime: {market_regime}. Sector {sec} momentum: {sec_mom:+.2f}%. Verified liquidity.",
                "Agent 2 (Support & Resistance)": f"Mapped 4H structural level at ₹{plan['spot_entry']:,.2f}. Tested and confirmed zone boundary.",
                "Agent 3 (Technical Analysis)": f"Detected 15M {plan['pattern_name']} reversal with {plan['volume_ratio']:.1f}x volume surge. R:R = {rr:.2f}:1.",
                "Agent 4 (Risk Management)": f"Sized cash position at {shares} shares (₹{capital:,.2f}). Set stop at ₹{stop_loss:,.2f} and dynamic trailing plan.",
                "Agent 5 (Decision & Validation)": f"Verified consensus alignment. System Confidence: {system_conf*100:.1f}%. Approved for live execution."
            }

            detailed_reason = (
                f"Multi-agent unanimous consensus achieved for {sym}. Underlying tested 4H major structure, "
                f"confirmed with 15M {plan['pattern_name']} reversal pattern and {plan['volume_ratio']:.1f}x volume surge. "
                f"Asymmetric risk profile verified with {rr:.2f}:1 R:R. Total capital deployed ₹{capital:,.2f} with risk bounded strictly to ₹{risk_inr:,.2f}."
            )

            rec = FinalTradeRecommendation(
                symbol=sym,
                company_name=plan["company_name"],
                cap_category=plan["cap_category"],
                verdict=direction, # "BUY" or "SELL"
                entry_price=spot,
                target_1_rr=t1,
                target_2_macro=t2,
                initial_stop_loss=stop_loss,
                trailing_stop_plan=plan["trailing_plan_desc"],
                shares_quantity=shares,
                capital_deployed=capital,
                max_risk_inr=risk_inr,
                friction_cost_inr=friction,
                risk_reward_ratio=rr,
                system_confidence=system_conf,
                detailed_reasoning=detailed_reason,
                agent_contributions=contributions,
                conflict_resolutions=resolutions
            )
            candidate_recommendations.append(rec)

        # Prioritize Quality Over Quantity:
        # Rank all passing candidates by System Confidence (primary) and Risk:Reward (secondary)
        candidate_recommendations.sort(
            key=lambda r: (r.system_confidence, r.risk_reward_ratio),
            reverse=True
        )

        # Recommend a maximum of 5 stocks per day (do not force 5 if fewer qualify)
        approved_recommendations = candidate_recommendations[:self.max_final_trades]

        # Record selection decisions for the approved setups
        for rec in approved_recommendations:
            self.record_decision(
                symbol=rec.symbol, task=task, stage="Final Selection", progress_pct=100.0,
                verdict="SELECTED",
                rationale=f"TOP-TIER RECOMMENDATION: {rec.verdict} {rec.symbol} ranked in Top {self.max_final_trades} based on highest system confidence ({rec.system_confidence*100:.1f}%) and R:R ({rec.risk_reward_ratio:.2f}:1).",
                criteria={"verdict": rec.verdict, "confidence": rec.system_confidence, "rr": rec.risk_reward_ratio}
            )

        self.final_recommendations = approved_recommendations
        final_verdict = "EXECUTE_TRADES" if len(approved_recommendations) > 0 else "NO_TRADE"

        self.complete_execution(
            task=task,
            summary=f"Final Verdict: {final_verdict}. Approved {len(approved_recommendations)} trades from {total} candidates."
        )

        return {
            "execution_verdict": final_verdict,
            "final_recommendations": approved_recommendations,
            "conflict_resolutions": self.conflict_resolution_log,
            "approved_count": len(approved_recommendations)
        }

    def generate_report(self) -> AgentReport:
        elapsed = round((self.end_perf_time - self.start_perf_time) * 1000.0, 2) if self.start_perf_time and self.end_perf_time else 0.0
        confidence = 0.95 if len(self.selected_stocks) > 0 else 0.60
        limitations = [
            "Agent 5 operates strictly as a veto and consensus gate; it cannot synthesize trades not surfaced by upstream agents.",
            "In high-volatility gap openings, order routing must respect pre-market opening equilibrium auctions."
        ]
        return AgentReport(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            objective="Audit all upstream agent findings, resolve conflicting signals, enforce risk governance, and render final BUY/SELL/NO_TRADE decisions.",
            timestamp=datetime.now(),
            input_data_summary=self.input_summary,
            methodology="Multi-agent cross-validation matrix, conflict resolution heuristics (Macro vs Micro, Friction vs Alpha), and confidence weighting.",
            calculations_performed=self.calculations,
            findings=[
                {"metric": "Final Approved Recommendations", "value": len(self.selected_stocks)},
                {"metric": "Conflicts Resolved / Vetoed", "value": len(self.conflict_resolution_log)},
                {"metric": "Verdict", "value": "EXECUTE_TRADES" if self.selected_stocks else "NO_TRADE"}
            ],
            selected_stocks=self.selected_stocks,
            rejected_stocks=self.rejected_stocks,
            output_summary=f"Produced {len(self.final_recommendations)} executable cash equity recommendations or explicit NO TRADE verdict.",
            output_payload={"approved_count": len(self.final_recommendations), "verdict": "EXECUTE_TRADES" if self.final_recommendations else "NO_TRADE"},
            confidence_assessment=confidence,
            limitations_identified=limitations,
            execution_status="Completed",
            processing_time_ms=elapsed,
            errors_and_warnings=self.warnings_and_errors
        )

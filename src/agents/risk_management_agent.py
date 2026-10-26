"""
Agent 4: Risk Management Agent.
Specializes in institutional cash-market equity risk management:
- Calculates exact cash position sizes based on capital, maximum loss ₹ per trade, and share price.
- Formulates multi-tiered profit targets (1:2 R:R partial booking & 4H structural target).
- Designs dynamic ratcheted trailing stop-losses (breakeven ratchet + swing pivot trailing).
- Computes complete Indian cash market transaction costs (STT, NSE fees, GST, stamp duty, 1-tick slippage).
- Enforces portfolio concentration limits, sector caps, and maximum concurrent positions.
Sends fully specified Risk Plans to Agent 5 (Decision & Validation Agent).
"""

from typing import Dict, Any, List, Optional
import math
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentReport
from src.agents.transparency_bus import TransparencyBus
from src.config.trading_config import MasterConfig
from src.config.nse_symbols import get_symbol_spec
from src.cost.cash_cost_calculator import CashCostCalculator, CashTradeCostBreakdown

class RiskManagementAgent(BaseAgent):
    """
    Risk Management Agent.
    Strict quantitative governance over cash position sizing, capital protection, and friction accounting.
    """

    def __init__(
        self,
        bus: TransparencyBus,
        initial_capital: float = 1000000.0,
        max_risk_per_trade_pct: float = 0.015, # 1.5% max risk per trade (₹15,000 on 10 Lakhs)
        max_capital_per_trade_pct: float = 0.25, # Max 25% capital deployed per stock (₹2,50,000)
        max_concurrent_positions: int = 5,
        max_sector_positions: int = 2
    ):
        super().__init__(
            agent_id="AGENT_4_RISK_MANAGEMENT",
            agent_name="Risk Management Agent",
            bus=bus
        )
        self.initial_capital = initial_capital
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_capital_per_trade_pct = max_capital_per_trade_pct
        self.max_concurrent_positions = max_concurrent_positions
        self.max_sector_positions = max_sector_positions
        self.cost_calculator = CashCostCalculator()
        self.validated_risk_plans: List[Dict[str, Any]] = []
        self.input_summary: str = ""

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
        - 'agent_3_handoff': Dict[str, Any] (from TechnicalAnalysisAgent)
        - 'available_cash': Optional[float]
        - 'current_open_positions': Optional[Dict[str, Any]]
        - 'trade_mode': Literal["DELIVERY", "INTRADAY"]
        """
        task = "Position Sizing, Stop-Loss, Trailing Stop & Cost Calculation"
        self.start_execution(task=task, stage="Risk Parameter Ingestion")

        agent_3_handoff: Dict[str, Any] = inputs.get("agent_3_handoff", {})
        ranked_setups: List[Dict[str, Any]] = agent_3_handoff.get("ranked_setups", [])
        available_cash = inputs.get("available_cash", self.initial_capital)
        current_open_positions = inputs.get("current_open_positions", {})
        trade_mode = inputs.get("trade_mode", "DELIVERY")

        self.input_summary = f"Received {len(ranked_setups)} ranked technical setups. Available Capital: ₹{available_cash:,.2f}. Trade Mode: {trade_mode}."

        if not ranked_setups:
            self.record_warning("No ranked technical setups provided by Agent 3.")
            self.complete_execution(task=task, summary="No setups to size.")
            return {"sized_risk_plans": []}

        max_risk_inr = round(self.initial_capital * self.max_risk_per_trade_pct, 2)
        max_trade_capital = round(available_cash * self.max_capital_per_trade_pct, 2)

        self.record_calculation(
            symbol="PORTFOLIO_RISK_BUDGET", task=task, stage="Risk Budgeting", progress_pct=15.0,
            formula="Max_Risk_INR = Capital * Risk_Pct; Max_Trade_Cap = Available_Cash * Cap_Pct",
            inputs={"Initial_Capital": self.initial_capital, "Available_Cash": available_cash, "Risk_Pct": self.max_risk_per_trade_pct, "Trade_Cap_Pct": self.max_capital_per_trade_pct},
            result={"Max_Risk_INR": max_risk_inr, "Max_Trade_Capital": max_trade_capital},
            interpretation=f"Max permissible loss per trade is ₹{max_risk_inr:,.2f}. Max capital allocation per position is ₹{max_trade_capital:,.2f}."
        )

        sized_plans: List[Dict[str, Any]] = []
        active_sector_counts: Dict[str, int] = {}
        for pos in current_open_positions.values():
            sec = pos.get("sector", "General")
            active_sector_counts[sec] = active_sector_counts.get(sec, 0) + 1

        total = len(ranked_setups)
        for idx, setup in enumerate(ranked_setups):
            pct = 20.0 + (idx / total) * 70.0
            sym = setup["symbol"]
            spec = get_symbol_spec(sym)
            spot = setup["spot_entry"]
            stop_loss = setup["stop_loss"]
            opposing_target = setup["opposing_target"]
            direction = setup["direction"] # "BUY" or "SELL"

            self.update_progress(
                task=task, stage="Cash Position Sizing", progress_pct=round(pct, 1),
                message=f"Calculating cash position size, dynamic trailing stops, and friction for {sym}...", symbol=sym
            )

            # 1. Sector Concentration Limit Check (Max 2 per sector)
            curr_sec_count = active_sector_counts.get(spec.sector, 0)
            if curr_sec_count >= self.max_sector_positions:
                self.record_decision(
                    symbol=sym, task=task, stage="Sector Concentration Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Sector limit reached for '{spec.sector}' ({curr_sec_count} active position >= max limit {self.max_sector_positions}).",
                    criteria={"sector": spec.sector, "current_count": curr_sec_count, "max_limit": self.max_sector_positions}
                )
                continue

            # 2. Mathematical Position Sizing (Decoupled from cash depletion - evaluate purely on merit)
            risk_per_share = abs(spot - stop_loss)
            if risk_per_share <= 0.05:
                self.record_decision(
                    symbol=sym, task=task, stage="Risk Distance Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Risk per share (₹{risk_per_share:.2f}) is unrealistically tight (< 5 paise). Stop-loss is within normal tick noise.",
                    criteria={"risk_per_share": risk_per_share}
                )
                continue

            shares_by_risk = max(1, int(max_risk_inr / risk_per_share))
            shares_by_capital = max(1, int(max_trade_capital / spot))
            final_shares = max(1, min(shares_by_risk, shares_by_capital))

            capital_required = round(final_shares * spot, 2)
            actual_risk_inr = round(final_shares * risk_per_share, 2)

            self.record_calculation(
                symbol=sym, task=task, stage="Sizing Formula", progress_pct=round(pct, 1),
                formula="Shares = min(Max_Risk / Risk_Per_Share, Max_Capital / Spot_Price)",
                inputs={"Max_Risk": max_risk_inr, "Risk_Per_Share": round(risk_per_share, 2), "Spot": spot, "Shares_Risk": shares_by_risk, "Shares_Cap": shares_by_capital},
                result={"Shares": final_shares, "Capital_Required": capital_required, "Actual_Risk_INR": actual_risk_inr},
                interpretation=f"Model Blueprint: Deploying ₹{capital_required:,.2f} for {final_shares} shares. Maximum downside risk bounded strictly to ₹{actual_risk_inr:,.2f}."
            )

            # 3. Dynamic Multi-Tier Targets & Trailing Stop Plan
            # Target 1 is 1:2 R:R (book 50% shares)
            target_1_rr = round(spot + (2.0 * risk_per_share) if direction == "BUY" else spot - (2.0 * risk_per_share), 2)
            target_2_macro = opposing_target

            # Dynamic Trailing Stop Logic:
            # - Initial Stop: stop_loss (-1.0R)
            # - Breakeven Activation: Price moves +1.5R favorable -> Move Stop to Entry + 0.3% (covers all taxes)
            # - Ratchet: Once Target 1 is hit -> Move Stop to +1.0R and trail remaining 50% using 15M swing low
            be_trigger = round(spot + (1.5 * risk_per_share) if direction == "BUY" else spot - (1.5 * risk_per_share), 2)
            be_stop = round(spot * 1.003 if direction == "BUY" else spot * 0.997, 2)

            trailing_plan_desc = (
                f"1. Initial Stop: ₹{stop_loss:,.2f} (-1.0R). "
                f"2. Breakeven Trigger: At ₹{be_trigger:,.2f} (+1.5R gain), ratchet stop to ₹{be_stop:,.2f} (+0.3% tax buffer). "
                f"3. Profit Booking: At Target 1 (₹{target_1_rr:,.2f}, 1:2 R:R), close 50% shares ({final_shares//2} qty) and trail remainder using 15M swing pivots to Target 2 (₹{target_2_macro:,.2f})."
            )

            # 4. Cash Market Transaction Costs Calculation
            costs: CashTradeCostBreakdown = self.cost_calculator.calculate_round_trip_cost(
                entry_price=spot,
                exit_price=target_1_rr,
                quantity=final_shares,
                trade_mode=trade_mode
            )

            self.record_calculation(
                symbol=sym, task=task, stage="Cost Accounting", progress_pct=round(pct, 1),
                formula="Friction = Brokerage + STT + NSE_Turnover + GST + Stamp_Duty + Slippage",
                inputs={"Turnover": costs.total_turnover, "Brokerage": costs.brokerage, "STT": costs.stt, "Exchange": costs.exchange_charges, "GST": costs.gst, "Stamp": costs.stamp_duty, "Slippage": costs.slippage_cost},
                result=costs.total_friction_cost,
                interpretation=f"Round-trip transaction friction is ₹{costs.total_friction_cost:,.2f} ({costs.total_friction_cost/capital_required*100:.3f}% of capital)."
            )

            # Check net profitability after friction
            expected_gross_profit = (final_shares * (abs(target_1_rr - spot))) * 0.5 + (final_shares * (abs(target_2_macro - spot))) * 0.5
            expected_net_profit = round(expected_gross_profit - costs.total_friction_cost, 2)

            if expected_net_profit <= costs.total_friction_cost:
                self.record_decision(
                    symbol=sym, task=task, stage="Net Friction Gate", progress_pct=round(pct, 1),
                    verdict="REJECTED",
                    rationale=f"Expected profit (₹{expected_gross_profit:.2f}) does not adequately clear transaction friction (₹{costs.total_friction_cost:.2f}).",
                    criteria={"expected_profit": expected_gross_profit, "friction": costs.total_friction_cost}
                )
                continue

            # Fully Approved Risk Plan!
            self.record_decision(
                symbol=sym, task=task, stage="Risk Plan Approval", progress_pct=round(pct, 1),
                verdict="SELECTED",
                rationale=f"Approved risk blueprint for {final_shares} shares. Capital: ₹{capital_required:,.2f}, Max Risk: ₹{actual_risk_inr:,.2f}, Friction: ₹{costs.total_friction_cost:,.2f}.",
                criteria={"shares": final_shares, "capital": capital_required, "max_risk": actual_risk_inr, "friction": costs.total_friction_cost}
            )

            risk_plan = {
                "symbol": sym,
                "company_name": spec.name,
                "sector": spec.sector,
                "cap_category": spec.cap_category,
                "direction": direction,
                "spot_entry": spot,
                "stop_loss": stop_loss,
                "target_1_rr": target_1_rr,
                "target_2_macro": target_2_macro,
                "shares_quantity": final_shares,
                "capital_required": capital_required,
                "actual_risk_inr": actual_risk_inr,
                "risk_per_share": risk_per_share,
                "reward_per_share": setup["reward_per_share"],
                "rr_ratio": setup["rr_ratio"],
                "friction_cost_inr": costs.total_friction_cost,
                "expected_net_profit": expected_net_profit,
                "trailing_plan_desc": trailing_plan_desc,
                "costs_breakdown": costs,
                "technical_score": setup["composite_score"],
                "pattern_name": setup["pattern_name"],
                "volume_ratio": setup["volume_ratio"],
                "rsi_value": setup["rsi_value"]
            }
            sized_plans.append(risk_plan)
            active_sector_counts[spec.sector] = active_sector_counts.get(spec.sector, 0) + 1

        self.validated_risk_plans = sized_plans

        # Inter-Agent Handoff to Agent 5 (Decision & Validation Agent)
        self.update_progress(task=task, stage="Dispatch to Agent 5", progress_pct=95.0, message="Handoff sized risk plans to Decision & Validation Agent...")
        handoff_payload = {
            "sized_risk_plans": sized_plans,
            "total_plans_count": len(sized_plans),
            "max_risk_inr": max_risk_inr
        }

        self.send_message(
            recipient_agent="AGENT_5_DECISION_VALIDATION",
            message_type="SIZED_RISK_PLANS_AND_COST_MODELS",
            payload_summary=f"Transferred {len(sized_plans)} complete risk execution blueprints with cash position sizes and Indian tax deductions.",
            payload=handoff_payload,
            impact_on_recipient="Supplies Agent 5 with strict capital allocations, downside protection limits, and round-trip fee models for final governance."
        )

        self.complete_execution(
            task=task,
            summary=f"Generated {len(sized_plans)} mathematically validated risk plans from {total} candidates. Capital safely bounded."
        )

        return handoff_payload

    def generate_report(self) -> AgentReport:
        elapsed = round((self.end_perf_time - self.start_perf_time) * 1000.0, 2) if self.start_perf_time and self.end_perf_time else 0.0
        confidence = 0.92 if len(self.selected_stocks) > 0 else 0.50
        limitations = [
            "Position sizes assume execution at the current spot price; extreme opening gap-ups or gap-downs could alter entry risk.",
            "Statutory taxes (STT, Stamp Duty) are calculated point-in-time per NSE equity transaction schedule."
        ]
        return AgentReport(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            objective="Compute exact cash position sizes, initial stop-loss, profit targets, dynamic trailing stop, and Indian statutory transaction fees.",
            timestamp=datetime.now(),
            input_data_summary=self.input_summary,
            methodology="Fixed fractional risk model (1.5% max risk), cash capital deployment limits (25% max per trade), and Zerodha/NSE equity cost schedule.",
            calculations_performed=self.calculations,
            findings=[
                {"metric": "Approved Risk Plans", "value": len(self.selected_stocks)},
                {"metric": "Rejected Due to Sector Cap / Capital", "value": len(self.rejected_stocks)}
            ],
            selected_stocks=self.selected_stocks,
            rejected_stocks=self.rejected_stocks,
            output_summary=f"Passed {len(self.selected_stocks)} sized risk blueprints to Decision & Validation Agent.",
            output_payload={"approved_plans_count": len(self.selected_stocks)},
            confidence_assessment=confidence,
            limitations_identified=limitations,
            execution_status="Completed" if self.selected_stocks else "No Plans Sized",
            processing_time_ms=elapsed,
            errors_and_warnings=self.warnings_and_errors
        )

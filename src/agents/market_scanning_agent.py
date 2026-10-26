"""
Agent 1: Market & Stock Scanning Agent.
Scans the eligible NSE stock universe (Large, Mid, Small Cap).
Analyzes overall market regime, sector relative strength, market breadth, and volatility environment.
Filters out illiquid, erratic, or range-bound stocks and shortlists high-potential candidates for Agent 2.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentReport
from src.agents.transparency_bus import TransparencyBus
from src.config.nse_symbols import get_symbol_spec, SymbolSpec

class MarketScanningAgent(BaseAgent):
    """
    Market & Stock Scanning Agent.
    Evaluates macro market structure, sector performance, liquidity, and shortlists candidates.
    """

    def __init__(self, bus: TransparencyBus, min_daily_volume: int = 100000, min_atr_pct: float = 0.0020):
        super().__init__(
            agent_id="AGENT_1_MARKET_SCANNER",
            agent_name="Market & Stock Scanning Agent",
            bus=bus
        )
        self.min_daily_volume = min_daily_volume
        self.min_atr_pct = min_atr_pct # 0.20% minimum 15M ATR relative to stock price
        self.market_regime: str = "UNKNOWN"
        self.sector_performance: Dict[str, float] = {}
        self.shortlisted_stocks_data: Dict[str, Any] = {}
        self.total_scanned_count: int = 0
        self.input_summary: str = ""

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
        - 'universe_data': Dict[str, pd.DataFrame] (symbol -> 15M dataframe)
        - 'timestamp': Optional[pd.Timestamp]
        """
        task = "Scanning NSE Universe and Macro Market Regimes"
        self.start_execution(task=task, stage="Universe Ingestion")

        universe_data: Dict[str, pd.DataFrame] = inputs.get("universe_data", {})
        evaluation_time = inputs.get("timestamp", None)
        self.total_scanned_count = len(universe_data)
        self.input_summary = f"{len(universe_data)} NSE stocks ingested across Large, Mid, and Small-cap tiers. Evaluation time: {evaluation_time or 'Latest'}."

        if not universe_data:
            self.record_warning("Universe data feed is empty. No stocks provided to scan.")
            self.fail_execution(task=task, error_msg="Universe data dictionary is empty.")
            return {"shortlisted_stocks": [], "market_regime": "NEUTRAL", "sector_performance": {}}

        # Stage 1: Market Breadth and Macro Regime Analysis
        self.update_progress(task=task, stage="Market Breadth Analysis", progress_pct=15.0, message="Calculating market breadth, median ATR, and benchmark trend...")
        positive_momentum_count = 0
        atr_pct_list = []
        sector_returns: Dict[str, List[float]] = {}

        valid_symbols = []
        for sym, df_15m in universe_data.items():
            if df_15m.empty or len(df_15m) < 50:
                self.record_decision(
                    symbol=sym, task=task, stage="Data Validation", progress_pct=20.0,
                    verdict="REJECTED", rationale=f"Insufficient history ({len(df_15m)} bars < 50 bars required for warm-up).",
                    criteria={"bars_count": len(df_15m), "min_required": 50}
                )
                continue
            valid_symbols.append(sym)

            # Extract latest close & moving averages
            curr_bar = df_15m.iloc[-1]
            close_p = float(curr_bar["Close"])
            atr_val = float(curr_bar.get("ATR_14", close_p * 0.01))
            atr_pct = atr_val / close_p
            atr_pct_list.append(atr_pct)

            # 20-bar momentum
            past_close = float(df_15m.iloc[-min(20, len(df_15m))]["Close"])
            ret_20 = (close_p - past_close) / past_close
            if ret_20 > 0:
                positive_momentum_count += 1

            spec = get_symbol_spec(sym)
            if spec.sector not in sector_returns:
                sector_returns[spec.sector] = []
            sector_returns[spec.sector].append(ret_20)

        # Breadth calculation
        breadth_ratio = positive_momentum_count / max(1, len(valid_symbols))
        median_atr_pct = float(np.median(atr_pct_list)) if atr_pct_list else 0.01

        if breadth_ratio > 0.60:
            self.market_regime = "BULLISH_EXPANSION"
        elif breadth_ratio < 0.40:
            self.market_regime = "BEARISH_CONTRACTION"
        else:
            self.market_regime = "RANGE_BOUND_NEUTRAL"

        self.record_calculation(
            symbol="MARKET_BREADTH", task=task, stage="Macro Regime", progress_pct=35.0,
            formula="Breadth_Ratio = Positive_Momentum_Stocks / Total_Valid_Stocks",
            inputs={"positive_count": positive_momentum_count, "total_valid": len(valid_symbols)},
            result=round(breadth_ratio, 3),
            interpretation=f"Market Regime classified as {self.market_regime} with median ATR {median_atr_pct*100:.2f}%."
        )

        # Average sector returns
        self.sector_performance = {sec: round(float(np.mean(rets)) * 100.0, 2) for sec, rets in sector_returns.items()}

        # Stage 2: Individual Stock Liquidity & Volatility Screening
        self.update_progress(task=task, stage="Candidate Filtering", progress_pct=50.0, message="Screening candidate stocks against volume and volatility gates...")
        shortlist: List[str] = []

        for idx, sym in enumerate(valid_symbols):
            pct = 50.0 + (idx / len(valid_symbols)) * 40.0
            df_15m = universe_data[sym]
            spec = get_symbol_spec(sym)
            curr_bar = df_15m.iloc[-1]
            close_p = float(curr_bar["Close"])
            atr_val = float(curr_bar.get("ATR_14", close_p * 0.01))
            atr_pct = atr_val / close_p

            # Volume filter (20 SMA volume)
            avg_vol = float(df_15m["Volume"].tail(20).mean())
            turnover_inr = avg_vol * close_p

            self.record_calculation(
                symbol=sym, task=task, stage="Screening Filters", progress_pct=round(pct, 1),
                formula="Turnover_INR = 20_SMA_Volume * Close_Price",
                inputs={"20_SMA_Volume": int(avg_vol), "Close": close_p},
                result=round(turnover_inr, 2),
                interpretation=f"Daily turnover ₹{turnover_inr:,.0f}, ATR% = {atr_pct*100:.2f}%"
            )

            # Evaluation Gates
            rejection_reason = None
            if avg_vol < 5000:
                rejection_reason = f"Average volume ({avg_vol:.0f}) below institutional threshold (5,000 shares/15m)."
            elif atr_pct < self.min_atr_pct:
                rejection_reason = f"Volatility ATR% ({atr_pct*100:.2f}%) below minimum required ({self.min_atr_pct*100:.2f}%). Stock is excessively compressed."

            if rejection_reason:
                self.record_decision(
                    symbol=sym, task=task, stage="Screening Filters", progress_pct=round(pct, 1),
                    verdict="REJECTED", rationale=rejection_reason,
                    criteria={"avg_volume": avg_vol, "atr_pct": atr_pct, "min_atr_pct": self.min_atr_pct}
                )
            else:
                self.record_decision(
                    symbol=sym, task=task, stage="Screening Filters", progress_pct=round(pct, 1),
                    verdict="SELECTED",
                    rationale=f"Passed all liquidity and volatility gates. Sector: {spec.sector} ({self.sector_performance.get(spec.sector, 0.0)}% momentum).",
                    criteria={"avg_volume": avg_vol, "turnover_inr": turnover_inr, "atr_pct": atr_pct}
                )
                shortlist.append(sym)
                self.shortlisted_stocks_data[sym] = {
                    "symbol": sym,
                    "spec": spec,
                    "close": close_p,
                    "atr_14": atr_val,
                    "atr_pct": atr_pct,
                    "avg_volume": avg_vol,
                    "sector": spec.sector,
                    "sector_momentum": self.sector_performance.get(spec.sector, 0.0)
                }

        # Stage 3: Inter-Agent Handoff to Agent 2 (Support & Resistance Agent)
        self.update_progress(task=task, stage="Dispatch to Agent 2", progress_pct=95.0, message="Dispatching shortlisted candidates to Support & Resistance Agent...")
        handoff_payload = {
            "market_regime": self.market_regime,
            "breadth_ratio": breadth_ratio,
            "median_atr_pct": median_atr_pct,
            "sector_performance": self.sector_performance,
            "shortlisted_symbols": shortlist,
            "stocks_data": self.shortlisted_stocks_data
        }

        self.send_message(
            recipient_agent="AGENT_2_SUPPORT_RESISTANCE",
            message_type="CANDIDATE_SHORTLIST_AND_MARKET_REGIME",
            payload_summary=f"Transferred {len(shortlist)} screened stocks under {self.market_regime} market environment.",
            payload=handoff_payload,
            impact_on_recipient="Supplies Agent 2 with clean, high-volatility candidates and sets sector baseline for structural mapping."
        )

        self.complete_execution(
            task=task,
            summary=f"Identified {len(shortlist)} candidates from {self.total_scanned_count} stocks. Macro regime: {self.market_regime}."
        )

        return handoff_payload

    def generate_report(self) -> AgentReport:
        elapsed = round((self.end_perf_time - self.start_perf_time) * 1000.0, 2) if self.start_perf_time and self.end_perf_time else 0.0
        confidence = 0.90 if len(self.selected_stocks) > 0 else 0.50
        limitations = [
            "Market breadth is approximated from the ingested universe rather than the full 2000+ NSE equity list.",
            "Historical volume spikes on quarterly earnings dates can temporarily elevate average turnover metrics."
        ]
        return AgentReport(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            objective="Scan multi-cap universe, assess benchmark trend & sector momentum, and eliminate illiquid stocks.",
            timestamp=datetime.now(),
            input_data_summary=self.input_summary,
            methodology="20-bar momentum breadth ratio, 14-period ATR % volatility thresholding, and 20-period average volume gating.",
            calculations_performed=self.calculations,
            findings=[
                {"metric": "Market Regime", "value": self.market_regime},
                {"metric": "Sector Performance", "value": self.sector_performance},
                {"metric": "Shortlisted Count", "value": len(self.selected_stocks)}
            ],
            selected_stocks=self.selected_stocks,
            rejected_stocks=self.rejected_stocks,
            output_summary=f"Shortlisted {len(self.selected_stocks)} stocks passed to Support & Resistance Agent with full sector metrics.",
            output_payload={"shortlist": self.selected_stocks, "regime": self.market_regime},
            confidence_assessment=confidence,
            limitations_identified=limitations,
            execution_status="Completed" if self.selected_stocks else "No Candidates",
            processing_time_ms=elapsed,
            errors_and_warnings=self.warnings_and_errors
        )

"""
Multi-Agent Workflow Orchestrator.
Coordinates the end-to-end execution of the 5 Specialized AI Agents:
1. Market & Stock Scanning Agent
2. Support & Resistance Agent
3. Technical Analysis & Stock Selection Agent
4. Risk Management Agent
5. Decision & Validation Agent

Captures real-time transparency telemetry, inter-agent messages, structured reports,
and ensures strict non-fabricated execution and point-in-time reproducibility.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import time
import pandas as pd
from datetime import datetime

from src.agents.transparency_bus import TransparencyBus, AgentStatus, ActivityLogEntry, InterAgentMessage
from src.agents.base_agent import AgentReport
from src.agents.market_scanning_agent import MarketScanningAgent
from src.agents.support_resistance_agent import SupportResistanceAgent
from src.agents.technical_analysis_agent import TechnicalAnalysisAgent
from src.agents.risk_management_agent import RiskManagementAgent
from src.agents.decision_validation_agent import DecisionValidationAgent, FinalTradeRecommendation
from src.config.trading_config import MasterConfig

@dataclass
class MultiAgentExecutionResult:
    timestamp: datetime
    execution_verdict: str # "EXECUTE_TRADES" or "NO_TRADE"
    final_recommendations: List[FinalTradeRecommendation]
    total_execution_time_ms: float
    stocks_scanned_count: int
    qualified_count: int
    agent_reports: Dict[str, AgentReport]
    inter_agent_messages: List[InterAgentMessage]
    activity_logs: List[ActivityLogEntry]
    agent_states: Dict[str, Any]

class MultiAgentOrchestrator:
    """
    Central Coordinator for the 5-Agent Stock Trading System.
    """

    def __init__(
        self,
        config: Optional[MasterConfig] = None,
        initial_capital: float = 1000000.0,
        min_daily_volume: int = 100000,
        min_rr: float = 1.5,
        min_system_confidence: float = 0.65,
        max_recommendations: int = 5
    ):
        self.config = config or MasterConfig()
        self.initial_capital = initial_capital
        self.bus = TransparencyBus()

        # Instantiate all 5 Specialized AI Agents
        self.agent_1 = MarketScanningAgent(bus=self.bus, min_daily_volume=min_daily_volume)
        self.agent_2 = SupportResistanceAgent(bus=self.bus, config=self.config)
        min_tech_score = max(40.0, round(min_system_confidence * 90.0, 1))
        self.agent_3 = TechnicalAnalysisAgent(bus=self.bus, config=self.config, min_rr=min_rr, min_score=min_tech_score)
        self.agent_4 = RiskManagementAgent(bus=self.bus, initial_capital=initial_capital)
        self.agent_5 = DecisionValidationAgent(bus=self.bus, min_system_confidence=min_system_confidence, max_final_trades=max_recommendations)

        self.agents_dict = {
            self.agent_1.agent_id: self.agent_1,
            self.agent_2.agent_id: self.agent_2,
            self.agent_3.agent_id: self.agent_3,
            self.agent_4.agent_id: self.agent_4,
            self.agent_5.agent_id: self.agent_5
        }

    def execute_workflow(
        self,
        universe_data: Dict[str, pd.DataFrame],
        evaluation_timestamp: Optional[pd.Timestamp] = None,
        trade_mode: str = "DELIVERY",
        available_cash: Optional[float] = None
    ) -> MultiAgentExecutionResult:
        """
        Runs the full 5-agent pipeline sequentially with complete transparency and audit trail.
        """
        start_time = time.perf_counter()
        cash = available_cash or self.initial_capital

        # -------------------------------------------------------------
        # STEP 1: Execute Agent 1 (Market & Stock Scanning Agent)
        # -------------------------------------------------------------
        a1_output = self.agent_1.run({
            "universe_data": universe_data,
            "timestamp": evaluation_timestamp
        })

        # -------------------------------------------------------------
        # STEP 2: Execute Agent 2 (Support & Resistance Agent)
        # -------------------------------------------------------------
        a2_output = self.agent_2.run({
            "universe_data": universe_data,
            "agent_1_handoff": a1_output,
            "timestamp": evaluation_timestamp
        })

        # -------------------------------------------------------------
        # STEP 3: Execute Agent 3 (Technical Analysis Agent)
        # -------------------------------------------------------------
        a3_output = self.agent_3.run({
            "universe_data": universe_data,
            "agent_2_handoff": a2_output,
            "timestamp": evaluation_timestamp
        })

        # -------------------------------------------------------------
        # STEP 4: Execute Agent 4 (Risk Management Agent)
        # -------------------------------------------------------------
        a4_output = self.agent_4.run({
            "agent_3_handoff": a3_output,
            "available_cash": cash,
            "trade_mode": trade_mode
        })

        # -------------------------------------------------------------
        # STEP 5: Execute Agent 5 (Decision & Validation Agent)
        # -------------------------------------------------------------
        a5_output = self.agent_5.run({
            "agent_1_handoff": a1_output,
            "agent_2_handoff": a2_output,
            "agent_3_handoff": a3_output,
            "agent_4_handoff": a4_output
        })

        end_time = time.perf_counter()
        total_latency_ms = round((end_time - start_time) * 1000.0, 2)

        # Collect structured reports from all 5 agents
        agent_reports = {
            self.agent_1.agent_id: self.agent_1.generate_report(),
            self.agent_2.agent_id: self.agent_2.generate_report(),
            self.agent_3.agent_id: self.agent_3.generate_report(),
            self.agent_4.agent_id: self.agent_4.generate_report(),
            self.agent_5.agent_id: self.agent_5.generate_report()
        }

        final_recs = a5_output.get("final_recommendations", [])
        verdict = a5_output.get("execution_verdict", "NO_TRADE")

        return MultiAgentExecutionResult(
            timestamp=datetime.now(),
            execution_verdict=verdict,
            final_recommendations=final_recs,
            total_execution_time_ms=total_latency_ms,
            stocks_scanned_count=len(universe_data),
            qualified_count=len(final_recs),
            agent_reports=agent_reports,
            inter_agent_messages=self.bus.messages,
            activity_logs=self.bus.logs,
            agent_states=self.bus.agent_states
        )

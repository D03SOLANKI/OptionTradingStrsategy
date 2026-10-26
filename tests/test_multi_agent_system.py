"""
Comprehensive Unit & Integration Test Suite for the 5-Agent AI Stock Trading System.
Verifies cash cost calculations, transparency logging, inter-agent communication,
individual agent logic, risk sizing, and strict NO_TRADE enforcement.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, date

from src.cost.cash_cost_calculator import CashCostCalculator, CashTradeCostBreakdown
from src.agents.transparency_bus import TransparencyBus, AgentStatus
from src.agents.market_scanning_agent import MarketScanningAgent
from src.agents.support_resistance_agent import SupportResistanceAgent
from src.agents.technical_analysis_agent import TechnicalAnalysisAgent
from src.agents.risk_management_agent import RiskManagementAgent
from src.agents.decision_validation_agent import DecisionValidationAgent, FinalTradeRecommendation
from src.agents.orchestrator import MultiAgentOrchestrator

def test_cash_cost_calculator_delivery_and_intraday():
    calc = CashCostCalculator()

    # Test Case 1: Delivery Trade (100 shares of Reliance @ 2500 -> 2600)
    # Buy Turnover: 2,50,000 | Sell Turnover: 2,60,000
    res_delivery = calc.calculate_round_trip_cost(entry_price=2500.0, exit_price=2600.0, quantity=100, trade_mode="DELIVERY")
    assert res_delivery.brokerage == 0.0 # Free delivery
    assert res_delivery.stt == round((250000 + 260000) * 0.0010, 2) # 0.1% on buy + sell = 510 INR
    assert res_delivery.exchange_charges > 0
    assert res_delivery.stamp_duty == round(250000 * 0.00015, 2) # 0.015% on buy = 37.5 INR
    assert res_delivery.slippage_cost == round(0.05 * 2.0 * 100, 2) # 10 INR
    assert res_delivery.total_friction_cost > 550.0

    # Test Case 2: Intraday Trade (Brokerage applies, STT on sell only)
    res_intraday = calc.calculate_round_trip_cost(entry_price=2500.0, exit_price=2600.0, quantity=100, trade_mode="INTRADAY")
    assert res_intraday.brokerage == 40.0 # 20 buy + 20 sell
    assert res_intraday.stt == round(260000 * 0.00025, 2) # 0.025% on sell = 65 INR
    assert res_intraday.stamp_duty == round(250000 * 0.00003, 2) # 0.003% on buy = 7.5 INR

def test_transparency_bus_logging_and_messaging():
    bus = TransparencyBus()
    bus.register_agent("AGENT_TEST_1", "Test Agent 1")
    bus.register_agent("AGENT_TEST_2", "Test Agent 2")

    # Set status
    bus.set_agent_status("AGENT_TEST_1", AgentStatus.RUNNING, task="Testing", stage="Unit Testing", progress_pct=50.0)
    assert bus.agent_states["AGENT_TEST_1"].status == AgentStatus.RUNNING
    assert bus.agent_states["AGENT_TEST_1"].progress_pct == 50.0

    # Log entry
    log_entry = bus.log(
        agent_id="AGENT_TEST_1", task="Testing", stage="Unit Testing", progress_pct=50.0,
        log_type="CALCULATION", message="Sample math calculation", symbol="TCS",
        details={"formula": "2+2", "result": 4}
    )
    assert len(bus.logs) == 1
    assert bus.logs[0].details["result"] == 4

    # Inter-agent message
    msg = bus.record_message(
        sender_agent="AGENT_TEST_1", recipient_agent="AGENT_TEST_2",
        message_type="DATA_HANDOFF", payload_summary="Sample payload",
        payload={"stocks": ["TCS", "INFY"]}, impact_on_recipient="Provides candidates to Agent 2"
    )
    assert len(bus.messages) == 1
    assert msg.sender_agent == "AGENT_TEST_1"
    assert msg.recipient_agent == "AGENT_TEST_2"

    # Export JSON telemetry
    json_str = bus.export_telemetry_json()
    assert "AGENT_TEST_1" in json_str

def test_market_scanning_agent_screening():
    bus = TransparencyBus()
    agent = MarketScanningAgent(bus=bus)

    # Mock 15M dataframe
    timestamps = pd.date_range("2026-08-01 09:15", periods=60, freq="15min", tz="Asia/Kolkata")
    df_valid = pd.DataFrame({
        "Open": np.linspace(3400, 3500, 60),
        "High": np.linspace(3410, 3510, 60),
        "Low": np.linspace(3390, 3490, 60),
        "Close": np.linspace(3405, 3505, 60),
        "Volume": np.full(60, 25000),
        "ATR_14": np.full(60, 35.0)
    }, index=timestamps)

    df_illiquid = pd.DataFrame({
        "Open": np.full(60, 100.0), "High": np.full(60, 100.5), "Low": np.full(60, 99.5),
        "Close": np.full(60, 100.0), "Volume": np.full(60, 100), "ATR_14": np.full(60, 0.2)
    }, index=timestamps)

    handoff = agent.run({
        "universe_data": {"TCS": df_valid, "ILLIQUID_STOCK": df_illiquid}
    })

    assert "TCS" in handoff["shortlisted_symbols"]
    assert "ILLIQUID_STOCK" not in handoff["shortlisted_symbols"]
    assert handoff["market_regime"] in ["BULLISH_EXPANSION", "RANGE_BOUND_NEUTRAL", "BEARISH_CONTRACTION"]

    # Verify Agent 1 Report
    rep = agent.generate_report()
    assert rep.agent_id == "AGENT_1_MARKET_SCANNER"
    assert "TCS" in rep.selected_stocks
    assert "ILLIQUID_STOCK" in rep.rejected_stocks

def test_risk_management_agent_cash_sizing_and_targets():
    bus = TransparencyBus()
    agent = RiskManagementAgent(bus=bus, initial_capital=1000000.0, max_risk_per_trade_pct=0.015, max_capital_per_trade_pct=0.25)

    mock_technical_handoff = {
        "ranked_setups": [
            {
                "symbol": "TCS",
                "direction": "BUY",
                "spot_entry": 3500.0,
                "stop_loss": 3450.0, # 50 INR risk per share
                "opposing_target": 3650.0, # 150 INR reward per share (3:1 R:R)
                "risk_per_share": 50.0,
                "reward_per_share": 150.0,
                "rr_ratio": 3.0,
                "pattern_name": "HAMMER",
                "volume_ratio": 1.5,
                "rsi_value": 42.0,
                "composite_score": 78.0
            }
        ]
    }

    handoff = agent.run({
        "agent_3_handoff": mock_technical_handoff,
        "available_cash": 1000000.0,
        "trade_mode": "DELIVERY"
    })

    sized_plans = handoff["sized_risk_plans"]
    assert len(sized_plans) == 1
    plan = sized_plans[0]

    # Max risk is 1.5% of 10 Lakhs = 15,000 INR
    # Risk per share is 50 INR -> 15,000 / 50 = 300 shares by risk
    # Capital limit is 25% of 10 Lakhs = 2,50,000 INR -> 250000 / 3500 = 71 shares by capital
    # Minimum is 71 shares!
    assert plan["shares_quantity"] == 71
    assert plan["capital_required"] == round(71 * 3500.0, 2)
    assert plan["target_1_rr"] == round(3500.0 + (2.0 * 50.0), 2) # 3600 INR
    assert plan["target_2_macro"] == 3650.0
    assert plan["friction_cost_inr"] > 0
    assert "Breakeven Trigger" in plan["trailing_plan_desc"]

def test_decision_validation_agent_conflict_resolution_and_approval():
    bus = TransparencyBus()
    agent = DecisionValidationAgent(bus=bus, min_system_confidence=0.60)

    # Input with 1 high-quality setup
    valid_plan = {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services Ltd",
        "sector": "Information Technology",
        "cap_category": "LARGE_CAP",
        "direction": "BUY",
        "spot_entry": 3500.0,
        "stop_loss": 3450.0,
        "target_1_rr": 3600.0,
        "target_2_macro": 3650.0,
        "shares_quantity": 71,
        "capital_required": 248500.0,
        "actual_risk_inr": 3550.0,
        "risk_per_share": 50.0,
        "reward_per_share": 150.0,
        "rr_ratio": 3.0,
        "friction_cost_inr": 580.0,
        "trailing_plan_desc": "Breakeven at +1.5R",
        "technical_score": 82.0,
        "pattern_name": "HAMMER",
        "volume_ratio": 1.6,
        "rsi_value": 42.0
    }

    res = agent.run({
        "agent_1_handoff": {"market_regime": "BULLISH_EXPANSION", "sector_performance": {"Information Technology": 1.5}},
        "agent_2_handoff": {},
        "agent_3_handoff": {},
        "agent_4_handoff": {"sized_risk_plans": [valid_plan]}
    })

    assert res["execution_verdict"] == "EXECUTE_TRADES"
    assert len(res["final_recommendations"]) == 1
    rec: FinalTradeRecommendation = res["final_recommendations"][0]
    assert rec.symbol == "TCS"
    assert rec.verdict == "BUY"
    assert rec.shares_quantity == 71
    assert rec.system_confidence >= 0.70
    assert "Agent 1 (Market Scanner)" in rec.agent_contributions

def test_orchestrator_strict_no_trade_when_unconfirmed():
    """Verify that when market data does not confirm, the 5-agent system returns NO_TRADE."""
    orchestrator = MultiAgentOrchestrator()
    # Empty universe
    res = orchestrator.execute_workflow(universe_data={})
    assert res.execution_verdict == "NO_TRADE"
    assert len(res.final_recommendations) == 0
    assert len(res.agent_reports) == 5

"""
Unit Tests for Indian Equity Options Cost Calculator and Tax Schedules.
"""

import pytest
from src.risk.cost_calculator import CostCalculator
from src.config.trading_config import RiskConfig

def test_indian_options_cost_breakdown():
    """
    Verifies that all components of the Indian regulatory fee schedule are calculated correctly.
    """
    config = RiskConfig(
        brokerage_per_order=20.0,
        stt_sell_rate=0.0010,       # 0.1% on sell turnover
        exchange_turnover_rate=0.0005, # 0.05%
        gst_rate=0.18,              # 18%
        sebi_turnover_rate=0.000001,# 10 per crore
        stamp_duty_buy_rate=0.00003,# 0.003%
        slippage_ticks=2.0          # 2 ticks = 0.10 INR per share
    )
    calculator = CostCalculator(config)

    entry_price = 100.0
    exit_price = 120.0
    quantity = 250 # 1 lot of RELIANCE

    costs = calculator.calculate_round_trip_cost(entry_price, exit_price, quantity)

    # Buy turnover = 100 * 250 = 25,000
    # Sell turnover = 120 * 250 = 30,000
    # Total turnover = 55,000
    assert costs.buy_turnover == 25000.0
    assert costs.sell_turnover == 30000.0
    assert costs.total_turnover == 55000.0

    # Brokerage: 2 orders * 20 = 40.0
    assert costs.brokerage == 40.0

    # STT: 0.1% on sell turnover (30,000 * 0.0010 = 30.0)
    assert costs.stt == 30.0

    # Exchange charges: 55,000 * 0.0005 = 27.5
    assert costs.exchange_charges == 27.5

    # GST: 18% of (40.0 + 27.5) = 18% of 67.5 = 12.15
    assert costs.gst == 12.15

    # Stamp duty: 0.003% on buy turnover = 25,000 * 0.00003 = 0.75
    assert costs.stamp_duty == 0.75

    # Slippage: 2 * 0.05 = 0.10 per share round-trip * 2 = 0.20 * 250 = 50.0
    assert costs.slippage_cost == 50.0

    # Total friction must exceed 0 and equal the sum
    expected_total = round(40.0 + 30.0 + 27.5 + 12.15 + 0.06 + 0.75 + 50.0, 2)
    assert abs(costs.total_friction_cost - expected_total) < 0.50

"""
Cost Calculator: Institutional Indian Equity Options Cost, Taxes, and Slippage Model.
Accurately implements Zerodha/NSE fee structures:
Brokerage, STT, Exchange Turnover Fees, GST, SEBI Charges, Stamp Duty, and Slippage.
"""

from dataclasses import dataclass
from typing import Dict, Any

from src.config.trading_config import RiskConfig
from src.config.constants import TICK_SIZE

@dataclass
class TradeCostBreakdown:
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    brokerage: float
    stt: float
    exchange_charges: float
    gst: float
    sebi_charges: float
    stamp_duty: float
    slippage_cost: float
    total_friction_cost: float

class CostCalculator:
    """
    Computes exact regulatory costs and market friction for Indian options trading.
    """

    def __init__(self, config: RiskConfig):
        self.config = config

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        is_averaging_entry: bool = False
    ) -> TradeCostBreakdown:
        """
        Calculates all round-trip fees for entering and exiting an option position.
        turnover = option_premium * quantity
        """
        buy_turnover = entry_price * quantity
        sell_turnover = exit_price * quantity
        total_turnover = buy_turnover + sell_turnover

        # 1. Brokerage: ₹20 per order (1 buy order, 1 sell order = 2 orders, or 3 if averaged)
        num_orders = 3 if is_averaging_entry else 2
        brokerage = self.config.brokerage_per_order * num_orders

        # 2. STT: 0.1% on sell side option premium turnover
        stt = sell_turnover * self.config.stt_sell_rate

        # 3. Exchange Turnover Charges: 0.05% on total premium turnover
        exchange_charges = total_turnover * self.config.exchange_turnover_rate

        # 4. GST: 18% on (Brokerage + Exchange Charges)
        gst = (brokerage + exchange_charges) * self.config.gst_rate

        # 5. SEBI Turnover Charges: ₹10 per crore (0.0001% of turnover)
        sebi_charges = total_turnover * self.config.sebi_turnover_rate

        # 6. Stamp Duty: 0.003% on buy side turnover
        stamp_duty = buy_turnover * self.config.stamp_duty_buy_rate

        # 7. Slippage Cost: price slippage per share (both entry and exit)
        slippage_per_share = self.config.slippage_ticks * TICK_SIZE
        slippage_cost = slippage_per_share * 2.0 * quantity

        # Total friction
        total_friction = (
            brokerage +
            stt +
            exchange_charges +
            gst +
            sebi_charges +
            stamp_duty +
            slippage_cost
        )

        return TradeCostBreakdown(
            buy_turnover=round(buy_turnover, 2),
            sell_turnover=round(sell_turnover, 2),
            total_turnover=round(total_turnover, 2),
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_charges=round(exchange_charges, 2),
            gst=round(gst, 2),
            sebi_charges=round(sebi_charges, 2),
            stamp_duty=round(stamp_duty, 2),
            slippage_cost=round(slippage_cost, 2),
            total_friction_cost=round(total_friction, 2)
        )

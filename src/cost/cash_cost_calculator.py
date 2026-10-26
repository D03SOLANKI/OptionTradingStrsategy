"""
Cash Equity Cost Calculator: Institutional Indian Cash Market (NSE) Fee and Friction Model.
Accurately implements Zerodha and NSE cash equity regulatory structures:
- Delivery (CNC): ₹0 Brokerage, 0.1% STT on Buy & Sell, Exchange Turnover Fees (0.00297%),
  GST (18% on fees), SEBI charges (₹10/crore), Stamp Duty (0.015% on buy), and 1-tick slippage.
- Intraday (MIS): ₹20/order or 0.03%, 0.025% STT on Sell, Exchange Turnover (0.00297%),
  GST (18%), SEBI charges, Stamp Duty (0.003% on buy), and 1-tick slippage.
"""

from dataclasses import dataclass
from typing import Literal

TICK_SIZE_EQUITY = 0.05 # 5 paise standard NSE equity tick size

@dataclass
class CashTradeCostBreakdown:
    trade_mode: Literal["DELIVERY", "INTRADAY"]
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

class CashCostCalculator:
    """
    Computes exact regulatory costs, exchange fees, and market friction for Indian cash equity trades.
    """

    def __init__(
        self,
        brokerage_per_order_intraday: float = 20.0,
        stt_delivery_rate: float = 0.0010,     # 0.1% on buy and sell
        stt_intraday_sell_rate: float = 0.00025, # 0.025% on sell only
        exchange_turnover_rate: float = 0.0000297, # 0.00297% NSE equity turnover charge
        gst_rate: float = 0.18,                 # 18% GST on (Brokerage + Exchange fees)
        sebi_turnover_rate: float = 0.000001,   # ₹10 per crore (0.0001%)
        stamp_duty_delivery_rate: float = 0.00015, # 0.015% on buy turnover
        stamp_duty_intraday_rate: float = 0.00003, # 0.003% on buy turnover
        slippage_ticks: float = 1.0             # 1 tick slippage per side (0.05 INR)
    ):
        self.brokerage_per_order_intraday = brokerage_per_order_intraday
        self.stt_delivery_rate = stt_delivery_rate
        self.stt_intraday_sell_rate = stt_intraday_sell_rate
        self.exchange_turnover_rate = exchange_turnover_rate
        self.gst_rate = gst_rate
        self.sebi_turnover_rate = sebi_turnover_rate
        self.stamp_duty_delivery_rate = stamp_duty_delivery_rate
        self.stamp_duty_intraday_rate = stamp_duty_intraday_rate
        self.slippage_ticks = slippage_ticks

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        trade_mode: Literal["DELIVERY", "INTRADAY"] = "DELIVERY"
    ) -> CashTradeCostBreakdown:
        """
        Calculates all round-trip fees for entering and exiting a cash equity stock trade.
        """
        buy_turnover = entry_price * quantity
        sell_turnover = exit_price * quantity
        total_turnover = buy_turnover + sell_turnover

        # 1. Brokerage
        if trade_mode == "DELIVERY":
            brokerage = 0.0 # Free delivery on discount brokers (Zerodha/Groww/Angel)
        else:
            # Intraday: min(0.03%, ₹20) per executed order
            buy_brokerage = min(self.brokerage_per_order_intraday, buy_turnover * 0.0003)
            sell_brokerage = min(self.brokerage_per_order_intraday, sell_turnover * 0.0003)
            brokerage = round(buy_brokerage + sell_brokerage, 2)

        # 2. STT (Securities Transaction Tax)
        if trade_mode == "DELIVERY":
            stt = round((buy_turnover + sell_turnover) * self.stt_delivery_rate, 2)
        else:
            stt = round(sell_turnover * self.stt_intraday_sell_rate, 2)

        # 3. Exchange Turnover Charges (NSE)
        exchange_charges = round(total_turnover * self.exchange_turnover_rate, 2)

        # 4. GST: 18% on (Brokerage + Exchange Charges)
        gst = round((brokerage + exchange_charges) * self.gst_rate, 2)

        # 5. SEBI Turnover Charges: ₹10 per crore
        sebi_charges = round(total_turnover * self.sebi_turnover_rate, 2)

        # 6. Stamp Duty (Buy side only)
        stamp_rate = self.stamp_duty_delivery_rate if trade_mode == "DELIVERY" else self.stamp_duty_intraday_rate
        stamp_duty = round(buy_turnover * stamp_rate, 2)

        # 7. Slippage Cost: price slippage per share (1 tick entry + 1 tick exit)
        slippage_per_share = self.slippage_ticks * TICK_SIZE_EQUITY
        slippage_cost = round(slippage_per_share * 2.0 * quantity, 2)

        # Total friction
        total_friction = round(
            brokerage +
            stt +
            exchange_charges +
            gst +
            sebi_charges +
            stamp_duty +
            slippage_cost,
            2
        )

        return CashTradeCostBreakdown(
            trade_mode=trade_mode,
            buy_turnover=round(buy_turnover, 2),
            sell_turnover=round(sell_turnover, 2),
            total_turnover=round(total_turnover, 2),
            brokerage=brokerage,
            stt=stt,
            exchange_charges=exchange_charges,
            gst=gst,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            slippage_cost=slippage_cost,
            total_friction_cost=total_friction
        )

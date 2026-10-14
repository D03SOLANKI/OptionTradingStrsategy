"""
Constants and Market Specifications for Indian Equities and Options (NSE).
All timestamps, trading sessions, lot sizes, and taxation schedules are strictly aligned with NSE rules.
"""

from typing import Final, Dict, Any

# Indian Standard Time (IST) Timezone
MARKET_TIMEZONE: Final[str] = "Asia/Kolkata"

# NSE Equity & F&O Trading Session
MARKET_OPEN_TIME: Final[str] = "09:15:00"
MARKET_CLOSE_TIME: Final[str] = "15:30:00"
INTRADAY_SQUAREOFF_TIME: Final[str] = "15:15:00"

# Timeframe specifications (in minutes)
TF_15M_MINUTES: Final[int] = 15
TF_4H_MINUTES: Final[int] = 240

# Trading session duration: 09:15 to 15:30 = 375 minutes
# In 15M candles: exactly 25 candles per trading day
CANDLES_PER_DAY_15M: Final[int] = 25

# Standard Tick Size for NSE Options and Equities
TICK_SIZE: Final[float] = 0.05

# Indian Taxation and Brokerage Structure for Equity Options (NSE)
# Reflects updated SEBI/STT rates for discount brokers (Zerodha / Upstox / AngelOne)
DEFAULT_COST_STRUCTURE: Final[Dict[str, float]] = {
    # Brokerage per executed order in INR (flat)
    "brokerage_per_order": 20.0,
    # Securities Transaction Tax (STT): 0.1% on sell side option premium
    "stt_sell_rate": 0.0010,
    # Exchange Transaction Charges (NSE Options): 0.05% of turnover (premium turnover)
    "exchange_turnover_rate": 0.0005,
    # GST on Brokerage + Exchange Transaction Charges: 18%
    "gst_rate": 0.18,
    # SEBI Turnover Charges: INR 10 per crore (0.0001%)
    "sebi_turnover_rate": 0.000001,
    # Stamp Duty: 0.003% on buy side turnover (options premium)
    "stamp_duty_buy_rate": 0.00003,
    # Default estimated slippage in ticks (1 tick = 0.05 INR)
    "default_slippage_ticks": 2.0,
}

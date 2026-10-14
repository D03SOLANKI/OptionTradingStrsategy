"""
Configuration Dataclasses for Multi-Timeframe S/R Options Trading Strategy.
Contains all configurable hyperparameters, risk limits, and backtest configurations.
"""

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional, Dict, Any
import json

@dataclass
class TimeframeConfig:
    tf_major_minutes: int = 240       # 4-Hour timeframe
    tf_entry_minutes: int = 15        # 15-Minute timeframe
    candles_per_day_15m: int = 25     # NSE 09:15-15:30 = 25 candles
    warmup_bars_4h: int = 50          # Minimum 4H bars before generating signals
    warmup_bars_15m: int = 100        # Minimum 15M bars for indicators

@dataclass
class SRConfig:
    # 4H Market Structure & S/R Parameters
    pivot_order_4h: int = 3           # Bars on each side required for 4H swing pivot confirmation
    zone_tolerance_pct_4h: float = 0.008  # 0.8% zone thickness around 4H price level
    touch_decay_half_life_days: float = 30.0 # Half-life in days for recency scoring
    min_touches_for_strong_level: int = 2    # Retests required for solid S/R level
    rejection_wick_ratio_threshold: float = 0.35 # Wick size / candle range ratio for rejection
    volume_surge_multiplier: float = 1.25    # Volume vs SMA(20) to qualify as high-volume reaction
    min_level_strength_score: float = 0.40   # Minimum normalized score [0, 1] to qualify as active zone
    max_active_zones: int = 8                # Max active zones to track per side

    # 15M Entry S/R Parameters
    pivot_order_15m: int = 2          # Bars on each side for 15M micro swing confirmation
    zone_tolerance_pct_15m: float = 0.004 # 0.4% zone thickness for 15M level
    confluence_distance_pct: float = 0.006 # Max distance between 4H and 15M level to declare confluence
    confluence_weight_4h: float = 0.65     # Weight of 4H strength in confluence
    confluence_weight_15m: float = 0.35    # Weight of 15M strength in confluence
    min_confluence_score: float = 0.50     # Cutoff score for qualifying confluence zone

@dataclass
class ConfirmationConfig:
    # 15M Candlestick & Indicator Confirmation
    enable_candlestick_patterns: bool = True
    enable_volume_confirmation: bool = True
    enable_momentum_filter: bool = True
    rsi_period: int = 14
    rsi_oversold_threshold: float = 38.0   # RSI cutoff for bullish reversal
    rsi_overbought_threshold: float = 62.0  # RSI cutoff for bearish reversal
    volume_ma_period: int = 20
    min_volume_ratio: float = 1.10         # Entry candle volume vs 20 SMA
    atr_period: int = 14
    trend_ema_period: int = 50             # 15M EMA for micro-trend context

@dataclass
class OptionConfig:
    # Strike & Expiry Selection
    strike_selection_mode: Literal["ATM", "ITM1", "OTM1", "DELTA_TARGET"] = "ATM"
    target_delta: float = 0.50             # Target absolute delta if DELTA_TARGET is selected
    min_days_to_expiry: int = 2            # Avoid entering positions with < 2 DTE (terminal theta)
    max_days_to_expiry: int = 35           # Max DTE to avoid low delta response
    prefer_monthly_expiry: bool = True
    max_bid_ask_spread_pct: float = 0.035  # Max allowable spread as % of premium (3.5%)
    min_contract_volume: int = 50          # Minimum daily contract volume for liquidity
    risk_free_rate: float = 0.065          # 6.5% Indian 91-day T-Bill rate approximation
    dividend_yield: float = 0.012          # 1.2% approximate dividend yield

@dataclass
class TrailingStopConfig:
    # Initial Stop & Dynamic Trailing Protection
    initial_stop_atr_multiplier: float = 1.5   # Stop distance based on 15M ATR below support/above resistance
    initial_stop_premium_pct: float = 0.30      # Max hard stop on option premium (-30%)
    activation_profit_pct: float = 0.18         # Trailing kicks in once premium gains +18%
    trailing_method: Literal["PERCENTAGE_RATCHET", "ATR_CHANDELIER", "STRUCTURE_SWING"] = "PERCENTAGE_RATCHET"
    trailing_distance_pct: float = 0.12         # Trail 12% behind peak premium
    trailing_atr_multiplier: float = 2.0        # ATR multiplier if ATR chandelier is used
    enable_partial_profit: bool = True          # Book partial profits
    partial_profit_ratio: float = 0.50          # Close 50% of position at target
    partial_profit_trigger_rr: float = 2.0      # Target at 1:2 Risk-Reward ratio
    eod_squareoff_time: str = "15:15:00"        # Square off intraday positions before market close if intraday

@dataclass
class AveragingConfig:
    # Intelligent Position Averaging
    enable_averaging: bool = True               # Master switch for averaging
    max_averaging_entries: int = 1              # Maximum additional entries allowed (total 2 entries max)
    min_distance_atr: float = 1.25              # Minimum distance in 15M ATR between entries
    size_multiplier: float = 1.0                # Sizing of second entry relative to initial (1.0 = equal size)
    max_thesis_invalidation_buffer_atr: float = 0.75 # Stop & deny averaging if underlying penetrates S/R by > 0.75 ATR
    require_new_15m_reversal: bool = True       # Must see a fresh 15M reversal signal to trigger average
    max_combined_risk_pct: float = 0.025        # Total loss across all entries cannot exceed 2.5% portfolio

@dataclass
class RiskConfig:
    initial_capital: float = 500000.0           # ₹5,00,000 standard starting account size
    max_capital_per_trade_pct: float = 0.08     # Max 8% of portfolio deployed in a single trade premium
    max_risk_per_trade_pct: float = 0.015       # Max 1.5% portfolio equity risked per trade
    max_daily_loss_pct: float = 0.035           # Daily loss circuit breaker (-3.5% halts trading)
    max_simultaneous_positions: int = 3         # Maximum open trades simultaneously
    max_sector_concentration: int = 2           # Maximum positions in the same sector
    max_consecutive_losses_circuit: int = 4     # Pause trading for 2 days after 4 consecutive losses
    pause_duration_days: int = 2
    slippage_ticks: float = 2.0                 # Estimated slippage in ticks (0.05 * 2 = 0.10 INR)
    brokerage_per_order: float = 20.0           # ₹20 flat brokerage per order
    stt_sell_rate: float = 0.0010               # 0.1% STT on sell side premium
    exchange_turnover_rate: float = 0.0005      # 0.05% exchange fee
    gst_rate: float = 0.18                      # 18% GST
    sebi_turnover_rate: float = 0.000001        # ₹10 per crore
    stamp_duty_buy_rate: float = 0.00003        # 0.003% stamp duty on buy side

@dataclass
class BacktestConfig:
    start_date: str = "2024-01-01"
    end_date: str = "2026-10-14"
    train_ratio: float = 0.60                   # 60% Chronological In-Sample Train
    val_ratio: float = 0.20                     # 20% Chronological Validation
    test_ratio: float = 0.20                    # 20% Untouched Out-of-Sample Test
    wfa_train_months: int = 6                   # Walk-Forward Analysis train window
    wfa_test_months: int = 2                    # Walk-Forward Analysis test window
    purge_days: int = 3                         # Purging period between folds to eliminate leakage
    embargo_days: int = 2                       # Embargo period after test fold
    monte_carlo_simulations: int = 1500         # Number of bootstrap paths for robustness analysis

@dataclass
class MasterConfig:
    timeframe: TimeframeConfig = field(default_factory=TimeframeConfig)
    sr: SRConfig = field(default_factory=SRConfig)
    confirmation: ConfirmationConfig = field(default_factory=ConfirmationConfig)
    option: OptionConfig = field(default_factory=OptionConfig)
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)
    averaging: AveragingConfig = field(default_factory=AveragingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MasterConfig":
        return cls(
            timeframe=TimeframeConfig(**data.get("timeframe", {})),
            sr=SRConfig(**data.get("sr", {})),
            confirmation=ConfirmationConfig(**data.get("confirmation", {})),
            option=OptionConfig(**data.get("option", {})),
            trailing_stop=TrailingStopConfig(**data.get("trailing_stop", {})),
            averaging=AveragingConfig(**data.get("averaging", {})),
            risk=RiskConfig(**data.get("risk", {})),
            backtest=BacktestConfig(**data.get("backtest", {})),
        )

"""
Option Position Data Structure and Lifecycle Tracker.
Tracks entries, intelligent averaging tranches, weighted average prices,
MFE (Maximum Favorable Excursion), MAE (Maximum Adverse Excursion), Greeks, and exits.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
import pandas as pd

from src.options.strike_selector import OptionContract
from src.strategy.trailing_stop_manager import TrailingState
from src.indicators.support_resistance_15m import ConfluenceZone
from src.risk.cost_calculator import TradeCostBreakdown

@dataclass
class AveragingTranche:
    timestamp: pd.Timestamp
    underlying_price: float
    option_price: float
    quantity: int

@dataclass
class OptionPosition:
    position_id: str
    symbol: str
    contract: OptionContract
    option_type: Literal["CE", "PE"]
    entry_time: pd.Timestamp
    initial_underlying_price: float
    initial_entry_price: float
    initial_quantity: int
    current_quantity: int
    weighted_avg_entry_price: float
    initial_stop_loss: float
    current_stop_loss: float
    confluence_zone: Optional[ConfluenceZone]
    trailing_state: TrailingState

    # Tranches tracking
    tranches: List[AveragingTranche] = field(default_factory=list)
    averaging_count: int = 0
    is_averaged: bool = False

    # Intrabar tracking & Excursions
    peak_premium: float = 0.0
    trough_premium: float = 999999.0
    max_adverse_excursion: float = 0.0      # Max unrealized loss (₹)
    max_favorable_excursion: float = 0.0    # Max unrealized gain (₹)

    # Exit tracking
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    costs: Optional[TradeCostBreakdown] = None
    is_closed: bool = False

    def __post_init__(self):
        if not self.tranches:
            self.tranches.append(AveragingTranche(
                timestamp=self.entry_time,
                underlying_price=self.initial_underlying_price,
                option_price=self.initial_entry_price,
                quantity=self.initial_quantity
            ))
        self.peak_premium = self.initial_entry_price
        self.trough_premium = self.initial_entry_price

    def add_averaging_entry(
        self,
        timestamp: pd.Timestamp,
        underlying_price: float,
        option_price: float,
        quantity: int,
        new_weighted_avg: float,
        new_stop_loss: float
    ):
        """
        Executes an intelligent averaging tranche on this position.
        """
        self.tranches.append(AveragingTranche(
            timestamp=timestamp,
            underlying_price=underlying_price,
            option_price=option_price,
            quantity=quantity
        ))
        self.averaging_count += 1
        self.is_averaged = True
        self.current_quantity += quantity
        self.weighted_avg_entry_price = new_weighted_avg
        self.current_stop_loss = new_stop_loss
        self.trailing_state.current_stop_loss = new_stop_loss

    def mark_to_market(self, current_option_price: float):
        """
        Updates unrealized PnL, peak/trough premiums, and MFE/MAE.
        """
        if current_option_price > self.peak_premium:
            self.peak_premium = current_option_price
        if current_option_price < self.trough_premium:
            self.trough_premium = current_option_price

        # Unrealized PnL vs weighted average
        unrealized = (current_option_price - self.weighted_avg_entry_price) * self.current_quantity
        if unrealized > self.max_favorable_excursion:
            self.max_favorable_excursion = unrealized
        if unrealized < -self.max_adverse_excursion:
            self.max_adverse_excursion = abs(unrealized)

    def close_position(
        self,
        exit_time: pd.Timestamp,
        exit_price: float,
        exit_reason: str,
        costs: TradeCostBreakdown
    ):
        """
        Closes position and locks in final gross and net PnL.
        """
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.costs = costs
        self.is_closed = True

        total_buy_cost = sum(t.option_price * t.quantity for t in self.tranches)
        total_sell_proceeds = exit_price * self.current_quantity

        self.gross_pnl = round(total_sell_proceeds - total_buy_cost, 2)
        self.net_pnl = round(self.gross_pnl - costs.total_friction_cost, 2)

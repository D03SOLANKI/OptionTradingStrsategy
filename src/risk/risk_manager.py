"""
Comprehensive Risk Management Engine.
Enforces capital limits, position sizing based on risk per trade,
daily drawdown circuit breakers, consecutive loss cooling periods,
and portfolio/sector concentration limits.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Set

from src.config.trading_config import RiskConfig
from src.config.nse_symbols import get_symbol_spec

@dataclass
class PositionSizingResult:
    allowed: bool
    num_lots: int
    total_quantity: int
    total_capital_required: float
    total_risk_amount: float
    rejection_reason: Optional[str] = None

class RiskManager:
    """
    Portfolio Risk Engine for Indian Stock Options.
    """

    def __init__(self, config: RiskConfig):
        self.config = config
        self.current_equity = config.initial_capital
        self.daily_start_equity = config.initial_capital
        self.current_trade_date: Optional[date] = None

        self.consecutive_losses: int = 0
        self.is_paused: bool = False
        self.pause_until_date: Optional[date] = None

        # Daily tracking
        self.daily_realized_pnl: float = 0.0
        self.active_positions_count: int = 0
        self.active_sectors: Dict[str, int] = {}

    def on_new_day(self, current_date: date):
        """
        Resets daily circuit breakers and updates daily starting equity.
        """
        if self.current_trade_date != current_date:
            self.current_trade_date = current_date
            self.daily_start_equity = self.current_equity
            self.daily_realized_pnl = 0.0

            # Check if pause period expired
            if self.is_paused and self.pause_until_date is not None:
                if current_date >= self.pause_until_date:
                    self.is_paused = False
                    self.pause_until_date = None

    def can_open_position(
        self,
        symbol: str,
        current_date: date,
        option_price: float,
        stop_loss_price: float,
        lot_size: int
    ) -> PositionSizingResult:
        """
        Validates risk constraints and sizes position using maximum acceptable loss
        and capital allocation limits.
        """
        self.on_new_day(current_date)

        # 1. Circuit Breaker: Consecutive Loss Pause
        if self.is_paused:
            return PositionSizingResult(
                allowed=False, num_lots=0, total_quantity=0,
                total_capital_required=0.0, total_risk_amount=0.0,
                rejection_reason=f"Risk paused due to {self.consecutive_losses} consecutive losses."
            )

        # 2. Circuit Breaker: Daily Drawdown Limit
        daily_loss_pct = self.daily_realized_pnl / self.daily_start_equity
        if daily_loss_pct <= -self.config.max_daily_loss_pct:
            return PositionSizingResult(
                allowed=False, num_lots=0, total_quantity=0,
                total_capital_required=0.0, total_risk_amount=0.0,
                rejection_reason=f"Daily loss circuit breaker hit: {daily_loss_pct*100:.2f}%."
            )

        # 3. Limit: Simultaneous Open Positions
        if self.active_positions_count >= self.config.max_simultaneous_positions:
            return PositionSizingResult(
                allowed=False, num_lots=0, total_quantity=0,
                total_capital_required=0.0, total_risk_amount=0.0,
                rejection_reason=f"Max simultaneous positions reached: {self.config.max_simultaneous_positions}."
            )

        # 4. Limit: Sector Concentration
        spec = get_symbol_spec(symbol)
        current_sector_count = self.active_sectors.get(spec.sector, 0)
        if current_sector_count >= self.config.max_sector_concentration:
            return PositionSizingResult(
                allowed=False, num_lots=0, total_quantity=0,
                total_capital_required=0.0, total_risk_amount=0.0,
                rejection_reason=f"Max sector concentration reached for {spec.sector}."
            )

        # 5. Position Sizing
        # Max capital to deploy in this trade premium
        max_capital_for_trade = self.current_equity * self.config.max_capital_per_trade_pct
        # Max risk amount willing to lose in this trade
        max_risk_for_trade = self.current_equity * self.config.max_risk_per_trade_pct

        risk_per_share = max(0.05, option_price - stop_loss_price)
        cost_per_lot = option_price * lot_size
        risk_per_lot = risk_per_share * lot_size

        if cost_per_lot <= 0 or risk_per_lot <= 0:
            return PositionSizingResult(
                allowed=False, num_lots=0, total_quantity=0,
                total_capital_required=0.0, total_risk_amount=0.0,
                rejection_reason="Invalid cost or risk per lot."
            )

        lots_by_capital = int(max_capital_for_trade // cost_per_lot)
        lots_by_risk = int(max_risk_for_trade // risk_per_lot)
        num_lots = min(lots_by_capital, lots_by_risk)

        if num_lots < 1:
            # If 1 lot exceeds max risk by less than 20% and capital permits, allow 1 lot
            if cost_per_lot <= max_capital_for_trade and risk_per_lot <= max_risk_for_trade * 1.25:
                num_lots = 1
            else:
                return PositionSizingResult(
                    allowed=False, num_lots=0, total_quantity=0,
                    total_capital_required=cost_per_lot, total_risk_amount=risk_per_lot,
                    rejection_reason=f"Position size exceeds risk or capital limits (1 lot requires ₹{cost_per_lot:.0f}, risk ₹{risk_per_lot:.0f})."
                )

        total_quantity = num_lots * lot_size
        total_capital = total_quantity * option_price
        total_risk = total_quantity * risk_per_share

        return PositionSizingResult(
            allowed=True,
            num_lots=num_lots,
            total_quantity=total_quantity,
            total_capital_required=round(total_capital, 2),
            total_risk_amount=round(total_risk, 2)
        )

    def on_trade_opened(self, symbol: str):
        self.active_positions_count += 1
        spec = get_symbol_spec(symbol)
        self.active_sectors[spec.sector] = self.active_sectors.get(spec.sector, 0) + 1

    def on_trade_closed(self, symbol: str, net_pnl: float, exit_date: date):
        self.active_positions_count = max(0, self.active_positions_count - 1)
        spec = get_symbol_spec(symbol)
        if spec.sector in self.active_sectors:
            self.active_sectors[spec.sector] = max(0, self.active_sectors[spec.sector] - 1)

        self.current_equity += net_pnl
        self.daily_realized_pnl += net_pnl

        # Track consecutive losses
        if net_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.config.max_consecutive_losses_circuit:
                self.is_paused = True
                from datetime import timedelta
                self.pause_until_date = exit_date + timedelta(days=self.config.pause_duration_days)
        else:
            self.consecutive_losses = 0

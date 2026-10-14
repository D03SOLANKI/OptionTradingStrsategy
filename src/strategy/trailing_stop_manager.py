"""
Dynamic Profit Protection and Trailing Stop-Loss Manager.
Guarantees monotonic stop tightening (never loosens), implements profit activation thresholds,
percentage ratchet, ATR chandelier, and partial profit-taking mechanics.
"""

from dataclasses import dataclass
from typing import Optional, Literal
import math

from src.config.trading_config import TrailingStopConfig

@dataclass
class TrailingState:
    is_activated: bool
    current_stop_loss: float
    peak_premium_reached: float
    initial_risk_per_share: float
    partial_profit_taken: bool
    breakeven_reached: bool
    exit_triggered: bool
    exit_reason: Optional[str]

class TrailingStopManager:
    """
    Manages initial stop-loss, dynamic profit activation, and ratcheting trailing stops.
    """

    def __init__(self, config: TrailingStopConfig):
        self.config = config

    def initialize_state(
        self,
        entry_price: float,
        initial_stop_loss: float
    ) -> TrailingState:
        """
        Initializes trailing state upon trade entry.
        """
        initial_risk = max(0.05, entry_price - initial_stop_loss)
        return TrailingState(
            is_activated=False,
            current_stop_loss=round(initial_stop_loss, 2),
            peak_premium_reached=entry_price,
            initial_risk_per_share=initial_risk,
            partial_profit_taken=False,
            breakeven_reached=False,
            exit_triggered=False,
            exit_reason=None
        )

    def update(
        self,
        state: TrailingState,
        current_option_price: float,
        underlying_spot: float,
        entry_price: float,
        option_atr: float = 1.0
    ) -> TrailingState:
        """
        Updates the trailing stop state based on the latest candle close / intrabar high.
        STRICT RULE: Stop loss is NEVER loosened. It can only stay constant or increase.
        """
        # 1. Update peak premium reached
        if current_option_price > state.peak_premium_reached:
            state.peak_premium_reached = current_option_price

        # Check if stop-loss was breached
        if current_option_price <= state.current_stop_loss:
            state.exit_triggered = True
            state.exit_reason = f"STOP_LOSS_HIT (Price {current_option_price:.2f} <= Stop {state.current_stop_loss:.2f})"
            return state

        # 2. Check Profit Activation Threshold
        profit_ratio = (current_option_price - entry_price) / entry_price
        if profit_ratio >= self.config.activation_profit_pct:
            state.is_activated = True

        # 3. Partial Profit Booking Check (at target R:R)
        if self.config.enable_partial_profit and not state.partial_profit_taken:
            current_r_multiple = (current_option_price - entry_price) / state.initial_risk_per_share
            if current_r_multiple >= self.config.partial_profit_trigger_rr:
                state.partial_profit_taken = True
                # Move stop to Breakeven (+ 1 tick) to guarantee risk-free runner
                be_stop = round(entry_price + 0.10, 2)
                if be_stop > state.current_stop_loss:
                    state.current_stop_loss = be_stop
                    state.breakeven_reached = True

        # 4. Compute Dynamic Trailing Stop
        if state.is_activated:
            new_stop = state.current_stop_loss

            if self.config.trailing_method == "PERCENTAGE_RATCHET":
                # Trail by trailing_distance_pct behind peak premium
                ratchet_stop = state.peak_premium_reached * (1.0 - self.config.trailing_distance_pct)
                new_stop = max(new_stop, ratchet_stop)

            elif self.config.trailing_method == "ATR_CHANDELIER":
                # Trail by trailing_atr_multiplier behind peak premium
                chandelier_stop = state.peak_premium_reached - (self.config.trailing_atr_multiplier * option_atr)
                new_stop = max(new_stop, chandelier_stop)

            # Enforce Monotonicity: Never loosen
            state.current_stop_loss = round(max(state.current_stop_loss, new_stop), 2)

        return state

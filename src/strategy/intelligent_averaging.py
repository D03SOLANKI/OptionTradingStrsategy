"""
Intelligent Position Averaging Engine.
Reassesses underlying 4H and 15M support/resistance structure before any additional entry.
Strictly forbids averaging if the zone has been invalidated, requires a fresh 15M reversal confirmation,
and recalculates weighted-average entry price, breakeven, and combined risk.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Literal
import pandas as pd

from src.config.trading_config import AveragingConfig
from src.indicators.support_resistance_4h import SRZone, MarketStructureState
from src.indicators.support_resistance_15m import ConfluenceZone
from src.indicators.reversal_confirmation import ReversalSignal

@dataclass
class AveragingDecision:
    allow_average: bool
    rejection_reason: Optional[str]
    additional_quantity: int
    additional_price: float
    new_weighted_avg_price: float
    new_total_quantity: int
    new_stop_loss_price: float
    new_breakeven_price: float

class IntelligentAveragingEngine:
    """
    Evaluates whether an additional averaging entry is structurally justified.
    """

    def __init__(self, config: AveragingConfig):
        self.config = config

    def evaluate_averaging(
        self,
        symbol: str,
        option_type: Literal["CE", "PE"],
        current_underlying_spot: float,
        current_option_price: float,
        initial_underlying_entry_price: float,
        initial_option_entry_price: float,
        initial_quantity: int,
        current_averaging_count: int,
        confluence_zone: Optional[ConfluenceZone],
        market_structure: MarketStructureState,
        reversal_signal: ReversalSignal,
        atr_15m: float,
        lot_size: int
    ) -> AveragingDecision:
        """
        Determines whether to execute an intelligent averaging entry.
        """
        if not self.config.enable_averaging:
            return AveragingDecision(
                allow_average=False, rejection_reason="Averaging disabled in configuration.",
                additional_quantity=0, additional_price=0.0,
                new_weighted_avg_price=initial_option_entry_price,
                new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                new_breakeven_price=initial_option_entry_price
            )

        # 1. Limit on max averaging entries
        if current_averaging_count >= self.config.max_averaging_entries:
            return AveragingDecision(
                allow_average=False, rejection_reason=f"Max averaging entries reached ({self.config.max_averaging_entries}).",
                additional_quantity=0, additional_price=0.0,
                new_weighted_avg_price=initial_option_entry_price,
                new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                new_breakeven_price=initial_option_entry_price
            )

        # 2. Minimum distance in underlying ATR from initial entry
        price_diff = abs(current_underlying_spot - initial_underlying_entry_price)
        min_required_diff = self.config.min_distance_atr * atr_15m
        if price_diff < min_required_diff:
            return AveragingDecision(
                allow_average=False,
                rejection_reason=f"Underlying distance ({price_diff:.2f}) < minimum ATR requirement ({min_required_diff:.2f}).",
                additional_quantity=0, additional_price=0.0,
                new_weighted_avg_price=initial_option_entry_price,
                new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                new_breakeven_price=initial_option_entry_price
            )

        # 3. Structural Invalidation Check
        # For CE: underlying must NOT have broken decisively below the support zone
        # For PE: underlying must NOT have broken decisively above the resistance zone
        invalidation_buffer = self.config.max_thesis_invalidation_buffer_atr * atr_15m

        if option_type == "CE":
            if confluence_zone is not None:
                invalid_level = confluence_zone.lower_bound - invalidation_buffer
            elif market_structure.nearest_support is not None:
                invalid_level = market_structure.nearest_support.lower_bound - invalidation_buffer
            else:
                invalid_level = initial_underlying_entry_price - 2.0 * atr_15m

            if current_underlying_spot < invalid_level:
                return AveragingDecision(
                    allow_average=False,
                    rejection_reason=f"Support thesis decisively invalidated (Spot {current_underlying_spot:.2f} < Invalid Level {invalid_level:.2f}).",
                    additional_quantity=0, additional_price=0.0,
                    new_weighted_avg_price=initial_option_entry_price,
                    new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                    new_breakeven_price=initial_option_entry_price
                )

        elif option_type == "PE":
            if confluence_zone is not None:
                invalid_level = confluence_zone.upper_bound + invalidation_buffer
            elif market_structure.nearest_resistance is not None:
                invalid_level = market_structure.nearest_resistance.upper_bound + invalidation_buffer
            else:
                invalid_level = initial_underlying_entry_price + 2.0 * atr_15m

            if current_underlying_spot > invalid_level:
                return AveragingDecision(
                    allow_average=False,
                    rejection_reason=f"Resistance thesis decisively invalidated (Spot {current_underlying_spot:.2f} > Invalid Level {invalid_level:.2f}).",
                    additional_quantity=0, additional_price=0.0,
                    new_weighted_avg_price=initial_option_entry_price,
                    new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                    new_breakeven_price=initial_option_entry_price
                )

        # 4. Require Fresh 15M Reversal Signal
        if self.config.require_new_15m_reversal:
            expected_dir = "BULLISH" if option_type == "CE" else "BEARISH"
            if reversal_signal.direction != expected_dir or reversal_signal.composite_confirmation_score < 0.45:
                return AveragingDecision(
                    allow_average=False,
                    rejection_reason=f"No valid fresh 15M reversal confirmation (Signal: {reversal_signal.pattern_name}, Score: {reversal_signal.composite_confirmation_score}).",
                    additional_quantity=0, additional_price=0.0,
                    new_weighted_avg_price=initial_option_entry_price,
                    new_total_quantity=initial_quantity, new_stop_loss_price=0.0,
                    new_breakeven_price=initial_option_entry_price
                )

        # Sizing the additional entry
        additional_qty = int(initial_quantity * self.config.size_multiplier)
        additional_qty = max(lot_size, (additional_qty // lot_size) * lot_size)

        new_total_qty = initial_quantity + additional_qty
        new_weighted_avg = (
            (initial_option_entry_price * initial_quantity) +
            (current_option_price * additional_qty)
        ) / new_total_qty

        # Combined stop loss: structured on option premium (-30% of new weighted average or hard invalidation)
        new_stop_loss = max(0.05, round(new_weighted_avg * 0.70, 2))
        new_breakeven = round(new_weighted_avg, 2)

        return AveragingDecision(
            allow_average=True,
            rejection_reason=None,
            additional_quantity=additional_qty,
            additional_price=current_option_price,
            new_weighted_avg_price=round(new_weighted_avg, 2),
            new_total_quantity=new_total_qty,
            new_stop_loss_price=new_stop_loss,
            new_breakeven_price=new_breakeven
        )

"""
Multi-Timeframe Support & Resistance Strategy Orchestrator.
Combines 4H Major Market Structure, 15M Short-Term S/R, MTF Confluence Analysis,
and 15M Reversal Confirmations to generate high-probability Options entries (CE/PE).
Zero look-ahead bias strictly enforced.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Literal, Dict, Any, List
import pandas as pd

from src.config.trading_config import MasterConfig
from src.indicators.support_resistance_4h import SupportResistance4H, MarketStructureState, SRZone
from src.indicators.support_resistance_15m import SupportResistance15M, ConfluenceZone
from src.indicators.reversal_confirmation import ReversalConfirmation, ReversalSignal
from src.options.strike_selector import StrikeSelector, OptionContract

@dataclass
class TradeSignal:
    timestamp: pd.Timestamp
    symbol: str
    action: Literal["BUY_CE", "BUY_PE", "HOLD"]
    underlying_spot: float
    option_contract: Optional[OptionContract]
    underlying_stop_loss: float
    option_entry_price: float
    option_stop_loss: float
    confluence_zone: Optional[ConfluenceZone]
    reversal_signal: Optional[ReversalSignal]
    market_trend_4h: str
    confidence_score: float

class MTFSRStrategy:
    """
    Automated Multi-Timeframe S/R Options Strategy.
    """

    def __init__(self, config: MasterConfig):
        self.config = config
        self.sr_4h_engine = SupportResistance4H(config.sr)
        self.sr_15m_engine = SupportResistance15M(config.sr)
        self.reversal_engine = ReversalConfirmation(config.confirmation)

    def evaluate_setup(
        self,
        symbol: str,
        df_15m: pd.DataFrame,
        bar_idx: int,
        df_4h_visible: pd.DataFrame,
        current_spot: float,
        current_volatility: float,
        current_atr_15m: float
    ) -> Optional[TradeSignal]:
        """
        Evaluates trading setup at the close of 15M candle at bar_idx.
        df_4h_visible contains only 4H candles closed strictly at or before this 15M bar.
        """
        current_time = df_15m.index[bar_idx]

        # 1. Check warm-up requirements
        if bar_idx < self.config.timeframe.warmup_bars_15m or len(df_4h_visible) < self.config.timeframe.warmup_bars_4h:
            return None

        # 2. 4H Major Market Structure & S/R Zones
        market_structure_4h = self.sr_4h_engine.analyze_market_structure(
            df_4h_visible=df_4h_visible,
            current_time=current_time,
            current_spot=current_spot
        )

        # 3. 15M S/R Zones
        df_15m_visible = df_15m.iloc[:bar_idx + 1]
        supports_15m, resistances_15m = self.sr_15m_engine.detect_15m_zones(
            df_15m_visible=df_15m_visible,
            current_time=current_time
        )

        # 4. Multi-Timeframe Confluence Zones
        confluent_supports, confluent_resistances = self.sr_15m_engine.find_confluence_zones(
            market_structure_4h=market_structure_4h,
            supports_15m=supports_15m,
            resistances_15m=resistances_15m,
            current_spot=current_spot
        )

        # 5. 15M Reversal Confirmation (Pattern + Volume + RSI)
        reversal = self.reversal_engine.evaluate_bar(df_15m, bar_idx)

        # 6. Check for BUY CE Setup (Bullish Reversal off Support)
        if reversal.direction == "BULLISH" and reversal.composite_confirmation_score >= 0.45:
            # Find if price is testing a valid support zone
            matched_support: Optional[ConfluenceZone] = None
            for s_zone in confluent_supports:
                # Check proximity: spot within zone tolerance or upper bound
                if s_zone.lower_bound * 0.995 <= current_spot <= s_zone.upper_bound * 1.008:
                    matched_support = s_zone
                    break

            # Fallback to 4H nearest support if no confluence zone matched
            if matched_support is None and market_structure_4h.nearest_support is not None:
                ns = market_structure_4h.nearest_support
                if ns.lower_bound * 0.995 <= current_spot <= ns.upper_bound * 1.008:
                    matched_support = ConfluenceZone(
                        zone_type="SUPPORT",
                        center_price=ns.price_level,
                        lower_bound=ns.lower_bound,
                        upper_bound=ns.upper_bound,
                        confluence_score=ns.strength_score * 0.8,
                        zone_4h=ns,
                        zone_15m=None,
                        distance_pct=0.0,
                        is_tested=True
                    )

            if matched_support is not None:
                # Avoid trading against strong 4H downtrend unless confidence is high
                if market_structure_4h.trend == "BEARISH" and matched_support.confluence_score < 0.65:
                    return None

                # Select optimal CE contract
                contract = StrikeSelector.select_best_contract(
                    symbol=symbol,
                    current_datetime=current_time,
                    spot_price=current_spot,
                    option_type="CE",
                    volatility=current_volatility,
                    mode=self.config.option.strike_selection_mode,
                    target_delta=self.config.option.target_delta,
                    min_dte=self.config.option.min_days_to_expiry,
                    max_dte=self.config.option.max_days_to_expiry,
                    risk_free_rate=self.config.option.risk_free_rate,
                    dividend_yield=self.config.option.dividend_yield,
                    max_spread_pct=self.config.option.max_bid_ask_spread_pct
                )

                if contract is not None and contract.ask_price > 0.10:
                    underlying_stop = matched_support.lower_bound - (self.config.trailing_stop.initial_stop_atr_multiplier * current_atr_15m)
                    option_entry = contract.ask_price
                    option_stop = round(max(0.05, option_entry * (1.0 - self.config.trailing_stop.initial_stop_premium_pct)), 2)

                    confidence = (matched_support.confluence_score * 0.5 + reversal.composite_confirmation_score * 0.5)

                    return TradeSignal(
                        timestamp=current_time,
                        symbol=symbol,
                        action="BUY_CE",
                        underlying_spot=current_spot,
                        option_contract=contract,
                        underlying_stop_loss=round(underlying_stop, 2),
                        option_entry_price=option_entry,
                        option_stop_loss=option_stop,
                        confluence_zone=matched_support,
                        reversal_signal=reversal,
                        market_trend_4h=market_structure_4h.trend,
                        confidence_score=round(confidence, 3)
                    )

        # 7. Check for BUY PE Setup (Bearish Reversal off Resistance)
        if reversal.direction == "BEARISH" and reversal.composite_confirmation_score >= 0.45:
            matched_resistance: Optional[ConfluenceZone] = None
            for r_zone in confluent_resistances:
                if r_zone.lower_bound * 0.992 <= current_spot <= r_zone.upper_bound * 1.005:
                    matched_resistance = r_zone
                    break

            if matched_resistance is None and market_structure_4h.nearest_resistance is not None:
                nr = market_structure_4h.nearest_resistance
                if nr.lower_bound * 0.992 <= current_spot <= nr.upper_bound * 1.005:
                    matched_resistance = ConfluenceZone(
                        zone_type="RESISTANCE",
                        center_price=nr.price_level,
                        lower_bound=nr.lower_bound,
                        upper_bound=nr.upper_bound,
                        confluence_score=nr.strength_score * 0.8,
                        zone_4h=nr,
                        zone_15m=None,
                        distance_pct=0.0,
                        is_tested=True
                    )

            if matched_resistance is not None:
                if market_structure_4h.trend == "BULLISH" and matched_resistance.confluence_score < 0.65:
                    return None

                contract = StrikeSelector.select_best_contract(
                    symbol=symbol,
                    current_datetime=current_time,
                    spot_price=current_spot,
                    option_type="PE",
                    volatility=current_volatility,
                    mode=self.config.option.strike_selection_mode,
                    target_delta=self.config.option.target_delta,
                    min_dte=self.config.option.min_days_to_expiry,
                    max_dte=self.config.option.max_days_to_expiry,
                    risk_free_rate=self.config.option.risk_free_rate,
                    dividend_yield=self.config.option.dividend_yield,
                    max_spread_pct=self.config.option.max_bid_ask_spread_pct
                )

                if contract is not None and contract.ask_price > 0.10:
                    underlying_stop = matched_resistance.upper_bound + (self.config.trailing_stop.initial_stop_atr_multiplier * current_atr_15m)
                    option_entry = contract.ask_price
                    option_stop = round(max(0.05, option_entry * (1.0 - self.config.trailing_stop.initial_stop_premium_pct)), 2)

                    confidence = (matched_resistance.confluence_score * 0.5 + reversal.composite_confirmation_score * 0.5)

                    return TradeSignal(
                        timestamp=current_time,
                        symbol=symbol,
                        action="BUY_PE",
                        underlying_spot=current_spot,
                        option_contract=contract,
                        underlying_stop_loss=round(underlying_stop, 2),
                        option_entry_price=option_entry,
                        option_stop_loss=option_stop,
                        confluence_zone=matched_resistance,
                        reversal_signal=reversal,
                        market_trend_4h=market_structure_4h.trend,
                        confidence_score=round(confidence, 3)
                    )

        return None

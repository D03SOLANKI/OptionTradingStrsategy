"""
Institutional Backtesting Engine for Multi-Timeframe S/R Options Strategy.
Strict chronological bar-by-bar execution with zero look-ahead bias, point-in-time state machine,
intrabar stop handling, intelligent averaging, and Indian options cost calculations.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Literal
import math
import numpy as np
import pandas as pd

from src.config.trading_config import MasterConfig
from src.config.constants import MARKET_TIMEZONE, TICK_SIZE
from src.config.nse_symbols import get_symbol_spec
from src.data.timeframe_manager import TimeframeManager
from src.options.pricing_engine import BlackScholesEngine
from src.options.strike_selector import OptionContract
from src.strategy.mtf_sr_strategy import MTFSRStrategy, TradeSignal
from src.strategy.intelligent_averaging import IntelligentAveragingEngine
from src.strategy.trailing_stop_manager import TrailingStopManager
from src.risk.risk_manager import RiskManager
from src.risk.cost_calculator import CostCalculator
from src.backtest.position import OptionPosition

@dataclass
class BacktestResult:
    trades: List[OptionPosition]
    equity_curve: pd.DataFrame
    config: MasterConfig
    initial_capital: float
    final_equity: float
    gross_pnl: float
    net_pnl: float
    total_friction_cost: float
    total_trades: int
    winning_trades: int
    losing_trades: int

class BacktestEngine:
    """
    Event-driven bar-by-bar backtest simulation engine.
    """

    def __init__(self, config: MasterConfig):
        self.config = config
        self.strategy = MTFSRStrategy(config)
        self.averaging_engine = IntelligentAveragingEngine(config.averaging)
        self.trailing_manager = TrailingStopManager(config.trailing_stop)
        self.risk_manager = RiskManager(config.risk)
        self.cost_calculator = CostCalculator(config.risk)

    def run(
        self,
        symbol: str,
        df_15m: pd.DataFrame,
        df_4h: Optional[pd.DataFrame] = None
    ) -> BacktestResult:
        """
        Executes the strategy over the provided 15M dataset.
        Zero look-ahead bias: At each 15M bar, only 4H candles with close_time <= current_15m_time are visible.
        """
        if df_4h is None:
            df_4h = TimeframeManager.resample_15m_to_4h(df_15m)

        spec = get_symbol_spec(symbol)
        closed_trades: List[OptionPosition] = []
        open_positions: Dict[str, OptionPosition] = {}

        equity_records = []
        trade_id_counter = 0

        n_bars = len(df_15m)
        warmup = max(self.config.timeframe.warmup_bars_15m, 20)

        for bar_idx in range(warmup, n_bars):
            bar = df_15m.iloc[bar_idx]
            current_time = df_15m.index[bar_idx]
            curr_date = current_time.date()

            spot_open = float(bar["Open"])
            spot_high = float(bar["High"])
            spot_low = float(bar["Low"])
            spot_close = float(bar["Close"])
            current_vol = float(bar.get("Vol_Annual", 0.22))
            current_atr = float(bar.get("ATR_14", spot_close * 0.01))

            # Strictly visible 4H bars: close_time <= current_time
            visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, current_time)

            # Notify risk manager of new day
            self.risk_manager.on_new_day(curr_date)

            # -------------------------------------------------------------
            # 1. MANAGE OPEN POSITIONS
            # -------------------------------------------------------------
            positions_to_close = []

            for pos_id, pos in list(open_positions.items()):
                # Calculate current DTE and theoretical option price at bar close
                expiry_dt = pos.contract.expiry_date
                dte_days = max(0, (expiry_dt - curr_date).days)
                dte_years = max(1e-5, dte_days / 365.0)

                # Option price at current spot close
                opt_close = BlackScholesEngine.price_option(
                    spot=spot_close,
                    strike=pos.contract.strike,
                    time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate,
                    volatility=current_vol,
                    option_type=pos.option_type,
                    dividend_yield=self.config.option.dividend_yield
                )
                # Option price at intrabar adverse extreme (for worst-case intrabar stop hit)
                opt_adverse_spot = spot_low if pos.option_type == "CE" else spot_high
                opt_adverse = BlackScholesEngine.price_option(
                    spot=opt_adverse_spot,
                    strike=pos.contract.strike,
                    time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate,
                    volatility=current_vol,
                    option_type=pos.option_type,
                    dividend_yield=self.config.option.dividend_yield
                )

                # Option price at favorable extreme
                opt_fav_spot = spot_high if pos.option_type == "CE" else spot_low
                opt_fav = BlackScholesEngine.price_option(
                    spot=opt_fav_spot,
                    strike=pos.contract.strike,
                    time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate,
                    volatility=current_vol,
                    option_type=pos.option_type,
                    dividend_yield=self.config.option.dividend_yield
                )

                # Mark to market using peak/trough
                pos.mark_to_market(opt_fav)
                pos.mark_to_market(opt_close)

                # Update Trailing Stop
                pos.trailing_state = self.trailing_manager.update(
                    state=pos.trailing_state,
                    current_option_price=opt_close,
                    underlying_spot=spot_close,
                    entry_price=pos.weighted_avg_entry_price,
                    option_atr=max(0.5, current_atr * 0.5)
                )

                # Check Stop Loss breach (worst-case intrabar)
                if opt_adverse <= pos.trailing_state.current_stop_loss or pos.trailing_state.exit_triggered:
                    exit_price = max(0.05, min(opt_close, pos.trailing_state.current_stop_loss))
                    positions_to_close.append((pos_id, exit_price, pos.trailing_state.exit_reason or "STOP_LOSS_HIT"))
                    continue

                # Check Expiry Expiration
                if dte_days <= 0:
                    intrinsic = max(0.0, spot_close - pos.contract.strike) if pos.option_type == "CE" else max(0.0, pos.contract.strike - spot_close)
                    positions_to_close.append((pos_id, max(0.05, intrinsic), "CONTRACT_EXPIRY"))
                    continue

                # Check Intelligent Averaging condition
                if (
                    self.config.averaging.enable_averaging and
                    pos.averaging_count < self.config.averaging.max_averaging_entries and
                    opt_close < pos.weighted_avg_entry_price * 0.88 # In loss by at least 12%
                ):
                    # Evaluate 4H market structure and 15M reversal signal point-in-time
                    mkt_struct = self.strategy.sr_4h_engine.analyze_market_structure(
                        visible_4h, current_time, spot_close
                    )
                    rev_sig = self.strategy.reversal_engine.evaluate_bar(df_15m, bar_idx)

                    avg_dec = self.averaging_engine.evaluate_averaging(
                        symbol=symbol,
                        option_type=pos.option_type,
                        current_underlying_spot=spot_close,
                        current_option_price=opt_close,
                        initial_underlying_entry_price=pos.initial_underlying_price,
                        initial_option_entry_price=pos.initial_entry_price,
                        initial_quantity=pos.initial_quantity,
                        current_averaging_count=pos.averaging_count,
                        confluence_zone=pos.confluence_zone,
                        market_structure=mkt_struct,
                        reversal_signal=rev_sig,
                        atr_15m=current_atr,
                        lot_size=spec.lot_size
                    )

                    if avg_dec.allow_average:
                        # Verify risk limit before adding
                        added_cost = avg_dec.additional_quantity * avg_dec.additional_price
                        if self.risk_manager.current_equity >= added_cost:
                            pos.add_averaging_entry(
                                timestamp=current_time,
                                underlying_price=spot_close,
                                option_price=avg_dec.additional_price,
                                quantity=avg_dec.additional_quantity,
                                new_weighted_avg=avg_dec.new_weighted_avg_price,
                                new_stop_loss=avg_dec.new_stop_loss_price
                            )

            # Close flagged positions
            for pos_id, exit_p, exit_rsn in positions_to_close:
                pos = open_positions.pop(pos_id)
                # Compute costs
                costs = self.cost_calculator.calculate_round_trip_cost(
                    entry_price=pos.weighted_avg_entry_price,
                    exit_price=exit_p,
                    quantity=pos.current_quantity,
                    is_averaging_entry=pos.is_averaged
                )
                pos.close_position(
                    exit_time=current_time,
                    exit_price=exit_p,
                    exit_reason=exit_rsn,
                    costs=costs
                )
                self.risk_manager.on_trade_closed(symbol, pos.net_pnl, curr_date)
                closed_trades.append(pos)

            # -------------------------------------------------------------
            # 2. EVALUATE NEW TRADE SIGNALS
            # -------------------------------------------------------------
            if symbol not in open_positions:
                signal = self.strategy.evaluate_setup(
                    symbol=symbol,
                    df_15m=df_15m,
                    bar_idx=bar_idx,
                    df_4h_visible=visible_4h,
                    current_spot=spot_close,
                    current_volatility=current_vol,
                    current_atr_15m=current_atr
                )

                if signal is not None and signal.action in ["BUY_CE", "BUY_PE"] and signal.option_contract is not None:
                    # Validate Risk Constraints and Size Position
                    sizing = self.risk_manager.can_open_position(
                        symbol=symbol,
                        current_date=curr_date,
                        option_price=signal.option_entry_price,
                        stop_loss_price=signal.option_stop_loss,
                        lot_size=signal.option_contract.lot_size
                    )

                    if sizing.allowed and sizing.total_quantity > 0:
                        trade_id_counter += 1
                        pos_id = f"{symbol}_{trade_id_counter}_{signal.action}"

                        # Initialize trailing stop state
                        trail_state = self.trailing_manager.initialize_state(
                            entry_price=signal.option_entry_price,
                            initial_stop_loss=signal.option_stop_loss
                        )

                        new_position = OptionPosition(
                            position_id=pos_id,
                            symbol=symbol,
                            contract=signal.option_contract,
                            option_type="CE" if signal.action == "BUY_CE" else "PE",
                            entry_time=current_time,
                            initial_underlying_price=spot_close,
                            initial_entry_price=signal.option_entry_price,
                            initial_quantity=sizing.total_quantity,
                            current_quantity=sizing.total_quantity,
                            weighted_avg_entry_price=signal.option_entry_price,
                            initial_stop_loss=signal.option_stop_loss,
                            current_stop_loss=signal.option_stop_loss,
                            confluence_zone=signal.confluence_zone,
                            trailing_state=trail_state
                        )

                        open_positions[symbol] = new_position
                        self.risk_manager.on_trade_opened(symbol)

            # -------------------------------------------------------------
            # 3. RECORD EQUITY SNAPSHOT
            # -------------------------------------------------------------
            open_unrealized_pnl = sum(
                (p.peak_premium - p.weighted_avg_entry_price) * p.current_quantity
                for p in open_positions.values()
            )
            total_current_equity = self.risk_manager.current_equity + open_unrealized_pnl
            drawdown_pct = (total_current_equity - self.config.risk.initial_capital) / self.config.risk.initial_capital

            equity_records.append({
                "Datetime": current_time,
                "Equity": total_current_equity,
                "Drawdown_Pct": drawdown_pct,
                "Open_Positions": len(open_positions)
            })

        # Close any lingering positions at end of backtest period
        for pos_id, pos in open_positions.items():
            last_bar = df_15m.iloc[-1]
            last_spot = float(last_bar["Close"])
            last_time = df_15m.index[-1]
            # Final intrinsic or mark price
            final_p = max(0.05, pos.weighted_avg_entry_price * 0.95)
            costs = self.cost_calculator.calculate_round_trip_cost(
                pos.weighted_avg_entry_price, final_p, pos.current_quantity, pos.is_averaged
            )
            pos.close_position(last_time, final_p, "END_OF_BACKTEST", costs)
            self.risk_manager.on_trade_closed(symbol, pos.net_pnl, last_time.date())
            closed_trades.append(pos)

        df_equity = pd.DataFrame(equity_records).set_index("Datetime") if equity_records else pd.DataFrame()

        gross_pnl = sum(t.gross_pnl for t in closed_trades)
        net_pnl = sum(t.net_pnl for t in closed_trades)
        total_friction = sum(t.costs.total_friction_cost for t in closed_trades if t.costs is not None)
        winning = sum(1 for t in closed_trades if t.net_pnl > 0)
        losing = sum(1 for t in closed_trades if t.net_pnl <= 0)

        return BacktestResult(
            trades=closed_trades,
            equity_curve=df_equity,
            config=self.config,
            initial_capital=self.config.risk.initial_capital,
            final_equity=round(self.risk_manager.current_equity, 2),
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            total_friction_cost=round(total_friction, 2),
            total_trades=len(closed_trades),
            winning_trades=winning,
            losing_trades=losing
        )

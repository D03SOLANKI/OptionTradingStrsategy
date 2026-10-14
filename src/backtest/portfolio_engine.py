"""
Unified Multi-Stock Portfolio Backtesting Engine.
Simulates a live multi-asset portfolio with a shared capital pool, global risk limits,
sector concentration controls, concurrent position caps, and rank-ordered entry prioritization.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Set, Any
import math
import numpy as np
import pandas as pd

from src.config.trading_config import MasterConfig
from src.config.constants import TICK_SIZE
from src.config.nse_symbols import get_symbol_spec, SymbolSpec
from src.data.timeframe_manager import TimeframeManager
from src.options.pricing_engine import BlackScholesEngine
from src.options.strike_selector import OptionContract
from src.strategy.mtf_sr_strategy import MTFSRStrategy, TradeSignal
from src.strategy.intelligent_averaging import IntelligentAveragingEngine
from src.strategy.trailing_stop_manager import TrailingStopManager
from src.risk.risk_manager import RiskManager
from src.risk.cost_calculator import CostCalculator
from src.backtest.position import OptionPosition
from src.reporting.performance_metrics import PerformanceMetrics, PerformanceScorecard

@dataclass
class PortfolioBacktestResult:
    trades: List[OptionPosition]
    equity_curve: pd.DataFrame
    daily_performance: pd.DataFrame
    monthly_performance: pd.DataFrame
    scorecard: PerformanceScorecard
    stock_breakdowns: Dict[str, Dict[str, Any]]
    sector_breakdowns: Dict[str, Dict[str, Any]]
    avg_concurrent_positions: float
    max_concurrent_positions: int
    trades_per_day: float

class PortfolioEngine:
    """
    Multi-Asset Institutional Portfolio Execution Engine.
    Executes a basket of N stocks concurrently against a unified cash pool.
    """

    def __init__(self, config: MasterConfig, max_concurrent_positions: int = 3, max_sector_limit: int = 1):
        self.config = config
        self.max_concurrent_positions = max_concurrent_positions
        self.max_sector_limit = max_sector_limit
        self.strategy = MTFSRStrategy(config)
        self.averaging_engine = IntelligentAveragingEngine(config.averaging)
        self.trailing_manager = TrailingStopManager(config.trailing_stop)
        self.risk_manager = RiskManager(config.risk)
        self.risk_manager.config.max_simultaneous_positions = max_concurrent_positions
        self.risk_manager.config.max_sector_concentration = max_sector_limit
        self.cost_calculator = CostCalculator(config.risk)

    def run_portfolio(
        self,
        symbol_data: Dict[str, pd.DataFrame]
    ) -> PortfolioBacktestResult:
        """
        Runs portfolio simulation across all symbols in symbol_data simultaneously.
        symbol_data: dict of symbol -> df_15m (with aligned or common datetime index)
        """
        # 1. Precompute 4H data for each symbol
        symbol_4h: Dict[str, pd.DataFrame] = {}
        for sym, df_15m in symbol_data.items():
            symbol_4h[sym] = TimeframeManager.resample_15m_to_4h(df_15m)

        # 2. Extract unified sorted chronological timeline
        all_timestamps = set()
        for df in symbol_data.values():
            all_timestamps.update(df.index)
        sorted_timestamps = sorted(list(all_timestamps))

        open_positions: Dict[str, OptionPosition] = {} # symbol -> position
        closed_trades: List[OptionPosition] = []
        equity_records = []
        trade_id_counter = 0

        current_cash = self.config.risk.initial_capital
        peak_equity = self.config.risk.initial_capital

        daily_trades_count: Dict[date, int] = {}
        concurrent_positions_history = []

        print(f"    [Portfolio Engine] Stepping through {len(sorted_timestamps)} intraday 15M candles across {len(symbol_data)} stocks...")

        for t_idx, current_time in enumerate(sorted_timestamps):
            curr_date = current_time.date()
            self.risk_manager.on_new_day(curr_date)

            # -------------------------------------------------------------
            # STEP A: UPDATE AND MANAGE ACTIVE OPEN POSITIONS
            # -------------------------------------------------------------
            positions_to_close = []

            for sym, pos in list(open_positions.items()):
                df_15m = symbol_data[sym]
                if current_time not in df_15m.index:
                    continue

                bar = df_15m.loc[current_time]
                spot_close = float(bar["Close"])
                spot_high = float(bar["High"])
                spot_low = float(bar["Low"])
                current_vol = float(bar.get("Vol_Annual", 0.22))
                current_atr = float(bar.get("ATR_14", spot_close * 0.01))

                expiry_dt = pos.contract.expiry_date
                dte_days = max(0, (expiry_dt - curr_date).days)
                dte_years = max(1e-5, dte_days / 365.0)

                opt_close = BlackScholesEngine.price_option(
                    spot=spot_close, strike=pos.contract.strike, time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate, volatility=current_vol,
                    option_type=pos.option_type, dividend_yield=self.config.option.dividend_yield
                )
                opt_adverse_spot = spot_low if pos.option_type == "CE" else spot_high
                opt_adverse = BlackScholesEngine.price_option(
                    spot=opt_adverse_spot, strike=pos.contract.strike, time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate, volatility=current_vol,
                    option_type=pos.option_type, dividend_yield=self.config.option.dividend_yield
                )
                opt_fav_spot = spot_high if pos.option_type == "CE" else spot_low
                opt_fav = BlackScholesEngine.price_option(
                    spot=opt_fav_spot, strike=pos.contract.strike, time_to_expiry=dte_years,
                    rate=self.config.option.risk_free_rate, volatility=current_vol,
                    option_type=pos.option_type, dividend_yield=self.config.option.dividend_yield
                )

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

                # Stop loss breached
                if opt_adverse <= pos.trailing_state.current_stop_loss or pos.trailing_state.exit_triggered:
                    exit_p = max(0.05, min(opt_close, pos.trailing_state.current_stop_loss))
                    positions_to_close.append((sym, exit_p, pos.trailing_state.exit_reason or "STOP_LOSS_HIT"))
                    continue

                # Expiry
                if dte_days <= 0:
                    intrinsic = max(0.0, spot_close - pos.contract.strike) if pos.option_type == "CE" else max(0.0, pos.contract.strike - spot_close)
                    positions_to_close.append((sym, max(0.05, intrinsic), "CONTRACT_EXPIRY"))
                    continue

            # Close flagged positions and return cash to pool
            for sym, exit_p, exit_rsn in positions_to_close:
                pos = open_positions.pop(sym)
                costs = self.cost_calculator.calculate_round_trip_cost(
                    pos.weighted_avg_entry_price, exit_p, pos.current_quantity, pos.is_averaged
                )
                pos.close_position(current_time, exit_p, exit_rsn, costs)
                self.risk_manager.on_trade_closed(sym, pos.net_pnl, curr_date)
                closed_trades.append(pos)
                current_cash += (pos.current_quantity * exit_p) - costs.total_friction_cost

            # -------------------------------------------------------------
            # STEP B: SCAN UNIVERSE AND SELECT NEW TRADES
            # -------------------------------------------------------------
            # Only consider opening new trades if available capacity exists
            if len(open_positions) < self.max_concurrent_positions:
                candidate_signals: List[Tuple[float, TradeSignal]] = []

                for sym, df_15m in symbol_data.items():
                    if sym in open_positions or current_time not in df_15m.index:
                        continue

                    # Check sector concentration limit
                    spec = get_symbol_spec(sym)
                    current_sector_count = sum(1 for p in open_positions.values() if get_symbol_spec(p.symbol).sector == spec.sector)
                    if current_sector_count >= self.max_sector_limit:
                        continue

                    bar_idx = df_15m.index.get_loc(current_time)
                    if bar_idx < self.config.timeframe.warmup_bars_15m:
                        continue

                    bar = df_15m.iloc[bar_idx]
                    spot_close = float(bar["Close"])
                    current_vol = float(bar.get("Vol_Annual", 0.22))
                    current_atr = float(bar.get("ATR_14", spot_close * 0.01))

                    df_4h = symbol_4h[sym]
                    visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, current_time)

                    sig = self.strategy.evaluate_setup(
                        symbol=sym, df_15m=df_15m, bar_idx=bar_idx,
                        df_4h_visible=visible_4h, current_spot=spot_close,
                        current_volatility=current_vol, current_atr_15m=current_atr
                    )

                    if sig is not None and sig.action in ["BUY_CE", "BUY_PE"] and sig.option_contract is not None:
                        candidate_signals.append((sig.confidence_score, sig))

                # Rank candidate signals by confidence score (highest quality first)
                candidate_signals.sort(key=lambda x: x[0], reverse=True)

                for _, sig in candidate_signals:
                    if len(open_positions) >= self.max_concurrent_positions:
                        break

                    spec = get_symbol_spec(sig.symbol)
                    current_sector_count = sum(1 for p in open_positions.values() if get_symbol_spec(p.symbol).sector == spec.sector)
                    if current_sector_count >= self.max_sector_limit:
                        continue

                    # Risk sizing check
                    sizing = self.risk_manager.can_open_position(
                        symbol=sig.symbol, current_date=curr_date,
                        option_price=sig.option_entry_price,
                        stop_loss_price=sig.option_stop_loss,
                        lot_size=sig.option_contract.lot_size
                    )

                    if sizing.allowed and sizing.total_quantity > 0 and current_cash >= sizing.total_capital_required:
                        trade_id_counter += 1
                        pos_id = f"{sig.symbol}_{trade_id_counter}_{sig.action}"

                        trail_state = self.trailing_manager.initialize_state(
                            entry_price=sig.option_entry_price,
                            initial_stop_loss=sig.option_stop_loss
                        )

                        new_pos = OptionPosition(
                            position_id=pos_id,
                            symbol=sig.symbol,
                            contract=sig.option_contract,
                            option_type="CE" if sig.action == "BUY_CE" else "PE",
                            entry_time=current_time,
                            initial_underlying_price=sig.underlying_spot,
                            initial_entry_price=sig.option_entry_price,
                            initial_quantity=sizing.total_quantity,
                            current_quantity=sizing.total_quantity,
                            weighted_avg_entry_price=sig.option_entry_price,
                            initial_stop_loss=sig.option_stop_loss,
                            current_stop_loss=sig.option_stop_loss,
                            confluence_zone=sig.confluence_zone,
                            trailing_state=trail_state
                        )

                        open_positions[sig.symbol] = new_pos
                        current_cash -= sizing.total_capital_required
                        self.risk_manager.on_trade_opened(sig.symbol)

                        daily_trades_count[curr_date] = daily_trades_count.get(curr_date, 0) + 1

            # -------------------------------------------------------------
            # STEP C: RECORD PORTFOLIO EQUITY SNAPSHOT
            # -------------------------------------------------------------
            open_positions_val = sum(
                p.current_quantity * p.peak_premium for p in open_positions.values()
            )
            total_equity = self.risk_manager.current_equity + sum(
                (p.peak_premium - p.weighted_avg_entry_price) * p.current_quantity for p in open_positions.values()
            )
            peak_equity = max(peak_equity, total_equity)
            dd_pct = (peak_equity - total_equity) / peak_equity * 100.0

            concurrent_positions_history.append(len(open_positions))
            equity_records.append({
                "Datetime": current_time,
                "Equity": total_equity,
                "Cash": current_cash,
                "Open_Positions_Count": len(open_positions),
                "Drawdown_Pct": dd_pct
            })

        # Close any open positions at end of backtest
        for sym, pos in list(open_positions.items()):
            last_time = sorted_timestamps[-1]
            final_p = max(0.05, pos.weighted_avg_entry_price * 0.95)
            costs = self.cost_calculator.calculate_round_trip_cost(
                pos.weighted_avg_entry_price, final_p, pos.current_quantity, pos.is_averaged
            )
            pos.close_position(last_time, final_p, "END_OF_PORTFOLIO_BACKTEST", costs)
            self.risk_manager.on_trade_closed(sym, pos.net_pnl, last_time.date())
            closed_trades.append(pos)

        df_equity = pd.DataFrame(equity_records).set_index("Datetime") if equity_records else pd.DataFrame()

        # Scorecard
        scorecard = PerformanceMetrics.calculate_scorecard(
            trades=closed_trades,
            equity_curve=df_equity,
            initial_capital=self.config.risk.initial_capital
        )

        # Daily performance aggregation
        df_equity["date"] = df_equity.index.date
        daily_perf = df_equity.groupby("date").agg({
            "Equity": "last",
            "Drawdown_Pct": "max",
            "Open_Positions_Count": "mean"
        })
        daily_perf["Daily_Return_Pct"] = daily_perf["Equity"].pct_change() * 100.0

        # Monthly performance aggregation
        df_equity["year_month"] = df_equity.index.to_period("M")
        monthly_perf = df_equity.groupby("year_month").agg({
            "Equity": ["first", "last"]
        })
        monthly_perf.columns = ["Start_Equity", "End_Equity"]
        monthly_perf["Monthly_PnL"] = monthly_perf["End_Equity"] - monthly_perf["Start_Equity"]
        monthly_perf["Monthly_Return_Pct"] = (monthly_perf["Monthly_PnL"] / monthly_perf["Start_Equity"]) * 100.0

        # Stock-by-stock breakdown
        stock_breakdowns = {}
        for sym in symbol_data.keys():
            sym_trades = [t for t in closed_trades if t.symbol == sym]
            n_t = len(sym_trades)
            w_t = sum(1 for t in sym_trades if t.net_pnl > 0)
            pnl = sum(t.net_pnl for t in sym_trades)
            stock_breakdowns[sym] = {
                "trades": n_t,
                "wins": w_t,
                "win_rate": (w_t / n_t * 100.0) if n_t > 0 else 0.0,
                "net_pnl": round(pnl, 2),
                "sector": get_symbol_spec(sym).sector
            }

        # Sector breakdown
        sector_breakdowns = {}
        for sym, info in stock_breakdowns.items():
            sec = info["sector"]
            if sec not in sector_breakdowns:
                sector_breakdowns[sec] = {"trades": 0, "net_pnl": 0.0}
            sector_breakdowns[sec]["trades"] += info["trades"]
            sector_breakdowns[sec]["net_pnl"] += info["net_pnl"]

        total_trading_days = len(daily_perf)
        avg_trades_day = len(closed_trades) / total_trading_days if total_trading_days > 0 else 0.0
        avg_concurrent = float(np.mean(concurrent_positions_history)) if concurrent_positions_history else 0.0
        max_concurrent = int(np.max(concurrent_positions_history)) if concurrent_positions_history else 0

        return PortfolioBacktestResult(
            trades=closed_trades,
            equity_curve=df_equity,
            daily_performance=daily_perf,
            monthly_performance=monthly_perf,
            scorecard=scorecard,
            stock_breakdowns=stock_breakdowns,
            sector_breakdowns=sector_breakdowns,
            avg_concurrent_positions=round(avg_concurrent, 2),
            max_concurrent_positions=max_concurrent,
            trades_per_day=round(avg_trades_day, 2)
        )

"""
Cash Equity Portfolio Backtesting Engine.
Simulates multi-asset cash-market stock trading (Equity Delivery/Intraday) with:
- Zero options: pure stock buying and selling
- Multi-timeframe 4H structural macro S/R + 15M reversal entry confirmation
- Dynamic multi-tier trailing stop (1:2 R:R partial booking, breakeven ratchet, swing trailing)
- Full Indian regulatory cash market friction (Zerodha delivery STT, turnover charges, GST, stamp duty, 1-tick slippage)
- Unified capital pool (e.g. ₹10 Lakhs), sector concentration caps, and concurrent position limits.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple, Any, Literal
import math
import numpy as np
import pandas as pd

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import get_symbol_spec, SymbolSpec
from src.data.timeframe_manager import TimeframeManager
from src.cost.cash_cost_calculator import CashCostCalculator, CashTradeCostBreakdown
from src.reporting.performance_metrics import PerformanceMetrics, PerformanceScorecard
from src.indicators.support_resistance_4h import SupportResistance4H
from src.indicators.reversal_confirmation import ReversalConfirmation

@dataclass
class CashPosition:
    position_id: str
    symbol: str
    company_name: str
    sector: str
    direction: Literal["BUY", "SELL"]
    entry_time: pd.Timestamp
    entry_price: float
    initial_shares: int
    current_shares: int
    initial_stop_loss: float
    current_stop_loss: float
    target_1_rr: float
    target_2_macro: float
    be_trigger_price: float
    be_ratchet_price: float
    risk_per_share: float
    is_target_1_booked: bool = False
    is_breakeven_activated: bool = False
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    gross_pnl: float = 0.0
    friction_cost: float = 0.0
    net_pnl: float = 0.0
    return_pct: float = 0.0
    highest_price: float = field(default=0.0)
    lowest_price: float = field(default=999999.0)

    def mark_to_market(self, high: float, low: float, close: float):
        if high > self.highest_price:
            self.highest_price = high
        if low < self.lowest_price:
            self.lowest_price = low

@dataclass
class CashPortfolioBacktestResult:
    trades: List[CashPosition]
    equity_curve: pd.DataFrame
    daily_performance: pd.DataFrame
    monthly_performance: pd.DataFrame
    scorecard: PerformanceScorecard
    stock_breakdowns: Dict[str, Dict[str, Any]]
    sector_breakdowns: Dict[str, Dict[str, Any]]
    avg_concurrent_positions: float
    max_concurrent_positions: int
    trades_per_day: float

class CashPortfolioEngine:
    """
    Cash Equity Multi-Stock Portfolio Execution Engine.
    """

    def __init__(
        self,
        config: Optional[MasterConfig] = None,
        initial_capital: float = 1000000.0,
        max_concurrent_positions: int = 4,
        max_sector_limit: int = 1,
        max_risk_per_trade_pct: float = 0.015,
        max_capital_per_trade_pct: float = 0.25,
        trade_mode: Literal["DELIVERY", "INTRADAY"] = "DELIVERY"
    ):
        self.config = config or MasterConfig()
        self.initial_capital = initial_capital
        self.max_concurrent_positions = max_concurrent_positions
        self.max_sector_limit = max_sector_limit
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_capital_per_trade_pct = max_capital_per_trade_pct
        self.trade_mode = trade_mode
        self.cost_calculator = CashCostCalculator()
        self.sr_4h_engine = SupportResistance4H(self.config.sr)
        self.reversal_engine = ReversalConfirmation(self.config.confirmation)

    def run_backtest(
        self,
        symbol_data: Dict[str, pd.DataFrame]
    ) -> CashPortfolioBacktestResult:
        """
        Executes unified chronological cash stock simulation across all symbols.
        """
        # 1. Precompute 4H data for each symbol strictly using session-aware resampler
        symbol_4h: Dict[str, pd.DataFrame] = {}
        for sym, df_15m in symbol_data.items():
            symbol_4h[sym] = TimeframeManager.resample_15m_to_4h(df_15m)

        # 2. Extract global sorted timeline
        all_timestamps = set()
        for df in symbol_data.values():
            all_timestamps.update(df.index)
        sorted_timestamps = sorted(list(all_timestamps))

        open_positions: Dict[str, CashPosition] = {}
        closed_trades: List[CashPosition] = []
        equity_records = []
        trade_id_counter = 0

        current_cash = self.initial_capital
        peak_equity = self.initial_capital
        concurrent_history = []
        daily_trades_count: Dict[date, int] = {}

        for t_idx, current_time in enumerate(sorted_timestamps):
            curr_date = current_time.date()
            if curr_date not in daily_trades_count:
                daily_trades_count[curr_date] = 0

            # ---------------------------------------------------------
            # STEP A: UPDATE AND MANAGE ACTIVE CASH POSITIONS
            # ---------------------------------------------------------
            positions_to_close = []

            for sym, pos in list(open_positions.items()):
                df_15m = symbol_data[sym]
                if current_time not in df_15m.index:
                    continue

                bar = df_15m.loc[current_time]
                spot_close = float(bar["Close"])
                spot_high = float(bar["High"])
                spot_low = float(bar["Low"])

                pos.mark_to_market(spot_high, spot_low, spot_close)

                # Check Breakeven Trigger (+1.5R)
                if not pos.is_breakeven_activated:
                    if (pos.direction == "BUY" and spot_high >= pos.be_trigger_price) or \
                       (pos.direction == "SELL" and spot_low <= pos.be_trigger_price):
                        pos.is_breakeven_activated = True
                        pos.current_stop_loss = pos.be_ratchet_price

                # Check Target 1 (1:2 R:R Partial Booking - 50% shares)
                if not pos.is_target_1_booked:
                    if (pos.direction == "BUY" and spot_high >= pos.target_1_rr) or \
                       (pos.direction == "SELL" and spot_low <= pos.target_1_rr):
                        pos.is_target_1_booked = True
                        shares_to_book = pos.current_shares // 2
                        if shares_to_book > 0:
                            pos.current_shares -= shares_to_book
                            # Return partial capital & profit to cash pool
                            book_costs = self.cost_calculator.calculate_round_trip_cost(
                                pos.entry_price, pos.target_1_rr, shares_to_book, self.trade_mode
                            )
                            pnl_booked = ((pos.target_1_rr - pos.entry_price) * shares_to_book) - book_costs.total_friction_cost
                            current_cash += (shares_to_book * pos.target_1_rr) - book_costs.total_friction_cost
                            pos.friction_cost += book_costs.total_friction_cost
                            # Ratchet stop to +1.0R
                            pos.current_stop_loss = pos.entry_price + (1.0 * pos.risk_per_share) if pos.direction == "BUY" else pos.entry_price - (1.0 * pos.risk_per_share)

                # Check Target 2 (Macro 4H Structural Level)
                if (pos.direction == "BUY" and spot_high >= pos.target_2_macro) or \
                   (pos.direction == "SELL" and spot_low <= pos.target_2_macro):
                    positions_to_close.append((sym, pos.target_2_macro, "TARGET_2_MACRO_REACHED"))
                    continue

                # Check Stop Loss Breached
                if pos.direction == "BUY" and spot_low <= pos.current_stop_loss:
                    positions_to_close.append((sym, pos.current_stop_loss, "STOP_LOSS_HIT"))
                    continue
                elif pos.direction == "SELL" and spot_high >= pos.current_stop_loss:
                    positions_to_close.append((sym, pos.current_stop_loss, "STOP_LOSS_HIT"))
                    continue

            # Process Closures
            for sym, exit_p, exit_reason in positions_to_close:
                pos = open_positions.pop(sym)
                rem_shares = pos.current_shares
                costs = self.cost_calculator.calculate_round_trip_cost(
                    pos.entry_price, exit_p, rem_shares, self.trade_mode
                )
                pos.exit_time = current_time
                pos.exit_price = exit_p
                pos.exit_reason = exit_reason
                pos.friction_cost += costs.total_friction_cost

                # Calculate total position PnL
                if pos.is_target_1_booked:
                    booked_shares = pos.initial_shares - rem_shares
                    gross = ((pos.target_1_rr - pos.entry_price) * booked_shares) + ((exit_p - pos.entry_price) * rem_shares) if pos.direction == "BUY" else \
                            ((pos.entry_price - pos.target_1_rr) * booked_shares) + ((pos.entry_price - exit_p) * rem_shares)
                else:
                    gross = (exit_p - pos.entry_price) * rem_shares if pos.direction == "BUY" else (pos.entry_price - exit_p) * rem_shares

                pos.gross_pnl = round(gross, 2)
                pos.net_pnl = round(gross - pos.friction_cost, 2)
                pos.return_pct = round((pos.net_pnl / (pos.initial_shares * pos.entry_price)) * 100.0, 2)

                current_cash += (rem_shares * exit_p) - costs.total_friction_cost
                closed_trades.append(pos)
                daily_trades_count[curr_date] += 1

            # ---------------------------------------------------------
            # STEP B: SCAN UNIVERSE & OPEN NEW POSITIONS
            # ---------------------------------------------------------
            if len(open_positions) < self.max_concurrent_positions:
                for sym, df_15m in symbol_data.items():
                    if len(open_positions) >= self.max_concurrent_positions:
                        break
                    if sym in open_positions or current_time not in df_15m.index:
                        continue

                    spec = get_symbol_spec(sym)
                    current_sec_count = sum(1 for p in open_positions.values() if p.sector == spec.sector)
                    if current_sec_count >= self.max_sector_limit:
                        continue

                    bar_idx = df_15m.index.get_loc(current_time)
                    if bar_idx < 50:
                        continue

                    # 1. Fast Pre-Filter: 15M Reversal Confirmation (Hammer, Engulfing, Morning Star + Volume)
                    reversal = self.reversal_engine.evaluate_bar(df_15m, bar_idx)
                    if reversal.direction != "BULLISH" or reversal.composite_confirmation_score < 0.40:
                        continue

                    bar = df_15m.iloc[bar_idx]
                    spot_close = float(bar["Close"])
                    atr_15m = float(bar.get("ATR_14", spot_close * 0.01))

                    # 2. Check 4H Market Structure & Major S/R Zones (Strict Point-In-Time)
                    df_4h = symbol_4h[sym]
                    visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, current_time)
                    if len(visible_4h) < self.config.timeframe.warmup_bars_4h:
                        continue

                    mkt = self.sr_4h_engine.analyze_market_structure(
                        df_4h_visible=visible_4h,
                        current_time=current_time,
                        current_spot=spot_close
                    )

                    # Find matched active support zone within proximity tolerance
                    matched_support = None
                    for sz in mkt.active_supports:
                        if sz.lower_bound * 0.990 <= spot_close <= sz.upper_bound * 1.020:
                            matched_support = sz
                            break

                    if matched_support is None and mkt.nearest_support is not None:
                        ns = mkt.nearest_support
                        if ns.lower_bound * 0.990 <= spot_close <= ns.upper_bound * 1.020:
                            matched_support = ns

                    if matched_support is None:
                        continue

                    # 3. Macro 4H Resistance Target & S/R Confluence
                    nearest_res = mkt.nearest_resistance
                    target_macro = nearest_res.price_level if (nearest_res and nearest_res.price_level > spot_close) else round(spot_close + (3.0 * atr_15m), 2)

                    # Dynamic stop-loss below support zone
                    stop_p = round(min(matched_support.lower_bound - (0.5 * atr_15m), spot_close - (1.0 * atr_15m)), 2)
                    risk_per_sh = max(0.05, spot_close - stop_p)
                    reward_per_sh = max(0.05, target_macro - spot_close)
                    rr = reward_per_sh / risk_per_sh

                    # 4. Enforce institutional Risk-to-Reward ratio
                    if rr < 1.5:
                        continue

                    # 5. Cash Position Sizing (Fixed fractional risk & capital cap)
                    max_risk_inr = self.initial_capital * self.max_risk_per_trade_pct
                    max_trade_cap = min(current_cash * 0.95, self.initial_capital * self.max_capital_per_trade_pct)

                    sh_risk = int(max_risk_inr / risk_per_sh)
                    sh_cap = int(max_trade_cap / spot_close)
                    final_sh = min(sh_risk, sh_cap)

                    if final_sh > 0 and (final_sh * spot_close) <= current_cash:
                        trade_id_counter += 1
                        pos_id = f"{sym}_{trade_id_counter}_BUY"
                        t1_rr = round(spot_close + (2.0 * risk_per_sh), 2)
                        be_trig = round(spot_close + (1.5 * risk_per_sh), 2)
                        be_ratchet = round(spot_close * 1.003, 2)

                        new_pos = CashPosition(
                            position_id=pos_id,
                            symbol=sym,
                            company_name=spec.name,
                            sector=spec.sector,
                            direction="BUY",
                            entry_time=current_time,
                            entry_price=spot_close,
                            initial_shares=final_sh,
                            current_shares=final_sh,
                            initial_stop_loss=stop_p,
                            current_stop_loss=stop_p,
                            target_1_rr=t1_rr,
                            target_2_macro=target_macro,
                            be_trigger_price=be_trig,
                            be_ratchet_price=be_ratchet,
                            risk_per_share=risk_per_sh
                        )
                        open_positions[sym] = new_pos
                        current_cash -= (final_sh * spot_close)
                        daily_trades_count[curr_date] += 1

            # ---------------------------------------------------------
            # STEP C: MARK-TO-MARKET PORTFOLIO VALUATION
            # ---------------------------------------------------------
            open_equity_val = 0.0
            for sym, pos in open_positions.items():
                df_15m = symbol_data[sym]
                if current_time in df_15m.index:
                    cur_p = float(df_15m.loc[current_time, "Close"])
                    open_equity_val += (pos.current_shares * cur_p)
                else:
                    open_equity_val += (pos.current_shares * pos.entry_price)

            total_portfolio_equity = current_cash + open_equity_val
            if total_portfolio_equity > peak_equity:
                peak_equity = total_portfolio_equity
            dd_pct = (peak_equity - total_portfolio_equity) / peak_equity * 100.0

            concurrent_history.append(len(open_positions))
            equity_records.append({
                "Datetime": current_time,
                "Equity": round(total_portfolio_equity, 2),
                "Cash": round(current_cash, 2),
                "Open_Positions": len(open_positions),
                "Peak_Equity": round(peak_equity, 2),
                "Drawdown_Pct": round(dd_pct, 2)
            })

        df_equity = pd.DataFrame(equity_records).set_index("Datetime") if equity_records else pd.DataFrame()

        # Scorecard metrics
        scorecard = PerformanceMetrics.calculate_cash_scorecard(
            trades=closed_trades,
            initial_capital=self.initial_capital,
            equity_curve=df_equity
        )

        # Monthly performance breakdown
        if not df_equity.empty:
            idx = df_equity.index.tz_localize(None) if df_equity.index.tz is not None else df_equity.index
            df_equity["year_month"] = idx.to_period("M")
        else:
            df_equity["year_month"] = []
        monthly_recs = []
        for ym, grp in df_equity.groupby("year_month"):
            start_eq = grp["Equity"].iloc[0]
            end_eq = grp["Equity"].iloc[-1]
            m_pnl = end_eq - start_eq
            m_ret = (m_pnl / start_eq) * 100.0
            monthly_recs.append({
                "Month": str(ym),
                "Starting_Equity": round(start_eq, 2),
                "Ending_Equity": round(end_eq, 2),
                "Monthly_Net_PnL": round(m_pnl, 2),
                "Monthly_Return_Pct": round(m_ret, 2)
            })
        df_monthly = pd.DataFrame(monthly_recs)

        # Stock breakdowns
        stock_breakdowns = {}
        for pos in closed_trades:
            if pos.symbol not in stock_breakdowns:
                stock_breakdowns[pos.symbol] = {"trades": 0, "wins": 0, "net_pnl": 0.0, "sector": pos.sector}
            stock_breakdowns[pos.symbol]["trades"] += 1
            if pos.net_pnl > 0:
                stock_breakdowns[pos.symbol]["wins"] += 1
            stock_breakdowns[pos.symbol]["net_pnl"] += pos.net_pnl

        # Sector breakdowns
        sector_breakdowns = {}
        for pos in closed_trades:
            if pos.sector not in sector_breakdowns:
                sector_breakdowns[pos.sector] = {"trades": 0, "net_pnl": 0.0}
            sector_breakdowns[pos.sector]["trades"] += 1
            sector_breakdowns[pos.sector]["net_pnl"] += pos.net_pnl

        days_count = max(1, len(daily_trades_count))
        avg_trades_day = round(len(closed_trades) / days_count, 2)
        avg_conc = round(float(np.mean(concurrent_history)), 2) if concurrent_history else 0.0
        max_conc = max(concurrent_history) if concurrent_history else 0

        return CashPortfolioBacktestResult(
            trades=closed_trades,
            equity_curve=df_equity,
            daily_performance=pd.DataFrame(),
            monthly_performance=df_monthly,
            scorecard=scorecard,
            stock_breakdowns=stock_breakdowns,
            sector_breakdowns=sector_breakdowns,
            avg_concurrent_positions=avg_conc,
            max_concurrent_positions=max_conc,
            trades_per_day=avg_trades_day
        )

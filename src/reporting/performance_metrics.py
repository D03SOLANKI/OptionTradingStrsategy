"""
Quantitative Performance Analytics Engine.
Calculates Net PnL, Win Rate, Profit Factor, Sharpe Ratio, Sortino Ratio, Calmar Ratio,
Maximum Drawdown, Expectancy, Payoff Ratio, Consecutive Losses, and MAE/MFE statistics.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import math
import numpy as np
import pandas as pd

from src.backtest.position import OptionPosition

@dataclass
class PerformanceScorecard:
    initial_capital: float
    final_equity: float
    net_profit: float
    return_pct: float
    gross_profit: float
    gross_loss: float
    total_friction_costs: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    loss_rate_pct: float
    profit_factor: float
    avg_trade_pnl: float
    avg_winning_trade: float
    avg_losing_trade: float
    payoff_ratio: float
    expectancy: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_bars: float
    avg_mfe: float
    avg_mae: float
    averaged_trades_count: int
    averaged_trades_win_rate: float
    non_averaged_trades_win_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class PerformanceMetrics:
    """
    Computes institutional performance scorecard from trade logs and equity curves.
    """

    @classmethod
    def calculate_scorecard(
        cls,
        trades: List[OptionPosition],
        equity_curve: pd.DataFrame,
        initial_capital: float = 500000.0,
        risk_free_rate: float = 0.065
    ) -> PerformanceScorecard:
        """
        Calculates all key risk-adjusted metrics.
        """
        if not trades:
            return PerformanceScorecard(
                initial_capital=initial_capital, final_equity=initial_capital,
                net_profit=0.0, return_pct=0.0, gross_profit=0.0, gross_loss=0.0,
                total_friction_costs=0.0, total_trades=0, winning_trades=0, losing_trades=0,
                win_rate_pct=0.0, loss_rate_pct=0.0, profit_factor=0.0, avg_trade_pnl=0.0,
                avg_winning_trade=0.0, avg_losing_trade=0.0, payoff_ratio=0.0, expectancy=0.0,
                max_drawdown_amount=0.0, max_drawdown_pct=0.0, sharpe_ratio=0.0,
                sortino_ratio=0.0, calmar_ratio=0.0, max_consecutive_wins=0,
                max_consecutive_losses=0, avg_holding_bars=0.0, avg_mfe=0.0, avg_mae=0.0,
                averaged_trades_count=0, averaged_trades_win_rate=0.0, non_averaged_trades_win_rate=0.0
            )

        net_pnls = [t.net_pnl for t in trades]
        gross_pnls = [t.gross_pnl for t in trades]
        friction = [t.costs.total_friction_cost for t in trades if t.costs is not None]

        total_trades = len(trades)
        winning_trades = [p for p in net_pnls if p > 0]
        losing_trades = [p for p in net_pnls if p <= 0]

        n_win = len(winning_trades)
        n_loss = len(losing_trades)
        win_rate = (n_win / total_trades) * 100.0 if total_trades > 0 else 0.0
        loss_rate = (n_loss / total_trades) * 100.0 if total_trades > 0 else 0.0

        gross_profit = sum(winning_trades)
        gross_loss = abs(sum(losing_trades))
        net_profit = sum(net_pnls)
        final_equity = initial_capital + net_profit
        return_pct = (net_profit / initial_capital) * 100.0
        total_friction = sum(friction)

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        avg_trade_pnl = net_profit / total_trades if total_trades > 0 else 0.0
        avg_win = (gross_profit / n_win) if n_win > 0 else 0.0
        avg_loss = (gross_loss / n_loss) if n_loss > 0 else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        p_win = n_win / total_trades if total_trades > 0 else 0.0
        p_loss = n_loss / total_trades if total_trades > 0 else 0.0
        expectancy = (p_win * avg_win) - (p_loss * avg_loss)

        # Max Consecutive Wins & Losses
        consec_wins = 0
        max_consec_wins = 0
        consec_losses = 0
        max_consec_losses = 0
        for p in net_pnls:
            if p > 0:
                consec_wins += 1
                consec_losses = 0
                max_consec_wins = max(max_consec_wins, consec_wins)
            else:
                consec_losses += 1
                consec_wins = 0
                max_consec_losses = max(max_consec_losses, consec_losses)

        # Drawdown calculation
        if not equity_curve.empty and "Equity" in equity_curve.columns:
            eq = equity_curve["Equity"]
            peak = eq.cummax()
            dd_amount = peak - eq
            dd_pct = dd_amount / peak
            max_dd_amount = float(dd_amount.max())
            max_dd_pct = float(dd_pct.max()) * 100.0
        else:
            # Fallback trade-level drawdown
            cum_pnl = np.cumsum(net_pnls)
            peak_pnl = np.maximum.accumulate(cum_pnl)
            dd = peak_pnl - cum_pnl
            max_dd_amount = float(np.max(dd)) if len(dd) > 0 else 0.0
            max_dd_pct = (max_dd_amount / initial_capital) * 100.0

        # Sharpe, Sortino, Calmar Ratios
        if not equity_curve.empty and len(equity_curve) > 1:
            returns = equity_curve["Equity"].pct_change().dropna()
            # Annualization factor for 15M candles: 252 days * 25 candles = 6300 bars/year
            bars_per_year = 252.0 * 25.0
            rf_per_bar = risk_free_rate / bars_per_year
            excess_returns = returns - rf_per_bar
            std_ret = float(returns.std())
            sharpe = (float(excess_returns.mean()) / std_ret * math.sqrt(bars_per_year)) if std_ret > 1e-8 else 0.0

            downside_returns = returns[returns < 0]
            downside_std = float(downside_returns.std())
            sortino = (float(excess_returns.mean()) / downside_std * math.sqrt(bars_per_year)) if downside_std > 1e-8 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0

        calmar = (return_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

        # Excursions & Holding duration
        mfe_list = [t.max_favorable_excursion for t in trades]
        mae_list = [t.max_adverse_excursion for t in trades]
        avg_mfe = float(np.mean(mfe_list)) if mfe_list else 0.0
        avg_mae = float(np.mean(mae_list)) if mae_list else 0.0

        # Averaging Analysis
        averaged_trades = [t for t in trades if t.is_averaged]
        non_averaged_trades = [t for t in trades if not t.is_averaged]
        avg_win_rate = (sum(1 for t in averaged_trades if t.net_pnl > 0) / len(averaged_trades) * 100.0) if averaged_trades else 0.0
        non_avg_win_rate = (sum(1 for t in non_averaged_trades if t.net_pnl > 0) / len(non_averaged_trades) * 100.0) if non_averaged_trades else 0.0

        return PerformanceScorecard(
            initial_capital=round(initial_capital, 2),
            final_equity=round(final_equity, 2),
            net_profit=round(net_profit, 2),
            return_pct=round(return_pct, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            total_friction_costs=round(total_friction, 2),
            total_trades=total_trades,
            winning_trades=n_win,
            losing_trades=n_loss,
            win_rate_pct=round(win_rate, 2),
            loss_rate_pct=round(loss_rate, 2),
            profit_factor=round(profit_factor, 2),
            avg_trade_pnl=round(avg_trade_pnl, 2),
            avg_winning_trade=round(avg_win, 2),
            avg_losing_trade=round(avg_loss, 2),
            payoff_ratio=round(payoff_ratio, 2),
            expectancy=round(expectancy, 2),
            max_drawdown_amount=round(max_dd_amount, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            calmar_ratio=round(calmar, 2),
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            avg_holding_bars=0.0,
            avg_mfe=round(avg_mfe, 2),
            avg_mae=round(avg_mae, 2),
            averaged_trades_count=len(averaged_trades),
            averaged_trades_win_rate=round(avg_win_rate, 2),
            non_averaged_trades_win_rate=round(non_avg_win_rate, 2)
        )

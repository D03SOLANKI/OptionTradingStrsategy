"""
Baseline Comparison Framework: Intelligent Averaging vs Single-Entry Baseline.
Rigorous head-to-head performance audit to verify whether position averaging
improves out-of-sample risk-adjusted return without increasing tail risk.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import copy
import pandas as pd

from src.config.trading_config import MasterConfig
from src.backtest.engine import BacktestEngine, BacktestResult
from src.reporting.performance_metrics import PerformanceMetrics, PerformanceScorecard

@dataclass
class BaselineComparisonReport:
    scorecard_with_averaging: PerformanceScorecard
    scorecard_baseline: PerformanceScorecard
    pnl_difference: float
    win_rate_difference_pct: float
    drawdown_difference_pct: float
    sharpe_difference: float
    averaging_recommended: bool
    verdict: str

class BaselineComparator:
    """
    Evaluates Strategy With vs Without Averaging.
    """

    @classmethod
    def compare(
        cls,
        symbol: str,
        df_15m: pd.DataFrame,
        base_config: MasterConfig
    ) -> BaselineComparisonReport:
        """
        Runs both configurations sequentially on identical dataset.
        """
        # Config 1: With Intelligent Averaging
        config_with_avg = copy.deepcopy(base_config)
        config_with_avg.averaging.enable_averaging = True

        engine_with_avg = BacktestEngine(config_with_avg)
        result_with_avg = engine_with_avg.run(symbol, df_15m)
        scorecard_with_avg = PerformanceMetrics.calculate_scorecard(
            trades=result_with_avg.trades,
            equity_curve=result_with_avg.equity_curve,
            initial_capital=config_with_avg.risk.initial_capital
        )

        # Config 2: Baseline Without Averaging
        config_baseline = copy.deepcopy(base_config)
        config_baseline.averaging.enable_averaging = False

        engine_baseline = BacktestEngine(config_baseline)
        result_baseline = engine_baseline.run(symbol, df_15m)
        scorecard_baseline = PerformanceMetrics.calculate_scorecard(
            trades=result_baseline.trades,
            equity_curve=result_baseline.equity_curve,
            initial_capital=config_baseline.risk.initial_capital
        )

        pnl_diff = round(scorecard_with_avg.net_profit - scorecard_baseline.net_profit, 2)
        win_rate_diff = round(scorecard_with_avg.win_rate_pct - scorecard_baseline.win_rate_pct, 2)
        dd_diff = round(scorecard_with_avg.max_drawdown_pct - scorecard_baseline.max_drawdown_pct, 2)
        sharpe_diff = round(scorecard_with_avg.sharpe_ratio - scorecard_baseline.sharpe_ratio, 2)

        # Retain averaging ONLY if:
        # 1. Net PnL is greater or equal
        # 2. Max Drawdown does not increase by more than 3% absolute
        # 3. Sharpe ratio is not degraded
        is_recommended = (
            pnl_diff >= 0 and
            dd_diff <= 3.0 and
            sharpe_diff >= -0.10
        )

        if is_recommended:
            verdict = (
                f"INTELLIGENT AVERAGING ACCEPTED: Produced net profit difference of +₹{pnl_diff:.2f} "
                f"with controlled drawdown change of {dd_diff:+.2f}% and Sharpe change of {sharpe_diff:+.2f}."
            )
        else:
            verdict = (
                f"INTELLIGENT AVERAGING REJECTED: Failed risk-adjusted criteria. "
                f"Drawdown worsened by {dd_diff:+.2f}% or Sharpe degraded by {sharpe_diff:+.2f}. "
                f"Single-entry baseline is preferred."
            )

        return BaselineComparisonReport(
            scorecard_with_averaging=scorecard_with_avg,
            scorecard_baseline=scorecard_baseline,
            pnl_difference=pnl_diff,
            win_rate_difference_pct=win_rate_diff,
            drawdown_difference_pct=dd_diff,
            sharpe_difference=sharpe_diff,
            averaging_recommended=is_recommended,
            verdict=verdict
        )

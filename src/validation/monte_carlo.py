"""
Monte Carlo Robustness Engine.
Performs trade sequence shuffling and bootstrap resampling (e.g. 1500 iterations)
to quantify drawdown distributions, risk of ruin, and parameter stability.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd

from src.backtest.position import OptionPosition

@dataclass
class MonteCarloReport:
    num_simulations: int
    median_final_equity: float
    equity_5th_percentile: float
    equity_95th_percentile: float
    median_max_drawdown_pct: float
    max_drawdown_95th_percentile_pct: float
    max_drawdown_99th_percentile_pct: float
    probability_of_ruin_pct: float    # Probability of drawdown > 25%
    sharpe_5th_percentile: float
    sharpe_median: float
    sharpe_95th_percentile: float

class MonteCarloSimulator:
    """
    Bootstrap Monte Carlo simulator for trade sequence uncertainty analysis.
    """

    @classmethod
    def run_simulation(
        cls,
        trades: List[OptionPosition],
        initial_capital: float = 500000.0,
        num_simulations: int = 1500,
        ruin_drawdown_threshold: float = 0.25,
        seed: int = 42
    ) -> MonteCarloReport:
        """
        Resamples trade PnLs with replacement across multiple synthetic paths.
        """
        if not trades:
            return MonteCarloReport(
                num_simulations=num_simulations,
                median_final_equity=initial_capital,
                equity_5th_percentile=initial_capital,
                equity_95th_percentile=initial_capital,
                median_max_drawdown_pct=0.0,
                max_drawdown_95th_percentile_pct=0.0,
                max_drawdown_99th_percentile_pct=0.0,
                probability_of_ruin_pct=0.0,
                sharpe_5th_percentile=0.0,
                sharpe_median=0.0,
                sharpe_95th_percentile=0.0
            )

        np.random.seed(seed)
        pnls = np.array([t.net_pnl for t in trades])
        n_trades = len(pnls)

        final_equities = []
        max_drawdowns = []
        sharpe_estimates = []
        ruin_count = 0

        for _ in range(num_simulations):
            sampled_pnls = np.random.choice(pnls, size=n_trades, replace=True)
            equity_curve = initial_capital + np.cumsum(sampled_pnls)
            final_eq = equity_curve[-1]
            final_equities.append(final_eq)

            # Max drawdown
            peak = np.maximum.accumulate(equity_curve)
            dd = (peak - equity_curve) / peak
            max_dd = float(np.max(dd))
            max_drawdowns.append(max_dd)

            if max_dd >= ruin_drawdown_threshold:
                ruin_count += 1

            # Trade-level Sharpe approximation
            mean_pnl = np.mean(sampled_pnls)
            std_pnl = np.std(sampled_pnls)
            sim_sharpe = (mean_pnl / std_pnl * np.sqrt(252)) if std_pnl > 1e-6 else 0.0
            sharpe_estimates.append(sim_sharpe)

        return MonteCarloReport(
            num_simulations=num_simulations,
            median_final_equity=round(float(np.median(final_equities)), 2),
            equity_5th_percentile=round(float(np.percentile(final_equities, 5)), 2),
            equity_95th_percentile=round(float(np.percentile(final_equities, 95)), 2),
            median_max_drawdown_pct=round(float(np.median(max_drawdowns)) * 100.0, 2),
            max_drawdown_95th_percentile_pct=round(float(np.percentile(max_drawdowns, 95)) * 100.0, 2),
            max_drawdown_99th_percentile_pct=round(float(np.percentile(max_drawdowns, 99)) * 100.0, 2),
            probability_of_ruin_pct=round((ruin_count / num_simulations) * 100.0, 2),
            sharpe_5th_percentile=round(float(np.percentile(sharpe_estimates, 5)), 2),
            sharpe_median=round(float(np.median(sharpe_estimates)), 2),
            sharpe_95th_percentile=round(float(np.percentile(sharpe_estimates, 95)), 2)
        )

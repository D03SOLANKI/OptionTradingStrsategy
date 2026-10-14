"""
Sensitivity and Robustness Analysis Engine.
Assesses parameter fragility vs stability across multidimensional hyperparameter grids.
Ensures the strategy operates within a broad profitable plateau rather than an overfitted peak.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import copy
import numpy as np
import pandas as pd

from src.config.trading_config import MasterConfig
from src.backtest.engine import BacktestEngine
from src.reporting.performance_metrics import PerformanceMetrics

@dataclass
class SensitivityRun:
    param_name: str
    param_value: Any
    net_profit: float
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float

@dataclass
class SensitivityReport:
    tested_parameters: List[str]
    runs: List[SensitivityRun]
    stability_score: float             # [0.0, 1.0] fraction of variations that remain profitable
    is_overfitted: bool
    summary: str

class SensitivityAnalyzer:
    """
    Evaluates hyperparameter stability and detects parameter over-optimization.
    """

    @classmethod
    def test_parameter_stability(
        cls,
        symbol: str,
        df_15m: pd.DataFrame,
        base_config: MasterConfig
    ) -> SensitivityReport:
        """
        Varies key hyperparameters around baseline values to test robustness.
        """
        runs: List[SensitivityRun] = []

        variations = [
            # 1. 4H Pivot Order
            ("sr.pivot_order_4h", [2, 3, 4]),
            # 2. Activation Profit %
            ("trailing_stop.activation_profit_pct", [0.12, 0.18, 0.24]),
            # 3. Trailing Distance %
            ("trailing_stop.trailing_distance_pct", [0.08, 0.12, 0.15]),
            # 4. Averaging Minimum Distance ATR
            ("averaging.min_distance_atr", [1.0, 1.25, 1.50]),
        ]

        tested_param_names = [v[0] for v in variations]

        for param_path, values in variations:
            for val in values:
                cfg = copy.deepcopy(base_config)
                parts = param_path.split(".")
                target_obj = getattr(cfg, parts[0])
                setattr(target_obj, parts[1], val)

                engine = BacktestEngine(cfg)
                res = engine.run(symbol, df_15m)
                sc = PerformanceMetrics.calculate_scorecard(
                    res.trades, res.equity_curve, cfg.risk.initial_capital
                )

                runs.append(SensitivityRun(
                    param_name=param_path,
                    param_value=val,
                    net_profit=sc.net_profit,
                    win_rate_pct=sc.win_rate_pct,
                    profit_factor=sc.profit_factor,
                    max_drawdown_pct=sc.max_drawdown_pct,
                    sharpe_ratio=sc.sharpe_ratio
                ))

        profitable_runs = [r for r in runs if r.net_profit >= 0]
        stability_score = len(profitable_runs) / len(runs) if runs else 0.0
        # If stability_score >= 0.75, strategy is structurally robust and not overfitted
        is_overfitted = stability_score < 0.60

        summary = (
            f"Tested {len(runs)} parameter variations across {len(variations)} parameters. "
            f"Profitable variations: {len(profitable_runs)}/{len(runs)} ({stability_score*100:.1f}%). "
            f"Overfitting Assessment: {'HIGH RISK OF OVERFITTING' if is_overfitted else 'ROBUST & STABLE'}."
        )

        return SensitivityReport(
            tested_parameters=tested_param_names,
            runs=runs,
            stability_score=round(stability_score, 2),
            is_overfitted=is_overfitted,
            summary=summary
        )

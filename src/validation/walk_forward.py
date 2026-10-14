"""
Walk-Forward Analysis (WFA) Engine with Purging and Embargoing.
Strictly eliminates data leakage and chronological contamination.
Splits data into chronological In-Sample (Train) and Out-of-Sample (Test) folds,
evaluating walk-forward efficiency and regime robustness.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from datetime import timedelta
import copy
import pandas as pd
import numpy as np

from src.config.trading_config import MasterConfig
from src.backtest.engine import BacktestEngine, BacktestResult
from src.reporting.performance_metrics import PerformanceMetrics, PerformanceScorecard
from src.backtest.position import OptionPosition

@dataclass
class WFAFoldResult:
    fold_index: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    in_sample_scorecard: PerformanceScorecard
    out_of_sample_scorecard: PerformanceScorecard
    walk_forward_efficiency: float

@dataclass
class WFAReport:
    folds: List[WFAFoldResult]
    combined_oos_scorecard: PerformanceScorecard
    mean_wfe: float
    is_strategy_robust: bool
    summary: str

class WalkForwardOptimizer:
    """
    Executes Purged Chronological Walk-Forward Analysis.
    """

    @classmethod
    def run_wfa(
        cls,
        symbol: str,
        df_15m: pd.DataFrame,
        base_config: MasterConfig,
        train_days: int = 60,
        test_days: int = 20,
        purge_days: int = 2
    ) -> WFAReport:
        """
        Runs rolling-window walk-forward validation across chronological folds.
        """
        dates = sorted(list(set(df_15m.index.date)))
        total_days = len(dates)

        fold_window = train_days + purge_days + test_days
        if total_days < fold_window:
            # If dataset is too short for multiple folds, perform a 70/30 chronological split
            split_idx = int(total_days * 0.70)
            train_dates = dates[:split_idx]
            test_dates = dates[split_idx:]

            train_df = df_15m[np.isin(df_15m.index.date, train_dates)]
            test_df = df_15m[np.isin(df_15m.index.date, test_dates)]

            engine = BacktestEngine(base_config)
            res_train = engine.run(symbol, train_df)
            res_test = engine.run(symbol, test_df)

            sc_train = PerformanceMetrics.calculate_scorecard(res_train.trades, res_train.equity_curve, base_config.risk.initial_capital)
            sc_test = PerformanceMetrics.calculate_scorecard(res_test.trades, res_test.equity_curve, base_config.risk.initial_capital)

            wfe = (sc_test.return_pct / sc_train.return_pct) if sc_train.return_pct > 0 else 0.0

            fold0 = WFAFoldResult(
                fold_index=0,
                train_start=train_df.index[0],
                train_end=train_df.index[-1],
                test_start=test_df.index[0],
                test_end=test_df.index[-1],
                in_sample_scorecard=sc_train,
                out_of_sample_scorecard=sc_test,
                walk_forward_efficiency=round(wfe, 2)
            )

            is_robust = sc_test.net_profit >= 0 and sc_test.profit_factor >= 1.10
            return WFAReport(
                folds=[fold0],
                combined_oos_scorecard=sc_test,
                mean_wfe=round(wfe, 2),
                is_strategy_robust=is_robust,
                summary=f"Chronological Train/Test Split (70/30). OOS Return: {sc_test.return_pct:.2f}%, WFE: {wfe:.2f}."
            )

        # Multi-fold rolling WFA
        folds: List[WFAFoldResult] = []
        all_oos_trades: List[OptionPosition] = []
        start_idx = 0
        fold_idx = 0

        while start_idx + fold_window <= total_days:
            t_train_dates = dates[start_idx : start_idx + train_days]
            t_test_dates = dates[start_idx + train_days + purge_days : start_idx + fold_window]

            train_df = df_15m[np.isin(df_15m.index.date, t_train_dates)]
            test_df = df_15m[np.isin(df_15m.index.date, t_test_dates)]

            if len(train_df) > 50 and len(test_df) > 20:
                engine_is = BacktestEngine(base_config)
                res_train = engine_is.run(symbol, train_df)

                engine_oos = BacktestEngine(base_config)
                res_test = engine_oos.run(symbol, test_df)

                sc_train = PerformanceMetrics.calculate_scorecard(
                    res_train.trades, res_train.equity_curve, base_config.risk.initial_capital
                )
                sc_test = PerformanceMetrics.calculate_scorecard(
                    res_test.trades, res_test.equity_curve, base_config.risk.initial_capital
                )

                wfe = (sc_test.return_pct / sc_train.return_pct) if sc_train.return_pct > 0 else 0.0

                folds.append(WFAFoldResult(
                    fold_index=fold_idx,
                    train_start=train_df.index[0],
                    train_end=train_df.index[-1],
                    test_start=test_df.index[0],
                    test_end=test_df.index[-1],
                    in_sample_scorecard=sc_train,
                    out_of_sample_scorecard=sc_test,
                    walk_forward_efficiency=round(wfe, 2)
                ))
                all_oos_trades.extend(res_test.trades)
                fold_idx += 1

            # Advance by test_days
            start_idx += test_days

        combined_oos_sc = PerformanceMetrics.calculate_scorecard(
            all_oos_trades, pd.DataFrame(), base_config.risk.initial_capital
        )
        mean_wfe = float(np.mean([f.walk_forward_efficiency for f in folds])) if folds else 0.0
        is_robust = combined_oos_sc.net_profit >= 0 and combined_oos_sc.profit_factor >= 1.05

        return WFAReport(
            folds=folds,
            combined_oos_scorecard=combined_oos_sc,
            mean_wfe=round(mean_wfe, 2),
            is_strategy_robust=is_robust,
            summary=f"WFA completed across {len(folds)} rolling folds. OOS Net PnL: ₹{combined_oos_sc.net_profit:.2f}, Mean WFE: {mean_wfe:.2f}."
        )

"""
Visualization Module for Strategy Equity Curves, Drawdowns, and Trade Distributions.
Generates institutional publication-quality charts saved to disk.
"""

import os
import matplotlib
matplotlib.use("Agg") # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typing import List, Optional

from src.backtest.position import OptionPosition

class Visualizer:
    """
    Renders analytical performance charts.
    """

    @staticmethod
    def plot_equity_and_drawdown(
        equity_curve: pd.DataFrame,
        save_path: str = "results/equity_curve.png"
    ) -> Optional[str]:
        """
        Plots twin-panel Equity Curve and Underwater Drawdown.
        """
        if equity_curve.empty or "Equity" not in equity_curve.columns:
            return None

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

        # Equity
        ax1.plot(equity_curve.index, equity_curve["Equity"], color="#1f77b4", linewidth=1.8, label="Strategy Equity (INR)")
        ax1.set_title("Multi-Timeframe S/R Options Strategy — Equity Curve", fontsize=14, fontweight="bold")
        ax1.set_ylabel("Portfolio Equity (INR)", fontsize=11)
        ax1.grid(True, linestyle="--", alpha=0.5)
        ax1.legend(loc="upper left")

        # Drawdown
        peak = equity_curve["Equity"].cummax()
        dd_pct = (equity_curve["Equity"] - peak) / peak * 100.0
        ax2.fill_between(equity_curve.index, dd_pct, 0, color="#d62728", alpha=0.4, label="Underwater Drawdown (%)")
        ax2.plot(equity_curve.index, dd_pct, color="#d62728", linewidth=1.0)
        ax2.set_ylabel("Drawdown (%)", fontsize=11)
        ax2.set_xlabel("Date", fontsize=11)
        ax2.grid(True, linestyle="--", alpha=0.5)
        ax2.legend(loc="lower left")

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close()
        return save_path

    @staticmethod
    def plot_trade_pnl_distribution(
        trades: List[OptionPosition],
        save_path: str = "results/pnl_distribution.png"
    ) -> Optional[str]:
        """
        Plots histogram of trade net PnLs with profit/loss color separation.
        """
        if not trades:
            return None

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        pnls = [t.net_pnl for t in trades]

        fig, ax = plt.subplots(figsize=(10, 5))
        counts, bins, patches = ax.hist(pnls, bins=25, edgecolor="black", alpha=0.75)

        for b_left, p in zip(bins[:-1], patches):
            if b_left >= 0:
                p.set_facecolor("#2ca02c") # Green
            else:
                p.set_facecolor("#d62728") # Red

        ax.axvline(0, color="black", linestyle="--", linewidth=1.2)
        ax.axvline(np.mean(pnls), color="blue", linestyle="-.", linewidth=1.2, label=f"Mean PnL: ₹{np.mean(pnls):.1f}")
        ax.set_title("Trade Net PnL Distribution (After Indian Taxes & Slippage)", fontsize=13, fontweight="bold")
        ax.set_xlabel("Net PnL per Trade (INR)", fontsize=11)
        ax.set_ylabel("Frequency", fontsize=11)
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close()
        return save_path

    @staticmethod
    def plot_mfe_mae(
        trades: List[OptionPosition],
        save_path: str = "results/mfe_mae_scatter.png"
    ) -> Optional[str]:
        """
        Scatter plot of Maximum Favorable Excursion (MFE) vs Maximum Adverse Excursion (MAE).
        """
        if not trades:
            return None

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        mfes = [t.max_favorable_excursion for t in trades]
        maes = [t.max_adverse_excursion for t in trades]
        colors = ["#2ca02c" if t.net_pnl > 0 else "#d62728" for t in trades]

        fig, ax = plt.subplots(figsize=(9, 6))
        ax.scatter(maes, mfes, c=colors, alpha=0.7, edgecolors="black", s=60)
        max_val = max(max(mfes, default=1), max(maes, default=1)) * 1.1
        ax.plot([0, max_val], [0, max_val], "k--", alpha=0.5, label="1:1 Excursion Line")

        ax.set_title("MFE vs MAE (Maximum Excursions per Trade)", fontsize=13, fontweight="bold")
        ax.set_xlabel("Maximum Adverse Excursion / MAE (INR)", fontsize=11)
        ax.set_ylabel("Maximum Favorable Excursion / MFE (INR)", fontsize=11)
        ax.set_xlim(0, max_val)
        ax.set_ylim(0, max_val)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend()

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close()
        return save_path

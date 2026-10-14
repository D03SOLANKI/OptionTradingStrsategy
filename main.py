"""
Main Strategy Runner and Optimization CLI.
Executes end-to-end Multi-Timeframe S/R Options Trading Strategy:
Data Fetching, Backtesting, Baseline Comparison, Monte Carlo Simulation,
Walk-Forward Optimization, Sensitivity Grids, Chart Generation, and Report Publishing.
"""

import os
import sys
import argparse
from datetime import datetime
import pandas as pd

# Ensure UTF-8 output encoding on Windows console
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import get_symbol_spec
from src.data.market_data_feed import MarketDataFeed
from src.backtest.engine import BacktestEngine
from src.reporting.performance_metrics import PerformanceMetrics
from src.reporting.visualizer import Visualizer
from src.reporting.report_generator import ReportGenerator
from src.validation.baseline_comparison import BaselineComparator
from src.validation.monte_carlo import MonteCarloSimulator
from src.validation.walk_forward import WalkForwardOptimizer
from src.validation.sensitivity import SensitivityAnalyzer

def main():
    parser = argparse.ArgumentParser(
        description="Institutional Automated Stock Options Trading Strategy (Multi-Timeframe 4H & 15M S/R)"
    )
    parser.add_argument("--symbol", type=str, default="RELIANCE", help="NSE F&O Symbol (e.g., RELIANCE, TCS, INFY)")
    parser.add_argument("--mode", type=str, choices=["real", "synthetic", "compare", "wfa", "sensitivity", "full"], default="full", help="Execution mode")
    parser.add_argument("--capital", type=float, default=500000.0, help="Initial portfolio capital in INR")
    parser.add_argument("--output-dir", type=str, default="results", help="Directory to save audit reports and charts")
    parser.add_argument("--no-averaging", action="store_true", help="Disable position averaging")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    symbol = args.symbol.upper().replace(".NS", "")
    spec = get_symbol_spec(symbol)

    print("=" * 80)
    print(f"  MULTI-TIMEFRAME S/R OPTIONS TRADING STRATEGY (4H & 15M)")
    print(f"  Symbol: {spec.name} ({spec.symbol}) | Lot Size: {spec.lot_size} | Sector: {spec.sector}")
    print(f"  Mode: {args.mode.upper()} | Initial Capital: ₹{args.capital:,.2f}")
    print("=" * 80)

    # 1. Initialize Master Configuration
    config = MasterConfig()
    config.risk.initial_capital = args.capital
    if args.no_averaging:
        config.averaging.enable_averaging = False

    feed = MarketDataFeed(cache_dir="data/raw")

    # 2. Acquire Market Data
    if args.mode in ["real", "compare", "full"]:
        print(f"\n[+] Fetching recent 15M intraday market data for {spec.yf_ticker}...")
        try:
            df_15m = feed.fetch_yfinance_data(symbol, period="60d", interval="15m")
            print(f"    Loaded {len(df_15m)} bars from {df_15m.index[0]} to {df_15m.index[-1]}.")
        except Exception as e:
            print(f"    [!] Warning: Failed fetching real data ({e}). Generating high-fidelity calibrated data...")
            df_15m = feed.generate_synthetic_regime_data(symbol=symbol, num_days=90, regime="MULTI_REGIME")
    else:
        print(f"\n[+] Generating 180-day calibrated multi-regime intraday market data for {symbol}...")
        df_15m = feed.generate_synthetic_regime_data(symbol=symbol, num_days=180, regime="MULTI_REGIME")
        print(f"    Generated {len(df_15m)} bars across Bull, Bear, and Sideways regimes.")

    # 3. Execute Primary Backtest
    print("\n[+] Running chronological backtest with zero look-ahead bias...")
    engine = BacktestEngine(config)
    result = engine.run(symbol, df_15m)

    scorecard = PerformanceMetrics.calculate_scorecard(
        trades=result.trades,
        equity_curve=result.equity_curve,
        initial_capital=config.risk.initial_capital
    )

    print("\n" + "=" * 50)
    print("  PRIMARY BACKTEST PERFORMANCE SCORECARD")
    print("=" * 50)
    print(f"  Starting Capital    : ₹{scorecard.initial_capital:,.2f}")
    print(f"  Final Equity        : ₹{scorecard.final_equity:,.2f}")
    print(f"  Net Profit          : ₹{scorecard.net_profit:,.2f} ({scorecard.return_pct:+.2f}%)")
    print(f"  Gross Profit / Loss : ₹{scorecard.gross_profit:,.2f} / ₹{scorecard.gross_loss:,.2f}")
    print(f"  Indian Friction Cost: ₹{scorecard.total_friction_costs:,.2f}")
    print(f"  Total Trades        : {scorecard.total_trades} (Wins: {scorecard.winning_trades}, Losses: {scorecard.losing_trades})")
    print(f"  Win Rate            : {scorecard.win_rate_pct:.1f}%")
    print(f"  Profit Factor       : {scorecard.profit_factor:.2f}")
    print(f"  Expectancy / Trade  : ₹{scorecard.expectancy:,.2f}")
    print(f"  Max Drawdown        : ₹{scorecard.max_drawdown_amount:,.2f} ({scorecard.max_drawdown_pct:.2f}%)")
    print(f"  Sharpe Ratio        : {scorecard.sharpe_ratio:.2f}")
    print(f"  Max Consec Losses   : {scorecard.max_consecutive_losses}")
    print(f"  Averaged Trades     : {scorecard.averaged_trades_count} (Win Rate: {scorecard.averaged_trades_win_rate:.1f}%)")
    print("=" * 50)

    # 4. Generate Visual Charts
    print("\n[+] Generating visual charts...")
    chart_eq = Visualizer.plot_equity_and_drawdown(result.equity_curve, os.path.join(args.output_dir, "equity_curve.png"))
    chart_pnl = Visualizer.plot_trade_pnl_distribution(result.trades, os.path.join(args.output_dir, "pnl_distribution.png"))
    chart_mfe = Visualizer.plot_mfe_mae(result.trades, os.path.join(args.output_dir, "mfe_mae_scatter.png"))
    if chart_eq:
        print(f"    Saved: {chart_eq}")
    if chart_pnl:
        print(f"    Saved: {chart_pnl}")
    if chart_mfe:
        print(f"    Saved: {chart_mfe}")

    # 5. Baseline Comparison (Intelligent Averaging vs Single-Entry)
    baseline_report = None
    if args.mode in ["compare", "full"]:
        print("\n[+] Running Baseline Comparison: With Averaging vs Single-Entry Baseline...")
        baseline_report = BaselineComparator.compare(symbol, df_15m, config)
        print(f"    {baseline_report.verdict}")
        print(f"    Net PnL Difference      : {baseline_report.pnl_difference:+,.2f} ₹")
        print(f"    Win Rate Difference     : {baseline_report.win_rate_difference_pct:+.1f}%")
        print(f"    Max Drawdown Difference : {baseline_report.drawdown_difference_pct:+.2f}%")

    # 6. Bootstrap Monte Carlo Simulation
    monte_carlo_report = None
    if args.mode in ["full"]:
        print("\n[+] Running Bootstrap Monte Carlo Simulation (1,500 iterations)...")
        monte_carlo_report = MonteCarloSimulator.run_simulation(
            trades=result.trades,
            initial_capital=config.risk.initial_capital,
            num_simulations=1500
        )
        print(f"    Median Equity           : ₹{monte_carlo_report.median_final_equity:,.2f}")
        print(f"    5th - 95th Pct Equity   : ₹{monte_carlo_report.equity_5th_percentile:,.2f} to ₹{monte_carlo_report.equity_95th_percentile:,.2f}")
        print(f"    95% VaR Max Drawdown    : {monte_carlo_report.max_drawdown_95th_percentile_pct:.2f}%")
        print(f"    Probability of Ruin     : {monte_carlo_report.probability_of_ruin_pct:.2f}%")

    # 7. Walk-Forward Analysis (WFA)
    wfa_report = None
    if args.mode in ["wfa", "full"]:
        print("\n[+] Running Chronological Purged Walk-Forward Analysis...")
        wfa_report = WalkForwardOptimizer.run_wfa(
            symbol=symbol,
            df_15m=df_15m,
            base_config=config,
            train_days=45,
            test_days=15,
            purge_days=2
        )
        print(f"    {wfa_report.summary}")
        print(f"    Robustness Assessment   : {'ROBUST OUT-OF-SAMPLE' if wfa_report.is_strategy_robust else 'FRAGILE'}")

    # 8. Sensitivity Analysis
    sensitivity_report = None
    if args.mode in ["sensitivity", "full"]:
        print("\n[+] Running Parameter Sensitivity & Robustness Grid...")
        sensitivity_report = SensitivityAnalyzer.test_parameter_stability(symbol, df_15m, config)
        print(f"    {sensitivity_report.summary}")

    # 9. Export Trade Logs and Markdown Audit Report
    print("\n[+] Exporting granular audit reports...")
    csv_path = ReportGenerator.export_trade_log_csv(result.trades, os.path.join(args.output_dir, "trade_log.csv"))
    md_path = ReportGenerator.generate_markdown_report(
        scorecard=scorecard,
        baseline_report=baseline_report,
        monte_carlo_report=monte_carlo_report,
        wfa_report=wfa_report,
        sensitivity_report=sensitivity_report,
        output_path=os.path.join(args.output_dir, "strategy_audit_report.md")
    )
    print(f"    Exported Trade Log   : {csv_path}")
    print(f"    Exported Audit Report: {md_path}")
    print("\n" + "=" * 80)
    print("  STRATEGY EXECUTION & VALIDATION COMPLETE")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()

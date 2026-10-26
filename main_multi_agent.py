"""
Main Entry Point for the 5-Agent AI Stock Trading System (Indian Cash Market / NSE).
Executes the MultiAgentOrchestrator, streams real-time transparent activity to the terminal,
generates individual agent reports, and exports the live interactive HTML dashboard.
"""

import os
import sys
import argparse
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime

# Enforce UTF-8 on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import NSE_FO_UNIVERSE, get_symbol_spec
from src.data.market_data_feed import MarketDataFeed
from src.agents.orchestrator import MultiAgentOrchestrator, MultiAgentExecutionResult
from src.reporting.agent_dashboard_generator import AgentDashboardGenerator

def run_multi_agent_system(
    symbols: Optional[List[str]] = None,
    timestamp_str: Optional[str] = None,
    initial_capital: float = 1000000.0,
    min_rr: float = 1.5,
    min_confidence: float = 0.60,
    output_dir: str = "results/multi_agent"
):
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 100)
    print("   5-AGENT AI STOCK TRADING SYSTEM (NSE CASH MARKET)")
    print(f"   Unified Portfolio Capital: ₹{initial_capital:,.2f} (10 Lakhs INR)")
    print("   Architecture: 5 Autonomous Specialized Agents with Full Transparency")
    print("=" * 100)

    # Ingest Data
    feed = MarketDataFeed(cache_dir="data/raw")
    universe_data: Dict[str, pd.DataFrame] = {}

    target_symbols = symbols or [
        # Balanced Multi-Cap Basket across Large, Mid, and Small Cap
        "TCS", "RELIANCE", "ICICIBANK", "SBIN", "LT", "BHARTIARTL", "SUNPHARMA",
        "POLYCAB", "PERSISTENT", "COFORGE", "VOLTAS", "AUROPHARMA",
        "BSOFT", "NATIONALUM", "RBLBANK", "IDFCFIRSTB", "CHAMBLFERT"
    ]

    print(f"\n[+] Ingesting 15M cash equity market data for {len(target_symbols)} stocks...")
    for sym in target_symbols:
        spec = get_symbol_spec(sym)
        print(f"    - [{spec.cap_category:<9}] {sym:<11} | {spec.name:<30}", end="")
        try:
            df = feed.get_stock_data(sym, period="60d", interval="15m")
            universe_data[sym] = df
            print(f" -> Loaded ({len(df)} bars)")
        except Exception as e:
            print(f" -> Error: {e}")

    # Initialize Orchestrator
    config = MasterConfig()
    orchestrator = MultiAgentOrchestrator(
        config=config,
        initial_capital=initial_capital,
        min_rr=min_rr,
        min_system_confidence=min_confidence
    )

    # Attach live terminal activity listener
    def console_streamer(log_entry):
        tag_colors = {
            "INFO": "\033[94m[INFO]\033[0m",
            "CALCULATION": "\033[92m[CALC]\033[0m",
            "DECISION": "\033[93m[DECISION]\033[0m",
            "COMMUNICATION": "\033[95m[MSG]\033[0m",
            "WARNING": "\033[33m[WARN]\033[0m",
            "ERROR": "\033[91m[ERROR]\033[0m"
        }
        ts = log_entry.timestamp.strftime("%H:%M:%S")
        tag = tag_colors.get(log_entry.log_type, f"[{log_entry.log_type}]")
        sym_str = f"({log_entry.symbol}) " if log_entry.symbol else ""
        print(f"  {ts} {tag} [{log_entry.agent_id[:10]}] {sym_str}{log_entry.message}")

    orchestrator.bus.subscribe(console_streamer)

    eval_ts = None
    if timestamp_str:
        eval_ts = pd.Timestamp(timestamp_str)
        if eval_ts.tz is None:
            eval_ts = eval_ts.tz_localize("Asia/Kolkata")

    print(f"\n[+] Initiating 5-Agent Execution Workflow (Target Timestamp: {eval_ts or 'LATEST'})...\n")
    result: MultiAgentExecutionResult = orchestrator.execute_workflow(
        universe_data=universe_data,
        evaluation_timestamp=eval_ts,
        trade_mode="DELIVERY",
        available_cash=initial_capital
    )

    # Print Executive Summary to Console
    print("\n" + "=" * 100)
    print(f"   FINAL MULTI-AGENT EXECUTION VERDICT: {result.execution_verdict}")
    print(f"   Total Pipeline Latency: {result.total_execution_time_ms:.2f} ms | Timestamp: {result.timestamp}")
    print(f"   Stocks Scanned: {result.stocks_scanned_count} | Approved Recommendations: {result.qualified_count}")
    print("=" * 100)

    if result.final_recommendations:
        print("\n" + "-" * 100)
        print("   APPROVED CASH EQUITY TRADE EXECUTION BLUEPRINTS")
        print("-" * 100)
        for idx, rec in enumerate(result.final_recommendations):
            print(f"\n[TRADE #{idx+1}] {rec.symbol} ({rec.company_name}) — {rec.verdict} (CASH EQUITY)")
            print(f"    Category: {rec.cap_category} | System Confidence: {rec.system_confidence*100:.1f}% | R:R Ratio: {rec.risk_reward_ratio:.2f}:1")
            print(f"    * Entry Price       : ₹{rec.entry_price:,.2f}")
            print(f"    * Stop-Loss         : ₹{rec.initial_stop_loss:,.2f}")
            print(f"    * Target 1 (1:2 R:R): ₹{rec.target_1_rr:,.2f} (Book 50% shares)")
            print(f"    * Target 2 (4H Macro: ₹{rec.target_2_macro:,.2f} (Full target)")
            print(f"    * Position Size     : {rec.shares_quantity} Shares (Capital Deployed: ₹{rec.capital_deployed:,.2f})")
            print(f"    * Max Permitted Risk: ₹{rec.max_risk_inr:,.2f} (Strict downside cap)")
            print(f"    * Round-Trip Taxes  : ₹{rec.friction_cost_inr:,.2f} (Zerodha/NSE delivery schedule)")
            print(f"    * Trailing Stop Plan: {rec.trailing_stop_plan}")
            print(f"    * Reasoning         : {rec.detailed_reasoning}")
    else:
        print("\n[!] VERDICT: NO TRADE")
        print("    None of the scanned multi-cap stocks satisfied unanimous 5-agent institutional criteria.")
        print("    Capital is 100% preserved in cash buffer.")

    # Generate Reports & Artifacts
    print("\n[+] Generating Agent-Level Reports & Interactive Dashboard...")
    dashboard_path = os.path.join(output_dir, "agent_transparency_dashboard.html")
    AgentDashboardGenerator.generate_html_dashboard(result, dashboard_path)
    print(f"    -> Interactive Dashboard: {dashboard_path}")

    # Save Agent Markdown Reports
    for aid, rep in result.agent_reports.items():
        rep_file = os.path.join(output_dir, f"{aid.lower()}_report.md")
        with open(rep_file, "w", encoding="utf-8") as f:
            f.write(rep.to_markdown())
        print(f"    -> Saved Agent Report: {rep_file}")

    # Save Master Audit Summary
    master_summary_file = os.path.join(output_dir, "multi_agent_audit_report.md")
    with open(master_summary_file, "w", encoding="utf-8") as f:
        f.write(f"# Multi-Agent AI Stock Trading System — Execution Audit Report\n\n")
        f.write(f"**Execution Timestamp**: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Final Verdict**: `{result.execution_verdict}`  \n")
        f.write(f"**Total Latency**: {result.total_execution_time_ms:.2f} ms  \n")
        f.write(f"**Stocks Scanned**: {result.stocks_scanned_count} | **Approved Trades**: {result.qualified_count}\n\n")
        f.write("## 1. Executive Trade Recommendations\n\n")
        if result.final_recommendations:
            for rec in result.final_recommendations:
                f.write(f"### {rec.symbol} — {rec.verdict} ({rec.shares_quantity} Shares)\n")
                f.write(f"- **Company**: {rec.company_name} ({rec.cap_category})\n")
                f.write(f"- **Entry**: ₹{rec.entry_price:,.2f} | **Stop Loss**: ₹{rec.initial_stop_loss:,.2f}\n")
                f.write(f"- **Target 1**: ₹{rec.target_1_rr:,.2f} | **Target 2**: ₹{rec.target_2_macro:,.2f}\n")
                f.write(f"- **Capital Deployed**: ₹{rec.capital_deployed:,.2f} | **Max Risk**: ₹{rec.max_risk_inr:,.2f}\n")
                f.write(f"- **Confidence**: {rec.system_confidence*100:.1f}% | **R:R**: {rec.risk_reward_ratio:.2f}:1\n")
                f.write(f"- **Trailing Stop**: {rec.trailing_stop_plan}\n")
                f.write(f"- **Reasoning**: {rec.detailed_reasoning}\n\n")
        else:
            f.write("> **NO TRADE**: No stock met institutional criteria. Capital is 100% in cash buffer.\n\n")

        f.write("## 2. Inter-Agent Communication Audit Trail\n\n")
        f.write("| Message ID | Timestamp | Sender | Recipient | Type | Summary |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for m in result.inter_agent_messages:
            f.write(f"| `{m.message_id}` | {m.timestamp.strftime('%H:%M:%S.%f')[:-3]} | `{m.sender_agent}` | `{m.recipient_agent}` | `{m.message_type}` | {m.payload_summary} |\n")

    print(f"    -> Master Audit Report: {master_summary_file}")

    # Copy HTML dashboard to artifact directory as well
    app_artifact_dir = "C:\\Users\\DEV SOLANKI\\.gemini\\antigravity\\brain\\10d8365f-b6a6-4124-8f85-dcf58eb257b0"
    if os.path.exists(app_artifact_dir):
        artifact_dash = os.path.join(app_artifact_dir, "agent_transparency_dashboard.html")
        AgentDashboardGenerator.generate_html_dashboard(result, artifact_dash)
        print(f"    -> Saved to Conversation Artifact Directory: {artifact_dash}")

    print("\n" + "=" * 100)
    print("   MULTI-AGENT PIPELINE EXECUTION COMPLETED")
    print("=" * 100)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="5-Agent AI Stock Trading System (NSE Cash Market)")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated stock symbols")
    parser.add_argument("--timestamp", type=str, default=None, help="Evaluation timestamp (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--capital", type=float, default=1000000.0, help="Unified cash portfolio capital in INR")
    parser.add_argument("--min-rr", type=float, default=1.5, help="Minimum Risk-to-Reward ratio (default: 1.5)")
    parser.add_argument("--min-confidence", type=float, default=0.60, help="Minimum multi-agent system confidence (default: 0.60)")
    args = parser.parse_args()

    syms = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None
    run_multi_agent_system(
        symbols=syms,
        timestamp_str=args.timestamp,
        initial_capital=args.capital,
        min_rr=args.min_rr,
        min_confidence=args.min_confidence
    )


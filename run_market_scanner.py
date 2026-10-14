"""
NSE Multi-Cap Options Scanner & Opportunity Ranking Runner.
Scans all eligible Large-Cap, Mid-Cap, and Small-Cap F&O stocks.
Analyzes 4H Major S/R levels + 15M Entry Reversal Confirmations.
Ranks all candidates and produces actionable TradePlans or NO_TRADE verdicts.
"""

import sys
import argparse
import pandas as pd
from datetime import datetime

# Enforce UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import NSE_FO_UNIVERSE, SymbolSpec
from src.data.market_data_feed import MarketDataFeed
from src.scanner.market_scanner import MarketScanner, ScanResult

def run_multi_cap_scanner(target_timestamp: str = None):
    print("=" * 95)
    print("   NSE MULTI-CAP STOCK OPTIONS SCANNER & OPPORTUNITY RANKING ENGINE")
    print("   Unified Account Capital: ₹1,000,000.00 (10 Lakhs) | Max Risk per Trade: ₹12,000.00")
    print("   Universe: Large-Cap, Mid-Cap, and Small-Cap Permitted NSE F&O Derivatives")
    print("=" * 95)

    config = MasterConfig()
    scanner = MarketScanner(config, min_composite_score=55.0, min_rr=1.5, max_recommendations=3)

    # 1. Ingest multi-cap universe
    print("\n[+] Ingesting intraday data across multi-cap universe...")
    feed = MarketDataFeed()
    universe_data = {}
    
    # Select balanced representation across all three tiers
    target_symbols = [
        # Large Caps
        "TCS", "RELIANCE", "ICICIBANK", "SBIN", "LT", "BHARTIARTL", "ITC", "SUNPHARMA",
        # Mid Caps
        "POLYCAB", "PERSISTENT", "COFORGE", "VOLTAS", "AUROPHARMA",
        # Small / High-Beta F&O Caps
        "BSOFT", "NATIONALUM", "RBLBANK", "IDFCFIRSTB", "CHAMBLFERT"
    ]

    for sym in target_symbols:
        spec = NSE_FO_UNIVERSE[sym]
        print(f"    - [{spec.cap_category:<9}] {sym:<11} | {spec.name:<30} | Lot: {spec.lot_size:>5}", end="")
        try:
            df = feed.get_stock_data(sym, period="60d", interval="15m")
            universe_data[sym] = df
            print(f" -> Loaded ({len(df)} candles)")
        except Exception as e:
            print(f" -> Error: {e}")

    # 2. Execute Market Scan across universe
    ts_param = None
    if target_timestamp:
        ts_param = pd.Timestamp(target_timestamp)
        if ts_param.tz is None:
            ts_param = ts_param.tz_localize("Asia/Kolkata")

    print(f"\n[+] Scanning {len(universe_data)} multi-cap stocks for 4H S/R and 15M Reversal Confirmations (Time: {ts_param or 'LATEST'})...")
    scan_result: ScanResult = scanner.scan_universe(
        symbol_data_15m=universe_data,
        current_time=ts_param,
        available_cash=1000000.0,
        max_risk_per_trade=12000.0
    )

    print("\n" + "=" * 95)
    print(f"   SCAN EXECUTION VERDICT: {scan_result.execution_verdict}")
    print(f"   Timestamp: {scan_result.timestamp} | Total Scanned: {scan_result.total_stocks_scanned}")
    print(f"   Large Caps: {scan_result.large_caps_scanned} | Mid Caps: {scan_result.mid_caps_scanned} | Small Caps: {scan_result.small_caps_scanned}")
    print(f"   Top High-Conviction Opportunities Selected: {scan_result.valid_opportunities_found}")
    print("=" * 95)

    # 3. Present Selected Top Opportunities
    if scan_result.valid_opportunities_found > 0:
        print("\n" + "-" * 95)
        print("   RANKED TOP TRADING OPPORTUNITIES (HIGHEST INSTITUTIONAL EXPECTANCY)")
        print("-" * 95)

        for cand in scan_result.top_opportunities:
            plan = cand.trade_plan
            print(f"\n[RANK #{cand.rank}] {cand.symbol} ({cand.company_name}) — {cand.action}")
            print(f"    Sector: {cand.sector} | Cap Tier: {cand.cap_category} | Spot Price: ₹{cand.spot_price:,.2f}")
            print(f"    Multi-Factor Scores:")
            print(f"      - 4H Setup Strength : {cand.setup_strength_score:>5.1f} / 100")
            print(f"      - 15M Confirmation  : {cand.confirmation_quality_score:>5.1f} / 100")
            print(f"      - Liquidity & Spread: {cand.liquidity_score:>5.1f} / 100")
            print(f"      - Risk-to-Reward    : {cand.risk_reward_ratio:>5.2f} : 1")
            print(f"      - Net Expectancy    : ₹{cand.expected_net_profitability:>+9,.2f} (after taxes & slippage)")
            print(f"      => COMPOSITE SCORE  : {cand.composite_score:>5.1f} / 100")

            if plan:
                print(f"    Actionable Trade Execution Plan:")
                print(f"      * Underlying Range  : Entry ₹{plan.underlying_entry:,.2f} | Stop Loss ₹{plan.underlying_stop_loss:,.2f}")
                print(f"      * Target 1 (1:2 R:R): ₹{plan.target_1_rr:,.2f} (Partial profit booking)")
                print(f"      * Target 2 (4H S/R) : ₹{plan.target_2_structure:,.2f} (Macro structural target)")
                print(f"      * Option Contract   : Strike {plan.option_strike:.0f} | Expiry: {plan.option_expiry} | Premium: ₹{plan.option_entry_price:.2f}")
                print(f"      * Option Stop Loss  : ₹{plan.option_stop_loss:.2f} (Hard premium cutoff)")
                print(f"      * Position Sizing   : {plan.recommended_lots} Lot(s) ({plan.recommended_quantity} Qty)")
                print(f"      * Capital Deployed  : ₹{plan.capital_required:,.2f} | Max Risk ₹{plan.estimated_risk_inr:,.2f}")
                print(f"      * Round-Trip Taxes  : ₹{plan.friction_cost_inr:,.2f} (Zerodha/NSE taxes & 2-tick slippage)")
                print(f"      * Trailing Stop Plan: {plan.trailing_stop_plan}")
                print(f"      * Averaging Status  : {plan.averaging_evaluation}")
    else:
        print("\n[!] VERDICT: NO TRADE")
        print("    None of the scanned multi-cap stocks satisfied institutional quality filters:")
        print("    - Minimum composite score >= 55.0")
        print("    - Risk-Reward ratio >= 1.5:1")
        print("    - Minimum option premium >= ₹4.00 (slippage protection)")
        print("    Capital is 100% preserved in cash buffer.")

    # 4. Display Rejected Candidates & Rationale
    if scan_result.rejected_candidates:
        print("\n" + "-" * 95)
        print("   REJECTED CANDIDATES & OBJECTIVE INSTITUTIONAL RATIONALE (NO FORCED TRADES)")
        print("-" * 95)
        for r_cand in scan_result.rejected_candidates[:5]:
            print(f"    - {r_cand.symbol:<11} [{r_cand.cap_category:<9}]: Score {r_cand.composite_score:>4.1f} | RR {r_cand.risk_reward_ratio:>4.2f}:1 | Reason: {r_cand.rejection_reason}")

    # 5. Separately Validated Option Selling Strategy
    print("\n" + "-" * 95)
    print("   SEPARATELY VALIDATED OPTION SELLING STRATEGY (CREDIT SPREADS & THETA HARVESTING)")
    print("-" * 95)
    if scan_result.selling_opportunities:
        for sop in scan_result.selling_opportunities:
            print(f"    [SELL OPPORTUNITY] {sop['symbol']} ({sop['company']})")
            print(f"      Strategy    : {sop['strategy']}")
            print(f"      Short Strike: {sop['short_strike']} | Hedge Long Strike: {sop['hedge_strike']}")
            print(f"      Net Credit  : ₹{sop['net_credit']:.2f} | Max Risk: ₹{sop['max_risk']:,.2f}")
            print(f"      Margin Req  : ₹{sop['margin_required']:,.2f} | Regime: {sop['regime']}")
    else:
        print("    [!] NO OPTION SELLING OPPORTUNITIES VALIDATED.")
        print("        Institutional selling filters require: IV Rank >= 60%, ADX < 22 (Sideways), and 4H Extreme proximity.")
        print("        Option writing is strictly prohibited under low-IV or directional trending regimes to prevent tail risk.")

    print("\n" + "=" * 95)
    print("   MULTI-CAP SCANNER EXECUTION COMPLETED")
    print("=" * 95)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NSE Multi-Cap Options Scanner")
    parser.add_argument("--timestamp", type=str, default=None, help="Target timestamp to scan (YYYY-MM-DD HH:MM:SS)")
    args = parser.parse_args()
    run_multi_cap_scanner(target_timestamp=args.timestamp)

"""
NSE Multi-Cap Support & Resistance Zone Scanner.
Scans Large-Cap, Mid-Cap, and Small-Cap NSE stocks on 4H & 15M timeframes
to identify which stocks are currently sitting directly at or near Major Support & Resistance Zones.
Pure observation / screening mode — ZERO TRADING.
"""

import os
import sys
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import NSE_FO_UNIVERSE, get_symbol_spec
from src.data.market_data_feed import MarketDataFeed
from src.data.timeframe_manager import TimeframeManager
from src.indicators.support_resistance_4h import SupportResistance4H, SRZone
from src.indicators.reversal_confirmation import ReversalConfirmation

def run_sr_scanner(
    symbols: Optional[List[str]] = None,
    proximity_threshold_pct: float = 1.8, # within 1.8% of zone is considered "AT ZONE"
    output_dir: str = "results/multi_agent"
) -> Dict[str, List[Dict[str, Any]]]:
    os.makedirs(output_dir, exist_ok=True)
    feed = MarketDataFeed(cache_dir="data/raw")
    config = MasterConfig()
    sr_engine = SupportResistance4H(config.sr)
    rev_engine = ReversalConfirmation(config.confirmation)

    # All multi-cap symbols
    target_symbols = symbols or list(NSE_FO_UNIVERSE.keys())

    at_support: List[Dict[str, Any]] = []
    at_resistance: List[Dict[str, Any]] = []
    between_zones: List[Dict[str, Any]] = []

    print("=" * 110)
    print("   NSE MULTI-CAP 4H & 15M SUPPORT / RESISTANCE ZONE SCANNER")
    print(f"   Scanning Universe: {len(target_symbols)} Multi-Cap Stocks (Large, Mid, Small Cap)")
    print(f"   Proximity Gate: Within ±{proximity_threshold_pct:.1f}% of 4H Structural Zone | Mode: SCREENING ONLY (NO TRADES)")
    print("=" * 110)
    print(f"[*] Ingesting 15M & 4H market data across {len(target_symbols)} stocks using 16 concurrent threads...")
    batch_data = feed.get_batch_stock_data(target_symbols, max_workers=16)
    print(f"[+] Loaded data for {len(batch_data)} stocks. Analyzing 4H & 15M structures...\n")

    for sym in target_symbols:
        spec = get_symbol_spec(sym)
        df_15m = batch_data.get(sym)
        if df_15m is None or df_15m.empty or len(df_15m) < 60:
            continue

        # Session-aware 4H Resampling (Strictly point-in-time)
        df_4h = TimeframeManager.resample_15m_to_4h(df_15m)
        latest_time = df_15m.index[-1]
        visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, latest_time)

        if len(visible_4h) < config.timeframe.warmup_bars_4h:
            continue

        latest_bar = df_15m.iloc[-1]
        spot = float(latest_bar["Close"])
        bar_idx = len(df_15m) - 1

        # 15M Reversal check
        rev = rev_engine.evaluate_bar(df_15m, bar_idx)

        # 4H Market Structure & Zones
        mkt = sr_engine.analyze_market_structure(
            df_4h_visible=visible_4h,
            current_time=latest_time,
            current_spot=spot
        )

        nearest_sup: Optional[SRZone] = mkt.nearest_support
        nearest_res: Optional[SRZone] = mkt.nearest_resistance

        # Distances
        sup_dist_pct = ((spot - nearest_sup.price_level) / spot * 100.0) if nearest_sup else 999.0
        res_dist_pct = ((nearest_res.price_level - spot) / spot * 100.0) if nearest_res else 999.0

        item = {
            "symbol": sym,
            "name": spec.name,
            "category": spec.cap_category,
            "sector": spec.sector,
            "spot": spot,
            "trend_4h": mkt.trend,
            "support_level": nearest_sup.price_level if nearest_sup else None,
            "support_range": f"₹{nearest_sup.lower_bound:,.2f} – ₹{nearest_sup.upper_bound:,.2f}" if nearest_sup else "N/A",
            "support_dist_pct": round(sup_dist_pct, 2),
            "support_touches": nearest_sup.touch_count if nearest_sup else 0,
            "support_strength": round(nearest_sup.strength_score * 100.0, 1) if nearest_sup else 0.0,
            "resistance_level": nearest_res.price_level if nearest_res else None,
            "resistance_range": f"₹{nearest_res.lower_bound:,.2f} – ₹{nearest_res.upper_bound:,.2f}" if nearest_res else "N/A",
            "resistance_dist_pct": round(res_dist_pct, 2),
            "resistance_touches": nearest_res.touch_count if nearest_res else 0,
            "resistance_strength": round(nearest_res.strength_score * 100.0, 1) if nearest_res else 0.0,
            "pattern_15m": rev.pattern_name,
            "pattern_dir": rev.direction,
            "volume_ratio": round(rev.volume_ratio, 2),
            "rsi_15m": round(rev.rsi_value, 1)
        }

        # Classification
        is_at_sup = (-0.5 <= sup_dist_pct <= proximity_threshold_pct)
        is_at_res = (-0.5 <= res_dist_pct <= proximity_threshold_pct)

        if is_at_sup and is_at_res:
            if sup_dist_pct <= res_dist_pct:
                at_support.append(item)
            else:
                at_resistance.append(item)
        elif is_at_sup:
            at_support.append(item)
        elif is_at_res:
            at_resistance.append(item)
        else:
            between_zones.append(item)

    # Sort each list by proximity to zone (closest first)
    at_support.sort(key=lambda x: x["support_dist_pct"])
    at_resistance.sort(key=lambda x: x["resistance_dist_pct"])
    between_zones.sort(key=lambda x: min(x["support_dist_pct"], x["resistance_dist_pct"]))

    # Output Console Tables
    print("\n" + "=" * 110)
    print(f" [1] STOCKS CURRENTLY AT OR NEAR 4H MAJOR SUPPORT ZONES ({len(at_support)} STOCKS)")
    print("     Watch For: Bullish Reversal Confirmations (Hammer, Engulfing, Volume Surge)")
    print("=" * 110)
    print(f"{'Symbol':<12} {'Category':<11} {'Spot (₹)':<11} {'Support Zone':<24} {'Dist %':<9} {'Touches':<8} {'Strength':<9} {'15M Pattern':<18} {'RSI':<6}")
    print("-" * 110)
    for s in at_support:
        pat = f"{s['pattern_15m']} ({s['pattern_dir'][:4]})" if s['pattern_15m'] != "NONE" else "Neutral"
        print(f"{s['symbol']:<12} {s['category']:<11} ₹{s['spot']:<10,.2f} {s['support_range']:<24} +{s['support_dist_pct']:.2f}%   {s['support_touches']:<8} {s['support_strength']:.1f}%    {pat:<18} {s['rsi_15m']:<6}")

    print("\n" + "=" * 110)
    print(f" [2] STOCKS CURRENTLY AT OR NEAR 4H MAJOR RESISTANCE ZONES ({len(at_resistance)} STOCKS)")
    print("     Watch For: Bearish Rejection Confirmations (Shooting Star, Bearish Engulfing, Weakening Volume)")
    print("=" * 110)
    print(f"{'Symbol':<12} {'Category':<11} {'Spot (₹)':<11} {'Resistance Zone':<24} {'Dist %':<9} {'Touches':<8} {'Strength':<9} {'15M Pattern':<18} {'RSI':<6}")
    print("-" * 110)
    for s in at_resistance:
        pat = f"{s['pattern_15m']} ({s['pattern_dir'][:4]})" if s['pattern_15m'] != "NONE" else "Neutral"
        print(f"{s['symbol']:<12} {s['category']:<11} ₹{s['spot']:<10,.2f} {s['resistance_range']:<24} -{s['resistance_dist_pct']:.2f}%   {s['resistance_touches']:<8} {s['resistance_strength']:.1f}%    {pat:<18} {s['rsi_15m']:<6}")

    print("\n" + "=" * 110)
    print(f" [3] STOCKS IN MID-RANGE / BETWEEN ZONES ({len(between_zones)} STOCKS)")
    print("     Status: No Trade Zone (In No-Man's Land — Await Arrival at Boundary)")
    print("=" * 110)
    print(f"{'Symbol':<12} {'Category':<11} {'Spot (₹)':<11} {'Nearest Support':<16} {'Dist %':<8} {'Nearest Resistance':<19} {'Dist %':<8} {'4H Trend':<10}")
    print("-" * 110)
    for s in between_zones:
        sup_str = f"₹{s['support_level']:,.2f}" if s['support_level'] else "N/A"
        res_str = f"₹{s['resistance_level']:,.2f}" if s['resistance_level'] else "N/A"
        print(f"{s['symbol']:<12} {s['category']:<11} ₹{s['spot']:<10,.2f} {sup_str:<16} +{s['support_dist_pct']:.2f}%  {res_str:<19} -{s['resistance_dist_pct']:.2f}%  {s['trend_4h']:<10}")

    # Export Markdown Report
    scan_report_path = os.path.join(output_dir, "sr_zone_scan_watchlist.md")
    with open(scan_report_path, "w", encoding="utf-8") as f:
        f.write("# NSE Multi-Cap Support & Resistance Zone Watchlist\n\n")
        f.write(f"**Scan Mode**: SCREENING ONLY — ZERO TRADES PLACED  \n")
        f.write(f"**Proximity Threshold**: Within ±{proximity_threshold_pct:.1f}% of 4H Macro S/R Zone  \n")
        f.write(f"**Total Universe Scanned**: {len(target_symbols)} stocks across Large, Mid, and Small Cap  \n\n")

        f.write("## 1. Stocks Currently at or Near 4H Major Support Zones\n\n")
        f.write("> **Watch Plan**: Prime potential long bounce setups. Look for 15M Bullish Engulfing or Hammer with volume surge $\\ge 1.2\\times$ before considering an entry.\n\n")
        f.write("| Symbol | Category | Sector | Spot Price (₹) | 4H Support Range | Proximity to Support | Retests | Strength | 15M Pattern | RSI(14) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in at_support:
            pat = f"{s['pattern_15m']} ({s['pattern_dir']})" if s['pattern_15m'] != 'NONE' else 'Neutral'
            f.write(f"| **`{s['symbol']}`** | {s['category']} | {s['sector']} | ₹{s['spot']:,.2f} | `{s['support_range']}` | **+{s['support_dist_pct']:.2f}%** | {s['support_touches']} touches | {s['support_strength']:.1f}% | `{pat}` | {s['rsi_15m']} |\n")

        f.write("\n## 2. Stocks Currently at or Near 4H Major Resistance Zones\n\n")
        f.write("> **Watch Plan**: Prime potential short rejection or profit-booking levels. Look for 15M Shooting Star or Bearish Engulfing.\n\n")
        f.write("| Symbol | Category | Sector | Spot Price (₹) | 4H Resistance Range | Proximity to Resistance | Retests | Strength | 15M Pattern | RSI(14) |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in at_resistance:
            pat = f"{s['pattern_15m']} ({s['pattern_dir']})" if s['pattern_15m'] != 'NONE' else 'Neutral'
            f.write(f"| **`{s['symbol']}`** | {s['category']} | {s['sector']} | ₹{s['spot']:,.2f} | `{s['resistance_range']}` | **-{s['resistance_dist_pct']:.2f}%** | {s['resistance_touches']} touches | {s['resistance_strength']:.1f}% | `{pat}` | {s['rsi_15m']} |\n")

        f.write("\n## 3. Stocks in Mid-Range (Between Zones — No Action)\n\n")
        f.write("| Symbol | Category | Spot Price (₹) | Nearest Support | Dist to Support | Nearest Resistance | Dist to Resistance | 4H Trend |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for s in between_zones:
            sup_str = f"₹{s['support_level']:,.2f}" if s['support_level'] else "N/A"
            res_str = f"₹{s['resistance_level']:,.2f}" if s['resistance_level'] else "N/A"
            f.write(f"| `{s['symbol']}` | {s['category']} | ₹{s['spot']:,.2f} | {sup_str} | +{s['support_dist_pct']:.2f}% | {res_str} | -{s['resistance_dist_pct']:.2f}% | `{s['trend_4h']}` |\n")

    print(f"\n[+] Scan report successfully exported to: {scan_report_path}")

    # Also copy to artifact directory
    app_artifact_dir = "C:\\Users\\DEV SOLANKI\\.gemini\\antigravity\\brain\\10d8365f-b6a6-4124-8f85-dcf58eb257b0"
    if os.path.exists(app_artifact_dir):
        art_path = os.path.join(app_artifact_dir, "sr_zone_scan_watchlist.md")
        with open(art_path, "w", encoding="utf-8") as f:
            f.write(open(scan_report_path, "r", encoding="utf-8").read())
        print(f"[+] Synced to conversation artifact: {art_path}")

    return {
        "at_support": at_support,
        "at_resistance": at_resistance,
        "between_zones": between_zones
    }

if __name__ == "__main__":
    import argparse
    from src.config.nse_symbols import get_universe_by_category

    parser = argparse.ArgumentParser(description="NSE Multi-Cap Support & Resistance Zone Scanner")
    parser.add_argument("--category", type=str, default="all", choices=["all", "large", "mid", "small", "cached"], help="Market cap category to scan")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated custom stock symbols")
    parser.add_argument("--proximity", type=float, default=1.8, help="Proximity threshold percentage (default: 1.8)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of stocks to scan")
    args = parser.parse_args()

    sym_list = None
    if args.symbols:
        sym_list = [s.strip().upper() for s in args.symbols.split(",")]
    elif args.category == "cached":
        import glob
        files = glob.glob("data/raw/*_60d_15m.parquet")
        sym_list = [os.path.basename(f).split("_")[0] for f in files]
    elif args.category == "large":
        sym_list = get_universe_by_category("LARGE_CAP")
    elif args.category == "mid":
        sym_list = get_universe_by_category("MID_CAP")
    elif args.category == "small":
        sym_list = get_universe_by_category("SMALL_CAP")
    else:
        sym_list = get_universe_by_category("ALL")

    if args.limit and sym_list:
        sym_list = sym_list[:args.limit]

    run_sr_scanner(
        symbols=sym_list,
        proximity_threshold_pct=args.proximity
    )


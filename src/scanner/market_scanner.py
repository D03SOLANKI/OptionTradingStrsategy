"""
Multi-Cap Market Scanner Engine.
Scans all eligible Large-Cap, Mid-Cap, and Small-Cap NSE F&O stocks.
Performs 4H Support/Resistance and 15M Entry Reversal Confirmation.
Runs OptionSellingValidator for separately validated short option opportunities.
Ranks all opportunities through OpportunityRanker and outputs prioritized TradePlans.
If no setup meets institutional standards, explicitly returns NO TRADE.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import numpy as np

from src.config.trading_config import MasterConfig
from src.config.nse_symbols import NSE_FO_UNIVERSE, SymbolSpec, get_symbol_spec
from src.data.timeframe_manager import TimeframeManager
from src.strategy.mtf_sr_strategy import MTFSRStrategy
from src.options.strike_selector import StrikeSelector
from src.scanner.option_selling_validator import OptionSellingValidator, OptionSellingDecision
from src.scanner.opportunity_ranker import OpportunityRanker, OpportunityCandidate, TradePlan

@dataclass
class ScanResult:
    timestamp: pd.Timestamp
    total_stocks_scanned: int
    large_caps_scanned: int
    mid_caps_scanned: int
    small_caps_scanned: int
    valid_opportunities_found: int
    top_opportunities: List[OpportunityCandidate]
    rejected_candidates: List[OpportunityCandidate]
    selling_opportunities: List[Dict[str, Any]]
    execution_verdict: str # "EXECUTE_TRADES" or "NO_TRADE"

class MarketScanner:
    """
    Automated Multi-Cap NSE Options Scanner.
    """

    def __init__(
        self,
        config: MasterConfig,
        min_composite_score: float = 60.0,
        min_rr: float = 1.5,
        max_recommendations: int = 3
    ):
        self.config = config
        self.max_recommendations = max_recommendations
        self.strategy = MTFSRStrategy(config)
        self.ranker = OpportunityRanker(config, min_composite_score=min_composite_score, min_rr=min_rr)
        self.selling_validator = OptionSellingValidator()

    def scan_universe(
        self,
        symbol_data_15m: Dict[str, pd.DataFrame],
        current_time: Optional[pd.Timestamp] = None,
        available_cash: float = 1000000.0,
        max_risk_per_trade: float = 12000.0
    ) -> ScanResult:
        """
        Executes a complete scan across all ingested stocks at current_time.
        If current_time is None, evaluates the latest available candle.
        """
        all_candidates: List[OpportunityCandidate] = []
        selling_ops: List[Dict[str, Any]] = []

        large_count = 0
        mid_count = 0
        small_count = 0

        for sym, df_15m in symbol_data_15m.items():
            spec = get_symbol_spec(sym)
            if spec.cap_category == "LARGE_CAP":
                large_count += 1
            elif spec.cap_category == "MID_CAP":
                mid_count += 1
            else:
                small_count += 1

            if df_15m.empty:
                continue

            # Determine evaluation bar
            if current_time is not None:
                if current_time not in df_15m.index:
                    continue
                bar_idx = df_15m.index.get_loc(current_time)
            else:
                bar_idx = len(df_15m) - 1
                current_time = df_15m.index[bar_idx]

            if bar_idx < self.config.timeframe.warmup_bars_15m:
                continue

            bar = df_15m.iloc[bar_idx]
            spot_close = float(bar["Close"])
            current_vol = float(bar.get("Vol_Annual", 0.22))
            current_atr = float(bar.get("ATR_14", spot_close * 0.01))
            adx_val = float(bar.get("ADX_14", 18.0))

            # Resample 4H strictly up to current_time (Zero Look-Ahead)
            df_4h = TimeframeManager.resample_15m_to_4h(df_15m.iloc[:bar_idx + 1])
            visible_4h = TimeframeManager.get_visible_4h_bars_at_time(df_4h, current_time)

            if len(visible_4h) < self.config.timeframe.warmup_bars_4h:
                continue

            # Analyze 4H Market Structure
            market_structure = self.strategy.sr_4h_engine.analyze_market_structure(
                df_4h_visible=visible_4h,
                current_time=current_time,
                current_spot=spot_close
            )

            # Check 15M S/R and Confluence
            df_15m_sub = df_15m.iloc[:bar_idx + 1]
            supports_15m, resistances_15m = self.strategy.sr_15m_engine.detect_15m_zones(
                df_15m_visible=df_15m_sub, current_time=current_time
            )
            confluent_supports, confluent_resistances = self.strategy.sr_15m_engine.find_confluence_zones(
                market_structure_4h=market_structure,
                supports_15m=supports_15m,
                resistances_15m=resistances_15m,
                current_spot=spot_close
            )

            # Reversal confirmation
            reversal = self.strategy.reversal_engine.evaluate_bar(df_15m_sub, len(df_15m_sub) - 1)

            # ---------------------------------------------------------
            # 1. OPTION BUYING EVALUATION (CE at Support / PE at Resistance)
            # ---------------------------------------------------------
            action = None
            matched_zone = None

            if reversal.direction == "BULLISH" and reversal.composite_confirmation_score >= 0.40:
                # Check Support proximity
                for s_zone in confluent_supports:
                    if s_zone.lower_bound * 0.995 <= spot_close <= s_zone.upper_bound * 1.010:
                        matched_zone = s_zone
                        action = "BUY_CE"
                        break
                if action is None and market_structure.nearest_support:
                    ns = market_structure.nearest_support
                    if ns.lower_bound * 0.995 <= spot_close <= ns.upper_bound * 1.010:
                        action = "BUY_CE"

            elif reversal.direction == "BEARISH" and reversal.composite_confirmation_score >= 0.40:
                # Check Resistance proximity
                for r_zone in confluent_resistances:
                    if r_zone.lower_bound * 0.990 <= spot_close <= r_zone.upper_bound * 1.005:
                        matched_zone = r_zone
                        action = "BUY_PE"
                        break
                if action is None and market_structure.nearest_resistance:
                    nr = market_structure.nearest_resistance
                    if nr.lower_bound * 0.990 <= spot_close <= nr.upper_bound * 1.005:
                        action = "BUY_PE"

            if action is not None:
                contract = StrikeSelector.select_best_contract(
                    symbol=sym,
                    current_datetime=current_time,
                    spot_price=spot_close,
                    option_type="CE" if action == "BUY_CE" else "PE",
                    volatility=current_vol,
                    mode=self.config.option.strike_selection_mode,
                    target_delta=self.config.option.target_delta,
                    min_dte=self.config.option.min_days_to_expiry,
                    max_dte=self.config.option.max_days_to_expiry,
                    risk_free_rate=self.config.option.risk_free_rate,
                    dividend_yield=self.config.option.dividend_yield,
                    max_spread_pct=self.config.option.max_bid_ask_spread_pct
                )

                candidate = self.ranker.evaluate_candidate(
                    symbol=sym,
                    spot_price=spot_close,
                    action=action,
                    sr_zone=matched_zone,
                    market_structure=market_structure,
                    reversal=reversal,
                    contract=contract,
                    current_atr_15m=current_atr,
                    available_cash=available_cash,
                    max_risk_inr=max_risk_per_trade
                )
                all_candidates.append(candidate)

            # ---------------------------------------------------------
            # 2. SEPARATELY VALIDATED OPTION SELLING EVALUATION
            # ---------------------------------------------------------
            # Calculate mock IV rank (0-100) from annual volatility
            iv_rank_est = min(100.0, max(10.0, (current_vol / 0.35) * 100.0))
            sell_dec = self.selling_validator.evaluate_selling_opportunity(
                symbol=sym,
                spot_price=spot_close,
                current_iv=current_vol,
                iv_rank=iv_rank_est,
                adx_14=adx_val,
                market_structure_4h=market_structure,
                available_cash=available_cash,
                lot_size=spec.lot_size,
                strike_step=spec.strike_step
            )
            if sell_dec.allowed:
                selling_ops.append({
                    "symbol": sym,
                    "company": spec.name,
                    "strategy": sell_dec.strategy_type,
                    "short_strike": sell_dec.short_strike,
                    "hedge_strike": sell_dec.long_hedge_strike,
                    "net_credit": sell_dec.net_credit,
                    "max_risk": sell_dec.max_risk,
                    "margin_required": sell_dec.margin_required,
                    "regime": sell_dec.regime
                })

        # -------------------------------------------------------------
        # Rank-Ordering & Selection Filtering
        # -------------------------------------------------------------
        # Filter accepted vs rejected
        valid_candidates = [c for c in all_candidates if c.is_selected]
        rejected_candidates = [c for c in all_candidates if not c.is_selected]

        # Sort valid candidates by composite score descending
        valid_candidates.sort(key=lambda x: x.composite_score, reverse=True)

        # Enforce Sector Diversification: Max 1 trade per sector
        selected_top: List[OpportunityCandidate] = []
        seen_sectors = set()

        for cand in valid_candidates:
            if len(selected_top) >= self.max_recommendations:
                break
            if cand.sector in seen_sectors:
                cand.is_selected = False
                cand.rejection_reason = f"Sector limit reached: Another stock in {cand.sector} is already selected."
                rejected_candidates.append(cand)
                continue

            cand.rank = len(selected_top) + 1
            seen_sectors.add(cand.sector)
            selected_top.append(cand)

        verdict = "EXECUTE_TRADES" if len(selected_top) > 0 else "NO_TRADE"

        return ScanResult(
            timestamp=current_time or pd.Timestamp.now(),
            total_stocks_scanned=len(symbol_data_15m),
            large_caps_scanned=large_count,
            mid_caps_scanned=mid_count,
            small_caps_scanned=small_count,
            valid_opportunities_found=len(selected_top),
            top_opportunities=selected_top,
            rejected_candidates=rejected_candidates,
            selling_opportunities=selling_ops,
            execution_verdict=verdict
        )

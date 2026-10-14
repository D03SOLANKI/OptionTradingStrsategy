"""
Opportunity Ranker & Multi-Factor Scoring Engine.
Evaluates, scores, and ranks trading opportunities across:
1. Setup Strength (4H S/R structure, touches, rejection, recency)
2. Confirmation Quality (15M candlestick pattern, volume surge, RSI momentum)
3. Liquidity & Spread Score (bid-ask spread, lot size feasibility, minimum premium filter >= ₹5.00)
4. Risk-to-Reward Ratio (Target distance vs Stop distance >= 1.5)
5. Expected Net Profitability (Expected return after full Indian taxes & 2-tick slippage)

Generates actionable institutional TradePlans and enforces explicit NO_TRADE returns
when candidates do not meet minimum institutional quality thresholds.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Literal
import math

from src.config.nse_symbols import SymbolSpec, get_symbol_spec
from src.config.trading_config import MasterConfig
from src.indicators.support_resistance_4h import MarketStructureState, SRZone
from src.indicators.support_resistance_15m import ConfluenceZone
from src.indicators.reversal_confirmation import ReversalSignal
from src.options.strike_selector import OptionContract
from src.risk.cost_calculator import CostCalculator

@dataclass
class TradePlan:
    symbol: str
    action: Literal["BUY_CE", "BUY_PE", "SELL_OPTION"]
    underlying_entry: float
    underlying_stop_loss: float
    target_1_rr: float
    target_2_structure: float
    option_strike: float
    option_expiry: date
    option_entry_price: float
    option_stop_loss: float
    recommended_lots: int
    recommended_quantity: int
    capital_required: float
    estimated_risk_inr: float
    friction_cost_inr: float
    trailing_stop_plan: str
    averaging_evaluation: str

@dataclass
class OpportunityCandidate:
    symbol: str
    company_name: str
    sector: str
    cap_category: str
    action: Literal["BUY_CE", "BUY_PE", "SELL_OPTION", "NO_TRADE"]
    spot_price: float
    setup_strength_score: float         # 0 - 100
    confirmation_quality_score: float   # 0 - 100
    liquidity_score: float              # 0 - 100
    risk_reward_ratio: float            # e.g. 2.1
    expected_net_profitability: float   # ₹ net expectancy
    composite_score: float              # 0 - 100
    rank: int = 0
    is_selected: bool = False
    rejection_reason: Optional[str] = None
    trade_plan: Optional[TradePlan] = None

class OpportunityRanker:
    """
    Ranks multi-cap trading candidates using objective multi-factor scoring.
    """

    def __init__(self, config: MasterConfig, min_composite_score: float = 60.0, min_rr: float = 1.5):
        self.config = config
        self.min_composite_score = min_composite_score
        self.min_rr = min_rr
        self.cost_calculator = CostCalculator(config.risk)

    def evaluate_candidate(
        self,
        symbol: str,
        spot_price: float,
        action: Literal["BUY_CE", "BUY_PE"],
        sr_zone: Optional[ConfluenceZone],
        market_structure: MarketStructureState,
        reversal: Optional[ReversalSignal],
        contract: Optional[OptionContract],
        current_atr_15m: float,
        available_cash: float,
        max_risk_inr: float = 12000.0,
        historical_win_rate: float = 0.48
    ) -> OpportunityCandidate:
        """
        Calculates all 5 factors, builds TradePlan, and outputs scored candidate.
        """
        spec = get_symbol_spec(symbol)

        # -------------------------------------------------------------
        # Factor 1: Setup Strength (0 - 100)
        # -------------------------------------------------------------
        setup_score = 0.0
        if sr_zone is not None:
            # Confluence score is in 0..1 range
            setup_score = sr_zone.confluence_score * 75.0
            if sr_zone.zone_4h and sr_zone.zone_4h.touch_count >= 3:
                setup_score += 15.0
            if sr_zone.zone_15m is not None:
                setup_score += 10.0
        elif market_structure.nearest_support if action == "BUY_CE" else market_structure.nearest_resistance:
            s_lvl = market_structure.nearest_support if action == "BUY_CE" else market_structure.nearest_resistance
            setup_score = s_lvl.strength_score * 70.0
            if s_lvl.touch_count >= 3:
                setup_score += 15.0
        setup_score = min(100.0, max(0.0, setup_score))

        # -------------------------------------------------------------
        # Factor 2: Confirmation Quality (0 - 100)
        # -------------------------------------------------------------
        conf_score = 0.0
        if reversal is not None:
            conf_score = reversal.composite_confirmation_score * 100.0
        conf_score = min(100.0, max(0.0, conf_score))

        # -------------------------------------------------------------
        # Factor 3: Liquidity & Spread Score (0 - 100)
        # -------------------------------------------------------------
        # Penalize cheap options (< ₹5.00) due to extreme 2-tick slippage
        opt_price = contract.ask_price if contract else 0.0
        if opt_price < 2.0:
            liq_score = 15.0 # Severe slippage penalty
        elif opt_price < 5.0:
            liq_score = 45.0 # Moderate slippage drag
        elif opt_price < 15.0:
            liq_score = 80.0
        else:
            liq_score = 95.0

        # Adjust by market cap
        if spec.cap_category == "LARGE_CAP":
            liq_score = min(100.0, liq_score + 10.0)
        elif spec.cap_category == "SMALL_CAP":
            liq_score = max(10.0, liq_score - 15.0)

        # -------------------------------------------------------------
        # Factor 4: Risk-to-Reward Ratio (R:R)
        # -------------------------------------------------------------
        # Stop loss calculation
        underlying_stop = 0.0
        opposing_target = 0.0
        if action == "BUY_CE":
            ref_sup = sr_zone.lower_bound if sr_zone else (market_structure.nearest_support.lower_bound if market_structure.nearest_support else spot_price - current_atr_15m)
            underlying_stop = ref_sup - (self.config.trailing_stop.initial_stop_atr_multiplier * current_atr_15m)
            opposing_target = market_structure.nearest_resistance.price_level if market_structure.nearest_resistance else (spot_price + 3.0 * current_atr_15m)
        else:
            ref_res = sr_zone.upper_bound if sr_zone else (market_structure.nearest_resistance.upper_bound if market_structure.nearest_resistance else spot_price + current_atr_15m)
            underlying_stop = ref_res + (self.config.trailing_stop.initial_stop_atr_multiplier * current_atr_15m)
            opposing_target = market_structure.nearest_support.price_level if market_structure.nearest_support else (spot_price - 3.0 * current_atr_15m)

        underlying_risk = abs(spot_price - underlying_stop)
        underlying_reward = abs(opposing_target - spot_price)
        rr_ratio = round(underlying_reward / max(1e-4, underlying_risk), 2)

        # -------------------------------------------------------------
        # Sizing & Transaction Cost Estimation
        # -------------------------------------------------------------
        if contract is not None and opt_price > 0.10:
            opt_stop = round(max(0.05, opt_price * (1.0 - self.config.trailing_stop.initial_stop_premium_pct)), 2)
            opt_risk_per_unit = max(0.10, opt_price - opt_stop)

            # Sizing based on risk per trade
            target_quantity = int(max_risk_inr / opt_risk_per_unit)
            num_lots = max(1, target_quantity // spec.lot_size)
            final_quantity = num_lots * spec.lot_size
            capital_required = final_quantity * opt_price

            # Scale down if exceeds available cash or max trade capital
            max_trade_cap = available_cash * self.config.risk.max_capital_per_trade_pct
            max_allowed_cap = min(available_cash * 0.25, max_trade_cap)
            if capital_required > max_allowed_cap:
                num_lots = max(1, int(max_allowed_cap // (spec.lot_size * opt_price)))
                final_quantity = num_lots * spec.lot_size
                capital_required = final_quantity * opt_price

            estimated_risk = final_quantity * opt_risk_per_unit

            # Cost calculation
            cost_breakdown = self.cost_calculator.calculate_round_trip_cost(
                entry_price=opt_price,
                exit_price=opt_price * 1.30,
                quantity=final_quantity,
                is_averaging_entry=False
            )
            friction_cost = cost_breakdown.total_friction_cost

            # Factor 5: Expected Net Profitability (₹)
            # Expectancy = (Win_Rate * Avg_Win) - (Loss_Rate * Avg_Loss) - Friction
            expected_gross_win = final_quantity * (opt_price * 0.35) # 35% target gain
            expected_gross_loss = estimated_risk
            expected_net_pnl = (historical_win_rate * expected_gross_win) - ((1.0 - historical_win_rate) * expected_gross_loss) - friction_cost
            expected_net_pnl = round(expected_net_pnl, 2)
        else:
            opt_stop = 0.0
            num_lots = 0
            final_quantity = 0
            capital_required = 0.0
            estimated_risk = 0.0
            friction_cost = 0.0
            expected_net_pnl = 0.0

        # Profitability score (0 - 100)
        prof_score = min(100.0, max(0.0, (expected_net_pnl / max(1.0, max_risk_inr)) * 50.0 + 50.0))

        # -------------------------------------------------------------
        # Composite Weighted Score
        # -------------------------------------------------------------
        # 30% Setup, 25% Confirmation, 15% Liquidity, 20% R:R, 10% Expected Profitability
        rr_normalized = min(100.0, (rr_ratio / 3.0) * 100.0) # 3.0 RR = 100 score
        composite_score = round(
            (0.30 * setup_score) +
            (0.25 * conf_score) +
            (0.15 * liq_score) +
            (0.20 * rr_normalized) +
            (0.10 * prof_score),
            1
        )

        # -------------------------------------------------------------
        # Trailing Stop & Averaging Plan Formulation
        # -------------------------------------------------------------
        trailing_plan = (
            f"Initial Stop: ₹{opt_stop} (-{int(self.config.trailing_stop.initial_stop_premium_pct*100)}%). "
            f"At +15% gain (₹{round(opt_price*1.15, 2)}): ratchet to Breakeven (+2% tax buffer). "
            f"At +30% gain (₹{round(opt_price*1.30, 2)}): book 50% lots, trail remainder with 15M swing low."
        )

        averaging_plan = (
            "Permitted only if 4H structure remains valid and price retests secondary support at distance >= 1.5 ATR. "
            "Single-entry baseline enforced if market enters choppy consolidation."
        )

        # Rejection filters (Check fatal execution barriers first)
        rejection_reason = None
        if opt_price < 4.0:
            rejection_reason = f"Option premium (₹{opt_price:.2f}) is too cheap. Slippage drag would impair statistical edge."
        elif composite_score < self.min_composite_score:
            rejection_reason = f"Composite score ({composite_score:.1f}) below threshold ({self.min_composite_score:.1f})."
        elif rr_ratio < self.min_rr:
            rejection_reason = f"Risk-Reward ({rr_ratio}:1) below minimum threshold ({self.min_rr}:1)."
        elif capital_required > available_cash:
            rejection_reason = f"Insufficient capital (Required ₹{capital_required:,.2f} > Available ₹{available_cash:,.2f})."

        trade_plan = None
        if rejection_reason is None and contract is not None:
            target_1 = round(spot_price + (2.0 * underlying_risk) if action == "BUY_CE" else spot_price - (2.0 * underlying_risk), 2)
            trade_plan = TradePlan(
                symbol=symbol,
                action=action,
                underlying_entry=round(spot_price, 2),
                underlying_stop_loss=round(underlying_stop, 2),
                target_1_rr=target_1,
                target_2_structure=round(opposing_target, 2),
                option_strike=contract.strike,
                option_expiry=contract.expiry_date,
                option_entry_price=round(opt_price, 2),
                option_stop_loss=round(opt_stop, 2),
                recommended_lots=num_lots,
                recommended_quantity=final_quantity,
                capital_required=round(capital_required, 2),
                estimated_risk_inr=round(estimated_risk, 2),
                friction_cost_inr=round(friction_cost, 2),
                trailing_stop_plan=trailing_plan,
                averaging_evaluation=averaging_plan
            )

        return OpportunityCandidate(
            symbol=symbol,
            company_name=spec.name,
            sector=spec.sector,
            cap_category=spec.cap_category,
            action=action if rejection_reason is None else "NO_TRADE",
            spot_price=round(spot_price, 2),
            setup_strength_score=round(setup_score, 1),
            confirmation_quality_score=round(conf_score, 1),
            liquidity_score=round(liq_score, 1),
            risk_reward_ratio=rr_ratio,
            expected_net_profitability=expected_net_pnl,
            composite_score=composite_score,
            is_selected=(rejection_reason is None),
            rejection_reason=rejection_reason,
            trade_plan=trade_plan
        )

# Automated Stock Options Trading Strategy: Multi-Timeframe Support & Resistance (4H & 15M)

Institutional-grade, systematic, automated stock options trading strategy built on Multi-Timeframe (MTF) Support and Resistance analysis, dynamic trailing stop-loss protection, intelligent position averaging, strict risk management, and Indian National Stock Exchange (NSE) regulatory tax & cost models.

Strictly adheres to:
- **Zero Look-Ahead Bias**: 4H bars are session-aware and only visible after closing; swing pivots enforce strict confirmation lags.
- **No Overfitting**: Walk-forward analysis with purging/embargoing, Monte Carlo bootstrap simulations, and parameter stability grids.
- **No Hardcoding**: Dynamic S/R clustering, ATR-based zones, and market-calibrated Black-Scholes Greeks.
- **Real Indian Market F&O Constraints**: Flat brokerage, STT, exchange turnover fees, GST, SEBI charges, stamp duty, lot sizing, and slippage.

---

## Architecture Overview

```
OptionTradingStrategy/
├── src/
│   ├── config/
│   │   ├── constants.py          # NSE session hours (09:15-15:30 IST), tick size, taxes
│   │   ├── nse_symbols.py        # F&O contract specifications, lot sizes, strike steps
│   │   └── trading_config.py     # Strongly typed dataclasses for all hyperparameters
│   ├── data/
│   │   ├── timeframe_manager.py  # Session-aware 15M -> 4H resampler with point-in-time visibility
│   │   └── market_data_feed.py   # Yahoo Finance real NSE fetcher & multi-regime generator
│   ├── indicators/
│   │   ├── swing_detector.py     # Point-in-time Swing High/Low with lag confirmation
│   │   ├── support_resistance_4h.py # 4H Major Market Structure, S/R clustering & strength scoring
│   │   ├── support_resistance_15m.py# 15M S/R and MTF confluence evaluator
│   │   └── reversal_confirmation.py# Candlestick patterns (Hammer, Engulfing, etc.), RSI, volume
│   ├── options/
│   │   ├── pricing_engine.py     # Black-Scholes-Merton model, Greeks, and IV solver
│   │   └── strike_selector.py    # NSE monthly expiry calendar & dynamic ATM/ITM/OTM strike selection
│   ├── strategy/
│   │   ├── mtf_sr_strategy.py    # Master strategy orchestrator (CE/PE signal generation)
│   │   ├── intelligent_averaging.py # Thesis invalidation check, fresh reversal requirement
│   │   └── trailing_stop_manager.py# Monotonic ratcheting trailing stop & partial profit taking
│   ├── risk/
│   │   ├── risk_manager.py       # Position sizing, daily drawdown circuit breaker, consecutive loss pauses
│   │   └── cost_calculator.py    # Complete Indian NSE options taxation & brokerage model
│   ├── backtest/
│   │   ├── engine.py             # Event-driven chronological simulation engine
│   │   └── position.py           # Position lifecycle, tranches, MFE/MAE excursions
│   ├── validation/
│   │   ├── baseline_comparison.py# With-averaging vs Single-entry baseline head-to-head comparison
│   │   ├── walk_forward.py       # Purged chronological Walk-Forward Analysis (WFA)
│   │   ├── monte_carlo.py        # Bootstrap trade resampling (1,500 iterations)
│   │   └── sensitivity.py        # Multi-parameter fragility & robustness grids
│   └── reporting/
│       ├── performance_metrics.py# Comprehensive scorecard (PnL, Sharpe, Sortino, Drawdown)
│       ├── visualizer.py         # Publication-quality charts (Equity, Drawdown, MFE/MAE)
│       └── report_generator.py   # Markdown & CSV trade log generator
├── tests/                        # 100% passing test suite for pricing, S/R, and zero lookahead
├── results/                      # Audit reports, trade logs, and performance plots
├── main.py                       # CLI execution entry point
└── requirements.txt
```

---

## Key Strategy Mechanics

### 1. Multi-Timeframe S/R & Confluence
- **4-Hour Major Structure**: Analyzes major swing highs and lows confirmed point-in-time. Clusters price levels within $0.8\%$ tolerance into S/R zones. Calculates a normalized strength score $[0.0, 1.0]$ based on:
  $$\text{Score} = 0.35 \cdot S_{\text{touches}} + 0.25 \cdot e^{-\lambda \Delta t} + 0.20 \cdot S_{\text{rejection\_wicks}} + 0.20 \cdot S_{\text{volume}} - P_{\text{breakdown}}$$
- **15-Minute Entry Confirmation**: Detects short-term S/R levels. Identifies confluence where 15M and 4H levels overlap within $0.6\%$ price distance.
- **Directional Triggers**:
  - **Buy CE**: Underlying tests qualified Support + Confirmed Bullish Reversal (Hammer, Bullish Engulfing, Morning Star, Piercing line) + RSI hook + Volume surge.
  - **Buy PE**: Underlying tests qualified Resistance + Confirmed Bearish Reversal (Shooting Star, Bearish Engulfing, Evening Star) + RSI hook + Volume surge.

### 2. Automated Profit Booking & Dynamic Trailing Stop
- **Monotonicity Rule**: Active stop-loss can NEVER be loosened.
- **Profit Activation**: Trailing stop is activated when option premium gains $\ge +18\%$.
- **Ratcheting Trail**: Trails $12\%$ behind peak premium reached.
- **Partial Profit**: At $1:2$ Risk-to-Reward ratio, books $50\%$ of the position and moves remaining stop to Breakeven $+ 1\text{ tick}$, locking in a risk-free runner.

### 3. Intelligent Position Averaging
- **Thesis Invalidation**: If underlying breaches the support zone by more than $0.75 \times \text{ATR}$, the trade is invalidated. **Averaging is strictly forbidden** and stop-loss is taken.
- **Fresh Confirmation Required**: Averaging is only triggered if a brand new 15M reversal confirmation candle closes at the deeper structural level.
- **Mathematical Recalibration**: Recalculates weighted-average entry price, combined risk, and combined trailing stop.
- **Baseline Audit**: Tested head-to-head against a single-entry baseline. Retained only when it improves risk-adjusted return without creating unacceptable drawdowns.

### 4. Realistic Indian Market Options Cost Model
Includes all regulatory friction per executed trade:
- **Brokerage**: ₹20.00 flat per order
- **Securities Transaction Tax (STT)**: $0.10\%$ on sell side option premium turnover
- **Exchange Turnover Charges**: $0.05\%$ on premium turnover
- **GST**: $18\%$ on (Brokerage + Exchange Charges)
- **SEBI Charges**: ₹10 per crore ($0.0001\%$)
- **Stamp Duty**: $0.003\%$ on buy side turnover
- **Slippage**: Configurable ticks ($2 \text{ ticks} = ₹0.10$ per share round-trip)

---

## Installation & Running

### 1. Run Unit Tests
```bash
python -m pytest tests/ -v
```

### 2. Execute Full Audit on Real NSE Stock (e.g. TCS)
```bash
python main.py --symbol TCS --mode full --output-dir results/tcs
```

### 3. Execute on RELIANCE
```bash
python main.py --symbol RELIANCE --mode full --output-dir results/reliance
```

### 4. Command Line Arguments
- `--symbol`: NSE ticker (e.g., `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `ICICIBANK`)
- `--mode`: `full` (All validations), `compare` (Baseline vs Averaging), `wfa` (Walk-Forward), `sensitivity` (Robustness grid)
- `--capital`: Starting capital in INR (default: `500000.0`)
- `--no-averaging`: Disables averaging to run pure single-entry mode
- `--output-dir`: Output directory for reports and charts

# Multi-Agent Institutional AI Stock Trading System (NSE Cash Market)

A production-grade, systematic, multi-agent algorithmic trading system engineered for the **Indian National Stock Exchange (NSE)** Cash Equities market. The platform covers the entire **NIFTY 500** universe (520 liquid equities across Large-Cap, Mid-Cap, and Small-Cap tiers) using **Multi-Timeframe (MTF) Support & Resistance (4H & 15M)** confluence, deterministic candlestick reversal confirmation, institutional risk modeling, and a real-time Streamlit dashboard.

---

## 🏛️ System Architecture: 5 Specialized Autonomous Agents

The system operates on an asynchronous event-driven architecture where five specialized agents analyze market data through an immutable audit trail (`TransparencyBus`):

```
                                  [ NIFTY 500 Universe (520 Stocks) ]
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Market & Stock Scanning Agent (MarketScanningAgent)                                                 │
│    • Multi-threaded asynchronous ingestion (ThreadPoolExecutor with 45-min TTL caching)               │
│    • Evaluates session volume, liquidity, volatility (ATR), and price alignment                        │
└──────────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Support & Resistance Agent (SupportResistanceAgent)                                                │
│    • 4-Hour (4H) session-aware structural swing detection (Zero look-ahead bias)                       │
│    • ATR-based density clustering into institutional S/R zones with dynamic touch/rejection scoring    │
│    • 15-Minute (15M) local swing detection and MTF zone confluence check (≤ 0.60% distance)           │
└──────────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. Technical Analysis Agent (TechnicalAnalysisAgent)                                                   │
│    • Point-in-time candlestick reversal confirmation (Hammer, Engulfing, Morning/Evening Star)        │
│    • RSI dynamic momentum filter & volume expansion validation (≥ 1.25x 20-period SMA)                 │
└──────────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Risk Management Agent (RiskManagementAgent)                                                         │
│    • Fixed fractional risk model (1.0% NAV risk per trade)                                             │
│    • Position sizing decoupled from capital depletion (ranks purely by setup quality)                  │
│    • Enforces minimum Risk-to-Reward ratio (R:R ≥ 1.50) and sector concentration limits                │
└──────────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. Decision & Validation Agent (DecisionValidationAgent)                                               │
│    • Synthesizes confidence scores across all 5 agents                                                 │
│    • Maximum 5 high-conviction trades per day (quality over quantity; 0 if criteria not met)           │
│    • Classifies execution mode: Cash Delivery (CNC) for BUY, Intraday Short (MIS) for SELL            │
└──────────────────────────────────────────────────┬─────────────────────────────────────────────────────┘
                                                   │
                                                   ▼
                       [ Streamlit Live Dashboard & Multi-Agent Audit Log ]
```

---

## ⚡ Key Highlights

- **100% Cash Equities (Zero Options/Greeks)**: Eliminates options time decay (theta) and IV crush. Executes pure equity trades in full compliance with SEBI cash market guidelines:
  - **BUY Orders**: Cash Delivery (`CNC`) holding for swing targets.
  - **SELL Orders**: Intraday Short (`MIS`) with mandatory 3:15 PM auto-square-off.
- **Full NIFTY 500 Universe**: 520 officially mapped NSE equities:
  - **Large-Cap**: 104 benchmark stocks (NIFTY 50, NIFTY Next 50)
  - **Mid-Cap**: 153 high-growth stocks (NIFTY Midcap 150)
  - **Small-Cap**: 263 high-momentum stocks (NIFTY Smallcap 250)
- **High-Speed Ingestion & Live TTL Caching**: Multi-threaded batch ingestion using `ThreadPoolExecutor(max_workers=16)` with a 45-minute live cache invalidation window to prevent stale data while maintaining fast response times.
- **Top 5 Quality-First Trade Sizing**: Decoupled from cash balance constraints so every stock is evaluated strictly on merit. At most 5 highest-confidence candidates ($R:R \ge 1.50$, confidence $\ge 60\%$) are selected daily.
- **Zero Black-Box Transparency**: Every decision, rejection reason, S/R zone touch, and R:R calculation is logged to an immutable audit matrix accessible via the dashboard.

---

## 📁 Repository Structure

```
OptionTradingStrategy/
├── app_dashboard.py                    # Streamlit Live Interactive Control Panel & Visualizer
├── main_multi_agent.py                 # Multi-Agent Pipeline CLI entry point
├── scan_sr_zones.py                    # Multi-cap S/R zone scanner with custom watchlists
├── run_cash_multiagent_backtest.py     # End-to-end historical portfolio backtest engine
├── src/
│   ├── agents/
│   │   ├── base_agent.py               # Abstract base class & event messaging protocols
│   │   ├── market_scanning_agent.py    # Agent 1: Universe filtering & liquidity screening
│   │   ├── support_resistance_agent.py # Agent 2: 4H & 15M S/R clustering and MTF confluence
│   │   ├── technical_analysis_agent.py # Agent 3: Candlestick patterns, RSI, and volume surge
│   │   ├── risk_management_agent.py    # Agent 4: Position sizing, SL/Target, R:R calculation
│   │   ├── decision_validation_agent.py# Agent 5: Synthesis, ranking (Top ≤ 5), & trade emission
│   │   ├── orchestrator.py             # Multi-agent workflow pipeline coordinator
│   │   └── transparency_bus.py         # Thread-safe pub/sub audit log & event bus
│   ├── config/
│   │   ├── constants.py                # NSE market hours (09:15-15:30 IST), lot sizes, tick sizes
│   │   ├── nse_symbols.py              # Full 520 NIFTY 500 symbols mapped by market cap
│   │   └── trading_config.py           # Strongly typed configuration dataclasses
│   ├── cost/
│   │   └── cash_cost_calculator.py     # Indian SEBI/NSE cash equity friction (Brokerage, STT, GST, SEBI)
│   ├── data/
│   │   ├── market_data_feed.py         # Multi-threaded Yahoo Finance feed with 45-min TTL cache
│   │   └── timeframe_manager.py        # Session-aware 15M to 4H resampling (zero lookahead)
│   ├── indicators/
│   │   ├── swing_detector.py           # Structural swing highs/lows with confirmation lags
│   │   ├── support_resistance_4h.py    # 4H S/R zone clustering & scoring
│   │   ├── support_resistance_15m.py   # 15M S/R zone detection
│   │   └── reversal_confirmation.py   # Bullish/bearish reversal pattern recognition
│   ├── backtest/
│   │   └── cash_portfolio_engine.py    # Cash portfolio simulation engine with MFE/MAE tracking
│   └── reporting/
│       ├── performance_metrics.py      # Sharpe, Sortino, Calmar, Win Rate, Max Drawdown
│       └── agent_dashboard_generator.py# HTML & Markdown transparency report generator
├── tests/
│   └── test_multi_agent_system.py      # Multi-agent unit tests (100% pass)
└── requirements.txt                    # Project dependencies
```

---

## 🚀 Getting Started

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/D03SOLANKI/OptionTradingStrsategy.git
cd OptionTradingStrsategy
pip install -r requirements.txt
```

### 2. Launch the Streamlit Live Dashboard
```bash
streamlit run app_dashboard.py
```
Open `http://localhost:8501` to access:
- **Multi-Cap S/R Scanner**: Interactive scanner for Large-Cap, Mid-Cap, Small-Cap, or custom watchlists.
- **5-Agent Live Pipeline**: End-to-end multi-agent pipeline with real-time logs and decision matrix.
- **Cash Backtest & Analytics**: Historical performance analysis, equity curve, and PnL distributions.
- **Transparency Event Logs**: Full audit trail of every agent-to-agent message and decision rationale.

### 3. Run Multi-Agent Analysis from CLI
```bash
# Analyze a custom basket of stocks
python main_multi_agent.py --symbols RELIANCE TCS INFY HDFCBANK ICICIBANK --capital 500000

# Scan all Large-Cap stocks at Support / Resistance zones
python scan_sr_zones.py --category large_cap --proximity 0.015
```

### 4. Run Test Suite
```bash
python -m pytest tests/test_multi_agent_system.py -v
```

---

## 📊 Indian Regulatory Cost Model (Cash Equities)

The system accurately simulates all statutory friction per executed trade under NSE / SEBI rules:
- **Brokerage**: ₹20.00 or 0.05% per order (whichever is lower)
- **Securities Transaction Tax (STT)**: 0.10% on Delivery (Buy & Sell); 0.025% on Intraday Sell
- **Exchange Turnover Charges**: 0.00345%
- **GST**: 18% on (Brokerage + Exchange Charges)
- **SEBI Charges**: ₹10 per crore (0.0001%)
- **Stamp Duty**: 0.015% on Buy side
- **Slippage**: Configurable ticks model (default: 1 tick = ₹0.05 per share)

---

## 🛡️ License & Disclaimer

This project is licensed under the MIT License.

**Disclaimer**: *This software is intended for educational, research, and algorithmic strategy development purposes only. Trading in the Indian stock market involves substantial financial risk. None of the automated signals or agent recommendations constitute direct investment advice. Always test thoroughly in simulation before deploying real capital.*

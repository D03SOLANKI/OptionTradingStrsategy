# Multi-Timeframe Support & Resistance Automated Stock Options Strategy
## Institutional Performance Audit & Validation Report

> **Strict Compliance**: Zero Look-Ahead Bias | No Hardcoding | Indian NSE F&O Realistic Cost Model | Walk-Forward Validated

---

### 1. Executive Performance Scorecard (After All Indian Taxes & Slippage)

| Metric | Value | Metric | Value |
| :--- | :--- | :--- | :--- |
| **Starting Capital** | ₹500,000.00 | **Final Equity** | ₹438,757.37 |
| **Net Profit** | ₹-61,242.63 | **Return on Capital** | -12.25% |
| **Gross Profit** | ₹36,572.66 | **Gross Loss** | ₹97,815.29 |
| **Total Indian Friction/Taxes** | ₹9,414.56 | **Profit Factor** | 0.37 |
| **Total Closed Trades** | 20 | **Win Rate** | 40.0% |
| **Winning Trades** | 8 | **Losing Trades** | 12 |
| **Average Win** | ₹4,571.58 | **Average Loss** | ₹8,151.27 |
| **Payoff Ratio (Win/Loss)** | 0.56 | **Expectancy per Trade** | ₹-3,062.13 |
| **Maximum Drawdown (₹)** | ₹75,835.98 | **Maximum Drawdown (%)** | 14.74% |
| **Sharpe Ratio (Annualized)** | -2.48 | **Sortino Ratio** | -0.56 |
| **Calmar Ratio** | -0.83 | **Max Consecutive Losses** | 3 |
| **Avg MFE (Max Favorable)** | ₹6,227.58 | **Avg MAE (Max Adverse)** | ₹6,094.51 |

---

### 2. Intelligent Position Averaging Audit vs Single-Entry Baseline

**Verdict**: INTELLIGENT AVERAGING ACCEPTED: Produced net profit difference of +₹13180.04 with controlled drawdown change of -1.22% and Sharpe change of +2.14.

| Evaluation Dimension | With Intelligent Averaging | Baseline (No Averaging) | Difference |
| :--- | :--- | :--- | :--- |
| **Net Profit** | ₹-61,242.63 | ₹-74,422.67 | +13,180.04 ₹ |
| **Win Rate** | 40.0% | 30.0% | +10.0% |
| **Max Drawdown** | 14.74% | 15.96% | -1.22% |
| **Profit Factor** | 0.37 | 0.25 | +0.12 |
| **Sharpe Ratio** | -2.48 | -4.62 | +2.14 |

- **Averaged Trades Count**: 4
- **Averaged Trades Win Rate**: 50.0%
- **Non-Averaged Trades Win Rate**: 37.5%

---

### 3. Bootstrap Monte Carlo Robustness Analysis (1,500 Iterations)

- **Total Simulations**: 1,500
- **Median Final Equity**: ₹436,905.06
- **5th Percentile Equity (Conservative Lower Bound)**: ₹385,789.84
- **95th Percentile Equity (Optimistic Upper Bound)**: ₹489,943.37
- **Median Max Drawdown**: 13.46%
- **95th Percentile Max Drawdown (95% VaR)**: 22.58%
- **99th Percentile Max Drawdown (Tail Risk)**: 26.63%
- **Probability of Account Ruin (>25% Drawdown)**: **2.13%**
- **Sharpe Ratio Distribution**: 5th Pct: -15.16 | Median: -7.38 | 95th Pct: -1.13

---

### 4. Walk-Forward Analysis (WFA) & Out-of-Sample Efficiency

**Summary**: Chronological Train/Test Split (70/30). OOS Return: 0.00%, WFE: 0.00.
- **Robustness Assessment**: FRAGILE / NEEDS CALIBRATION
- **Mean Walk-Forward Efficiency (WFE)**: 0.00
- **Combined Out-of-Sample Net PnL**: ₹0.00
- **Combined Out-of-Sample Win Rate**: 0.0%
- **Combined Out-of-Sample Profit Factor**: 0.00

---

### 5. Hyperparameter Sensitivity & Overfitting Check

**Summary**: Tested 12 parameter variations across 4 parameters. Profitable variations: 0/12 (0.0%). Overfitting Assessment: HIGH RISK OF OVERFITTING.
- **Stability Score**: 0.0% of neighborhood variations profitable.
- **Overfitting Verdict**: OVERFITTED

| Parameter Path | Tested Value | Net Profit (₹) | Win Rate (%) | Profit Factor | Max DD (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sr.pivot_order_4h` | 2 | ₹-106,754 | 22.2% | 0.13 | 22.27% |
| `sr.pivot_order_4h` | 3 | ₹-61,243 | 40.0% | 0.37 | 14.74% |
| `sr.pivot_order_4h` | 4 | ₹-53,085 | 40.0% | 0.38 | 14.53% |
| `trailing_stop.activation_profit_pct` | 0.12 | ₹-71,479 | 23.5% | 0.17 | 16.71% |
| `trailing_stop.activation_profit_pct` | 0.18 | ₹-61,243 | 40.0% | 0.37 | 14.74% |
| `trailing_stop.activation_profit_pct` | 0.24 | ₹-61,789 | 36.8% | 0.37 | 14.74% |
| `trailing_stop.trailing_distance_pct` | 0.08 | ₹-49,958 | 45.0% | 0.48 | 14.21% |
| `trailing_stop.trailing_distance_pct` | 0.12 | ₹-61,243 | 40.0% | 0.37 | 14.74% |
| `trailing_stop.trailing_distance_pct` | 0.15 | ₹-55,598 | 38.9% | 0.39 | 15.39% |
| `averaging.min_distance_atr` | 1.0 | ₹-61,243 | 40.0% | 0.37 | 14.74% |
| `averaging.min_distance_atr` | 1.25 | ₹-61,243 | 40.0% | 0.37 | 14.74% |
| `averaging.min_distance_atr` | 1.5 | ₹-55,150 | 40.0% | 0.40 | 13.56% |

---

### 6. Architectural Guarantees & Verification

1. **Zero Look-Ahead Bias**:
   - 4-Hour structural candles are aggregated session-aware and timestamped at their close.
   - At any 15M decision bar $t$, only 4H candles with `close_time <= t` are visible.
   - Pivot High/Low detection enforces strict confirmation lag $N$; a pivot at bar $i$ is only visible at bar $i+N$.
2. **No Hardcoding**:
   - All S/R zones are dynamically clustered using relative price proximity, recency exponential decay, volume profile, and rejection wicks.
   - Dynamic strike selection adjusts to spot, DTE, volatility surface, and lot sizes.
3. **Real Indian Market F&O Constraints**:
   - Flat brokerage (₹20/order), STT (0.1% on sell), NSE Exchange turnover fees (0.05%), GST (18%), SEBI charges, Stamp Duty (0.003%), and 2-tick slippage per contract.
   - Position sizing uses true INR capital allocation and maximum risk-per-trade constraints.
4. **Dynamic Profit Protection**:
   - Monotonically ratcheting trailing stop-loss (never widens) with profit activation threshold (+18%) and partial profit-taking at 1:2 R:R.
5. **Intelligent Position Averaging**:
   - Strict thesis invalidation check immediately stops out and forbids averaging if the S/R boundary is broken.
   - Requires minimum distance of 1.25x ATR and a brand new 15M reversal confirmation.

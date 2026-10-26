# Multi-Agent AI Cash Equity Trading System — Portfolio Backtest Audit

**Audit Generated**: 2026-10-16 13:12:20  
**Portfolio Initial Capital**: ₹1,000,000.00 (10 Lakhs INR)  
**Asset Class**: Pure Cash Equity (Delivery & Intraday) — Zero Options / Derivatives  
**Universe Scanned**: 21 Liquid Multi-Cap Stocks (Large, Mid, Small Cap)  

## 1. Executive Answers to Core Operational Questions

### Q1: How much we can make in a month with 10 Lakhs capital?
- **Expected Monthly Net Profit**: **₹-80,893.54**
- **Expected Monthly Return**: **-8.09%**
- **Total 60-Day Realized Net Profit**: **₹-161,787.08** (-16.18% on ₹10L)
- **Gross Profit**: ₹47,780.61 | **Gross Loss**: ₹209,567.69
- **Total Taxes & Exchange Friction Deducted**: ₹56,582.48 (Full Zerodha Cash Delivery breakdown)

### Q2: How many positions does it place in a day?
- **Daily Trade Frequency**: **1.75 trades per day** (approx 1 trade every 1–2 days).
- **Average Concurrent Open Positions**: **2.1 stocks** held simultaneously.
- **Maximum Concurrent Position Cap**: **4 stocks** (with strict 1 stock per sector limit).
- **Capital Deployed per Trade**: Up to 25% (₹2,50,000 maximum), maintaining a minimum 25% cash buffer at all times.

## 2. Institutional Performance Scorecard

| Metric | Value | Benchmark / Target |
| :--- | :--- | :--- |
| **Initial Capital** | ₹1,000,000.00 | ₹10,00,000 |
| **Ending Equity** | ₹838,212.92 | — |
| **Net Realized Profit** | ₹-161,787.08 | — |
| **Total Net Return** | -16.18% | Positive Alpha |
| **Win Rate** | **29.5%** (31W / 74L) | > 50.0% |
| **Profit Factor** | **0.23** | > 1.50 |
| **Payoff Ratio (Win/Loss)** | **0.54** | > 1.50 |
| **Annualized Sharpe Ratio** | **-7.47** | > 1.00 |
| **Maximum Drawdown** | **16.91%** (₹170,274.60) | < 10.0% |
| **Calmar Ratio** | **-0.96** | > 2.00 |
| **Max Consecutive Wins** | 3 | — |
| **Max Consecutive Losses** | 10 | < 4 |

## 3. Performance by Market-Cap Category

| Category | Stocks Evaluated | Executed Trades | Win Rate | Net Realized PnL | Contribution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LARGE_CAP** | 9 | 58 | 34.5% | ₹-75,751.69 | 0.0% |
| **MID_CAP** | 7 | 30 | 20.0% | ₹-55,094.07 | 0.0% |
| **SMALL_CAP** | 5 | 17 | 29.4% | ₹-30,941.32 | 0.0% |

## 4. Individual Stock Performance Breakdown

| Symbol | Sector | Total Trades | Win Rate | Net PnL (₹) |
| :--- | :--- | :--- | :--- | :--- |
| `INFY` | Information Technology | 3 | 100.0% | ₹17,949.08 |
| `SUNPHARMA` | Healthcare & Pharma | 5 | 40.0% | ₹982.17 |
| `COFORGE` | Information Technology | 1 | 100.0% | ₹116.39 |
| `TCS` | Information Technology | 4 | 75.0% | ₹52.03 |
| `RBLBANK` | Banking & Financial Services | 3 | 33.3% | ₹-4,324.05 |
| `RELIANCE` | Energy / Conglomerate | 2 | 0.0% | ₹-4,720.56 |
| `AUROPHARMA` | Pharmaceuticals | 5 | 20.0% | ₹-4,761.89 |
| `BSOFT` | Information Technology | 3 | 33.3% | ₹-4,969.99 |
| `IDFCFIRSTB` | Banking & Financial Services | 3 | 33.3% | ₹-5,417.09 |
| `SBIN` | Banking & Financial Services | 5 | 40.0% | ₹-5,905.31 |
| `NATIONALUM` | Metals & Mining | 5 | 40.0% | ₹-7,925.48 |
| `CHAMBLFERT` | Chemicals & Fertilizers | 3 | 0.0% | ₹-8,304.71 |
| `BHARTIARTL` | Telecom | 6 | 33.3% | ₹-8,875.17 |
| `ICICIBANK` | Banking & Financial Services | 5 | 20.0% | ₹-8,999.63 |
| `HDFCBANK` | Banking & Financial Services | 5 | 40.0% | ₹-10,104.94 |
| `TITAN` | General | 4 | 25.0% | ₹-11,219.65 |
| `VOLTAS` | Consumer Durables | 3 | 0.0% | ₹-11,511.67 |
| `PERSISTENT` | Information Technology | 7 | 14.3% | ₹-16,828.39 |
| `BAJFINANCE` | General | 6 | 16.7% | ₹-19,214.34 |
| `POLYCAB` | Consumer Durables / Cables | 14 | 21.4% | ₹-22,108.51 |
| `LT` | Infrastructure | 13 | 23.1% | ₹-25,695.37 |

## 5. Executed Trade Log (Chronological)

| Trade ID | Symbol | Direction | Entry Date | Entry Price | Exit Date | Exit Price | Shares | Net PnL | Exit Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AUROPHARMA_2_BUY` | `AUROPHARMA` | BUY | 2026-08-25 09:30 | ₹1,605.10 | 2026-08-26 09:15 | ₹1,618.86 | 155 | ₹2,620.69 | `STOP_LOSS_HIT` |
| `POLYCAB_3_BUY` | `POLYCAB` | BUY | 2026-08-25 09:45 | ₹9,066.50 | 2026-08-27 10:15 | ₹8,946.29 | 27 | ₹-3,788.97 | `STOP_LOSS_HIT` |
| `TCS_4_BUY` | `TCS` | BUY | 2026-08-25 10:00 | ₹2,276.30 | 2026-08-27 10:30 | ₹2,247.57 | 107 | ₹-3,622.85 | `STOP_LOSS_HIT` |
| `IDFCFIRSTB_7_BUY` | `IDFCFIRSTB` | BUY | 2026-08-27 10:45 | ₹84.08 | 2026-08-27 14:30 | ₹83.78 | 2863 | ₹-1,679.22 | `STOP_LOSS_HIT` |
| `HDFCBANK_8_BUY` | `HDFCBANK` | BUY | 2026-08-27 14:30 | ₹714.15 | 2026-08-27 15:15 | ₹711.04 | 350 | ₹-1,677.80 | `STOP_LOSS_HIT` |
| `CHAMBLFERT_5_BUY` | `CHAMBLFERT` | BUY | 2026-08-26 09:15 | ₹429.35 | 2026-08-28 10:30 | ₹422.64 | 582 | ₹-4,514.64 | `STOP_LOSS_HIT` |
| `BAJFINANCE_9_BUY` | `BAJFINANCE` | BUY | 2026-08-28 09:30 | ₹1,080.50 | 2026-08-31 09:15 | ₹1,068.31 | 231 | ₹-3,390.70 | `STOP_LOSS_HIT` |
| `POLYCAB_6_BUY` | `POLYCAB` | BUY | 2026-08-27 10:30 | ₹8,963.50 | 2026-08-31 09:30 | ₹9,013.07 | 27 | ₹1,440.29 | `STOP_LOSS_HIT` |
| `BHARTIARTL_10_BUY` | `BHARTIARTL` | BUY | 2026-08-28 11:00 | ₹1,877.90 | 2026-08-31 10:30 | ₹1,883.53 | 133 | ₹179.73 | `STOP_LOSS_HIT` |
| `LT_13_BUY` | `LT` | BUY | 2026-08-31 10:30 | ₹3,999.00 | 2026-08-31 10:45 | ₹3,987.29 | 62 | ₹-1,282.42 | `STOP_LOSS_HIT` |
| `BHARTIARTL_14_BUY` | `BHARTIARTL` | BUY | 2026-08-31 10:45 | ₹1,893.50 | 2026-08-31 15:00 | ₹1,867.33 | 130 | ₹-3,958.55 | `STOP_LOSS_HIT` |
| `SUNPHARMA_1_BUY` | `SUNPHARMA` | BUY | 2026-08-25 09:15 | ₹1,907.70 | 2026-08-31 15:15 | ₹1,965.10 | 131 | ₹7,582.13 | `TARGET_2_MACRO_REACHED` |
| `RBLBANK_11_BUY` | `RBLBANK` | BUY | 2026-08-31 09:45 | ₹381.60 | 2026-09-01 09:15 | ₹378.50 | 655 | ₹-2,649.31 | `STOP_LOSS_HIT` |
| `INFY_12_BUY` | `INFY` | BUY | 2026-08-31 10:00 | ₹1,118.50 | 2026-09-01 09:15 | ₹1,143.70 | 200 | ₹4,517.70 | `TARGET_2_MACRO_REACHED` |
| `LT_15_BUY` | `LT` | BUY | 2026-09-01 09:15 | ₹4,022.60 | 2026-09-01 10:00 | ₹4,003.80 | 62 | ₹-1,724.80 | `STOP_LOSS_HIT` |
| `NATIONALUM_18_BUY` | `NATIONALUM` | BUY | 2026-09-01 11:00 | ₹376.45 | 2026-09-01 12:45 | ₹374.51 | 664 | ₹-1,908.68 | `STOP_LOSS_HIT` |
| `LT_16_BUY` | `LT` | BUY | 2026-09-01 10:15 | ₹4,011.20 | 2026-09-01 13:00 | ₹4,023.30 | 62 | ₹565.32 | `STOP_LOSS_HIT` |
| `NATIONALUM_20_BUY` | `NATIONALUM` | BUY | 2026-09-01 13:00 | ₹375.25 | 2026-09-01 13:30 | ₹374.02 | 666 | ₹-1,440.27 | `STOP_LOSS_HIT` |
| `LT_21_BUY` | `LT` | BUY | 2026-09-01 13:15 | ₹4,017.90 | 2026-09-01 13:30 | ₹4,005.71 | 61 | ₹-1,293.53 | `STOP_LOSS_HIT` |
| `POLYCAB_19_BUY` | `POLYCAB` | BUY | 2026-09-01 11:45 | ₹9,051.00 | 2026-09-01 13:45 | ₹8,906.27 | 25 | ₹-4,119.80 | `STOP_LOSS_HIT` |
| `POLYCAB_23_BUY` | `POLYCAB` | BUY | 2026-09-01 14:15 | ₹8,938.50 | 2026-09-01 15:00 | ₹8,905.93 | 27 | ₹-1,417.46 | `STOP_LOSS_HIT` |
| `LT_24_BUY` | `LT` | BUY | 2026-09-01 14:30 | ₹3,996.40 | 2026-09-01 15:00 | ₹3,987.79 | 56 | ₹-984.55 | `STOP_LOSS_HIT` |
| `NATIONALUM_25_BUY` | `NATIONALUM` | BUY | 2026-09-01 15:00 | ₹370.00 | 2026-09-01 15:15 | ₹371.11 | 675 | ₹126.01 | `STOP_LOSS_HIT` |
| `RBLBANK_22_BUY` | `RBLBANK` | BUY | 2026-09-01 14:00 | ₹380.35 | 2026-09-02 09:15 | ₹378.55 | 657 | ₹-1,802.36 | `STOP_LOSS_HIT` |
| `POLYCAB_27_BUY` | `POLYCAB` | BUY | 2026-09-02 09:15 | ₹8,861.50 | 2026-09-02 09:30 | ₹8,888.08 | 28 | ₹189.31 | `STOP_LOSS_HIT` |
| `SBIN_26_BUY` | `SBIN` | BUY | 2026-09-02 09:15 | ₹1,028.40 | 2026-09-02 10:15 | ₹1,031.49 | 243 | ₹170.47 | `STOP_LOSS_HIT` |
| `POLYCAB_29_BUY` | `POLYCAB` | BUY | 2026-09-02 09:45 | ₹8,892.50 | 2026-09-02 10:15 | ₹8,851.07 | 24 | ₹-1,469.94 | `STOP_LOSS_HIT` |
| `SBIN_30_BUY` | `SBIN` | BUY | 2026-09-02 10:30 | ₹1,034.00 | 2026-09-02 11:30 | ₹1,025.18 | 241 | ₹-2,701.25 | `STOP_LOSS_HIT` |
| `LT_28_BUY` | `LT` | BUY | 2026-09-02 09:45 | ₹3,969.00 | 2026-09-02 12:45 | ₹3,980.91 | 62 | ₹184.65 | `STOP_LOSS_HIT` |
| `PERSISTENT_33_BUY` | `PERSISTENT` | BUY | 2026-09-02 13:45 | ₹5,691.50 | 2026-09-03 09:15 | ₹5,549.92 | 37 | ₹-5,704.67 | `STOP_LOSS_HIT` |
| `LT_32_BUY` | `LT` | BUY | 2026-09-02 13:00 | ₹3,981.60 | 2026-09-03 12:00 | ₹3,993.54 | 62 | ₹184.76 | `STOP_LOSS_HIT` |
| `POLYCAB_35_BUY` | `POLYCAB` | BUY | 2026-09-03 12:00 | ₹8,921.50 | 2026-09-03 15:15 | ₹8,815.70 | 27 | ₹-3,391.59 | `STOP_LOSS_HIT` |
| `PERSISTENT_34_BUY` | `PERSISTENT` | BUY | 2026-09-03 09:15 | ₹5,590.00 | 2026-09-07 09:15 | ₹5,634.01 | 37 | ₹1,954.77 | `STOP_LOSS_HIT` |
| `PERSISTENT_37_BUY` | `PERSISTENT` | BUY | 2026-09-07 09:30 | ₹5,566.50 | 2026-09-07 12:15 | ₹5,543.36 | 37 | ₹-1,316.65 | `STOP_LOSS_HIT` |
| `PERSISTENT_38_BUY` | `PERSISTENT` | BUY | 2026-09-07 12:30 | ₹5,563.50 | 2026-09-07 13:00 | ₹5,539.39 | 37 | ₹-1,352.27 | `STOP_LOSS_HIT` |

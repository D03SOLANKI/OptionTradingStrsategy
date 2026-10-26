# Agent Report: Market & Stock Scanning Agent (`AGENT_1_MARKET_SCANNER`)
**Execution Timestamp**: 2026-10-16 13:15:10 | **Status**: Completed | **Processing Latency**: 1.97 ms
**Confidence Assessment**: 90.0%

---
### 1. Objective and Task Scope
Scan multi-cap universe, assess benchmark trend & sector momentum, and eliminate illiquid stocks.

### 2. Input Data Analyzed
1 NSE stocks ingested across Large, Mid, and Small-cap tiers. Evaluation time: 2026-08-31 10:00:00+05:30.

### 3. Analysis Methodology and Formulas
20-bar momentum breadth ratio, 14-period ATR % volatility thresholding, and 20-period average volume gating.

### 4. Mathematical Calculations & Evidence
- **MARKET_BREADTH**: `Breadth_Ratio = Positive_Momentum_Stocks / Total_Valid_Stocks` -> **1.0** (Inputs: {'positive_count': 1, 'total_valid': 1})
- **INFY**: `Turnover_INR = 20_SMA_Volume * Close_Price` -> **886026291.2** (Inputs: {'20_SMA_Volume': 814362, 'Close': 1088.0})

### 5. Selection and Rejection Breakdown
- **Selected Candidates (1)**: INFY
- **Rejected Stocks (0)**:

### 6. Output Passed to Downstream Agents
Shortlisted 1 stocks passed to Support & Resistance Agent with full sector metrics.

### 7. Limitations & Edge Cases Identified
- Market breadth is approximated from the ingested universe rather than the full 2000+ NSE equity list.
- Historical volume spikes on quarterly earnings dates can temporarily elevate average turnover metrics.
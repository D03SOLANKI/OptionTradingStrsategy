"""
Market Data Feed: Ingestion, Caching, Volatility Estimation, and Regime Simulation.
Supports real NSE stock data via yfinance, local parquet/csv files,
and institutional synthetic multi-regime time-series for comprehensive stress testing.
"""

import os
import math
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta, time
from typing import Optional, Dict, Tuple, List, Literal, Any, Callable

from src.config.nse_symbols import get_symbol_spec
from src.config.constants import MARKET_TIMEZONE

class MarketDataFeed:
    """
    Unified Data Feed for 15M and 4H NSE Market Data.
    """

    def __init__(self, cache_dir: str = "data/raw"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def fetch_yfinance_data(
        self,
        symbol: str,
        period: str = "60d",
        interval: str = "15m",
        force_reload: bool = False
    ) -> pd.DataFrame:
        """
        Fetches intraday 15M OHLCV data from Yahoo Finance for NSE stocks.
        Caches to disk as Parquet for deterministic reproducibility.
        """
        import yfinance as yf
        spec = get_symbol_spec(symbol)
        ticker_str = spec.yf_ticker
        cache_file = os.path.join(self.cache_dir, f"{spec.symbol}_{period}_{interval}.parquet")

        import time as time_mod
        # Check cache validity with TTL (45 mins during live market hours)
        if not force_reload and os.path.exists(cache_file):
            try:
                mtime = os.path.getmtime(cache_file)
                age_sec = time_mod.time() - mtime
                if age_sec < 2700:  # Fresh within 45 minutes
                    df = pd.read_parquet(cache_file)
                    if not df.empty and len(df) >= 30:
                        return self._clean_and_enrich(df)
            except Exception:
                pass

        try:
            ticker = yf.Ticker(ticker_str)
            df = ticker.history(period=period, interval=interval)
            if not df.empty and len(df) >= 10:
                # Standardize column names
                df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
                df.index = pd.to_datetime(df.index)

                # Convert timezone to IST Asia/Kolkata
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC").tz_convert(MARKET_TIMEZONE)
                else:
                    df.index = df.index.tz_convert(MARKET_TIMEZONE)

                # Save fresh data to cache
                df.to_parquet(cache_file)
                return self._clean_and_enrich(df)
        except Exception:
            pass

        # Graceful fallback: return existing cached data if live fetch hit a network hiccup
        if os.path.exists(cache_file):
            df = pd.read_parquet(cache_file)
            if not df.empty:
                return self._clean_and_enrich(df)

        raise ValueError(f"No data returned for ticker {ticker_str} (period={period}, interval={interval}).")

    def get_stock_data(
        self,
        symbol: str,
        period: str = "60d",
        interval: str = "15m",
        force_reload: bool = False
    ) -> pd.DataFrame:
        """
        Fetches real yfinance data with seamless fallback to realistic multi-regime simulation.
        """
        try:
            return self.fetch_yfinance_data(symbol, period=period, interval=interval, force_reload=force_reload)
        except Exception:
            spec = get_symbol_spec(symbol)
            prices = {
                "TCS": 3500.0, "RELIANCE": 2800.0, "INFY": 1500.0, "HDFCBANK": 1650.0,
                "ICICIBANK": 1250.0, "SBIN": 820.0, "LT": 3600.0, "BHARTIARTL": 1600.0,
                "ITC": 490.0, "TATAMOTORS": 980.0, "TATASTEEL": 160.0, "SUNPHARMA": 1850.0,
                "POLYCAB": 6800.0, "PERSISTENT": 5200.0, "COFORGE": 7500.0, "VOLTAS": 1800.0,
                "AUROPHARMA": 1400.0, "BSOFT": 650.0, "NATIONALUM": 220.0, "RBLBANK": 210.0,
                "IDFCFIRSTB": 75.0, "CHAMBLFERT": 510.0
            }
            base_p = prices.get(spec.symbol, 1000.0)
            return self.generate_synthetic_regime_data(
                symbol=spec.symbol,
                base_price=base_p,
                num_days=60,
                regime="MULTI_REGIME"
            )

    def get_batch_stock_data(
        self,
        symbols: List[str],
        period: str = "60d",
        interval: str = "15m",
        max_workers: int = 16,
        force_reload: bool = False,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        High-performance concurrent multi-threaded ingestion for hundreds of stocks in seconds.
        """
        import concurrent.futures
        results: Dict[str, pd.DataFrame] = {}
        total = len(symbols)
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sym = {
                executor.submit(self.get_stock_data, sym, period, interval, force_reload): sym
                for sym in symbols
            }
            for future in concurrent.futures.as_completed(future_to_sym):
                sym = future_to_sym[future]
                completed += 1
                try:
                    df = future.result()
                    if df is not None and not df.empty and len(df) >= 60:
                        results[sym] = df
                except Exception:
                    pass
                if progress_callback:
                    progress_callback(completed, total, sym)

        return results

    def generate_synthetic_regime_data(
        self,
        symbol: str = "RELIANCE",
        start_date: str = "2024-01-01",
        num_days: int = 180,
        regime: Literal["BULLISH", "BEARISH", "SIDEWAYS", "MULTI_REGIME"] = "MULTI_REGIME",
        base_price: float = 2500.0,
        base_annual_vol: float = 0.22,
        seed: int = 42
    ) -> pd.DataFrame:
        """
        Generates realistic synthetic 15-minute intraday NSE price series with
        stochastic volatility, intraday U-shape volume patterns, and distinct market regimes.
        Allows multi-year testing and walk-forward analysis free from look-ahead bias.
        """
        np.random.seed(seed)
        start_dt = pd.to_datetime(start_date)

        # Generate valid trading days (Monday to Friday)
        dates = []
        curr = start_dt
        while len(dates) < num_days:
            if curr.weekday() < 5:  # Monday to Friday
                dates.append(curr.date())
            curr += timedelta(days=1)

        # 25 bars per day (09:15 to 15:30)
        bars_per_day = 25
        dt_minutes = 15
        dt_annual = 15.0 / (252.0 * 375.0)

        rows = []
        current_spot = base_price

        # Intraday U-shaped volume multiplier
        t_norm = np.linspace(-1, 1, bars_per_day)
        u_shape_vol = 1.0 + 1.2 * (t_norm ** 2)

        for day_idx, trade_date in enumerate(dates):
            # Determine regime drift
            if regime == "BULLISH":
                daily_drift = 0.0012  # Steady upward trend
            elif regime == "BEARISH":
                daily_drift = -0.0012 # Steady downward trend
            elif regime == "SIDEWAYS":
                # Mean reverting around base_price
                daily_drift = -0.05 * (current_spot - base_price) / base_price
            else: # MULTI_REGIME (cycles between Bull, Bear, and Sideways)
                phase = (day_idx // 30) % 3
                if phase == 0:
                    daily_drift = 0.0015  # Bullish
                elif phase == 1:
                    daily_drift = -0.0015 # Bearish
                else:
                    daily_drift = -0.03 * (current_spot - base_price) / base_price # Sideways

            bar_drift = daily_drift / bars_per_day
            bar_vol = base_annual_vol * math.sqrt(dt_annual)

            for b in range(bars_per_day):
                bar_time = time(9, 15)
                # Compute timestamp: 09:15 + b * 15m
                bar_dt = datetime.combine(trade_date, time(9, 15)) + timedelta(minutes=b * 15)
                bar_dt_ts = pd.Timestamp(bar_dt).tz_localize(MARKET_TIMEZONE)

                # Return simulation with occasional jump
                jump = 0.0
                if np.random.rand() < 0.02:
                    jump = np.random.normal(0, 0.008)

                ret = bar_drift + bar_vol * np.random.normal(0, 1) + jump

                # Generate bar OHLC
                bar_open = current_spot
                bar_close = current_spot * math.exp(ret)
                # Intrabar noise for High and Low
                bar_high = max(bar_open, bar_close) * (1.0 + abs(np.random.normal(0, bar_vol * 0.7)))
                bar_low = min(bar_open, bar_close) * (1.0 - abs(np.random.normal(0, bar_vol * 0.7)))
                base_volume = int(np.random.lognormal(mean=11.5, sigma=0.4))
                volume = int(base_volume * u_shape_vol[b])

                current_spot = bar_close

                rows.append({
                    "Datetime": bar_dt_ts,
                    "Open": round(bar_open, 2),
                    "High": round(bar_high, 2),
                    "Low": round(bar_low, 2),
                    "Close": round(bar_close, 2),
                    "Volume": volume
                })

        df = pd.DataFrame(rows).set_index("Datetime").sort_index()
        return self._clean_and_enrich(df)

    def _clean_and_enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans data and enriches with point-in-time volatility metrics:
        - Parkinson Volatility (High-Low)
        - ATR (Average True Range)
        - Rolling Annualized Volatility
        """
        df = df.copy()
        # Drop duplicates & NaNs
        df = df[~df.index.duplicated(keep="first")]
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])

        # True Range
        high_low = df["High"] - df["Low"]
        high_prev_close = (df["High"] - df["Close"].shift(1)).abs()
        low_prev_close = (df["Low"] - df["Close"].shift(1)).abs()
        tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
        df["TR"] = tr
        df["ATR_14"] = tr.rolling(window=14, min_periods=1).mean()

        # Parkinson Volatility estimator (Annualized)
        # sigma_p = sqrt( (1 / (4 * ln(2))) * sum(ln(H/L)^2) / N ) * sqrt(252 * 25)
        hl_ratio_sq = (np.log(df["High"] / df["Low"])) ** 2
        rolling_hl = hl_ratio_sq.rolling(window=50, min_periods=10).mean()
        parkinson_vol = np.sqrt(rolling_hl / (4.0 * np.log(2))) * math.sqrt(252.0 * 25.0)
        df["Parkinson_Vol"] = parkinson_vol.fillna(0.22)

        # Log returns & Close-to-Close Volatility
        log_ret = np.log(df["Close"] / df["Close"].shift(1))
        df["Vol_Annual"] = log_ret.rolling(window=100, min_periods=20).std() * math.sqrt(252.0 * 25.0)
        df["Vol_Annual"] = df["Vol_Annual"].fillna(df["Parkinson_Vol"]).fillna(0.22)

        return df

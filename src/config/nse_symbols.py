"""
NSE F&O Stock Specifications: Lot Sizes, Strike Steps, and Sector Classifications.
Data reflects typical NSE derivatives contract specifications.
"""

from typing import Dict, Any, NamedTuple

class SymbolSpec(NamedTuple):
    symbol: str
    name: str
    lot_size: int
    strike_step: float
    sector: str
    yf_ticker: str

# Standard specifications for prominent NSE F&O universe
NSE_FO_UNIVERSE: Dict[str, SymbolSpec] = {
    "RELIANCE": SymbolSpec(
        symbol="RELIANCE",
        name="Reliance Industries Ltd",
        lot_size=250,
        strike_step=20.0,
        sector="Energy / Conglomerate",
        yf_ticker="RELIANCE.NS"
    ),
    "TCS": SymbolSpec(
        symbol="TCS",
        name="Tata Consultancy Services Ltd",
        lot_size=175,
        strike_step=50.0,
        sector="Information Technology",
        yf_ticker="TCS.NS"
    ),
    "INFY": SymbolSpec(
        symbol="INFY",
        name="Infosys Ltd",
        lot_size=400,
        strike_step=20.0,
        sector="Information Technology",
        yf_ticker="INFY.NS"
    ),
    "HDFCBANK": SymbolSpec(
        symbol="HDFCBANK",
        name="HDFC Bank Ltd",
        lot_size=550,
        strike_step=10.0,
        sector="Banking & Financial Services",
        yf_ticker="HDFCBANK.NS"
    ),
    "ICICIBANK": SymbolSpec(
        symbol="ICICIBANK",
        name="ICICI Bank Ltd",
        lot_size=700,
        strike_step=10.0,
        sector="Banking & Financial Services",
        yf_ticker="ICICIBANK.NS"
    ),
    "SBIN": SymbolSpec(
        symbol="SBIN",
        name="State Bank of India",
        lot_size=750,
        strike_step=10.0,
        sector="Banking & Financial Services",
        yf_ticker="SBIN.NS"
    ),
    "TATAMOTORS": SymbolSpec(
        symbol="TATAMOTORS",
        name="Tata Motors Ltd",
        lot_size=700,
        strike_step=10.0,
        sector="Automobile",
        yf_ticker="TATAMOTORS.NS"
    ),
    "BHARTIARTL": SymbolSpec(
        symbol="BHARTIARTL",
        name="Bharti Airtel Ltd",
        lot_size=475,
        strike_step=20.0,
        sector="Telecom",
        yf_ticker="BHARTIARTL.NS"
    ),
    "ITC": SymbolSpec(
        symbol="ITC",
        name="ITC Ltd",
        lot_size=1600,
        strike_step=5.0,
        sector="FMCG",
        yf_ticker="ITC.NS"
    ),
    "LT": SymbolSpec(
        symbol="LT",
        name="Larsen & Toubro Ltd",
        lot_size=175,
        strike_step=50.0,
        sector="Capital Goods / Infrastructure",
        yf_ticker="LT.NS"
    ),
}

def get_symbol_spec(symbol: str) -> SymbolSpec:
    clean_sym = symbol.replace(".NS", "").upper()
    if clean_sym in NSE_FO_UNIVERSE:
        return NSE_FO_UNIVERSE[clean_sym]
    # Default fallback specification
    return SymbolSpec(
        symbol=clean_sym,
        name=clean_sym,
        lot_size=250,
        strike_step=20.0,
        sector="General",
        yf_ticker=f"{clean_sym}.NS"
    )

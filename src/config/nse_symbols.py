"""
NSE F&O Stock Specifications: Lot Sizes, Strike Steps, Sector, and Market Cap Categories.
Covers Large Cap, Mid Cap, and Small-Mid Cap F&O Universe with exact contract parameters.
"""

from typing import Dict, Any, NamedTuple, Literal

class SymbolSpec(NamedTuple):
    symbol: str
    name: str
    lot_size: int
    strike_step: float
    sector: str
    cap_category: Literal["LARGE_CAP", "MID_CAP", "SMALL_CAP"]
    yf_ticker: str

# Standard specifications for prominent NSE F&O universe
NSE_FO_UNIVERSE: Dict[str, SymbolSpec] = {
    # ------------------ LARGE CAP F&O ------------------
    "RELIANCE": SymbolSpec(
        symbol="RELIANCE", name="Reliance Industries Ltd", lot_size=250,
        strike_step=20.0, sector="Energy / Conglomerate", cap_category="LARGE_CAP", yf_ticker="RELIANCE.NS"
    ),
    "TCS": SymbolSpec(
        symbol="TCS", name="Tata Consultancy Services Ltd", lot_size=175,
        strike_step=50.0, sector="Information Technology", cap_category="LARGE_CAP", yf_ticker="TCS.NS"
    ),
    "INFY": SymbolSpec(
        symbol="INFY", name="Infosys Ltd", lot_size=400,
        strike_step=20.0, sector="Information Technology", cap_category="LARGE_CAP", yf_ticker="INFY.NS"
    ),
    "HDFCBANK": SymbolSpec(
        symbol="HDFCBANK", name="HDFC Bank Ltd", lot_size=550,
        strike_step=10.0, sector="Banking & Financial Services", cap_category="LARGE_CAP", yf_ticker="HDFCBANK.NS"
    ),
    "ICICIBANK": SymbolSpec(
        symbol="ICICIBANK", name="ICICI Bank Ltd", lot_size=700,
        strike_step=10.0, sector="Banking & Financial Services", cap_category="LARGE_CAP", yf_ticker="ICICIBANK.NS"
    ),
    "SBIN": SymbolSpec(
        symbol="SBIN", name="State Bank of India", lot_size=750,
        strike_step=10.0, sector="Banking & Financial Services", cap_category="LARGE_CAP", yf_ticker="SBIN.NS"
    ),
    "LT": SymbolSpec(
        symbol="LT", name="Larsen & Toubro Ltd", lot_size=175,
        strike_step=50.0, sector="Infrastructure", cap_category="LARGE_CAP", yf_ticker="LT.NS"
    ),
    "BHARTIARTL": SymbolSpec(
        symbol="BHARTIARTL", name="Bharti Airtel Ltd", lot_size=475,
        strike_step=20.0, sector="Telecom", cap_category="LARGE_CAP", yf_ticker="BHARTIARTL.NS"
    ),
    "ITC": SymbolSpec(
        symbol="ITC", name="ITC Ltd", lot_size=1600,
        strike_step=5.0, sector="FMCG / Consumption", cap_category="LARGE_CAP", yf_ticker="ITC.NS"
    ),
    "TATAMOTORS": SymbolSpec(
        symbol="TATAMOTORS", name="Tata Motors Ltd", lot_size=700,
        strike_step=10.0, sector="Automobile", cap_category="LARGE_CAP", yf_ticker="TATAMOTORS.NS"
    ),
    "TATASTEEL": SymbolSpec(
        symbol="TATASTEEL", name="Tata Steel Ltd", lot_size=5500,
        strike_step=2.5, sector="Metals & Mining", cap_category="LARGE_CAP", yf_ticker="TATASTEEL.NS"
    ),
    "SUNPHARMA": SymbolSpec(
        symbol="SUNPHARMA", name="Sun Pharmaceutical Industries Ltd", lot_size=700,
        strike_step=10.0, sector="Healthcare & Pharma", cap_category="LARGE_CAP", yf_ticker="SUNPHARMA.NS"
    ),

    # ------------------ MID CAP F&O ------------------
    "POLYCAB": SymbolSpec(
        symbol="POLYCAB", name="Polycab India Ltd", lot_size=125,
        strike_step=50.0, sector="Consumer Durables / Cables", cap_category="MID_CAP", yf_ticker="POLYCAB.NS"
    ),
    "PERSISTENT": SymbolSpec(
        symbol="PERSISTENT", name="Persistent Systems Ltd", lot_size=100,
        strike_step=50.0, sector="Information Technology", cap_category="MID_CAP", yf_ticker="PERSISTENT.NS"
    ),
    "COFORGE": SymbolSpec(
        symbol="COFORGE", name="Coforge Ltd", lot_size=150,
        strike_step=50.0, sector="Information Technology", cap_category="MID_CAP", yf_ticker="COFORGE.NS"
    ),
    "VOLTAS": SymbolSpec(
        symbol="VOLTAS", name="Voltas Ltd", lot_size=375,
        strike_step=20.0, sector="Consumer Durables", cap_category="MID_CAP", yf_ticker="VOLTAS.NS"
    ),
    "AUROPHARMA": SymbolSpec(
        symbol="AUROPHARMA", name="Aurobindo Pharma Ltd", lot_size=550,
        strike_step=20.0, sector="Pharmaceuticals", cap_category="MID_CAP", yf_ticker="AUROPHARMA.NS"
    ),

    # ------------------ SMALL-MID CAP F&O ------------------
    # The smallest market-cap / high-beta permitted derivatives in the NSE F&O list
    "BSOFT": SymbolSpec(
        symbol="BSOFT", name="Birlasoft Ltd", lot_size=1000,
        strike_step=10.0, sector="Information Technology", cap_category="SMALL_CAP", yf_ticker="BSOFT.NS"
    ),
    "NATIONALUM": SymbolSpec(
        symbol="NATIONALUM", name="National Aluminium Co Ltd", lot_size=3750,
        strike_step=2.5, sector="Metals & Mining", cap_category="SMALL_CAP", yf_ticker="NATIONALUM.NS"
    ),
    "RBLBANK": SymbolSpec(
        symbol="RBLBANK", name="RBL Bank Ltd", lot_size=2500,
        strike_step=5.0, sector="Banking & Financial Services", cap_category="SMALL_CAP", yf_ticker="RBLBANK.NS"
    ),
    "IDFCFIRSTB": SymbolSpec(
        symbol="IDFCFIRSTB", name="IDFC First Bank Ltd", lot_size=7500,
        strike_step=1.0, sector="Banking & Financial Services", cap_category="SMALL_CAP", yf_ticker="IDFCFIRSTB.NS"
    ),
    "CHAMBLFERT": SymbolSpec(
        symbol="CHAMBLFERT", name="Chambal Fertilisers Ltd", lot_size=1500,
        strike_step=5.0, sector="Chemicals & Fertilizers", cap_category="SMALL_CAP", yf_ticker="CHAMBLFERT.NS"
    ),
}

def get_symbol_spec(symbol: str) -> SymbolSpec:
    clean_sym = symbol.replace(".NS", "").upper()
    if clean_sym in NSE_FO_UNIVERSE:
        return NSE_FO_UNIVERSE[clean_sym]
    return SymbolSpec(
        symbol=clean_sym,
        name=clean_sym,
        lot_size=250,
        strike_step=20.0,
        sector="General",
        cap_category="LARGE_CAP",
        yf_ticker=f"{clean_sym}.NS"
    )

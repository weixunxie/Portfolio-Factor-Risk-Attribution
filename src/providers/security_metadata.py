"""
src/providers/security_metadata.py

Static fallback metadata and normalization helpers for security profiles.

Used when live API sources (Alpha Vantage, yfinance) return incomplete
or missing company name, sector, or security type.

The fallback map covers the demo tickers and common ETFs.
Add new entries here for any tickers you want supported offline.
"""

from __future__ import annotations

# ── Static fallback map ────────────────────────────────────────────────────────

_FALLBACK_MAP: dict[str, dict] = {
    # ── Large-cap equities ────────────────────────────────────────────────────
    "AAPL":  {"name": "Apple Inc",                             "sector": "Technology",             "industry": "Consumer Electronics",          "security_type": "Equity"},
    "MSFT":  {"name": "Microsoft Corporation",                 "sector": "Technology",             "industry": "Software",                      "security_type": "Equity"},
    "NVDA":  {"name": "NVIDIA Corporation",                    "sector": "Technology",             "industry": "Semiconductors",                "security_type": "Equity"},
    "GOOGL": {"name": "Alphabet Inc",                          "sector": "Communication Services", "industry": "Internet Content & Information","security_type": "Equity"},
    "GOOG":  {"name": "Alphabet Inc",                          "sector": "Communication Services", "industry": "Internet Content & Information","security_type": "Equity"},
    "AMZN":  {"name": "Amazon.com Inc",                        "sector": "Consumer Cyclical",      "industry": "Internet Retail",               "security_type": "Equity"},
    "META":  {"name": "Meta Platforms Inc",                    "sector": "Communication Services", "industry": "Internet Content & Information","security_type": "Equity"},
    "TSLA":  {"name": "Tesla Inc",                             "sector": "Consumer Cyclical",      "industry": "Auto Manufacturers",            "security_type": "Equity"},
    "NFLX":  {"name": "Netflix Inc",                           "sector": "Communication Services", "industry": "Entertainment",                 "security_type": "Equity"},
    "ORCL":  {"name": "Oracle Corporation",                    "sector": "Technology",             "industry": "Software",                      "security_type": "Equity"},
    "CRM":   {"name": "Salesforce Inc",                        "sector": "Technology",             "industry": "Software",                      "security_type": "Equity"},
    "ADBE":  {"name": "Adobe Inc",                             "sector": "Technology",             "industry": "Software",                      "security_type": "Equity"},
    "INTC":  {"name": "Intel Corporation",                     "sector": "Technology",             "industry": "Semiconductors",                "security_type": "Equity"},
    "AMD":   {"name": "Advanced Micro Devices Inc",            "sector": "Technology",             "industry": "Semiconductors",                "security_type": "Equity"},
    "PYPL":  {"name": "PayPal Holdings Inc",                   "sector": "Financial Services",     "industry": "Credit Services",               "security_type": "Equity"},
    "JPM":   {"name": "JPMorgan Chase & Co",                   "sector": "Financial Services",     "industry": "Banks",                         "security_type": "Equity"},
    "BAC":   {"name": "Bank of America Corporation",           "sector": "Financial Services",     "industry": "Banks",                         "security_type": "Equity"},
    "GS":    {"name": "Goldman Sachs Group Inc",               "sector": "Financial Services",     "industry": "Capital Markets",               "security_type": "Equity"},
    "V":     {"name": "Visa Inc",                              "sector": "Financial Services",     "industry": "Credit Services",               "security_type": "Equity"},
    "MA":    {"name": "Mastercard Inc",                        "sector": "Financial Services",     "industry": "Credit Services",               "security_type": "Equity"},
    "BRK.B": {"name": "Berkshire Hathaway Inc",                "sector": "Financial Services",     "industry": "Insurance",                     "security_type": "Equity"},
    "JNJ":   {"name": "Johnson & Johnson",                     "sector": "Healthcare",             "industry": "Drug Manufacturers",            "security_type": "Equity"},
    "UNH":   {"name": "UnitedHealth Group Inc",                "sector": "Healthcare",             "industry": "Healthcare Plans",              "security_type": "Equity"},
    "PFE":   {"name": "Pfizer Inc",                            "sector": "Healthcare",             "industry": "Drug Manufacturers",            "security_type": "Equity"},
    "XOM":   {"name": "Exxon Mobil Corporation",               "sector": "Energy",                 "industry": "Oil & Gas Integrated",          "security_type": "Equity"},
    "CVX":   {"name": "Chevron Corporation",                   "sector": "Energy",                 "industry": "Oil & Gas Integrated",          "security_type": "Equity"},
    "WMT":   {"name": "Walmart Inc",                           "sector": "Consumer Defensive",     "industry": "Discount Stores",               "security_type": "Equity"},
    "KO":    {"name": "Coca-Cola Company",                     "sector": "Consumer Defensive",     "industry": "Beverages",                     "security_type": "Equity"},
    "DIS":   {"name": "The Walt Disney Company",               "sector": "Communication Services", "industry": "Entertainment",                 "security_type": "Equity"},
    # ── ETFs ─────────────────────────────────────────────────────────────────
    "SPY":   {"name": "SPDR S&P 500 ETF Trust",                "sector": "ETF",                    "industry": "Broad Market Proxy",            "security_type": "ETF"},
    "QQQ":   {"name": "Invesco QQQ Trust",                     "sector": "ETF",                    "industry": "Growth Proxy",                  "security_type": "ETF"},
    "TLT":   {"name": "iShares 20+ Year Treasury Bond ETF",    "sector": "ETF",                    "industry": "Treasury Duration Proxy",       "security_type": "ETF"},
    "IEF":   {"name": "iShares 7-10 Year Treasury Bond ETF",   "sector": "ETF",                    "industry": "Treasury Duration Proxy",       "security_type": "ETF"},
    "AGG":   {"name": "iShares Core U.S. Aggregate Bond ETF",  "sector": "ETF",                    "industry": "Bond Aggregate Proxy",          "security_type": "ETF"},
    "GLD":   {"name": "SPDR Gold Trust",                       "sector": "ETF",                    "industry": "Commodity Proxy",               "security_type": "ETF"},
    "SLV":   {"name": "iShares Silver Trust",                  "sector": "ETF",                    "industry": "Commodity Proxy",               "security_type": "ETF"},
    "VTI":   {"name": "Vanguard Total Stock Market ETF",       "sector": "ETF",                    "industry": "Broad Market Proxy",            "security_type": "ETF"},
    "VOO":   {"name": "Vanguard S&P 500 ETF",                  "sector": "ETF",                    "industry": "Broad Market Proxy",            "security_type": "ETF"},
    "VEA":   {"name": "Vanguard FTSE Developed Markets ETF",   "sector": "ETF",                    "industry": "International Equity Proxy",    "security_type": "ETF"},
    "EEM":   {"name": "iShares MSCI Emerging Markets ETF",     "sector": "ETF",                    "industry": "Emerging Market Proxy",         "security_type": "ETF"},
    "XLK":   {"name": "Technology Select Sector SPDR Fund",    "sector": "ETF",                    "industry": "Technology Sector Proxy",       "security_type": "ETF"},
    "XLF":   {"name": "Financial Select Sector SPDR Fund",     "sector": "ETF",                    "industry": "Financial Sector Proxy",        "security_type": "ETF"},
    "XLE":   {"name": "Energy Select Sector SPDR Fund",        "sector": "ETF",                    "industry": "Energy Sector Proxy",           "security_type": "ETF"},
    "XLV":   {"name": "Health Care Select Sector SPDR Fund",   "sector": "ETF",                    "industry": "Healthcare Sector Proxy",       "security_type": "ETF"},
    "ARKK":  {"name": "ARK Innovation ETF",                    "sector": "ETF",                    "industry": "Growth Proxy",                  "security_type": "ETF"},
    "HYG":   {"name": "iShares iBoxx $ High Yield Corp Bond ETF","sector": "ETF",                  "industry": "High Yield Bond Proxy",         "security_type": "ETF"},
    "LQD":   {"name": "iShares iBoxx $ Investment Grade Corp Bond ETF","sector": "ETF",            "industry": "Investment Grade Bond Proxy",   "security_type": "ETF"},
}

# ── Sector normalization map ───────────────────────────────────────────────────
# Alpha Vantage returns sector in ALLCAPS; map to consistent display labels.

_SECTOR_NORMALIZE: dict[str, str] = {
    "TECHNOLOGY":               "Technology",
    "COMMUNICATION SERVICES":   "Communication Services",
    "CONSUMER CYCLICAL":        "Consumer Cyclical",
    "CONSUMER DEFENSIVE":       "Consumer Defensive",
    "FINANCIAL SERVICES":       "Financial Services",
    "HEALTHCARE":               "Healthcare",
    "INDUSTRIALS":              "Industrials",
    "BASIC MATERIALS":          "Basic Materials",
    "REAL ESTATE":              "Real Estate",
    "UTILITIES":                "Utilities",
    "ENERGY":                   "Energy",
    # Alpha Vantage alternate labels
    "FINANCIALS":               "Financial Services",
    "CONSUMER DISCRETIONARY":  "Consumer Cyclical",
    "CONSUMER STAPLES":         "Consumer Defensive",
    "MATERIALS":                "Basic Materials",
    "INFORMATION TECHNOLOGY":  "Technology",
    "COMMUNICATION":            "Communication Services",
    # Pass-through for already-normalized values
    "ETF":                      "ETF",
    "CASH":                     "Cash",
}


# ── Public helpers ─────────────────────────────────────────────────────────────

def normalize_sector_label(sector: str) -> str:
    """
    Normalize a raw sector string to a consistent display label.
    Handles AV's ALLCAPS output and various alternate naming conventions.
    """
    if not sector:
        return ""
    upper = sector.upper().strip()
    if upper in _SECTOR_NORMALIZE:
        return _SECTOR_NORMALIZE[upper]
    # Fall back to title-case for unknown sectors
    return sector.strip().title()


def get_fallback_metadata(ticker: str) -> dict | None:
    """Return the static fallback entry for *ticker*, or None if not in the map."""
    return _FALLBACK_MAP.get(ticker.upper().strip())


def resolve_security_metadata(ticker: str, live_profile: dict) -> dict:
    """
    Apply the full fallback chain to a live profile dict.

    Resolution order per field
    --------------------------
    name          : live_profile → fallback map → ticker symbol
    sector        : live_profile (normalized) → fallback map → "Unknown"
    industry      : live_profile → fallback map → ""
    security_type : live_profile → fallback map → inferred from sector → "Equity"

    Returns a shallow copy of live_profile with resolved/normalized fields added.
    Does not modify the input dict.
    """
    t = ticker.upper().strip()
    fb = _FALLBACK_MAP.get(t, {})

    resolved = dict(live_profile)

    # ── name ─────────────────────────────────────────────────────────────────
    live_name = (live_profile.get("name") or "").strip()
    resolved["name"] = live_name or fb.get("name") or t

    # ── sector ───────────────────────────────────────────────────────────────
    raw_sector = (live_profile.get("sector") or "").strip()
    normalized = normalize_sector_label(raw_sector) if raw_sector else ""
    resolved["sector"] = normalized or fb.get("sector") or "Unknown"

    # ── industry ─────────────────────────────────────────────────────────────
    live_industry = (live_profile.get("industry") or "").strip()
    resolved["industry"] = live_industry or fb.get("industry") or ""

    # ── security_type ─────────────────────────────────────────────────────────
    live_sec_type = (live_profile.get("security_type") or "").strip()
    if not live_sec_type:
        live_sec_type = fb.get("security_type") or ""
    if not live_sec_type:
        # Infer from resolved sector
        live_sec_type = "ETF" if resolved["sector"] == "ETF" else "Equity"
    resolved["security_type"] = live_sec_type

    return resolved

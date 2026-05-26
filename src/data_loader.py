"""
data_loader.py
Downloads adjusted close prices for the asset universe, cleans the data,
and saves prices.csv and returns.csv to data/processed/.
"""

import os
import yfinance as yf
import pandas as pd
from datetime import date

# Asset universe
TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "TLT"]

DEFAULT_START = "2018-01-01"
DEFAULT_END = str(date.today())

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")


def download_prices(tickers=TICKERS, start=DEFAULT_START, end=DEFAULT_END):
    """Download adjusted close prices from Yahoo Finance."""
    print(f"Downloading data for: {tickers}")
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    # Keep only the Close column (auto_adjust=True gives adjusted prices as Close)
    prices = raw["Close"]

    # Drop any rows where all tickers are NaN, then forward-fill remaining gaps
    prices = prices.dropna(how="all").ffill()

    # Drop columns that still have any NaN (asset had no data at all)
    prices = prices.dropna(axis=1)

    print(f"Downloaded {len(prices)} trading days, {prices.shape[1]} tickers.")
    return prices


def calculate_returns(prices):
    """Calculate daily percentage returns from price series."""
    returns = prices.pct_change().dropna()
    return returns


def save_data(prices, returns):
    """Save prices and returns DataFrames as CSV files."""
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    prices_path = os.path.join(PROCESSED_DIR, "prices.csv")
    returns_path = os.path.join(PROCESSED_DIR, "returns.csv")

    prices.to_csv(prices_path)
    returns.to_csv(returns_path)

    print(f"Saved: {prices_path}")
    print(f"Saved: {returns_path}")


if __name__ == "__main__":
    prices = download_prices()
    returns = calculate_returns(prices)
    save_data(prices, returns)
    print("Data loading complete.")

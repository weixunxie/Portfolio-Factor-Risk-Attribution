"""
portfolio.py
Validates portfolio weights, computes daily portfolio returns,
and saves portfolio_returns.csv and portfolio_weights.csv to outputs/tables/.
"""

import os
import pandas as pd
import numpy as np

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")

# Allowed tickers (must match what data_loader downloaded)
UNIVERSE = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "TLT"]

# Sample portfolio — weights must sum to 1.0
SAMPLE_PORTFOLIO = {
    "AAPL": 0.15,
    "MSFT": 0.15,
    "NVDA": 0.20,
    "GOOGL": 0.10,
    "AMZN": 0.10,
    "META": 0.10,
    "TSLA": 0.10,
    "SPY":  0.05,
    "QQQ":  0.03,
    "TLT":  0.02,
}


def validate_weights(weights: dict):
    """
    Check that all tickers are in the allowed universe
    and that weights sum to 1.0 (tolerates small float rounding).
    Raises ValueError if validation fails.
    """
    for ticker in weights:
        if ticker not in UNIVERSE:
            raise ValueError(f"Ticker '{ticker}' is not in the allowed universe: {UNIVERSE}")

    total = sum(weights.values())
    # Accept weights expressed as percentages (e.g. 15 instead of 0.15)
    if abs(total - 100.0) < 0.01:
        weights = {k: v / 100.0 for k, v in weights.items()}
        total = 1.0

    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0 (or 100%). Got: {total:.4f}")

    return weights


def load_returns():
    """Load daily returns from the processed data directory."""
    path = os.path.join(PROCESSED_DIR, "returns.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            "returns.csv not found. Run 'python src/data_loader.py' first."
        )
    returns = pd.read_csv(path, index_col=0, parse_dates=True)
    return returns


def compute_portfolio_returns(weights: dict, returns: pd.DataFrame):
    """
    Compute daily portfolio returns as the weighted sum of asset returns.
    Only uses tickers present in both the weights dict and the returns DataFrame.
    """
    tickers = list(weights.keys())
    weight_values = np.array([weights[t] for t in tickers])

    # Align to tickers that exist in the returns data
    available = [t for t in tickers if t in returns.columns]
    if len(available) < len(tickers):
        missing = set(tickers) - set(available)
        print(f"Warning: missing return data for {missing}. Skipping them.")
        weight_values = np.array([weights[t] for t in available])
        # Renormalize so weights still sum to 1
        weight_values = weight_values / weight_values.sum()

    portfolio_returns = returns[available].dot(weight_values)
    portfolio_returns.name = "portfolio"
    return portfolio_returns


def save_outputs(weights: dict, portfolio_returns: pd.Series):
    """Save portfolio weights and portfolio returns to CSV."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save weights
    weights_df = pd.DataFrame.from_dict(
        weights, orient="index", columns=["weight"]
    )
    weights_path = os.path.join(OUTPUT_DIR, "portfolio_weights.csv")
    weights_df.to_csv(weights_path)
    print(f"Saved: {weights_path}")

    # Save portfolio returns
    returns_path = os.path.join(OUTPUT_DIR, "portfolio_returns.csv")
    portfolio_returns.to_csv(returns_path, header=True)
    print(f"Saved: {returns_path}")


if __name__ == "__main__":
    weights = validate_weights(SAMPLE_PORTFOLIO)
    returns = load_returns()
    portfolio_returns = compute_portfolio_returns(weights, returns)
    save_outputs(weights, portfolio_returns)
    print("Portfolio construction complete.")

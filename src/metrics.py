"""
metrics.py
Calculates core risk and performance metrics for the portfolio and
saves risk_summary.csv and correlation_matrix.csv to outputs/tables/.
"""

import os
import pandas as pd
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "tables")
TRADING_DAYS = 252  # annualization factor


# --------------------------------------------------------------------------- #
# Metric functions — each accepts a pandas Series of daily returns             #
# --------------------------------------------------------------------------- #

def annualized_return(returns: pd.Series) -> float:
    """Compound annual growth rate from daily returns."""
    total = (1 + returns).prod()
    n_years = len(returns) / TRADING_DAYS
    return float(total ** (1 / n_years) - 1)


def annualized_volatility(returns: pd.Series) -> float:
    """Standard deviation of daily returns scaled to annual."""
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio assuming a given risk-free rate."""
    excess = returns - risk_free_rate / TRADING_DAYS
    if excess.std() == 0:
        return 0.0
    return float((excess.mean() / excess.std()) * np.sqrt(TRADING_DAYS))


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline in cumulative returns."""
    cumulative = (1 + returns).cumprod()
    rolling_peak = cumulative.cummax()
    drawdown = (cumulative - rolling_peak) / rolling_peak
    return float(drawdown.min())


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Historical VaR: the loss not exceeded with the given confidence level.
    Returned as a positive number representing the loss magnitude.
    """
    return float(-np.percentile(returns, (1 - confidence) * 100))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    CVaR (Expected Shortfall): average of returns below the VaR threshold.
    Returned as a positive number.
    """
    var = -value_at_risk(returns, confidence)  # negative threshold
    tail = returns[returns <= var]
    if tail.empty:
        return value_at_risk(returns, confidence)
    return float(-tail.mean())


# --------------------------------------------------------------------------- #
# I/O helpers                                                                  #
# --------------------------------------------------------------------------- #

def load_portfolio_returns() -> pd.Series:
    """Load the portfolio daily returns saved by portfolio.py."""
    path = os.path.join(OUTPUT_DIR, "portfolio_returns.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            "portfolio_returns.csv not found. Run 'python src/portfolio.py' first."
        )
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df.squeeze()  # convert single-column DataFrame to Series


def load_asset_returns() -> pd.DataFrame:
    """Load the individual asset daily returns saved by data_loader.py."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "data", "processed", "returns.csv"
    )
    if not os.path.exists(path):
        raise FileNotFoundError(
            "returns.csv not found. Run 'python src/data_loader.py' first."
        )
    return pd.read_csv(path, index_col=0, parse_dates=True)


def compute_risk_summary(portfolio_returns: pd.Series) -> pd.DataFrame:
    """Bundle all metrics into a single summary DataFrame."""
    metrics = {
        "Annualized Return":    annualized_return(portfolio_returns),
        "Annualized Volatility": annualized_volatility(portfolio_returns),
        "Sharpe Ratio":         sharpe_ratio(portfolio_returns),
        "Max Drawdown":         max_drawdown(portfolio_returns),
        "VaR 95%":              value_at_risk(portfolio_returns, 0.95),
        "CVaR 95%":             conditional_var(portfolio_returns, 0.95),
        "VaR 99%":              value_at_risk(portfolio_returns, 0.99),
        "CVaR 99%":             conditional_var(portfolio_returns, 0.99),
    }
    summary = pd.DataFrame.from_dict(metrics, orient="index", columns=["Value"])
    summary.index.name = "Metric"
    return summary


def save_outputs(summary: pd.DataFrame, corr_matrix: pd.DataFrame):
    """Save risk summary and correlation matrix to CSV."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    summary_path = os.path.join(OUTPUT_DIR, "risk_summary.csv")
    summary.to_csv(summary_path)
    print(f"Saved: {summary_path}")

    corr_path = os.path.join(OUTPUT_DIR, "correlation_matrix.csv")
    corr_matrix.to_csv(corr_path)
    print(f"Saved: {corr_path}")


if __name__ == "__main__":
    portfolio_returns = load_portfolio_returns()
    asset_returns = load_asset_returns()

    summary = compute_risk_summary(portfolio_returns)
    corr_matrix = asset_returns.corr()

    print("\n--- Risk Summary ---")
    print(summary.to_string())

    save_outputs(summary, corr_matrix)
    print("Metrics calculation complete.")

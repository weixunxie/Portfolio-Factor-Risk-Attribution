import pandas as pd
import numpy as np
import os

TRADING_DAYS = 252


def load_data():
    weights = pd.read_csv("outputs/tables/portfolio_weights.csv", index_col=0).squeeze("columns")
    returns = pd.read_csv("data/processed/returns.csv", index_col=0, parse_dates=True)
    port_returns = pd.read_csv("outputs/tables/portfolio_returns.csv", index_col=0, parse_dates=True).squeeze("columns")
    return weights, returns, port_returns


def annualized_volatility(returns: pd.DataFrame) -> pd.Series:
    return returns.std() * np.sqrt(TRADING_DAYS)


def weight_volatility_contribution(weights: pd.Series, vol: pd.Series) -> pd.Series:
    return weights * vol


def correlation_with_portfolio(returns: pd.DataFrame, port_returns: pd.Series) -> pd.Series:
    aligned_assets, aligned_port = returns.align(port_returns, join="inner", axis=0)
    return aligned_assets.corrwith(aligned_port)


def worst_days_avg_return(returns: pd.DataFrame, port_returns: pd.Series, n: int = 5) -> pd.Series:
    worst_dates = port_returns.nsmallest(n).index
    return returns.loc[returns.index.isin(worst_dates)].mean()


def build_contributors_table(weights, returns, port_returns):
    # Keep only assets present in both weights and returns
    assets = weights.index.intersection(returns.columns)
    weights = weights.loc[assets]
    returns = returns[assets]

    vol = annualized_volatility(returns)
    wv_contrib = weight_volatility_contribution(weights, vol)
    corr = correlation_with_portfolio(returns, port_returns)
    worst_avg = worst_days_avg_return(returns, port_returns)

    table = pd.DataFrame({
        "weight": weights,
        "annualized_volatility": vol,
        "weight_volatility_contribution": wv_contrib,
        "correlation_with_portfolio": corr,
        "average_return_on_worst_5_days": worst_avg,
    })

    # Rank: 1 = highest risk contributor
    table["rank_by_wv_contribution"] = table["weight_volatility_contribution"].rank(ascending=False).astype(int)
    table["rank_by_correlation"] = table["correlation_with_portfolio"].rank(ascending=False).astype(int)
    table["rank_by_worst_day_loss"] = table["average_return_on_worst_5_days"].rank(ascending=True).astype(int)

    return table.sort_values("weight_volatility_contribution", ascending=False)


def save_table(table: pd.DataFrame):
    os.makedirs("outputs/tables", exist_ok=True)
    path = "outputs/tables/top_risk_contributors.csv"
    table.to_csv(path)
    print(f"Saved: {path}")
    return path


def main():
    weights, returns, port_returns = load_data()
    table = build_contributors_table(weights, returns, port_returns)

    print("\nTop Risk Contributors:")
    print(table.to_string())

    save_table(table)


if __name__ == "__main__":
    main()

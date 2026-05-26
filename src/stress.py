import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

STRESS_PERIODS = {
    "COVID Crash": ("2020-02-19", "2020-03-23"),
    "2022 Rate-Hike Selloff": ("2022-01-03", "2022-10-14"),
}

CHART_FILENAMES = {
    "COVID Crash": "outputs/charts/covid_stress_cumulative_return.png",
    "2022 Rate-Hike Selloff": "outputs/charts/rate_hike_stress_cumulative_return.png",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    returns = pd.read_csv(
        "data/processed/returns.csv", index_col=0, parse_dates=True
    )
    port_returns = pd.read_csv(
        "outputs/tables/portfolio_returns.csv", index_col=0, parse_dates=True
    ).squeeze("columns")
    weights = pd.read_csv(
        "outputs/tables/portfolio_weights.csv", index_col=0
    ).squeeze("columns")
    return returns, port_returns, weights


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def slice_period(series_or_df, start, end):
    """Return rows between start and end dates (inclusive)."""
    return series_or_df.loc[start:end]


def cumulative_return(returns):
    """Total cumulative return from a series or dataframe of daily returns."""
    return (1 + returns).prod() - 1


def max_drawdown(port_returns):
    """Maximum peak-to-trough drawdown for a daily returns series."""
    cum = (1 + port_returns).cumprod()
    rolling_peak = cum.cummax()
    drawdown = (cum - rolling_peak) / rolling_peak
    return drawdown.min()


def cumulative_return_series(port_returns):
    """Running cumulative return indexed to 0 at the start."""
    return (1 + port_returns).cumprod() - 1


# ---------------------------------------------------------------------------
# Per-period analysis
# ---------------------------------------------------------------------------

def analyze_period(name, start, end, returns, port_returns, weights):
    port_slice = slice_period(port_returns, start, end)
    asset_slice = slice_period(returns, start, end)

    # Keep only assets that exist in weights
    assets = weights.index.intersection(asset_slice.columns)
    asset_slice = asset_slice[assets]
    weights_aligned = weights.loc[assets]

    port_cum_return = cumulative_return(port_slice)
    port_mdd = max_drawdown(port_slice)

    asset_cum_returns = cumulative_return(asset_slice)
    weighted_contributions = weights_aligned * asset_cum_returns

    # Worst 3 contributors = most negative weighted contribution
    worst_3 = weighted_contributions.nsmallest(3)

    summary = {
        "period": name,
        "start": start,
        "end": end,
        "portfolio_cumulative_return": round(port_cum_return, 4),
        "portfolio_max_drawdown": round(port_mdd, 4),
        "worst_contributor_1": worst_3.index[0] if len(worst_3) > 0 else "",
        "worst_contributor_2": worst_3.index[1] if len(worst_3) > 1 else "",
        "worst_contributor_3": worst_3.index[2] if len(worst_3) > 2 else "",
    }

    contributions = pd.DataFrame({
        "period": name,
        "asset": asset_cum_returns.index,
        "weight": weights_aligned.values,
        "asset_cumulative_return": asset_cum_returns.values,
        "weighted_contribution": weighted_contributions.values,
    }).sort_values("weighted_contribution")

    cum_return_series = cumulative_return_series(port_slice)

    return summary, contributions, cum_return_series


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def plot_cumulative_return(name, cum_return_series, filepath):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(cum_return_series.index, cum_return_series * 100, color="steelblue", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.fill_between(
        cum_return_series.index,
        cum_return_series * 100,
        0,
        where=(cum_return_series < 0),
        alpha=0.2,
        color="red",
        label="Loss",
    )
    ax.set_title(f"Portfolio Cumulative Return — {name}", fontsize=14)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Return (%)")
    ax.legend()
    fig.tight_layout()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Chart saved: {filepath}")


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_outputs(all_summaries, all_contributions):
    os.makedirs("outputs/tables", exist_ok=True)

    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv("outputs/tables/stress_summary.csv", index=False)
    print("Saved: outputs/tables/stress_summary.csv")

    contributions_df = pd.concat(all_contributions, ignore_index=True)
    contributions_df.to_csv("outputs/tables/stress_asset_contributions.csv", index=False)
    print("Saved: outputs/tables/stress_asset_contributions.csv")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    returns, port_returns, weights = load_data()

    all_summaries = []
    all_contributions = []

    for name, (start, end) in STRESS_PERIODS.items():
        print(f"\n--- {name} ({start} to {end}) ---")
        summary, contributions, cum_series = analyze_period(
            name, start, end, returns, port_returns, weights
        )

        print(f"  Portfolio cumulative return : {summary['portfolio_cumulative_return']:.2%}")
        print(f"  Portfolio max drawdown      : {summary['portfolio_max_drawdown']:.2%}")
        print(f"  Worst contributors          : {summary['worst_contributor_1']}, "
              f"{summary['worst_contributor_2']}, {summary['worst_contributor_3']}")

        all_summaries.append(summary)
        all_contributions.append(contributions)

        plot_cumulative_return(name, cum_series, CHART_FILENAMES[name])

    save_outputs(all_summaries, all_contributions)


if __name__ == "__main__":
    main()

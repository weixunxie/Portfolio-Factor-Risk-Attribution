import pandas as pd
from datetime import date
import os


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    risk = pd.read_csv("outputs/tables/risk_summary.csv", index_col=0).squeeze("columns")
    contributors = pd.read_csv("outputs/tables/top_risk_contributors.csv", index_col=0)
    stress = pd.read_csv("outputs/tables/stress_summary.csv")
    return risk, contributors, stress


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def pct(val, decimals=2):
    return f"{float(val) * 100:.{decimals}f}%"


def num(val, decimals=2):
    return f"{float(val):.{decimals}f}"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_executive_summary(risk, contributors, stress):
    ann_return = pct(risk["Annualized Return"])
    ann_vol = pct(risk["Annualized Volatility"])
    sharpe = num(risk["Sharpe Ratio"])
    max_dd = pct(risk["Max Drawdown"])

    top_wv_asset = contributors["weight_volatility_contribution"].idxmax()
    top_worst_asset = contributors["average_return_on_worst_5_days"].idxmin()

    covid = stress[stress["period"] == "COVID Crash"].iloc[0]
    rate = stress[stress["period"] == "2022 Rate-Hike Selloff"].iloc[0]

    return f"""## Executive Summary

This memo summarizes the quantitative risk profile of a fixed tech-heavy portfolio comprising
AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, and TLT. All metrics are derived from
historical daily price data and are backward-looking in nature.

Over the full analysis period the portfolio generated an annualized return of **{ann_return}**
with an annualized volatility of **{ann_vol}** and a Sharpe ratio of **{sharpe}**. The maximum
drawdown recorded was **{max_dd}**.

The largest single risk contributor by weight-adjusted volatility is **{top_wv_asset}**.
**{top_worst_asset}** recorded the steepest average loss across the portfolio's five worst trading days.

During the COVID crash the portfolio declined **{pct(covid["portfolio_cumulative_return"])}**, and
during the 2022 rate-hike selloff it fell **{pct(rate["portfolio_cumulative_return"])}** — the more
severe of the two stress episodes analyzed.
"""


def build_risk_metrics(risk):
    rows = [
        ("Annualized Return",     pct(risk["Annualized Return"])),
        ("Annualized Volatility", pct(risk["Annualized Volatility"])),
        ("Sharpe Ratio",          num(risk["Sharpe Ratio"])),
        ("Max Drawdown",          pct(risk["Max Drawdown"])),
        ("VaR 95%",               pct(risk["VaR 95%"])),
        ("CVaR 95%",              pct(risk["CVaR 95%"])),
        ("VaR 99%",               pct(risk["VaR 99%"])),
        ("CVaR 99%",              pct(risk["CVaR 99%"])),
    ]
    table_lines = [
        "| Metric | Value |",
        "|---|---|",
    ] + [f"| {m} | {v} |" for m, v in rows]

    return "## Portfolio Risk Metrics\n\n" + "\n".join(table_lines) + "\n"


def build_top_contributors(contributors):
    top_wv = contributors["weight_volatility_contribution"].idxmax()
    top_worst = contributors["average_return_on_worst_5_days"].idxmin()

    top5 = contributors.head(5)
    table_lines = [
        "| Asset | Weight | Ann. Volatility | Weight × Volatility | Corr. w/ Portfolio | Avg Return Worst 5 Days |",
        "|---|---|---|---|---|---|",
    ]
    for asset, row in top5.iterrows():
        table_lines.append(
            f"| {asset} "
            f"| {pct(row['weight'])} "
            f"| {pct(row['annualized_volatility'])} "
            f"| {num(row['weight_volatility_contribution'], 4)} "
            f"| {num(row['correlation_with_portfolio'], 4)} "
            f"| {pct(row['average_return_on_worst_5_days'])} |"
        )

    wv_val = num(contributors.loc[top_wv, "weight_volatility_contribution"], 4)
    worst_val = pct(contributors.loc[top_worst, "average_return_on_worst_5_days"])

    commentary = (
        f"\n**{top_wv}** holds the highest weight-adjusted volatility contribution ({wv_val}), "
        f"driven by its combination of elevated annualized volatility and portfolio weight. "
        f"**{top_worst}** recorded the steepest average return of {worst_val} "
        f"across the portfolio's five worst trading days, indicating concentrated downside exposure "
        f"during periods of acute market stress."
    )

    return "## Top Risk Contributors\n\n" + "\n".join(table_lines) + "\n" + commentary + "\n"


def build_stress_analysis(stress, contributors):
    sections = []
    for _, row in stress.iterrows():
        period = row["period"]
        cum_ret = pct(row["portfolio_cumulative_return"])
        max_dd = pct(row["portfolio_max_drawdown"])
        w1, w2, w3 = row["worst_contributor_1"], row["worst_contributor_2"], row["worst_contributor_3"]

        section = f"""### {period}

| Metric | Value |
|---|---|
| Period | {row["start"]} to {row["end"]} |
| Portfolio Cumulative Return | {cum_ret} |
| Portfolio Max Drawdown | {max_dd} |
| Worst Contributors | {w1}, {w2}, {w3} |

The portfolio declined {cum_ret} with an intra-period maximum drawdown of {max_dd}.
The three assets that dragged performance the most were **{w1}**, **{w2}**, and **{w3}**.
"""
        sections.append(section)

    return "## Stress Period Analysis\n\n" + "\n".join(sections)


def build_key_observations(risk, contributors, stress):
    sharpe = float(risk["Sharpe Ratio"])
    max_dd = float(risk["Max Drawdown"])
    ann_vol = float(risk["Annualized Volatility"])
    var95 = float(risk["VaR 95%"])

    top_wv_asset = contributors["weight_volatility_contribution"].idxmax()
    top_wv_vol = float(contributors.loc[top_wv_asset, "annualized_volatility"])

    tlt_corr = float(contributors.loc["TLT", "correlation_with_portfolio"]) if "TLT" in contributors.index else None

    covid_loss = float(stress[stress["period"] == "COVID Crash"].iloc[0]["portfolio_cumulative_return"])
    rate_loss = float(stress[stress["period"] == "2022 Rate-Hike Selloff"].iloc[0]["portfolio_cumulative_return"])

    observations = []

    # Sharpe ratio quality
    if sharpe >= 1.0:
        observations.append(
            f"The Sharpe ratio of {num(sharpe)} indicates the portfolio has historically generated "
            f"reasonable risk-adjusted returns relative to its volatility."
        )
    else:
        observations.append(
            f"The Sharpe ratio of {num(sharpe)} is below 1.0, suggesting the historical risk-adjusted "
            f"return profile warrants scrutiny."
        )

    # Drawdown severity
    if abs(max_dd) > 0.40:
        observations.append(
            f"The maximum drawdown of {pct(max_dd)} is substantial. Investors should assess whether "
            f"this level of peak-to-trough decline is consistent with their risk tolerance."
        )

    # VaR context
    observations.append(
        f"At the 95% confidence level, daily VaR is {pct(var95)}, meaning the portfolio has historically "
        f"exceeded this daily loss threshold approximately once every 20 trading days."
    )

    # Concentration risk
    observations.append(
        f"**{top_wv_asset}** (annualized volatility: {pct(top_wv_vol)}) is the single largest source of "
        f"weight-adjusted risk and warrants close monitoring given its portfolio weight."
    )

    # TLT as hedge
    if tlt_corr is not None and tlt_corr < 0:
        observations.append(
            f"TLT (long-duration Treasuries) exhibits a negative correlation ({num(tlt_corr, 4)}) with the "
            f"portfolio, suggesting it has provided partial downside protection historically."
        )

    # Stress comparison
    if rate_loss < covid_loss:
        observations.append(
            f"The 2022 rate-hike selloff ({pct(rate_loss)}) caused a larger cumulative drawdown than the "
            f"COVID crash ({pct(covid_loss)}), reflecting the portfolio's sensitivity to rising interest rates "
            f"and compression in growth-stock valuations."
        )

    lines = "\n".join(f"- {obs}" for obs in observations)
    return f"## Key Observations\n\n{lines}\n"


def build_disclaimer():
    return (
        "## Disclaimer\n\n"
        "This memo is produced by a rule-based analytical system for educational and research purposes only. "
        "All metrics are derived from historical data and are backward-looking. Past performance is not "
        "indicative of future results. This document does not constitute investment advice, a solicitation, "
        "or a recommendation to buy, sell, or hold any security. Readers should consult a qualified financial "
        "professional before making any investment decisions."
    )


# ---------------------------------------------------------------------------
# Assemble and save
# ---------------------------------------------------------------------------

def generate_memo(risk, contributors, stress):
    today = date.today().strftime("%B %d, %Y")
    header = f"# Portfolio Risk Memo\n\n**Date:** {today}  \n**Classification:** Internal Research Use Only\n"

    sections = [
        header,
        build_executive_summary(risk, contributors, stress),
        build_risk_metrics(risk),
        build_top_contributors(contributors),
        build_stress_analysis(stress, contributors),
        build_key_observations(risk, contributors, stress),
        build_disclaimer(),
    ]
    return "\n---\n\n".join(sections)


def save_memo(memo):
    os.makedirs("outputs", exist_ok=True)
    path = "outputs/sample_memo.md"
    with open(path, "w") as f:
        f.write(memo)
    print(f"Memo saved: {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    risk, contributors, stress = load_data()
    memo = generate_memo(risk, contributors, stress)
    save_memo(memo)
    print("\n--- Memo Preview (first 20 lines) ---")
    for line in memo.splitlines()[:20]:
        print(line)


if __name__ == "__main__":
    main()

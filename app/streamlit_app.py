import streamlit as st
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Portfolio Risk Assistant",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_csv(path, **kwargs):
    p = Path(path)
    if p.exists():
        return pd.read_csv(p, **kwargs)
    return None


def pct(val):
    """Format a decimal as a percentage string."""
    try:
        return f"{float(val):.2%}"
    except (TypeError, ValueError):
        return val


def fmt_risk_summary(df):
    """Round and format the risk summary table for display."""
    df = df.copy()
    pct_metrics = {"Annualized Return", "Annualized Volatility", "Max Drawdown", "Sharpe Ratio"}
    for _, row in df.iterrows():
        pass  # formatting done below
    df["Value"] = df.apply(
        lambda r: pct(r["Value"]) if r["Metric"] in pct_metrics else round(float(r["Value"]), 4),
        axis=1,
    )
    return df


# ---------------------------------------------------------------------------
# Title and scope
# ---------------------------------------------------------------------------

st.title("AI Investment Research and Portfolio Risk Assistant")

st.markdown("""
**Project scope:** This MVP analyzes a fixed tech-heavy portfolio using historical daily price data
and quantitative risk metrics. All calculations are backward-looking and based on historical data only.

> This tool is for **research and educational purposes only**. It does not provide investment advice
> or trading recommendations.
""")

# ---------------------------------------------------------------------------
# Portfolio universe
# ---------------------------------------------------------------------------

st.header("Portfolio Universe")

tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "SPY", "QQQ", "TLT"]
st.markdown(
    " · ".join(f"**{t}**" for t in tickers)
)

# ---------------------------------------------------------------------------
# Risk Summary
# ---------------------------------------------------------------------------

st.header("Risk Summary")

risk_df = load_csv("outputs/tables/risk_summary.csv")
if risk_df is not None:
    try:
        display_df = fmt_risk_summary(risk_df)
    except Exception:
        display_df = risk_df
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.warning("risk_summary.csv not found. Run the pipeline first.")

# ---------------------------------------------------------------------------
# Correlation Matrix
# ---------------------------------------------------------------------------

st.header("Correlation Matrix")

corr_df = load_csv("outputs/tables/correlation_matrix.csv", index_col=0)
if corr_df is not None:
    st.dataframe(corr_df.style.format("{:.2f}").background_gradient(cmap="RdYlGn", vmin=-1, vmax=1),
                 use_container_width=True)
else:
    st.warning("correlation_matrix.csv not found.")

# ---------------------------------------------------------------------------
# Top Risk Contributors
# ---------------------------------------------------------------------------

st.header("Top Risk Contributors")

contrib_df = load_csv("outputs/tables/top_risk_contributors.csv", index_col=0)
if contrib_df is not None:
    st.dataframe(contrib_df.style.format({
        "weight": "{:.0%}",
        "annualized_volatility": "{:.2%}",
        "weight_volatility_contribution": "{:.4f}",
        "correlation_with_portfolio": "{:.4f}",
        "average_return_on_worst_5_days": "{:.2%}",
    }), use_container_width=True)

    # Automatic interpretation
    top_wv = contrib_df["weight_volatility_contribution"].idxmax()
    top_worst = contrib_df["average_return_on_worst_5_days"].idxmin()

    st.info(
        f"**Weight × Volatility:** {top_wv} is the largest risk contributor by weight × annualized volatility.  \n"
        f"**Worst-Day Loss:** {top_worst} had the steepest average loss on the portfolio's five worst days."
    )
else:
    st.warning("top_risk_contributors.csv not found.")

# ---------------------------------------------------------------------------
# Stress Period Analysis
# ---------------------------------------------------------------------------

st.header("Stress Period Analysis")

stress_df = load_csv("outputs/tables/stress_summary.csv")
if stress_df is not None:
    display_stress = stress_df.copy()
    for col in ["portfolio_cumulative_return", "portfolio_max_drawdown"]:
        display_stress[col] = display_stress[col].apply(pct)
    st.dataframe(display_stress, use_container_width=True, hide_index=True)
else:
    st.warning("stress_summary.csv not found.")

col1, col2 = st.columns(2)

covid_chart = Path("outputs/charts/covid_stress_cumulative_return.png")
rate_chart = Path("outputs/charts/rate_hike_stress_cumulative_return.png")

with col1:
    st.subheader("COVID Crash (Feb–Mar 2020)")
    if covid_chart.exists():
        st.image(str(covid_chart), use_container_width=True)
    else:
        st.warning("COVID chart not found.")

with col2:
    st.subheader("2022 Rate-Hike Selloff (Jan–Oct 2022)")
    if rate_chart.exists():
        st.image(str(rate_chart), use_container_width=True)
    else:
        st.warning("Rate-hike chart not found.")

# ---------------------------------------------------------------------------
# Stress Asset Contributions
# ---------------------------------------------------------------------------

st.header("Stress Asset Contributions")

stress_assets_df = load_csv("outputs/tables/stress_asset_contributions.csv")
if stress_assets_df is not None:
    for period_name, group in stress_assets_df.groupby("period"):
        st.subheader(period_name)
        display_group = group.drop(columns=["period"]).copy()
        st.dataframe(
            display_group.style.format({
                "weight": "{:.0%}",
                "asset_cumulative_return": "{:.2%}",
                "weighted_contribution": "{:.4f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.warning("stress_asset_contributions.csv not found.")

# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "**Disclaimer:** This tool is for educational and research purposes only. "
    "It does not provide investment advice or trading recommendations. "
    "Past performance is not indicative of future results."
)

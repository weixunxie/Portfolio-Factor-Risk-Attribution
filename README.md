# AI Investment Research and Portfolio Risk Assistant

A quantitative risk analytics tool that downloads historical price data, computes portfolio risk
metrics, identifies top risk contributors, and runs stress-period analysis — all presented through
a Streamlit dashboard and a rule-based risk memo.

**For research and educational purposes only. Not investment advice.**

---

## Project Overview

This project builds a reproducible risk analytics pipeline for a fixed, tech-heavy sample portfolio.
It is designed to demonstrate how quantitative risk metrics can be calculated, interpreted, and
communicated clearly — without relying on external AI APIs or live market data feeds.

All calculations are backward-looking and based on historical daily closing prices sourced from
Yahoo Finance via `yfinance`.

---

## Asset Universe

| Ticker | Name |
|--------|------|
| AAPL | Apple |
| MSFT | Microsoft |
| NVDA | NVIDIA |
| GOOGL | Alphabet |
| AMZN | Amazon |
| META | Meta Platforms |
| TSLA | Tesla |
| SPY | S&P 500 ETF |
| QQQ | Nasdaq-100 ETF |
| TLT | 20+ Year Treasury Bond ETF |

---

## Current MVP Features

1. **Data download** — pulls historical daily closing prices for all ten assets using `yfinance`.
2. **Portfolio construction** — builds a fixed, weighted sample portfolio.
3. **Risk metrics** — calculates the following at the portfolio level:
   - Annualized return
   - Annualized volatility
   - Sharpe ratio
   - Maximum drawdown
   - Value at Risk (VaR) at 95% and 99% confidence
   - Conditional Value at Risk (CVaR) at 95% and 99% confidence
4. **Top risk contributors** — ranks each asset by weight × volatility contribution, correlation with
   portfolio returns, and average loss on the portfolio's five worst trading days.
5. **Stress-period analysis** — evaluates portfolio behaviour during two historical stress episodes:
   - COVID Crash (2020-02-19 to 2020-03-23)
   - 2022 Rate-Hike Selloff (2022-01-03 to 2022-10-14)
6. **Rule-based risk memo** — generates a structured markdown memo summarising all findings,
   written in professional language without requiring any external AI API.
7. **Streamlit dashboard** — displays all tables, charts, and the risk memo in an interactive web UI.

---

## Methodology

| Step | Module | Description |
|------|--------|-------------|
| Download prices | `src/data_loader.py` | Fetches adjusted closing prices via `yfinance` |
| Compute returns | `src/data_loader.py` | Calculates daily log returns |
| Build portfolio | `src/portfolio.py` | Applies fixed weights; computes portfolio daily returns |
| Risk metrics | `src/metrics.py` | Annualised return, volatility, Sharpe, drawdown, VaR, CVaR |
| Risk contributors | `src/risk_contributors.py` | Weight × vol, correlation, worst-day average return |
| Stress analysis | `src/stress.py` | Cumulative return and max drawdown for fixed stress windows |
| Risk memo | `src/memo_generator.py` | Rule-based markdown memo from computed outputs |
| Dashboard | `app/streamlit_app.py` | Reads output files and renders all results |

**Portfolio weights (fixed sample):**

| Asset | Weight |
|-------|--------|
| AAPL | 15% |
| MSFT | 15% |
| NVDA | 20% |
| GOOGL | 10% |
| AMZN | 10% |
| META | 10% |
| TSLA | 10% |
| SPY | 5% |
| QQQ | 3% |
| TLT | 2% |

VaR and CVaR are computed using the historical simulation method on the empirical return distribution.
The Sharpe ratio assumes a risk-free rate of 0%.

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the pipeline (in order)

```bash
python src/data_loader.py
python src/portfolio.py
python src/metrics.py
python src/risk_contributors.py
python src/stress.py
python src/memo_generator.py
```

### 3. Launch the dashboard

```bash
streamlit run app/streamlit_app.py
```

The dashboard opens at `http://localhost:8501`.

---

## Output Files

### Tables (`outputs/tables/`)

| File | Contents |
|------|----------|
| `portfolio_weights.csv` | Asset weights |
| `portfolio_returns.csv` | Daily portfolio returns |
| `risk_summary.csv` | Annualised return, volatility, Sharpe, drawdown, VaR, CVaR |
| `correlation_matrix.csv` | Pairwise asset return correlations |
| `top_risk_contributors.csv` | Per-asset risk contribution rankings |
| `stress_summary.csv` | Portfolio-level metrics for each stress period |
| `stress_asset_contributions.csv` | Per-asset weighted contributions during each stress period |

### Charts (`outputs/charts/`)

| File | Contents |
|------|----------|
| `covid_stress_cumulative_return.png` | Portfolio cumulative return during the COVID crash |
| `rate_hike_stress_cumulative_return.png` | Portfolio cumulative return during the 2022 rate-hike selloff |

### Memo (`outputs/`)

| File | Contents |
|------|----------|
| `sample_memo.md` | Rule-based markdown risk memo |

---

## Limitations

- **Fixed portfolio** — weights are hard-coded for demonstration purposes and do not reflect any
  optimisation or real-world allocation.
- **Historical data only** — all metrics are backward-looking. Past performance is not indicative of
  future results.
- **No transaction costs** — return calculations do not account for trading costs, taxes, or slippage.
- **Risk-free rate** — the Sharpe ratio assumes a risk-free rate of 0%.
- **Fixed stress windows** — stress periods are predefined; the tool does not scan for drawdown
  episodes automatically.
- **No live data** — the pipeline must be re-run manually to incorporate new price data.

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute investment advice,
a solicitation, or a recommendation to buy, sell, or hold any security or financial instrument.
All analysis is based on historical data and is subject to the limitations described above.
Users should consult a qualified financial professional before making any investment decisions.

# Portfolio Risk Memo

**Date:** May 26, 2026  
**Classification:** Internal Research Use Only

---

## Executive Summary

This memo summarizes the quantitative risk profile of a fixed tech-heavy portfolio comprising
AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, and TLT. All metrics are derived from
historical daily price data and are backward-looking in nature.

Over the full analysis period the portfolio generated an annualized return of **34.52%**
with an annualized volatility of **29.60%** and a Sharpe ratio of **1.15**. The maximum
drawdown recorded was **-45.76%**.

The largest single risk contributor by weight-adjusted volatility is **NVDA**.
**NVDA** recorded the steepest average loss across the portfolio's five worst trading days.

During the COVID crash the portfolio declined **-28.84%**, and
during the 2022 rate-hike selloff it fell **-40.89%** — the more
severe of the two stress episodes analyzed.

---

## Portfolio Risk Metrics

| Metric | Value |
|---|---|
| Annualized Return | 34.52% |
| Annualized Volatility | 29.60% |
| Sharpe Ratio | 1.15 |
| Max Drawdown | -45.76% |
| VaR 95% | 3.04% |
| CVaR 95% | 4.32% |
| VaR 99% | 4.98% |
| CVaR 99% | 6.29% |

---

## Top Risk Contributors

| Asset | Weight | Ann. Volatility | Weight × Volatility | Corr. w/ Portfolio | Avg Return Worst 5 Days |
|---|---|---|---|---|---|
| NVDA | 20.00% | 50.71% | 0.1014 | 0.8571 | -11.44% |
| TSLA | 10.00% | 62.74% | 0.0627 | 0.6637 | -11.37% |
| AAPL | 15.00% | 30.51% | 0.0458 | 0.7893 | -8.90% |
| MSFT | 15.00% | 28.51% | 0.0428 | 0.8354 | -8.54% |
| META | 10.00% | 41.37% | 0.0414 | 0.7254 | -8.61% |

**NVDA** holds the highest weight-adjusted volatility contribution (0.1014), driven by its combination of elevated annualized volatility and portfolio weight. **NVDA** recorded the steepest average return of -11.44% across the portfolio's five worst trading days, indicating concentrated downside exposure during periods of acute market stress.

---

## Stress Period Analysis

### COVID Crash

| Metric | Value |
|---|---|
| Period | 2020-02-19 to 2020-03-23 |
| Portfolio Cumulative Return | -28.84% |
| Portfolio Max Drawdown | -31.48% |
| Worst Contributors | NVDA, TSLA, AAPL |

The portfolio declined -28.84% with an intra-period maximum drawdown of -31.48%.
The three assets that dragged performance the most were **NVDA**, **TSLA**, and **AAPL**.

### 2022 Rate-Hike Selloff

| Metric | Value |
|---|---|
| Period | 2022-01-03 to 2022-10-14 |
| Portfolio Cumulative Return | -40.89% |
| Portfolio Max Drawdown | -42.30% |
| Worst Contributors | NVDA, META, MSFT |

The portfolio declined -40.89% with an intra-period maximum drawdown of -42.30%.
The three assets that dragged performance the most were **NVDA**, **META**, and **MSFT**.

---

## Key Observations

- The Sharpe ratio of 1.15 indicates the portfolio has historically generated reasonable risk-adjusted returns relative to its volatility.
- The maximum drawdown of -45.76% is substantial. Investors should assess whether this level of peak-to-trough decline is consistent with their risk tolerance.
- At the 95% confidence level, daily VaR is 3.04%, meaning the portfolio has historically exceeded this daily loss threshold approximately once every 20 trading days.
- **NVDA** (annualized volatility: 50.71%) is the single largest source of weight-adjusted risk and warrants close monitoring given its portfolio weight.
- TLT (long-duration Treasuries) exhibits a negative correlation (-0.0720) with the portfolio, suggesting it has provided partial downside protection historically.
- The 2022 rate-hike selloff (-40.89%) caused a larger cumulative drawdown than the COVID crash (-28.84%), reflecting the portfolio's sensitivity to rising interest rates and compression in growth-stock valuations.

---

## Disclaimer

This memo is produced by a rule-based analytical system for educational and research purposes only. All metrics are derived from historical data and are backward-looking. Past performance is not indicative of future results. This document does not constitute investment advice, a solicitation, or a recommendation to buy, sell, or hold any security. Readers should consult a qualified financial professional before making any investment decisions.
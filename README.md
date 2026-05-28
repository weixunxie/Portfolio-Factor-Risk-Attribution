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

## Data Providers

The `src/providers/` layer adds dynamic data access on top of the static MVP pipeline.

### Alpha Vantage (`alpha_vantage_provider.py`)

Used for live market and company data.

| Function | Alpha Vantage endpoint | What it returns |
|---|---|---|
| `get_company_overview(ticker)` | `OVERVIEW` | Name, sector, industry, P/E, 52-week range, description |
| `get_daily_adjusted_prices(ticker)` | `TIME_SERIES_DAILY_ADJUSTED` | Last ~100 days of OHLCV data |

Set `ALPHA_VANTAGE_API_KEY` in your `.env` file.
The free tier allows 25 API calls per day — the local cache prevents re-fetching data that was already retrieved within the last 24 hours.

### SEC EDGAR (`sec_edgar_provider.py`)

Used for official company filings metadata. No API key required.

| Function | What it returns |
|---|---|
| `get_company_ticker_mapping()` | Full ticker → CIK mapping from SEC |
| `get_cik_for_ticker(ticker)` | CIK number and company name for a single ticker |
| `get_latest_10k_metadata(ticker)` | Most recent 10-K filing date, accession number, and document URLs |

Set `SEC_USER_AGENT` in your `.env` file (required by SEC): `"AppName your@email.com"`

### Unified interface (`market_data_provider.py`)

Wraps both sources with a consistent API and automatic fallback:

| Function | Primary source | Fallback |
|---|---|---|
| `validate_ticker(ticker)` | Alpha Vantage | yfinance |
| `get_company_profile(ticker)` | Alpha Vantage | yfinance |
| `get_price_history(ticker)` | Alpha Vantage | yfinance |

### Local cache (`cache.py`)

All API responses are cached in `data/cache/` (excluded from Git).
- JSON responses are cached as `.json` files.
- Cache keys are sanitised to safe filenames (e.g. `av_overview_AAPL.json`).
- Each cache entry has a configurable TTL: 24 hours for price/overview data, 7 days for SEC data.

---

## Deployment

### Backend — Railway or Render

| Setting | Value |
|---|---|
| Root directory | *(repo root)* |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

Required environment variables:

```
ALPHA_VANTAGE_API_KEY=...
SEC_USER_AGENT=AppName your@email.com
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=company_risk_documents
DATABASE_URL=postgresql://user:pass@host:5432/postgres   # direct connection — NEVER expose to frontend
FRONTEND_ORIGIN=https://your-vercel-app.vercel.app
```

> **Supabase note:** Use the direct connection string (port 5432), not the connection pooler (port 6543),
> because the pooler does not support all PostgreSQL features used by SQLAlchemy.
> Find it in your Supabase project → Settings → Database → Connection string → URI.

### Frontend — Vercel

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Next.js (auto-detected) |
| Build command | `npm run build` (auto) |

Required environment variable:

```
NEXT_PUBLIC_API_BASE_URL=https://your-railway-or-render-backend.up.railway.app
```

Set `NEXT_PUBLIC_API_BASE_URL` to your Railway/Render backend URL before deploying.
After deploying the frontend, also set `FRONTEND_ORIGIN` on the backend to the Vercel URL.

### Local development

```bash
# Backend (port 8000)
source .venv/bin/activate
uvicorn api.main:app --reload

# Frontend (port 3002)
cd frontend
npm run dev
```

---

## PostgreSQL / Supabase Integration

The backend connects to PostgreSQL (hosted on Supabase) via a direct `DATABASE_URL` using SQLAlchemy + psycopg2. No Supabase REST client or service role key is used.

| Table | What it stores |
|---|---|
| `companies` | Company profile data (name, sector, market cap, P/E, …) upserted by `/company-profile` |
| `portfolios` | Named portfolio records created by `/analyze-portfolio` when `save_to_database=true` |
| `portfolio_holdings` | Per-ticker weights for each saved portfolio |
| `sec_filings` | 10-K filing metadata (filing date, accession number, extraction status, Qdrant ingestion flag) |
| `analysis_runs` | Full risk analysis snapshots (metrics, contributors, stress periods, evidence) |
| `rag_documents` | Chunk-level metadata for every document ingested into Qdrant |
| `api_cache_metadata` | Record of external API cache entries (Alpha Vantage, SEC) |

**Architecture note:**
- **Qdrant** stores the actual vector embeddings and is queried for semantic similarity search over SEC risk factor text.
- **PostgreSQL / Supabase** stores structured metadata, portfolio history, and analysis snapshots — it is never queried for vectors.
- The **Next.js frontend calls FastAPI only**. `DATABASE_URL` belongs exclusively in backend environment variables and must never appear in any `NEXT_PUBLIC_` variable.

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute investment advice,
a solicitation, or a recommendation to buy, sell, or hold any security or financial instrument.
All analysis is based on historical data and is subject to the limitations described above.
Users should consult a qualified financial professional before making any investment decisions.

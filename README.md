# AI Portfolio Risk Assistant

**AI Portfolio Risk Assistant** is an AI-powered portfolio risk research system that combines
quantitative risk analytics, SEC filing retrieval, and portfolio-level evidence generation.
The system helps users review concentration risk, stress-period exposure, top risk contributors,
and company-specific risk disclosures for a given portfolio.

**For educational and research purposes only. Not investment advice.**

---

## Portfolio Description

Built an end-to-end AI-native portfolio risk analytics system that combines FastAPI, Next.js,
PostgreSQL, Qdrant, SEC EDGAR data, and quantitative risk metrics to support portfolio-level
risk review. The system calculates VaR/CVaR, drawdown, volatility, stress-period performance,
and top risk contributors, then retrieves source-grounded company risk evidence from SEC filings
to generate a research-style risk summary.

---

## What This Project Is

- Portfolio risk diagnostics system
- AI-assisted investment research workflow
- Quantitative risk analytics dashboard
- SEC filing evidence retrieval system
- End-to-end FinTech/AI engineering project

## What This Project Is Not

- Not a stock prediction model
- Not a trading bot
- Not a buy/sell recommendation system
- Not an alpha or factor-mining engine
- Not financial advice

---

## Core Workflow

```
User portfolio input
  → price and company data retrieval
  → risk metric calculation
  → stress scenario analysis
  → top risk contributor identification
  → SEC filing evidence retrieval
  → AI-style risk report generation
  → optional database persistence
```

---

## What the System Helps Answer

| Question | Module |
|---|---|
| Where is this portfolio's risk concentrated? | Top risk contributors (weight × volatility) |
| Which assets contribute most to downside risk? | Correlation with portfolio, worst-day returns |
| How would this portfolio have behaved during historical stress periods? | Stress scenario analysis |
| What official SEC risk disclosures are relevant to the current holdings? | Qdrant vector retrieval over 10-K filings |
| What risk themes should an analyst or investor monitor? | Research-style AI risk report |

The system does **not** answer: what to buy tomorrow, which stock will go up, or what trading
strategy to use.

---

## Current Capabilities

1. **Dynamic portfolio input** — accepts any user-defined portfolio via weight %, dollar amount, or share count; normalizes to weights before analysis.
2. **Price data retrieval** — fetches historical daily closing prices per ticker from Alpha Vantage, a local cache, or yfinance fallback (2018 to today).
3. **Risk metrics** — calculates the following at the portfolio level:
   - Annualized return
   - Annualized volatility
   - Sharpe ratio (risk-free rate = 0%)
   - Maximum drawdown
   - Value at Risk (VaR) at 95% and 99% confidence
   - Conditional Value at Risk (CVaR) at 95% and 99% confidence
4. **Top risk contributors** — ranks each asset by weight × volatility contribution, correlation with portfolio returns, and average return on the portfolio's five worst trading days.
5. **Stress-period analysis** — evaluates portfolio behavior during two historical stress windows:
   - COVID Crash (2020-02-19 to 2020-03-23)
   - 2022 Rate-Hike Selloff (2022-01-03 to 2022-10-14)
6. **Company risk evidence** — retrieves source-grounded risk factor excerpts from SEC 10-K filings using Qdrant vector search.
7. **Research-style risk report** — generates a structured markdown memo summarizing portfolio-level and company-level risk findings.
8. **Database persistence** — optionally saves portfolio, holdings, company data, and full analysis snapshots to PostgreSQL/Supabase.

---

## Technical Architecture

| Layer | Technology |
|---|---|
| Frontend | Next.js (React), Tailwind CSS |
| Backend | FastAPI (Python) |
| Structured storage | PostgreSQL / Supabase |
| Vector retrieval | Qdrant Cloud |
| SEC filings | SEC EDGAR (CIK lookup + 10-K parsing) |
| Market / company data | Alpha Vantage · yfinance (fallback) |
| Local cache | JSON cache — 24 h / 7 d TTL, avoids redundant API calls |

**Architecture notes:**
- **Qdrant** stores vector embeddings of SEC risk factor text and is queried for semantic similarity search.
- **PostgreSQL / Supabase** stores structured metadata: portfolios, holdings, company profiles, analysis snapshots.
- The **Next.js frontend calls FastAPI only**. `DATABASE_URL` belongs exclusively in backend environment variables and must never appear in any `NEXT_PUBLIC_` variable.

---

## Why This Matters

The project productizes a portfolio risk review workflow similar to what an analyst, portfolio
manager, or risk analyst might perform manually. It connects numerical portfolio risk metrics with
company-level textual risk evidence from official SEC filings — replacing a fragmented, manual
process with a structured, reproducible pipeline.

---

## Input Modes

The portfolio input panel supports three modes:

| Mode | Input | Backend behavior |
|---|---|---|
| Weight % | Weights summing to ≈ 100 (or ≈ 1.0) | Normalized and used directly |
| Dollar Amount | Dollar value per holding | Weights derived from total entered or provided portfolio value; unallocated amount shown; optional cash treatment |
| Shares | Share count per holding | Latest price fetched per ticker; market values computed; weights derived |

Cash (`CASH`) is supported as a synthetic zero-return asset that reduces portfolio volatility
proportionally to its allocation.

---

## Data Providers

### Alpha Vantage (`alpha_vantage_provider.py`)

Used for live market and company data.

| Function | Alpha Vantage endpoint | What it returns |
|---|---|---|
| `get_company_overview(ticker)` | `OVERVIEW` | Name, sector, industry, P/E, 52-week range |
| `get_daily_adjusted_prices(ticker)` | `TIME_SERIES_DAILY_ADJUSTED` | Last ~100 days of OHLCV data |

Set `ALPHA_VANTAGE_API_KEY` in your `.env` file.
The free tier allows 25 API calls per day — the local cache prevents re-fetching within the last 24 hours.

### SEC EDGAR (`sec_edgar_provider.py`)

Used for official company filings metadata. No API key required.

| Function | What it returns |
|---|---|
| `get_company_ticker_mapping()` | Full ticker → CIK mapping from SEC |
| `get_cik_for_ticker(ticker)` | CIK number and company name for a single ticker |
| `get_latest_10k_metadata(ticker)` | Most recent 10-K filing date, accession number, and document URLs |

Set `SEC_USER_AGENT` in your `.env` file (required by SEC): `"AppName your@email.com"`

### Qdrant

Used for vector retrieval over SEC 10-K risk factor chunks.

Set `QDRANT_URL`, `QDRANT_API_KEY`, and `QDRANT_COLLECTION_NAME` in your `.env` file.

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
- Each cache entry has a configurable TTL: 24 hours for price/overview data, 7 days for SEC data.

---

## PostgreSQL / Supabase Integration

The backend connects to PostgreSQL (hosted on Supabase) via a direct `DATABASE_URL` using
SQLAlchemy + psycopg2.

| Table | What it stores |
|---|---|
| `companies` | Company profile data upserted by `/company-profile` |
| `portfolios` | Named portfolio records created by `/analyze-portfolio` |
| `portfolio_holdings` | Per-ticker weights for each saved portfolio |
| `sec_filings` | 10-K filing metadata (filing date, accession number, ingestion status) |
| `analysis_runs` | Full risk analysis snapshots (metrics, contributors, stress periods, evidence) |
| `rag_documents` | Chunk-level metadata for every document ingested into Qdrant |
| `api_cache_metadata` | Record of external API cache entries (Alpha Vantage, SEC) |

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set environment variables

Copy `.env.example` to `.env` and fill in the required values:

```
ALPHA_VANTAGE_API_KEY=...
SEC_USER_AGENT=AppName your@email.com
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=company_risk_documents
DATABASE_URL=postgresql://user:pass@host:5432/postgres
FRONTEND_ORIGIN=http://localhost:3002
```

### 3. Start the backend

```bash
source .venv/bin/activate
uvicorn api.main:app --reload
# Backend available at http://localhost:8000
```

### 4. Start the frontend

```bash
cd frontend
npm run dev
# Frontend available at http://localhost:3002
```

---

## Deployment

### Backend — Railway or Render

| Setting | Value |
|---|---|
| Root directory | *(repo root)* |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

Required environment variables: see section above. The `DATABASE_URL` must use a direct connection
(port 5432), not the Supabase connection pooler (port 6543), unless `NullPool` is configured.

### Frontend — Vercel

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Next.js (auto-detected) |

Required environment variable:

```
NEXT_PUBLIC_API_BASE_URL=https://your-railway-or-render-backend.up.railway.app
```

After deploying the frontend, set `FRONTEND_ORIGIN` on the backend to the Vercel URL.

---

## Limitations

- **Historical data only** — all metrics are backward-looking. Past performance is not indicative of future results.
- **No transaction costs** — return calculations do not account for trading costs, taxes, or slippage.
- **Risk-free rate** — the Sharpe ratio assumes a risk-free rate of 0%.
- **Fixed stress windows** — stress periods are predefined; the tool does not scan for drawdown episodes automatically.
- **Price data coverage** — tickers not in the local cache require a live yfinance fetch; results depend on data availability.
- **SEC evidence coverage** — only tickers with ingested 10-K filings in Qdrant will return company risk evidence.

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute investment
advice, a solicitation, or a recommendation to buy, sell, or hold any security or financial
instrument. All analysis is based on historical data and is subject to the limitations described
above. Users should consult a qualified financial professional before making any investment
decisions.

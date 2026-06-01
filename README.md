# AI Portfolio Risk Assistant

**AI Portfolio Risk Assistant** is an interactive portfolio risk attribution and stress-testing
system that combines traditional risk metrics with factor-style risk attribution, concentration
diagnostics, stress/tail-risk analysis, and AI-generated explanations grounded in computed evidence.

**For educational and research purposes only. Not investment advice.**

---

## Portfolio Description

An interactive risk analytics system that decomposes portfolio risk into market, sector, style,
macro, concentration, and tail-risk drivers, then generates an evidence-grounded AI risk report.
Built with FastAPI, Next.js, PostgreSQL, Qdrant, SEC EDGAR data, and quantitative risk metrics
to support portfolio-level risk review.

---

## New: Proxy Factor Exposure Regression

The dashboard now includes a proxy-based factor exposure regression as a sub-section of Risk Attribution.

**Model:** OLS regression of portfolio daily returns on three market proxy ETF returns:

| Proxy factor | ETF | What it captures |
|---|---|---|
| Broad equity market | SPY daily returns | General equity market sensitivity |
| Growth / technology | QQQ daily returns | Tech and growth-stock cycle exposure |
| Duration / rates | TLT daily returns | Interest rate regime sensitivity (directional proxy — not a direct 10Y yield measure) |

**Output per factor:** beta coefficient, t-statistic, p-value, and a plain-English interpretation. Only factors with p < 0.05 are marked as statistically significant.

**Model fit:** R², Adjusted R², VIF per factor, and observation count are reported. A collinearity warning fires when any factor VIF exceeds 10 (SPY and QQQ are often highly correlated).

**What this is:**
Proxy-based regression using accessible, liquid market ETF return series. Each ETF captures a specific market regime directionally. This is not formal academic factor modeling — the proxies are not long-short constructed portfolios, and the regression does not isolate specific risk premia.

**What this is not:**
Not a formal factor model. TLT captures duration/rate-regime dynamics as a proxy only — it does not measure 10Y Treasury yield changes directly, and rate sensitivity should be read as directional, not precise.

**Planned future extension:** VIX daily changes (volatility-shock proxy) will be added when reliable `^VIX` daily data is available in the pipeline. Until then, volatility-shock sensitivity is not captured by this regression.

---

## New: Risk Attribution Layer

The dashboard now goes beyond reporting metrics — it answers **what is driving this portfolio's risk**.

| Driver | What it measures |
|--------|-----------------|
| **Market Risk** | Portfolio beta relative to SPY; how much broad equity moves amplify gains and losses |
| **Sector Risk** | Sector weight concentration; flags over-reliance on any single sector |
| **Style / Factor Risk** | Simplified style classification: high-beta, high-volatility, growth/tech-heavy, or defensive |
| **Macro Risk** | Sensitivity to QQQ (tech/growth proxy) and TLT (rate/duration proxy) |
| **Concentration Risk** | HHI score, top-1 / top-3 / top-5 position weights, number of holdings |
| **Tail Risk** | VaR / CVaR interpretation, max drawdown, worst-day analysis, CVaR/VaR ratio |

Each dimension returns:
- A risk level: **Low / Moderate / High**
- Key supporting metrics
- A plain-English explanation
- Individual driver bullets

The AI Risk Report is automatically enriched with attribution data — it now explains *why* risk is elevated, not just *how much*.

---

## What This Project Is

- Portfolio risk attribution and stress-testing system
- Quant-style risk driver analysis dashboard
- AI-assisted investment research workflow
- Concentration, tail-risk, and factor exposure diagnostics
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
  → risk metric calculation (VaR, CVaR, Sharpe, drawdown)
  → risk attribution (market beta, sector, concentration, tail, style, macro)
  → stress scenario analysis
  → top risk contributor identification
  → SEC filing evidence retrieval
  → AI risk report grounded in computed attribution
  → optional database persistence
```

---

## What the System Helps Answer

| Question | Module |
|---|---|
| What is driving this portfolio's risk? | Risk Attribution layer (6 dimensions) |
| Is the portfolio market-sensitive or defensive? | Market Risk (portfolio beta vs SPY) |
| Is the portfolio concentrated in a single sector? | Sector Risk (sector weight breakdown) |
| How concentrated is the portfolio by position? | Concentration Risk (HHI, top-N weights) |
| What is the tail-risk exposure? | Tail Risk (VaR, CVaR, max drawdown) |
| Where is this portfolio's risk concentrated? | Top risk contributors (weight × volatility) |
| Which assets contribute most to downside risk? | Correlation with portfolio, worst-day returns |
| How would this portfolio have behaved during historical stress periods? | Stress scenario analysis |
| What official SEC risk disclosures are relevant to the current holdings? | Qdrant vector retrieval over 10-K filings |
| What risk themes should an analyst or investor monitor? | AI risk report grounded in attribution + evidence |

The system does **not** answer: what to buy tomorrow, which stock will go up, or what trading
strategy to use.

---

## Current Capabilities

1. **Dynamic portfolio input** — accepts any user-defined portfolio via weight %, dollar amount, or share count; normalizes to weights before analysis.
2. **Price data retrieval** — fetches historical daily closing prices per ticker from Alpha Vantage, a local cache, or yfinance fallback (2018 to today).
3. **Risk metrics** — calculates the following at the portfolio level:
   - Annualized return and volatility
   - Sharpe ratio (risk-free rate = 0%)
   - Maximum drawdown
   - Value at Risk (VaR) at 95% and 99% confidence
   - Conditional Value at Risk (CVaR / Expected Shortfall) at 95% and 99%
4. **Risk attribution** — decomposes portfolio risk across six dimensions:
   - Market Risk: portfolio beta and R² vs SPY
   - Sector Risk: sector weight breakdown and concentration flag
   - Style / Factor Risk: high-beta / high-vol / growth classification
   - Macro Risk: QQQ (tech/growth) and TLT (rate/duration) correlation
   - Concentration Risk: HHI, top-1 / top-3 / top-5 weights
   - Tail Risk: VaR/CVaR interpretation, worst-day analysis, CVaR/VaR ratio
5. **Top risk contributors** — ranks each asset by weight × volatility contribution, correlation with portfolio returns, and average return on the portfolio's five worst trading days.
6. **Stress-period analysis** — evaluates portfolio behavior during two historical stress windows:
   - COVID Crash (2020-02-19 to 2020-03-23)
   - 2022 Rate-Hike Selloff (2022-01-03 to 2022-10-14)
7. **Company risk evidence** — retrieves source-grounded risk factor excerpts from SEC 10-K filings using Qdrant vector search.
8. **AI risk report** — generates a structured risk summary grounded in computed attribution data; explains *what is driving risk*, not just *how much*.
9. **Database persistence** — optionally saves portfolio, holdings, company data, and full analysis snapshots to PostgreSQL/Supabase.

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

This is a monorepo. The backend and frontend are deployed to separate services.

```
Backend  →  Railway   (FastAPI, repo root)
Frontend →  Vercel    (Next.js, /frontend directory)
```

---

### Quick checklist

**Backend (Railway)**
- [ ] Connect GitHub repo to Railway
- [ ] Set root directory to repo root (default)
- [ ] Set start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Add all backend environment variables (see table below)
- [ ] Confirm `GET /health` returns `{"status":"ok"}`

**Frontend (Vercel)**
- [ ] Import same GitHub repo into Vercel
- [ ] Set root directory to `frontend`
- [ ] Add `NEXT_PUBLIC_API_BASE_URL` pointing to the Railway backend URL
- [ ] Deploy and test Analyze Portfolio from the live URL

---

### Backend — Railway

| Setting | Value |
|---|---|
| Root directory | *(repo root — default)* |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| Watch paths | *(default)* |

**Required Railway environment variables:**

| Variable | Example / Notes |
|---|---|
| `DATABASE_URL` | Supabase pooler URL (port 6543) — NullPool is configured |
| `QDRANT_URL` | Your Qdrant cloud instance URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `QDRANT_COLLECTION_NAME` | `company_risk_documents` |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage free or premium key |
| `SEC_USER_AGENT` | `"Your Name your.email@example.com"` (required by SEC EDGAR) |
| `OPENAI_API_KEY` | OpenAI key for AI risk summary |
| `OPENAI_MODEL` | `gpt-4o-mini` (default) |
| `FRONTEND_ORIGIN` | Your Vercel URL, e.g. `https://your-app.vercel.app` — or `*` to allow all origins |

Copy `.env.example` as a reference. Do not commit `.env`.

**Health check URLs** (replace with your Railway domain):

```
GET https://your-backend.up.railway.app/             → API info
GET https://your-backend.up.railway.app/health       → {"status":"ok"}
GET https://your-backend.up.railway.app/ai-summary-status  → OpenAI config check
```

---

### Frontend — Vercel

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Framework preset | Next.js (auto-detected) |
| Build command | `npm run build` |
| Install command | `npm install` |
| Output directory | *(Next.js default)* |

**Required Vercel environment variable:**

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `https://your-backend.up.railway.app` (no trailing slash) |

> **Important:** Do NOT add backend secrets to Vercel.
> Never set `DATABASE_URL`, `OPENAI_API_KEY`, `QDRANT_API_KEY`, or `ALPHA_VANTAGE_API_KEY`
> as Vercel environment variables. Those belong on Railway only.

Copy `frontend/.env.example` to `frontend/.env.local` for local development.

---

### Local development

```bash
# Terminal 1 — backend
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev          # http://localhost:3002
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `frontend/.env.local`.
Default fallback is `http://127.0.0.1:8000`.

After deploying the frontend to Vercel, set `FRONTEND_ORIGIN` on the Railway backend to your Vercel URL so CORS allows requests from the live frontend.

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

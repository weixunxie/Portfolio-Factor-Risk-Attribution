# Portfolio Factor Risk Attribution Dashboard

An interactive risk analytics system that decomposes portfolio risk across holdings, sectors,
market sensitivity, style exposure, macro proxies, concentration, and tail-risk behavior,
with AI-generated explanations grounded in computed metrics.

**For educational and research purposes only. Not investment advice.**

---

## What This Dashboard Does

Most portfolio risk tools stop at metrics: volatility, VaR, drawdown. This dashboard goes one
step further and asks *why* — decomposing where risk actually comes from across six structured
dimensions, then presenting it in plain English backed by the underlying numbers.

A user enters a portfolio of tickers and weights. The system fetches historical price data,
computes standard risk metrics, runs a proxy factor exposure regression, identifies concentration
and tail-risk drivers, retrieves company-level evidence from SEC 10-K filings, and generates an
AI-narrated risk report grounded in all of the above.

The system is designed for students, researchers, and practitioners who want to build a
portfolio-readiness argument for a set of holdings — not to generate trading signals.

---

## Why Risk Attribution Matters

A portfolio with 20% annualized volatility and a −35% maximum drawdown tells you *how much* risk
there is. It does not tell you *what is driving it*.

Is the risk coming from concentrated exposure to a single sector? From high-beta technology names
that amplify broad market moves? From position sizing where the top three holdings dominate?
Or from tail-risk characteristics that make losses worse-than-normal during stress?

This dashboard answers those questions directly, making it easier to explain and present a
portfolio's risk profile in a structured, evidence-backed way.

---

## Main Modules

| Module | What it computes |
|---|---|
| **Risk Metrics** | Annualized return, volatility, Sharpe ratio, max drawdown, VaR/CVaR at 95% and 99% |
| **Market Risk** | Portfolio beta vs SPY; R² and correlation; market amplification estimate |
| **Sector Risk** | Sector weight breakdown; equity sector concentration; ETF holdings separated |
| **Style / Factor Risk** | Rule-based style classification: high-beta, high-volatility, growth/tech-heavy, defensive |
| **Macro Risk** | Correlation and beta vs QQQ (growth proxy) and TLT (duration/rates proxy) |
| **Concentration Risk** | HHI score; top-1, top-3, top-5 position weights; number of holdings |
| **Tail Risk** | VaR/CVaR interpretation; CVaR/VaR ratio; max drawdown; worst-day analysis |
| **Proxy Factor Regression** | OLS regression on SPY, QQQ, TLT proxy returns; beta, t-stat, p-value, R² per factor |
| **Top Risk Contributors** | Per-holding weight × volatility contribution; correlation with portfolio; worst-day returns |
| **Stress Scenarios** | Portfolio performance during COVID Crash and 2022 Rate-Hike Selloff |
| **SEC Risk Evidence** | Semantic search over ingested 10-K filings via Qdrant vector retrieval |
| **AI Risk Report** | GPT-narrated risk summary grounded in computed attribution and evidence |

---

## Methodology

### Risk Attribution (six heuristic dimensions)

Each dimension uses rule-based thresholds applied to computed statistics:

- **Market Risk**: OLS beta of portfolio returns vs SPY. Thresholds: High > 1.30, Moderate 0.85–1.30, Low ≤ 0.85.
- **Sector Risk**: sector weight aggregation from holding profiles. ETF holdings are separated and excluded from equity sector concentration.
- **Style / Factor Risk**: threshold rules on weighted-average volatility, beta, and growth-sector weight. Tags: high-beta, high-volatility, growth/tech-heavy, defensive.
- **Macro Risk**: Pearson correlation and beta vs QQQ and TLT. Weak correlations (|r| < 0.25 for TLT) are explicitly labeled inconclusive.
- **Concentration Risk**: Herfindahl-Hirschman Index (HHI), top-N weight sums. High when top-3 > 70% or top-1 > 35%.
- **Tail Risk**: historical VaR (percentile), CVaR (conditional mean), max drawdown, CVaR/VaR ratio.

### Proxy Factor Exposure Regression

OLS regression of portfolio daily returns on three market proxy ETF returns:

```
portfolio_return(t) = α + β₁·SPY(t) + β₂·QQQ(t) + β₃·TLT(t) + ε(t)
```

- **SPY** = broad equity market proxy
- **QQQ** = growth/technology proxy
- **TLT** = duration/rates proxy (directional only — not a direct 10Y Treasury yield measure)

Output per factor: beta coefficient, t-stat, p-value, and plain-English interpretation.
Only factors with p < 0.05 are marked statistically significant.
VIF is computed per factor. SPY and QQQ are often highly correlated; their individual betas
should be interpreted jointly rather than in isolation.

This is proxy-based regression, not a formal academic factor model. The proxies are accessible
ETF return series — not long-short constructed portfolios. Volatility-shock sensitivity (VIX proxy)
is planned as a future extension.

### AI Risk Report

The LLM (GPT-4o-mini by default) narrates already-computed metrics in plain English. It does not
calculate, estimate, or invent any values. The prompt payload includes risk metrics, attribution
results, factor regression output, and SEC evidence excerpts. The LLM is explicitly instructed
not to provide investment advice or predictions.

---

## Data Sources

| Source | What it provides | API key required |
|---|---|---|
| `data/processed/` | Pre-built daily returns for 10 demo tickers (2018–present) | No |
| Tiingo | **Primary** live price history — adjusted close, full history back to 2018, ~1000 calls/day free | Yes (`TIINGO_API_KEY`) |
| Alpha Vantage | Company profiles, sector data; fallback price history (free tier: 25 calls/day) | Yes (`ALPHA_VANTAGE_API_KEY`) |
| yfinance | Last-resort price/profile fallback (rate-limited on datacenter IPs) | No |
| SEC EDGAR | 10-K filing metadata and CIK lookup | No (user-agent required) |
| Qdrant Cloud | Vector store for 10-K risk factor chunks | Yes (`QDRANT_API_KEY`) |
| OpenAI | AI risk report narration | Yes (`OPENAI_API_KEY`) |
| PostgreSQL / Supabase | Portfolio/analysis persistence **+ durable provider cache (`provider_cache`)** | Yes (`DATABASE_URL`) |

The static fallback map in `src/providers/security_metadata.py` covers all ten demo tickers
and ~50 common ETFs, so sector and security-type resolution works offline for those tickers.

### Price-data resolution & caching

For any ticker, price history is resolved through this priority chain
(`src/dynamic_portfolio.py`):

1. **`data/processed/returns.csv`** — the 10 demo tickers, always available offline.
2. **Durable cache** (`provider_cache` table) — any series fetched on a previous run.
3. **Tiingo** — primary live source.
4. **Alpha Vantage** — fallback.
5. **yfinance** — last resort.

Every successful live fetch is written to a two-tier cache
(`src/providers/cache.py`): a local file under `data/cache/` **and** the
`provider_cache` Postgres table. The Postgres tier matters because Railway's
filesystem is ephemeral — without it, the file cache is wiped on every
restart/redeploy and non-demo tickers must be re-fetched on every cold
container, which fails whenever the live APIs are rate-limited or blocked.
Apply the table once via `db/migrations/001_provider_cache.sql` (Supabase SQL
Editor). If `DATABASE_URL` is absent the cache transparently degrades to
file-only.

The `GET /cache/health` endpoint reports the state of all of this:
`{ tiingo_key_set, alpha_vantage_key_set, database_configured, cache_persistence }`.

---

## Technical Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.11+), uvicorn |
| Statistical computation | numpy, pandas, scipy (OLS regression) |
| Structured storage | PostgreSQL via SQLAlchemy + psycopg2 (Supabase hosted) |
| Vector retrieval | Qdrant Cloud |
| Embeddings | sentence-transformers (local) |
| SEC filings | SEC EDGAR REST API (no key required) |
| Market data | Tiingo (primary) → Alpha Vantage → yfinance, with a Postgres-backed durable cache |
| AI narration | OpenAI Chat Completions API |

---

## How to Run

### 1. Install backend dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in the values you have. At minimum for local use:

```
TIINGO_API_KEY=your_key          # primary price source for non-demo tickers
ALPHA_VANTAGE_API_KEY=your_key   # optional: company profiles + fallback prices
OPENAI_API_KEY=your_key          # optional: enables AI risk report
SEC_USER_AGENT=YourName your@email.com
# DATABASE_URL enables the durable provider cache; QDRANT_* enables SEC evidence.
# Both are optional for local testing (cache degrades to file-only without DATABASE_URL).
```

### 3. Start the backend

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:3002
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `frontend/.env.local`.
Default fallback is `http://127.0.0.1:8000`.

---

## Deployment

```
Backend  →  Railway   (FastAPI, repo root, start: uvicorn api.main:app --host 0.0.0.0 --port $PORT)
Frontend →  Vercel    (Next.js, /frontend directory)
```

Set `FRONTEND_ORIGIN` on the Railway backend to your Vercel URL so CORS allows requests from the
deployed frontend. Never expose backend secrets (`DATABASE_URL`, `OPENAI_API_KEY`, etc.) in
Vercel environment variables.

**Railway backend variables** to set: `TIINGO_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `DATABASE_URL`,
`OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `SEC_USER_AGENT`, `FRONTEND_ORIGIN`. Paste keys
with no surrounding whitespace. After deploy, hit `GET /cache/health` to confirm
`tiingo_key_set`, `database_configured`, and `cache_persistence` are all `true`. Run the
`db/migrations/001_provider_cache.sql` migration once in Supabase so the durable cache survives
Railway's ephemeral filesystem across restarts/redeploys.

---

## Current Limitations

- **Backward-looking only** — all metrics and regression coefficients are computed from historical data. Past behavior is not predictive of future performance.
- **No transaction costs** — returns do not account for trading costs, taxes, or slippage.
- **Sharpe ratio** — assumes risk-free rate of 0%.
- **Fixed stress windows** — COVID Crash and 2022 Rate-Hike Selloff only; no automatic drawdown detection.
- **Factor regression proxy quality** — SPY, QQQ, TLT are accessible but imprecise proxies. TLT captures duration/rate-regime dynamics directionally, not 10Y Treasury yield changes directly. SPY and QQQ are highly correlated, which can distort individual betas.
- **Style classification** — rule-based heuristics, not a statistical factor model.
- **SEC evidence** — risk evidence comes from 10-K filings ingested into Qdrant. ~74 common large-cap tickers are pre-ingested (see `data/universe.txt` + `scripts/bulk_ingest.py`). Any other ticker is **ingested on demand**: the first analysis that references it triggers a background extract+ingest and shows a "preparing…" note; re-running the analysis ~30–60s later surfaces the evidence (it is then cached in Qdrant permanently). A ticker yields no evidence only when its 10-K has no machine-locatable Item 1A section (some filing layouts) or it has no 10-K at all (ETFs, foreign issuers).
- **Demo ticker coverage** — pre-built returns cover AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, SPY, QQQ, TLT. Other tickers are fetched live (Tiingo → Alpha Vantage → yfinance) and cached in `provider_cache`. A ticker only fails when it is delisted/invalid (no source has data) or all live sources are simultaneously rate-limited on a cold, un-cached request.

---

## Planned Future Extensions

- **VIX proxy factor** — add `^VIX` daily changes as a volatility-shock proxy in the factor regression (requires reliable daily VIX data in the pipeline)
- **Additional stress windows** — dot-com crash, 2008 financial crisis, 2020 March recovery
- **Rolling beta** — time-varying market beta chart using rolling windows
- **Sector ETF proxies** — XLK, XLF, XLE as additional macro sensitivity benchmarks

---

## Disclaimer

This tool is for **educational and research purposes only**. It does not constitute investment
advice, a solicitation, or a recommendation to buy, sell, or hold any security or financial
instrument. All analysis is based on historical data and is subject to the limitations described
above. Risk metrics, factor regression outputs, and AI-generated summaries describe past behavior
— they do not predict future performance. Users should consult a qualified financial professional
before making any investment decisions.

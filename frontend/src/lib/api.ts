const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// ── transport ──────────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `${path} → ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── static MVP types ───────────────────────────────────────────────────────────

export interface RiskSummaryRow {
  Metric: string;
  Value: number;
}

export interface TopRiskContributor {
  "": string;
  weight: number;
  annualized_volatility: number;
  weight_volatility_contribution: number;
  correlation_with_portfolio: number;
  average_return_on_worst_5_days: number;
  rank_by_wv_contribution: number;
  rank_by_correlation: number;
  rank_by_worst_day_loss: number;
}

export interface StressSummaryRow {
  period: string;
  start: string;
  end: string;
  portfolio_cumulative_return: number;
  portfolio_max_drawdown: number;
  worst_contributor_1: string;
  worst_contributor_2: string;
  worst_contributor_3: string;
}

export interface StressAssetContribution {
  period: string;
  asset: string;
  weight: number;
  asset_cumulative_return: number;
  weighted_contribution: number;
}

export interface MarkdownResponse {
  markdown: string;
}

// ── dynamic types ──────────────────────────────────────────────────────────────

export interface CompanyProfile {
  ticker: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  description: string;
  currency: string;
  market_cap: string;
  pe_ratio: string;
  week_52_high: string;
  week_52_low: string;
  dividend_yield: string;
  source: string | null;
  cached: boolean;
  error: string | null;
}

export interface SecRiskFactorsResponse {
  success: boolean;
  ticker: string;
  cik: number | null;
  filing_date: string | null;
  accession_number: string | null;
  source_url: string | null;
  preview: string | null;
  output_path: string | null;
  cached: boolean;
  error: string | null;
}

export interface RiskQueryHit {
  ticker: string;
  source_file: string;
  source_type: string;
  filing_date: string;
  accession_number: string;
  chunk_id: string;
  text: string;
  score: number;
}

export interface RiskQueryResponse {
  ticker: string;
  query: string;
  top_k: number;
  results: RiskQueryHit[];
}

export interface HoldingInput {
  ticker: string;
  weight: number;
}

export interface EnrichedHolding {
  ticker: string;
  weight: number;
  weight_pct: string;
  profile: {
    name: string;
    sector: string;
    industry: string;
    exchange: string;
    market_cap: string;
    pe_ratio: string;
    week_52_high: string;
    week_52_low: string;
    source: string;
  };
}

export interface AnalyzePortfolioResponse {
  holdings: EnrichedHolding[];
  total_weight: number;
  total_weight_pct: string;
  dynamic_risk_metrics_status: string;
  dynamic_risk_metrics_note: string;
  disclaimer: string;
}

// ── static MVP API calls ───────────────────────────────────────────────────────

export const fetchRiskSummary = () => get<RiskSummaryRow[]>("/risk-summary");
export const fetchTopRiskContributors = () => get<TopRiskContributor[]>("/top-risk-contributors");
export const fetchStressSummary = () => get<StressSummaryRow[]>("/stress-summary");
export const fetchStressAssetContributions = () => get<StressAssetContribution[]>("/stress-asset-contributions");
export const fetchRiskMemo = () => get<MarkdownResponse>("/risk-memo");
export const fetchCompanyRiskEvidence = () => get<MarkdownResponse>("/company-risk-evidence");

// ── dynamic API calls ──────────────────────────────────────────────────────────

export const fetchCompanyProfile = (ticker: string) =>
  get<CompanyProfile>(`/company-profile/${encodeURIComponent(ticker)}`);

export const fetchSecRiskFactors = (ticker: string, force = false) =>
  get<SecRiskFactorsResponse>(
    `/sec-risk-factors/${encodeURIComponent(ticker)}${force ? "?force=true" : ""}`
  );

export const queryCompanyRisk = (ticker: string, query: string, top_k = 5) =>
  get<RiskQueryResponse>(
    `/company-risk-query?ticker=${encodeURIComponent(ticker)}&query=${encodeURIComponent(query)}&top_k=${top_k}`
  );

export const analyzePortfolio = (holdings: HoldingInput[]) =>
  post<AnalyzePortfolioResponse>("/analyze-portfolio", { holdings });

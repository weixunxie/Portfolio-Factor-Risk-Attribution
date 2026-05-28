const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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

// ── Core types ────────────────────────────────────────────────────────────────

export type InputMode = "weights" | "amounts" | "shares";

export interface HoldingInput {
  ticker: string;
  weight?: number;  // input_mode="weights"
  amount?: number;  // input_mode="amounts"
  shares?: number;  // input_mode="shares"
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
    profile_error?: string | null;
  };
}

export interface RiskMetrics {
  annualized_return: number;
  annualized_volatility: number;
  sharpe_ratio: number;
  max_drawdown: number;
  var_95: number;
  cvar_95: number;
  var_99: number;
  cvar_99: number;
  trading_days_used: number;
  data_start: string;
  data_end: string;
}

export interface RiskContributor {
  ticker: string;
  weight: number;
  annualized_volatility: number;
  weight_volatility_contribution: number;
  correlation_with_portfolio: number;
  average_return_on_worst_5_portfolio_days: number;
}

export interface WorstContributor {
  ticker: string;
  contribution: number;
}

export interface StressPeriodResult {
  name: string;
  start: string;
  end: string;
  portfolio_cumulative_return: number;
  portfolio_max_drawdown: number;
  worst_contributors: WorstContributor[];
  asset_data_available: boolean;
}

export interface RiskEvidenceHit {
  ticker: string;
  source_file: string;
  source_type: string;
  filing_date: string;
  accession_number: string;
  chunk_id: string;
  text: string;
  score: number;
}

export type RiskEvidenceEntry = RiskEvidenceHit[] | { message: string };

export interface AnalyzePortfolioResponse {
  holdings: EnrichedHolding[];
  total_weight: number;
  total_weight_pct: string;
  dynamic_risk_metrics_status: string;
  risk_metrics: RiskMetrics;
  correlation_matrix: Record<string, Record<string, number>>;
  top_risk_contributors: RiskContributor[];
  stress_analysis: StressPeriodResult[];
  company_risk_evidence: Record<string, RiskEvidenceEntry>;
  failed_tickers: string[];
  warnings: string[];
  portfolio_id: string | null;
  analysis_id: string | null;
  disclaimer: string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const analyzePortfolio = (
  holdings: HoldingInput[],
  opts?: {
    input_mode?: InputMode;
    total_portfolio_value?: number;
    treat_unallocated_as_cash?: boolean;
    portfolio_name?: string;
    portfolio_goal?: string;
    save_to_database?: boolean;
  }
) =>
  post<AnalyzePortfolioResponse>("/analyze-portfolio", {
    holdings,
    input_mode: "weights",
    save_to_database: true,
    ...opts,
  });

// Static endpoints kept for backward compatibility
export interface MarkdownResponse {
  markdown: string;
}
export const fetchRiskMemo = () => get<MarkdownResponse>("/risk-memo");
export const fetchCompanyRiskEvidence = () =>
  get<MarkdownResponse>("/company-risk-evidence");

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  analyzePortfolio,
  type AnalyzePortfolioResponse,
  type HoldingInput,
  type InputMode,
  type RiskMetrics,
} from "@/lib/api";
import SidebarPortfolioForm from "@/components/SidebarPortfolioForm";
import EmptyState from "@/components/EmptyState";
import MetricCard, { type MetricColor } from "@/components/MetricCard";
import PortfolioComposition from "@/components/PortfolioComposition";
import RiskContributorCards from "@/components/RiskContributorCards";
import StressScenarioCards from "@/components/StressScenarioCards";
import CompanyEvidenceAccordion from "@/components/CompanyEvidenceAccordion";
import RiskReportPreview from "@/components/RiskReportPreview";
import RiskAttributionSection from "@/components/RiskAttributionSection";

// ── helpers ───────────────────────────────────────────────────────────────────

type Status = "idle" | "loading" | "error" | "result";

function pct(n: number, d = 1) {
  return `${(n * 100).toFixed(d)}%`;
}

function metricColor(key: string, value: number): MetricColor {
  switch (key) {
    case "return":   return value >= 0 ? "positive" : "negative";
    case "sharpe":   return value >= 1 ? "positive" : value >= 0.5 ? "warning" : "negative";
    case "drawdown": return value < -0.25 ? "negative" : value < -0.1 ? "warning" : "neutral";
    case "risk":     return "negative";
    default:         return "neutral";
  }
}

// ── shared section header ─────────────────────────────────────────────────────

function Sec({ title, sub }: { title: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <h2 style={{ color: "var(--text)", fontSize: 14, fontWeight: 600 }}>{title}</h2>
      {sub && <p style={{ color: "var(--faint)", fontSize: 11, marginTop: 3 }}>{sub}</p>}
    </div>
  );
}

// ── contact / author block (reused on both landing and results pages) ─────────

function ContactBlock() {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10, paddingTop: 4, paddingRight: 6 }}>
      <span style={{ color: "var(--faint)", fontSize: 10.5, fontWeight: 500, letterSpacing: "0.01em" }}>
        Built by Stephanie Xie
      </span>
      <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
        {/* GitHub */}
        <a href="https://github.com/weixunxie" target="_blank" rel="noopener noreferrer"
          aria-label="GitHub profile" className="contact-icon-link">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.09.682-.218.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
        </a>
        {/* LinkedIn */}
        <a href="https://www.linkedin.com/in/weixun-xie-0587202b0/" target="_blank" rel="noopener noreferrer"
          aria-label="LinkedIn profile" className="contact-icon-link">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
        </a>
        {/* Email */}
        <a href="mailto:weixunxie@outlook.com" aria-label="Send email" className="contact-icon-link">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="2" y="4" width="20" height="16" rx="2" />
            <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
          </svg>
        </a>
      </div>
    </div>
  );
}

// ── loading ───────────────────────────────────────────────────────────────────

const LOADING_STEPS = [
  "Validating holdings",
  "Loading historical prices",
  "Computing VaR / CVaR",
  "Running stress scenarios",
  "Retrieving company risk evidence",
  "Preparing risk report",
];

const STEP_DELAYS = [300, 2500, 5500, 9000, 14000, 22000];

function SkeletonBlock({
  h = 16,
  w = "100%",
  mb = 0,
}: {
  h?: number;
  w?: string;
  mb?: number;
}) {
  return (
    <div
      style={{
        height: h,
        width: w,
        background: "var(--border-lt)",
        borderRadius: 4,
        marginBottom: mb,
        animation: "skeletonPulse 1.6s ease-in-out infinite",
      }}
    />
  );
}

function SkeletonCard({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 7,
        padding: "14px 16px",
      }}
    >
      {children}
    </div>
  );
}

function LoadingView() {
  const [doneCount, setDoneCount] = useState(0);

  useEffect(() => {
    const timers = STEP_DELAYS.map((delay, i) =>
      setTimeout(() => setDoneCount(i + 1), delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <>
      <style>{`
        @keyframes skeletonPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.45; }
        }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            color: "var(--text)",
            fontSize: 20,
            fontWeight: 600,
            marginBottom: 5,
            letterSpacing: "-0.01em",
          }}
        >
          Analyzing portfolio risk
        </h1>
        <p style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.6, maxWidth: 520 }}>
          Fetching market data, computing risk metrics, and retrieving company evidence.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "200px 1fr",
          gap: 18,
          alignItems: "start",
        }}
      >
        {/* Left: animated step checklist */}
        <SkeletonCard>
          <p
            style={{
              color: "var(--faint)",
              fontSize: 9.5,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: 14,
            }}
          >
            Progress
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {LOADING_STEPS.map((label, i) => {
              const done = i < doneCount;
              const active = i === doneCount;
              return (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <div
                    style={{
                      width: 15,
                      height: 15,
                      borderRadius: "50%",
                      flexShrink: 0,
                      border: done
                        ? "none"
                        : active
                        ? "2px solid var(--text)"
                        : "1px solid var(--border)",
                      background: done ? "var(--positive)" : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      transition: "all 0.3s",
                    }}
                  >
                    {done && (
                      <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                        <path
                          d="M1.5 4L3.2 5.7L6.5 2.3"
                          stroke="white"
                          strokeWidth="1.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                    {active && (
                      <div
                        style={{
                          width: 5,
                          height: 5,
                          borderRadius: "50%",
                          background: "var(--text)",
                          animation: "skeletonPulse 0.9s ease-in-out infinite",
                        }}
                      />
                    )}
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      color: done
                        ? "var(--muted)"
                        : active
                        ? "var(--text)"
                        : "var(--faint)",
                      fontWeight: active ? 500 : 400,
                      transition: "color 0.3s",
                    }}
                  >
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        </SkeletonCard>

        {/* Right: skeleton result preview */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Skeleton metric cards row */}
          <SkeletonCard>
            <SkeletonBlock h={9} w="70px" mb={12} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  style={{
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    padding: "10px 12px",
                  }}
                >
                  <SkeletonBlock h={8} w="55%" mb={8} />
                  <SkeletonBlock h={20} w="75%" mb={5} />
                  <SkeletonBlock h={7} w="45%" />
                </div>
              ))}
            </div>
          </SkeletonCard>

          {/* Skeleton contributors */}
          <SkeletonCard>
            <SkeletonBlock h={9} w="130px" mb={12} />
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 14,
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: i < 3 ? "1px solid var(--border-lt)" : "none",
                }}
              >
                <SkeletonBlock h={9} w="20px" />
                <SkeletonBlock h={9} w="45px" />
                <SkeletonBlock h={9} w="35px" />
                <SkeletonBlock h={9} w="40px" />
                <SkeletonBlock h={9} w="40px" />
              </div>
            ))}
          </SkeletonCard>

          {/* Skeleton stress scenario cards */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {["COVID Crash", "2022 Rate-Hike Selloff"].map((name) => (
              <SkeletonCard key={name}>
                <SkeletonBlock h={11} w="65%" mb={5} />
                <SkeletonBlock h={8} w="45%" mb={14} />
                <SkeletonBlock h={22} w="38%" mb={4} />
                <SkeletonBlock h={8} w="55%" />
              </SkeletonCard>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ── error ─────────────────────────────────────────────────────────────────────

function ErrorView({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div style={{ maxWidth: 500, paddingTop: 60 }}>
      <p style={{ color: "var(--negative)", fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
        Analysis failed
      </p>
      <p style={{ color: "var(--muted)", fontSize: 13, lineHeight: 1.65, marginBottom: 20 }}>
        {message}
      </p>
      <button
        onClick={onDismiss}
        style={{
          background: "none",
          border: "1px solid var(--border)",
          color: "var(--muted)",
          borderRadius: 4,
          padding: "6px 14px",
          fontSize: 12,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        Try again
      </button>
    </div>
  );
}

// ── risk metrics grid ─────────────────────────────────────────────────────────

function MetricsGrid({ m }: { m: RiskMetrics }) {
  const cells: { label: string; value: string; helper?: string; colorKey: string }[] = [
    { label: "Annualised Return",     value: pct(m.annualized_return),     colorKey: "return" },
    { label: "Annualised Volatility", value: pct(m.annualized_volatility),  helper: "std dev × √252", colorKey: "neutral" },
    { label: "Sharpe Ratio",          value: m.sharpe_ratio.toFixed(2),    helper: "risk-free rate 0%", colorKey: "sharpe" },
    { label: "Maximum Drawdown",      value: pct(m.max_drawdown),          colorKey: "drawdown" },
    { label: "VaR 95%",               value: pct(m.var_95),                helper: "1-day historical", colorKey: "risk" },
    { label: "CVaR 95%",              value: pct(m.cvar_95),               helper: "expected shortfall", colorKey: "risk" },
    { label: "VaR 99%",               value: pct(m.var_99),                helper: "1-day historical", colorKey: "risk" },
    { label: "CVaR 99%",              value: pct(m.cvar_99),               helper: "expected shortfall", colorKey: "risk" },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
      {cells.map(({ label, value, helper, colorKey }) => (
        <MetricCard
          key={label}
          label={label}
          value={value}
          helper={helper}
          color={metricColor(colorKey, parseFloat(value))}
        />
      ))}
    </div>
  );
}

// ── result panel ──────────────────────────────────────────────────────────────

function ResultPanel({ result }: { result: AnalyzePortfolioResponse }) {
  const { risk_metrics: m } = result;
  const evidence = result.company_risk_evidence ?? {};
  const hasEvidence = Object.keys(evidence).length > 0;
  const hasContributors = result.top_risk_contributors.length > 0;
  const hasStress = result.stress_analysis.length > 0;

  return (
    <div>
      {/* Page header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ color: "var(--text)", fontSize: 20, fontWeight: 600, marginBottom: 4 }}>
            Portfolio Analysis Results
          </h1>
          <p style={{ color: "var(--faint)", fontSize: 12 }}>
            {m.trading_days_used} trading days · {m.data_start} to {m.data_end}
          </p>
        </div>
        <ContactBlock />
      </div>

      {/* Warnings — collapse noisy DB/company errors into a single line */}
      {result.warnings.length > 0 && (() => {
        const dbRelated = result.warnings.filter(w =>
          w.toLowerCase().includes("database") ||
          w.toLowerCase().includes("company upsert") ||
          w.toLowerCase().includes("db")
        );
        const other = result.warnings.filter(w =>
          !w.toLowerCase().includes("database") &&
          !w.toLowerCase().includes("company upsert") &&
          !w.toLowerCase().includes("db")
        );
        const displayed = [
          ...(dbRelated.length > 0
            ? ["Database save skipped (DATABASE_URL not configured locally). Analysis results are still shown."]
            : []),
          ...other,
        ];
        return (
          <div
            style={{
              background: "var(--warn-bg)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "10px 14px",
              marginBottom: 22,
            }}
          >
            {displayed.map((w, i) => (
              <p key={i} style={{ color: "var(--warning)", fontSize: 12, lineHeight: 1.5 }}>
                {w}
              </p>
            ))}
          </div>
        );
      })()}

      {/* ── Row 1: Risk Metrics ── */}
      <div style={{ marginBottom: 24 }}>
        <Sec title="Risk Metrics" />
        <MetricsGrid m={m} />
      </div>

      {/* ── Row 2: Portfolio Overview + Top Risk Contributors side-by-side ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 3fr",
          gap: 18,
          marginBottom: 24,
          alignItems: "start",
        }}
      >
        <div>
          <Sec title="Portfolio Overview" />
          <PortfolioComposition holdings={result.holdings} />
        </div>

        {hasContributors && (
          <div style={{ minWidth: 0 }}>
            <Sec
              title="Top Risk Contributors"
              sub="Ranked by weight × volatility contribution"
            />
            <RiskContributorCards contributors={result.top_risk_contributors} />
          </div>
        )}
      </div>

      {/* ── Row 3: Risk Attribution ── */}
      {result.risk_attribution && (
        <div style={{ marginBottom: 24 }}>
          <Sec
            title="Risk Attribution"
            sub="What is driving this portfolio's risk?"
          />
          <RiskAttributionSection attribution={result.risk_attribution} />
        </div>
      )}

      {/* ── Row 4: Stress Scenarios ── */}
      {hasStress && (
        <div style={{ marginBottom: 24 }}>
          <Sec
            title="Stress Scenarios"
            sub="Historical portfolio performance during major market events"
          />
          <StressScenarioCards scenarios={result.stress_analysis} />
        </div>
      )}

      {/* ── Row 5: Company Risk Evidence ── */}
      {hasEvidence && (
        <div style={{ marginBottom: 24 }}>
          <Sec
            title="Company Risk Evidence"
            sub="Semantic search over SEC 10-K filings · expand to read excerpts"
          />
          <CompanyEvidenceAccordion evidence={evidence} />
        </div>
      )}

      {/* ── Row 6: Risk Report ── */}
      <div style={{ marginBottom: 24 }}>
        <Sec title="Risk Report" />
        <RiskReportPreview result={result} />
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AnalyzePortfolioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = useCallback(async (
    holdings: HoldingInput[],
    opts?: {
      input_mode?: InputMode;
      total_portfolio_value?: number;
      treat_unallocated_as_cash?: boolean;
      generate_ai_summary?: boolean;
    }
  ) => {
    setStatus("loading");
    setError(null);
    try {
      const data = await analyzePortfolio(holdings, opts);
      setResult(data);
      setStatus("result");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analysis failed. Please try again.");
      setStatus("error");
    }
  }, []);

  const handleReset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
  }, []);

  return (
    <div style={{ height: "100vh", overflow: "hidden", display: "flex" }}>

      {/* ── Left panel ───────────────────────────────────────────────────── */}
      <aside className="app-sidebar">
        {/* Brand */}
        <div style={{ padding: "20px 22px 16px" }}>
          <p style={{ color: "var(--text)", fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>
            Portfolio Risk
          </p>
          <p style={{ color: "var(--faint)", fontSize: 12, marginTop: 3 }}>
            Portfolio Intelligence System
          </p>
        </div>

        <div style={{ height: 1, background: "var(--border)", margin: "0 22px" }} />

        {/* Form */}
        <div style={{ flex: 1, padding: "16px 22px", overflowY: "auto" }}>
          <SidebarPortfolioForm
            onAnalyze={handleAnalyze}
            onReset={handleReset}
            isLoading={status === "loading"}
          />
        </div>

      </aside>

      {/* ── Main panel ───────────────────────────────────────────────────── */}
      <main className="app-main">
        <div className="app-main-inner">

          {status === "idle" && (
            <div className="landing-wrapper">
              <EmptyState onRunSample={handleAnalyze} />
            </div>
          )}
          {status === "loading" && (
            <div className="panel-pad">
              <LoadingView />
            </div>
          )}
          {status === "error" && (
            <div className="panel-pad">
              <ErrorView message={error!} onDismiss={() => setStatus("idle")} />
            </div>
          )}
          {status === "result" && result && (
            <div className="panel-pad">
              <ResultPanel result={result} />
            </div>
          )}

          {/* Global disclaimer — always visible at bottom of main content */}
          <div className="global-disclaimer">
            <p style={{ color: "var(--faint)", fontSize: 11 }}>
              Educational use only. Not investment advice.
            </p>
          </div>

        </div>
      </main>
    </div>
  );
}

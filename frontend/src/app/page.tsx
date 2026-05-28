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
import DisclaimerBanner from "@/components/DisclaimerBanner";

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
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: "var(--text)", fontSize: 20, fontWeight: 600, marginBottom: 4 }}>
          Portfolio Analysis Results
        </h1>
        <p style={{ color: "var(--faint)", fontSize: 12 }}>
          {m.trading_days_used} trading days · {m.data_start} to {m.data_end}
        </p>
      </div>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div
          style={{
            background: "var(--warn-bg)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "10px 14px",
            marginBottom: 22,
          }}
        >
          {result.warnings.map((w, i) => {
            // Truncate long raw DB/SQL errors to a clean one-liner
            const isDbError = w.toLowerCase().includes("database save failed");
            const display = isDbError
              ? "Database save failed. Analysis results are still shown."
              : w;
            return (
              <p key={i} style={{ color: "var(--warning)", fontSize: 12, lineHeight: 1.5 }}>
                {display}
              </p>
            );
          })}
        </div>
      )}

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

      {/* ── Row 3: Stress Scenarios ── */}
      {hasStress && (
        <div style={{ marginBottom: 24 }}>
          <Sec
            title="Stress Scenarios"
            sub="Historical portfolio performance during major market events"
          />
          <StressScenarioCards scenarios={result.stress_analysis} />
        </div>
      )}

      {/* ── Row 4: Company Risk Evidence ── */}
      {hasEvidence && (
        <div style={{ marginBottom: 24 }}>
          <Sec
            title="Company Risk Evidence"
            sub="Semantic search over SEC 10-K filings · expand to read excerpts"
          />
          <CompanyEvidenceAccordion evidence={evidence} />
        </div>
      )}

      {/* ── Row 5: AI Risk Report ── */}
      <div style={{ marginBottom: 24 }}>
        <Sec title="AI Risk Report" sub="Generated from analysis results · copy as Markdown" />
        <RiskReportPreview result={result} />
      </div>

      <DisclaimerBanner />
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
      <aside
        style={{
          width: 320,
          flexShrink: 0,
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
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

        {/* Footer */}
        <div style={{ padding: "12px 22px 16px", borderTop: "1px solid var(--border-lt)" }}>
          <p style={{ color: "var(--faint)", fontSize: 10, lineHeight: 1.5, marginBottom: 8 }}>
            Built by Stephanie Xie
          </p>
          <p style={{ color: "var(--faint)", fontSize: 10, lineHeight: 1.5 }}>
            Educational use only.
            <br />
            Not investment advice.
          </p>
        </div>
      </aside>

      {/* ── Main panel ───────────────────────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          background: "var(--bg)",
          padding: "0 48px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {status === "idle" && (
          /* Flex wrapper that distributes equal whitespace above and below the
             empty-state block, so the 2×2 grid feels vertically balanced in
             the viewport rather than pushed toward the top. */
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              padding: "32px 0",
            }}
          >
            <EmptyState onRunSample={handleAnalyze} />
          </div>
        )}
        {status === "loading" && (
          <div style={{ padding: "40px 0" }}>
            <LoadingView />
          </div>
        )}
        {status === "error" && (
          <div style={{ padding: "40px 0" }}>
            <ErrorView message={error!} onDismiss={() => setStatus("idle")} />
          </div>
        )}
        {status === "result" && result && (
          <div style={{ padding: "40px 0" }}>
            <ResultPanel result={result} />
          </div>
        )}
      </main>
    </div>
  );
}

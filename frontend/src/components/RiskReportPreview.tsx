"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AnalyzePortfolioResponse, AiSummary, RiskAttribution } from "@/lib/api";
import { generateRiskSummary } from "@/lib/api";

// ── helpers ───────────────────────────────────────────────────────────────────

function pct(n: number, d = 1) {
  return `${(n * 100).toFixed(d)}%`;
}

function buildAttributionMarkdown(attr: RiskAttribution): string {
  const levelEmoji: Record<string, string> = { High: "🔴", Moderate: "🟡", Low: "🟢", Unknown: "⚪" };
  const keys: Array<keyof Omit<RiskAttribution, "overall" | "factor_regression">> = [
    "market_risk", "sector_risk", "concentration_risk", "tail_risk", "style_risk", "macro_risk",
  ];
  const titles: Record<string, string> = {
    market_risk: "Market Risk", sector_risk: "Sector Risk",
    concentration_risk: "Concentration Risk", tail_risk: "Tail Risk",
    style_risk: "Style / Factor Risk", macro_risk: "Macro Risk",
  };
  const rows = keys
    .map((k) => {
      const item = attr[k];
      if (!item) return "";
      const e = levelEmoji[item.risk_level] ?? "⚪";
      return `| ${titles[k]} | ${e} ${item.risk_level} | ${item.summary || "—"} |`;
    })
    .filter(Boolean)
    .join("\n");

  return `## Risk Attribution

| Driver | Level | Summary |
|--------|-------|---------|
${rows}
`;
}

function buildMarkdownReport(result: AnalyzePortfolioResponse): string {
  const { holdings, risk_metrics: m, top_risk_contributors: contrib, stress_analysis } = result;
  const today = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });

  const holdingsTable = holdings
    .map((h) => {
      const secType = h.profile.security_type || "Equity";
      const sectorDisplay = h.profile.sector || "Unknown";
      const nameDisplay = h.profile.name || h.ticker;
      const typeTag = secType === "ETF" ? " *(ETF)*" : "";
      return `| ${h.ticker} | ${nameDisplay}${typeTag} | ${sectorDisplay} | ${h.weight_pct} |`;
    })
    .join("\n");

  const topContribs = [...contrib]
    .sort((a, b) => b.weight_volatility_contribution - a.weight_volatility_contribution)
    .slice(0, 5)
    .map((c, i) =>
      `| ${i + 1} | ${c.ticker} | ${pct(c.weight)} | ${pct(c.annualized_volatility)} | ${pct(c.weight_volatility_contribution)} | ${c.correlation_with_portfolio.toFixed(2)} |`
    )
    .join("\n");

  const stressRows = stress_analysis
    .map((s) => `| ${s.name} | ${s.start} | ${s.end} | ${pct(s.portfolio_cumulative_return)} | ${pct(s.portfolio_max_drawdown)} |`)
    .join("\n");

  const sharpeQual =
    m.sharpe_ratio > 1.5 ? "excellent" :
    m.sharpe_ratio > 1.0 ? "good" :
    m.sharpe_ratio > 0.5 ? "moderate" : "below average";

  const attrSection = result.risk_attribution
    ? "\n---\n\n" + buildAttributionMarkdown(result.risk_attribution)
    : "";

  return `# Portfolio Risk Report

*${today} · Educational and research purposes only*

---

## Portfolio

| Ticker | Name | Sector | Weight |
|--------|------|--------|--------|
${holdingsTable}

Data period: ${m.data_start} to ${m.data_end} (${m.trading_days_used} trading days)

---

## Risk Metrics

| Metric | Value |
|--------|-------|
| Annualised Return | ${pct(m.annualized_return)} |
| Annualised Volatility | ${pct(m.annualized_volatility)} |
| Sharpe Ratio (rf = 0%) | ${m.sharpe_ratio.toFixed(2)} |
| Maximum Drawdown | ${pct(m.max_drawdown)} |
| 1-day VaR 95% | ${pct(m.var_95)} |
| Expected Shortfall 95% | ${pct(m.cvar_95)} |
| 1-day VaR 99% | ${pct(m.var_99)} |
| Expected Shortfall 99% | ${pct(m.cvar_99)} |

The portfolio's Sharpe ratio of **${m.sharpe_ratio.toFixed(2)}** is ${sharpeQual} on a risk-adjusted basis. The maximum drawdown of **${pct(m.max_drawdown)}** represents the worst peak-to-trough decline over the analysis window.

---

## Risk Contributors

| Rank | Ticker | Weight | Volatility | Wt × Vol | Correlation |
|------|--------|--------|------------|----------|-------------|
${topContribs}

---

## Stress Analysis

| Scenario | Start | End | Return | Max Drawdown |
|----------|-------|-----|--------|--------------|
${stressRows}

${attrSection}
---

## Disclaimer

*This report is for educational and research purposes only and does not constitute investment advice. All analysis is backward-looking. Past performance is not indicative of future results.*`;
}

function buildAiMarkdown(ai: AiSummary): string {
  const risks = (ai.key_risks ?? []).map((r) => `- ${r}`).join("\n");
  const attrSection = ai.risk_attribution_takeaway
    ? `\n## Risk Drivers\n${ai.risk_attribution_takeaway}\n`
    : "";
  const factorSection = ai.factor_regression_takeaway
    ? `\n## Factor Regression\n${ai.factor_regression_takeaway}\n`
    : "";
  return `# AI Risk Summary

## Summary
${ai.summary ?? ""}

## Key Risks
${risks}
${attrSection}${factorSection}
## Stress Period
${ai.stress_takeaway ?? ""}

## SEC Evidence
${ai.evidence_takeaway ?? ""}

## Disclaimer
${ai.disclaimer ?? ""}`;
}

// ── Shared styles ─────────────────────────────────────────────────────────────

const cardWrap: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  overflow: "hidden",
};

const cardHeader: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "11px 18px",
  borderBottom: "1px solid var(--border-lt)",
  background: "var(--bg)",
  gap: 10,
};

function borderBtn(style: React.CSSProperties = {}): React.CSSProperties {
  return {
    background: "var(--surface)",
    color: "var(--muted)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    padding: "4px 11px",
    fontSize: 11,
    fontWeight: 500,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.15s",
    whiteSpace: "nowrap" as const,
    ...style,
  };
}

function primaryBtn(style: React.CSSProperties = {}): React.CSSProperties {
  return {
    background: "var(--text)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "4px 12px",
    fontSize: 11,
    fontWeight: 500,
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.15s",
    whiteSpace: "nowrap" as const,
    ...style,
  };
}

const eyebrow: React.CSSProperties = {
  color: "var(--faint)",
  fontSize: 9.5,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  marginBottom: 5,
};

// ── Card 1: Portfolio Risk Report ─────────────────────────────────────────────

function ReportCard({ report }: { report: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(report).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={cardWrap}>
      <div style={cardHeader}>
        <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 500 }}>
          Portfolio Risk Report
        </span>
        <button
          onClick={handleCopy}
          style={borderBtn(copied ? { color: "var(--positive)", borderColor: "var(--border)" } : {})}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div style={{ padding: "18px 22px", maxHeight: 440, overflowY: "auto" }}>
        <div className="prose-report">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// ── Card 2: AI Risk Summary ───────────────────────────────────────────────────

function AiCard({
  aiSummary,
  aiLoading,
  aiError,
  onGenerate,
}: {
  aiSummary: AiSummary | null;
  aiLoading: boolean;
  aiError: string | null;
  onGenerate: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    if (!aiSummary) return;
    navigator.clipboard.writeText(buildAiMarkdown(aiSummary)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // Header right-side button: exactly one, mutually exclusive states
  let headerBtn: React.ReactNode;
  if (aiLoading) {
    headerBtn = (
      <button disabled style={borderBtn({ cursor: "not-allowed", color: "var(--faint)" })}>
        Generating…
      </button>
    );
  } else if (aiSummary) {
    headerBtn = (
      <button
        onClick={handleCopy}
        style={borderBtn(copied ? { color: "var(--positive)" } : {})}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    );
  } else {
    headerBtn = (
      <button onClick={onGenerate} style={primaryBtn()}>
        Generate AI Summary
      </button>
    );
  }

  return (
    <div style={cardWrap}>
      {/* Header */}
      <div style={cardHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 500 }}>
            AI Risk Summary
          </span>
          <span
            style={{
              fontSize: 9.5,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--faint)",
              border: "1px solid var(--border-lt)",
              borderRadius: 3,
              padding: "1px 6px",
            }}
          >
            GPT
          </span>
        </div>
        {headerBtn}
      </div>

      {/* Body */}
      <div style={{ padding: "16px 18px" }}>
        {/* Loading */}
        {aiLoading && (
          <p style={{ color: "var(--faint)", fontSize: 12, lineHeight: 1.6, margin: 0 }}>
            Generating AI summary from computed risk metrics and evidence…
          </p>
        )}

        {/* Error */}
        {!aiLoading && aiError && (
          <p style={{ color: "var(--warning)", fontSize: 12, lineHeight: 1.5, margin: 0 }}>
            {aiError}
          </p>
        )}

        {/* Placeholder — no summary, not loading, no error */}
        {!aiLoading && !aiError && !aiSummary && (
          <p style={{ color: "var(--muted)", fontSize: 12.5, lineHeight: 1.65, margin: 0, maxWidth: 520 }}>
            Portfolio metrics and evidence are ready. Generate an AI summary to create a
            concise research-style explanation of the portfolio&apos;s key risks.
          </p>
        )}

        {/* AI Summary content */}
        {!aiLoading && aiSummary && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {aiSummary.summary && (
              <p style={{ color: "var(--text)", fontSize: 12.5, lineHeight: 1.65, margin: 0 }}>
                {aiSummary.summary}
              </p>
            )}

            {aiSummary.key_risks && aiSummary.key_risks.length > 0 && (
              <div>
                <p style={eyebrow}>Key risks</p>
                <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 5 }}>
                  {aiSummary.key_risks.map((r, i) => (
                    <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <span style={{ color: "var(--negative)", fontSize: 11, marginTop: 2, flexShrink: 0 }}>▸</span>
                      <span style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.55 }}>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {aiSummary.risk_attribution_takeaway && (
              <div>
                <p style={eyebrow}>Risk Drivers</p>
                <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                  {aiSummary.risk_attribution_takeaway}
                </p>
              </div>
            )}

            {aiSummary.factor_regression_takeaway && (
              <div>
                <p style={eyebrow}>Factor Regression</p>
                <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                  {aiSummary.factor_regression_takeaway}
                </p>
              </div>
            )}

            {aiSummary.stress_takeaway && (
              <div>
                <p style={eyebrow}>Stress period</p>
                <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                  {aiSummary.stress_takeaway}
                </p>
              </div>
            )}

            {aiSummary.evidence_takeaway && (
              <div>
                <p style={eyebrow}>SEC evidence</p>
                <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, margin: 0 }}>
                  {aiSummary.evidence_takeaway}
                </p>
              </div>
            )}

            {aiSummary.disclaimer && (
              <p
                style={{
                  color: "var(--faint)",
                  fontSize: 10.5,
                  lineHeight: 1.5,
                  margin: 0,
                  borderTop: "1px solid var(--border-lt)",
                  paddingTop: 10,
                }}
              >
                {aiSummary.disclaimer}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function RiskReportPreview({ result }: { result: AnalyzePortfolioResponse }) {
  const [aiSummary, setAiSummary] = useState<AiSummary | null>(result.ai_summary ?? null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const report = buildMarkdownReport(result);

  async function handleGenerate() {
    setAiLoading(true);
    setAiError(null);
    try {
      const ai = await generateRiskSummary(result);
      setAiSummary(ai);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setAiError(`AI summary could not be generated. Risk metrics are still available. (${msg})`);
    } finally {
      setAiLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Card 1 — deterministic report, always shown */}
      <ReportCard report={report} />

      {/* Card 2 — AI summary, generate on demand */}
      <AiCard
        aiSummary={aiSummary}
        aiLoading={aiLoading}
        aiError={aiError}
        onGenerate={handleGenerate}
      />
    </div>
  );
}

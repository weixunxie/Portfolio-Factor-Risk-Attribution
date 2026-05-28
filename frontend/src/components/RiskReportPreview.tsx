"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AnalyzePortfolioResponse } from "@/lib/api";

function pct(n: number, d = 1) {
  return `${(n * 100).toFixed(d)}%`;
}

function buildReport(result: AnalyzePortfolioResponse): string {
  const { holdings, risk_metrics: m, top_risk_contributors: contrib, stress_analysis } = result;
  const today = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

  const holdingsTable = holdings
    .map((h) => `| ${h.ticker} | ${h.profile.name || "—"} | ${h.profile.sector || "—"} | ${h.weight_pct} |`)
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

---

## Disclaimer

*This report is for educational and research purposes only and does not constitute investment advice. All analysis is backward-looking. Past performance is not indicative of future results.*`;
}

export default function RiskReportPreview({ result }: { result: AnalyzePortfolioResponse }) {
  const report = buildReport(result);
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(report).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 18px",
          borderBottom: "1px solid var(--border-lt)",
          background: "var(--bg)",
        }}
      >
        <div>
          <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 500 }}>Report preview</span>
          <span style={{ color: "var(--faint)", fontSize: 11, marginLeft: 10 }}>
            Copy as Markdown
          </span>
        </div>
        <button
          onClick={handleCopy}
          style={{
            background: copied ? "var(--pos-bg)" : "var(--surface)",
            color: copied ? "var(--positive)" : "var(--muted)",
            border: "1px solid var(--border)",
            borderRadius: 4,
            padding: "5px 12px",
            fontSize: 11.5,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.15s",
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {/* Content */}
      <div style={{ padding: "18px 22px", maxHeight: 460, overflowY: "auto" }}>
        <div className="prose-report">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

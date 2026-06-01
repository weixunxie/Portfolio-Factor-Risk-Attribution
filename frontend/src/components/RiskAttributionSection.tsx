"use client";

import { useState } from "react";
import type {
  RiskAttribution,
  RiskAttributionItem,
  RiskAttributionOverall,
} from "@/lib/api";
import FactorRegressionTable from "@/components/FactorRegressionTable";

// ── helpers ───────────────────────────────────────────────────────────────────

function pct(n: number, d = 1) {
  return `${(n * 100).toFixed(d)}%`;
}

type RiskLevel = "Low" | "Moderate" | "High" | "Unknown";

const LEVEL_STYLES: Record<RiskLevel, { color: string; bg: string; border: string }> = {
  High:    { color: "var(--negative)", bg: "rgba(220,38,38,0.07)",  border: "rgba(220,38,38,0.3)" },
  Moderate:{ color: "var(--warning)",  bg: "rgba(234,179,8,0.07)",  border: "rgba(234,179,8,0.3)" },
  Low:     { color: "var(--positive)", bg: "rgba(34,197,94,0.07)",  border: "rgba(34,197,94,0.3)" },
  Unknown: { color: "var(--faint)",    bg: "var(--bg)",             border: "var(--border-lt)" },
};

const LEVEL_ORDER: Record<RiskLevel, number> = { High: 0, Moderate: 1, Low: 2, Unknown: 3 };

const CARD_TITLES: Record<string, string> = {
  market_risk:        "Market Risk",
  sector_risk:        "Sector Risk",
  style_risk:         "Style / Factor Risk",
  macro_risk:         "Macro Risk",
  concentration_risk: "Concentration Risk",
  tail_risk:          "Tail Risk",
};

const DRIVER_LABELS: Record<string, string> = {
  market_risk:        "Market",
  sector_risk:        "Sector",
  style_risk:         "Style",
  macro_risk:         "Macro",
  concentration_risk: "Concentration",
  tail_risk:          "Tail",
};

const CARD_ORDER: Array<keyof Omit<RiskAttribution, "overall">> = [
  "market_risk", "sector_risk", "concentration_risk", "tail_risk", "style_risk", "macro_risk",
];

// ── Risk level badge ──────────────────────────────────────────────────────────

function RiskBadge({ level, small }: { level: string; small?: boolean }) {
  const s = LEVEL_STYLES[(level as RiskLevel)] ?? LEVEL_STYLES.Unknown;
  return (
    <span
      style={{
        fontSize:        small ? 9 : 9.5,
        fontWeight:      700,
        textTransform:   "uppercase",
        letterSpacing:   "0.08em",
        padding:         small ? "1px 6px" : "2px 8px",
        borderRadius:    3,
        border:          `1px solid ${s.border}`,
        background:      s.bg,
        color:           s.color,
        whiteSpace:      "nowrap",
        flexShrink:      0,
      }}
    >
      {level}
    </span>
  );
}

// ── Chevron ───────────────────────────────────────────────────────────────────

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="11" height="11" viewBox="0 0 11 11" fill="none"
      style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.18s", flexShrink: 0 }}
    >
      <path d="M2.5 4L5.5 7L8.5 4" stroke="var(--faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Compact metric row ────────────────────────────────────────────────────────

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid var(--border-lt)" }}>
      <span style={{ color: "var(--faint)", fontSize: 11 }}>{label}</span>
      <span style={{ color: "var(--text)", fontSize: 11, fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ── Driver Ranking Table ──────────────────────────────────────────────────────

function DriverRankingTable({ attribution }: { attribution: RiskAttribution }) {
  const rows = CARD_ORDER
    .map((key) => ({ key, item: attribution[key] as RiskAttributionItem }))
    .filter((r) => r.item)
    .sort((a, b) => LEVEL_ORDER[a.item.risk_level as RiskLevel] - LEVEL_ORDER[b.item.risk_level as RiskLevel]);

  return (
    <div
      style={{
        background:   "var(--surface)",
        border:       "1px solid var(--border)",
        borderRadius: 6,
        marginBottom: 12,
        overflow:     "hidden",
      }}
    >
      <div style={{ padding: "8px 14px 6px", borderBottom: "1px solid var(--border-lt)" }}>
        <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", margin: 0 }}>
          Risk Driver Ranking
        </p>
      </div>
      <div>
        {rows.map(({ key, item }, i) => (
          <div
            key={key}
            style={{
              display:     "flex",
              alignItems:  "center",
              gap:         10,
              padding:     "6px 14px",
              borderBottom: i < rows.length - 1 ? "1px solid var(--border-lt)" : "none",
            }}
          >
            <span style={{ color: "var(--text)", fontSize: 12, fontWeight: 500, width: 150, flexShrink: 0 }}>
              {CARD_TITLES[key]}
            </span>
            <RiskBadge level={item.risk_level} small />
            {item.short_reason && (
              <span style={{ color: "var(--faint)", fontSize: 11, lineHeight: 1.4, flex: 1 }}>
                {item.short_reason}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sector bar chart ──────────────────────────────────────────────────────────

function SectorBars({ weights }: { weights: Record<string, number> }) {
  const sorted = Object.entries(weights)
    .filter(([, v]) => v > 0.005)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);
  if (!sorted.length) return null;

  return (
    <div style={{ marginTop: 8 }}>
      <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
        Sector Breakdown
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {sorted.map(([sector, weight]) => (
          <div key={sector}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ color: sector === "ETF" || sector === "Unknown" ? "var(--faint)" : "var(--muted)", fontSize: 10.5, fontStyle: sector === "Unknown" ? "italic" : "normal" }}>
                {sector}
              </span>
              <span style={{ color: "var(--text)", fontSize: 10.5, fontWeight: 500 }}>{pct(weight)}</span>
            </div>
            <div style={{ height: 3, background: "var(--border-lt)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{
                height: "100%",
                width:  `${Math.min(weight * 100, 100)}%`,
                background: sector === "ETF" ? "var(--faint)" : sector === "Unknown" ? "var(--border)" : "var(--text)",
                borderRadius: 2,
                opacity: sector === "ETF" || sector === "Unknown" ? 0.5 : 0.65,
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Concentration bars ────────────────────────────────────────────────────────

function ConcentrationBars({ metrics }: { metrics: Record<string, unknown> }) {
  const top1 = metrics.top_1_weight as number | undefined;
  const top3 = metrics.top_3_weight as number | undefined;
  const top5 = metrics.top_5_weight as number | undefined;
  const ticker = metrics.top_1_ticker as string | undefined;
  if (top3 == null) return null;

  const bars = [
    ...(top1 != null && ticker ? [{ label: `${ticker} (top 1)`, value: top1 }] : []),
    ...(top3 != null             ? [{ label: "Top 3 holdings",   value: top3 }] : []),
    ...(top5 != null && top5 !== top3 ? [{ label: "Top 5 holdings", value: top5 }] : []),
  ];

  return (
    <div style={{ marginTop: 8 }}>
      <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
        Concentration
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {bars.map(({ label, value }) => (
          <div key={label}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ color: "var(--muted)", fontSize: 10.5 }}>{label}</span>
              <span style={{ color: "var(--text)", fontSize: 10.5, fontWeight: 500 }}>{pct(value)}</span>
            </div>
            <div style={{ height: 3, background: "var(--border-lt)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${Math.min(value * 100, 100)}%`,
                background: value > 0.7 ? "var(--negative)" : value > 0.5 ? "var(--warning)" : "var(--text)",
                borderRadius: 2, opacity: 0.7,
              }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Card metric block (per-type) ──────────────────────────────────────────────

function CardMetrics({ id, metrics }: { id: string; metrics: Record<string, unknown> }) {
  if (!metrics || Object.keys(metrics).length === 0) return null;

  if (id === "market_risk") return (
    <div style={{ marginTop: 8 }}>
      {metrics.portfolio_beta   != null && <MetricRow label="Portfolio Beta (vs SPY)" value={String(metrics.portfolio_beta)} />}
      {metrics.spy_correlation  != null && <MetricRow label="SPY Correlation"          value={String(metrics.spy_correlation)} />}
      {metrics.r_squared        != null && <MetricRow label="R² (market explains)"     value={pct(metrics.r_squared as number)} />}
    </div>
  );

  if (id === "concentration_risk") return <ConcentrationBars metrics={metrics} />;

  if (id === "sector_risk") {
    const sw = metrics.sector_weights as Record<string, number> | undefined;
    return sw ? <SectorBars weights={sw} /> : null;
  }

  if (id === "tail_risk") return (
    <div style={{ marginTop: 8 }}>
      {metrics.var_95       != null && <MetricRow label="VaR 95% (1-day)"           value={pct(metrics.var_95   as number)} />}
      {metrics.cvar_95      != null && <MetricRow label="CVaR 95% (Exp. Shortfall)" value={pct(metrics.cvar_95  as number)} />}
      {metrics.max_drawdown != null && <MetricRow label="Max Drawdown"               value={pct(metrics.max_drawdown as number)} />}
      {metrics.cvar_var_ratio != null && <MetricRow label="CVaR / VaR Ratio"         value={String((metrics.cvar_var_ratio as number).toFixed(2))} />}
    </div>
  );

  if (id === "macro_risk") {
    const bc = metrics.benchmark_correlations as Record<string, number> | undefined;
    if (!bc) return null;
    return (
      <div style={{ marginTop: 8 }}>
        {Object.entries(bc).map(([ticker, corr]) => (
          <MetricRow key={ticker} label={`${ticker} Correlation`} value={corr.toFixed(2)} />
        ))}
      </div>
    );
  }

  if (id === "style_risk") {
    const tags  = metrics.style_tags as string[] | undefined;
    const vol   = metrics.weighted_avg_volatility as number | undefined;
    const gtw   = metrics.growth_tech_weight as number | undefined;
    return (
      <div style={{ marginTop: 8 }}>
        {tags && tags.length > 0 && (
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 7 }}>
            {tags.map((t) => (
              <span key={t} style={{ fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 3, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--muted)" }}>
                {t}
              </span>
            ))}
          </div>
        )}
        {vol != null && <MetricRow label="Wtd. Avg. Volatility"   value={pct(vol)} />}
        {gtw != null && gtw > 0 && <MetricRow label="Growth / Tech Exposure" value={pct(gtw)} />}
      </div>
    );
  }

  return null;
}

// ── Individual risk driver card ───────────────────────────────────────────────

function RiskDriverCard({ id, item, defaultOpen }: {
  id: string;
  item: RiskAttributionItem;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const metrics = item.metrics as Record<string, unknown>;

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 6, background: "var(--surface)", overflow: "hidden" }}>
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "9px 12px", background: "none", border: "none",
          cursor: "pointer", fontFamily: "inherit", textAlign: "left",
        }}
      >
        <span style={{ color: "var(--text)", fontSize: 12, fontWeight: 500, flexGrow: 1, lineHeight: 1.3 }}>
          {CARD_TITLES[id]}
        </span>
        <RiskBadge level={item.risk_level} />
        <Chevron open={open} />
      </button>

      {/* Collapsed: one-liner */}
      {!open && item.summary && (
        <p style={{ margin: 0, padding: "0 12px 9px", color: "var(--muted)", fontSize: 11.5, lineHeight: 1.5, borderTop: "1px solid var(--border-lt)", paddingTop: 7 }}>
          {item.summary.split(".")[0] + "."}
        </p>
      )}

      {/* Expanded */}
      {open && (
        <div style={{ padding: "8px 12px 12px", borderTop: "1px solid var(--border-lt)" }}>
          {item.summary && (
            <p style={{ color: "var(--muted)", fontSize: 11.5, lineHeight: 1.6, margin: 0, marginBottom: 6 }}>
              {item.summary}
            </p>
          )}

          <CardMetrics id={id} metrics={metrics} />

          {item.drivers && item.drivers.length > 0 && (
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 3, marginTop: 8 }}>
              {item.drivers.map((d, i) => (
                <li key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                  <span style={{ color: "var(--faint)", fontSize: 10, marginTop: 3, flexShrink: 0 }}>▸</span>
                  <span style={{ color: "var(--faint)", fontSize: 11, lineHeight: 1.5 }}>{d}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

// ── Overall risk banner ───────────────────────────────────────────────────────

function OverallBanner({ overall }: { overall: RiskAttributionOverall }) {
  const s = LEVEL_STYLES[(overall.overall_risk_level as RiskLevel)] ?? LEVEL_STYLES.Unknown;

  return (
    <div style={{
      background: s.bg, border: `1px solid ${s.border}`, borderRadius: 6,
      padding: "10px 14px", marginBottom: 10,
      display: "flex", alignItems: "flex-start", gap: 14, flexWrap: "wrap",
    }}>
      <div style={{ flexShrink: 0 }}>
        <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 2 }}>
          Overall Risk
        </p>
        <span style={{ fontSize: 16, fontWeight: 700, color: s.color }}>
          {overall.overall_risk_level}
        </span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {(overall.dominant_drivers.length > 0 || overall.secondary_drivers.length > 0) && (
          <>
            <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>
              {overall.dominant_drivers.length > 0 ? "Primary Drivers" : "Moderate Drivers"}
            </p>
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: overall.summary ? 7 : 0 }}>
              {overall.dominant_drivers.map((d) => (
                <span key={d} style={{ fontSize: 10.5, fontWeight: 600, padding: "2px 8px", borderRadius: 3, background: "rgba(220,38,38,0.1)", border: "1px solid rgba(220,38,38,0.3)", color: "var(--negative)" }}>
                  {DRIVER_LABELS[d] ?? d}
                </span>
              ))}
              {overall.dominant_drivers.length > 0 && overall.secondary_drivers.length > 0 && (
                <span style={{ color: "var(--faint)", fontSize: 10.5, alignSelf: "center" }}>·</span>
              )}
              {overall.dominant_drivers.length > 0 && overall.secondary_drivers.map((d) => (
                <span key={d} style={{ fontSize: 10.5, fontWeight: 500, padding: "2px 8px", borderRadius: 3, background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.25)", color: "var(--warning)" }}>
                  {DRIVER_LABELS[d] ?? d}
                </span>
              ))}
              {overall.dominant_drivers.length === 0 && overall.secondary_drivers.map((d) => (
                <span key={d} style={{ fontSize: 10.5, fontWeight: 600, padding: "2px 8px", borderRadius: 3, background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.3)", color: "var(--warning)" }}>
                  {DRIVER_LABELS[d] ?? d}
                </span>
              ))}
            </div>
          </>
        )}
        {overall.summary && (
          <p style={{ color: "var(--muted)", fontSize: 11.5, lineHeight: 1.55, margin: 0 }}>
            {overall.summary}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function RiskAttributionSection({ attribution }: { attribution: RiskAttribution }) {
  return (
    <div>
      {attribution.overall && <OverallBanner overall={attribution.overall} />}
      <DriverRankingTable attribution={attribution} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
        {CARD_ORDER.map((key) => {
          const item = attribution[key] as RiskAttributionItem | undefined;
          if (!item) return null;
          return (
            <RiskDriverCard
              key={key}
              id={key}
              item={item}
              defaultOpen={item.risk_level === "High"}
            />
          );
        })}
      </div>

      {/* Proxy Factor Exposure Regression sub-section */}
      {attribution.factor_regression && (
        <div style={{ marginTop: 18 }}>
          <div style={{ marginBottom: 10 }}>
            <p style={{ color: "var(--text)", fontSize: 13, fontWeight: 600, margin: 0 }}>
              Proxy Factor Exposure Regression
            </p>
            <p style={{ color: "var(--faint)", fontSize: 11, marginTop: 3, marginBottom: 0 }}>
              OLS on market proxy ETF returns (SPY, QQQ, TLT) ·
              proxy-based, not formal factor modeling ·
              volatility-shock proxy (VIX) planned
            </p>
          </div>
          <FactorRegressionTable data={attribution.factor_regression} />
        </div>
      )}
    </div>
  );
}

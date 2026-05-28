import type { RiskContributor } from "@/lib/api";

function pct(n: number, d = 1) {
  return isFinite(n) ? `${(n * 100).toFixed(d)}%` : "—";
}

function corrDesc(c: number) {
  if (c >= 0.8) return "very high";
  if (c >= 0.6) return "high";
  if (c >= 0.4) return "mod";
  return "low";
}

export default function RiskContributorCards({
  contributors,
}: {
  contributors: RiskContributor[];
}) {
  const sorted = [...contributors].sort(
    (a, b) => b.weight_volatility_contribution - a.weight_volatility_contribution
  );

  const hdr: React.CSSProperties = {
    color: "var(--faint)",
    fontSize: 9.5,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.07em",
  };

  return (
    /* overflow-x: auto keeps the table usable in narrow flex columns */
    <div style={{ overflowX: "auto" }}>
      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          overflow: "hidden",
          minWidth: 520,
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "26px 56px 54px 68px 68px 84px 88px",
            gap: 0,
            padding: "9px 16px",
            borderBottom: "1px solid var(--border-lt)",
            background: "var(--bg)",
          }}
        >
          <span style={hdr}>#</span>
          <span style={hdr}>Ticker</span>
          <span style={{ ...hdr, textAlign: "right" }}>Weight</span>
          <span style={{ ...hdr, textAlign: "right" }}>Vol.</span>
          <span style={{ ...hdr, textAlign: "right" }}>Wt×Vol</span>
          <span style={{ ...hdr, textAlign: "right" }}>Corr.</span>
          <span style={{ ...hdr, textAlign: "right" }}>Worst 5d</span>
        </div>

        {/* Rows */}
        {sorted.map((c, i) => {
          const worst = c.average_return_on_worst_5_portfolio_days;
          const worstColor =
            worst < -0.025 ? "var(--negative)" : worst < 0 ? "var(--warning)" : "var(--text)";

          return (
            <div
              key={c.ticker}
              style={{
                display: "grid",
                gridTemplateColumns: "26px 56px 54px 68px 68px 84px 88px",
                gap: 0,
                padding: "10px 16px",
                borderBottom: i < sorted.length - 1 ? "1px solid var(--border-lt)" : "none",
                alignItems: "center",
              }}
            >
              <span style={{ color: "var(--faint)", fontSize: 11 }}>{i + 1}</span>

              <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 600 }}>
                {c.ticker}
              </span>

              <span style={{ color: "var(--muted)", fontSize: 12, textAlign: "right" }}>
                {pct(c.weight)}
              </span>

              <span style={{ color: "var(--muted)", fontSize: 12, textAlign: "right" }}>
                {pct(c.annualized_volatility)}
              </span>

              <span
                style={{
                  color: "var(--text)",
                  fontSize: 12,
                  fontWeight: 500,
                  textAlign: "right",
                }}
              >
                {pct(c.weight_volatility_contribution)}
              </span>

              <span style={{ color: "var(--muted)", fontSize: 12, textAlign: "right" }}>
                {c.correlation_with_portfolio.toFixed(2)}{" "}
                <span style={{ color: "var(--faint)", fontSize: 10 }}>
                  {corrDesc(c.correlation_with_portfolio)}
                </span>
              </span>

              <span
                style={{
                  color: worstColor,
                  fontSize: 12,
                  fontWeight: 500,
                  textAlign: "right",
                }}
              >
                {pct(worst)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

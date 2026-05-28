import type { StressPeriodResult } from "@/lib/api";

function pct(n: number, d = 1) {
  return `${(n * 100).toFixed(d)}%`;
}

function safeContribution(n: number | null | undefined): string | null {
  if (n == null || !isFinite(n)) return null;
  return pct(n);
}

export default function StressScenarioCards({ scenarios }: { scenarios: StressPeriodResult[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
      {scenarios.map((s) => {
        const retNeg = s.portfolio_cumulative_return < 0;
        const retColor = retNeg ? "var(--negative)" : "var(--positive)";

        return (
          <div
            key={s.name}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 7,
              padding: "16px 18px",
            }}
          >
            {/* Header */}
            <div style={{ marginBottom: 12 }}>
              <h4 style={{ color: "var(--text)", fontSize: 13, fontWeight: 600, marginBottom: 3 }}>
                {s.name}
              </h4>
              <p style={{ color: "var(--faint)", fontSize: 11 }}>
                {s.start} → {s.end}
              </p>
            </div>

            {/* Key numbers */}
            <div style={{ display: "flex", gap: 20, marginBottom: 12 }}>
              <div>
                <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                  Return
                </p>
                <p style={{ color: retColor, fontSize: 20, fontWeight: 600, lineHeight: 1, letterSpacing: "-0.01em" }}>
                  {pct(s.portfolio_cumulative_return)}
                </p>
              </div>
              <div>
                <p style={{ color: "var(--faint)", fontSize: 9.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>
                  Max Drawdown
                </p>
                <p style={{ color: "var(--negative)", fontSize: 20, fontWeight: 600, lineHeight: 1, letterSpacing: "-0.01em" }}>
                  {pct(s.portfolio_max_drawdown)}
                </p>
              </div>
            </div>

            {/* Worst contributors */}
            {s.worst_contributors.length > 0 && (
              <div>
                <p style={{ color: "var(--faint)", fontSize: 10, fontWeight: 500, marginBottom: 5 }}>
                  Worst contributors
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                  {s.worst_contributors.slice(0, 4).map((w) => {
                    const contrib = safeContribution(w.contribution);
                    return (
                      <span
                        key={w.ticker}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          background: "var(--bg)",
                          border: "1px solid var(--border)",
                          borderRadius: 4,
                          padding: "2px 7px",
                        }}
                      >
                        <span style={{ color: "var(--text)", fontSize: 11, fontWeight: 500 }}>{w.ticker}</span>
                        {contrib && (
                          <span style={{ color: "var(--negative)", fontSize: 10 }}>{contrib}</span>
                        )}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

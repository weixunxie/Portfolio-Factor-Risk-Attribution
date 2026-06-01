import type { EnrichedHolding } from "@/lib/api";

export default function PortfolioComposition({ holdings }: { holdings: EnrichedHolding[] }) {
  const maxWeight = Math.max(...holdings.map((h) => h.weight));

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 7,
        padding: "16px 18px",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {holdings.map((h) => (
          <div key={h.ticker}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
                <span style={{ color: "var(--text)", fontSize: 13, fontWeight: 600 }}>
                  {h.ticker}
                </span>
                {h.profile.name && (
                  <span style={{ color: "var(--muted)", fontSize: 11.5 }}>
                    {h.profile.name}
                  </span>
                )}
              </div>
              <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 500 }}>
                {h.weight_pct}
              </span>
            </div>

            {/* Weight bar */}
            <div style={{ height: 3, background: "var(--bg)", borderRadius: 2, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${(h.weight / maxWeight) * 100}%`,
                  background: "#4B5563",
                  borderRadius: 2,
                }}
              />
            </div>

            {(h.profile.sector || h.profile.security_type) && (
              <p style={{ color: "var(--faint)", fontSize: 11, marginTop: 3 }}>
                {h.profile.sector || "Unknown"}
                {h.profile.industry ? ` · ${h.profile.industry}` : ""}
                {h.profile.security_type === "ETF" ? " · ETF" : ""}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

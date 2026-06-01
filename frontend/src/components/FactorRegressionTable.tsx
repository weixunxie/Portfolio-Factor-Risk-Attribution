"use client";

import type { FactorRegression, FactorEntry } from "@/lib/api";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtBeta(v: number) {
  return v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3);
}

function fmtPValue(p: number) {
  if (p < 0.001) return "<0.001";
  if (p < 0.01)  return p.toFixed(3);
  return p.toFixed(3);
}

function fmtTStat(t: number) {
  return t >= 0 ? `+${t.toFixed(2)}` : t.toFixed(2);
}

// ── row component ─────────────────────────────────────────────────────────────

function FactorRow({ f }: { f: FactorEntry }) {
  const sigColor  = f.significant ? "var(--text)"    : "var(--faint)";
  const betaColor = f.significant
    ? f.beta > 0 ? "var(--text)" : "var(--warning)"
    : "var(--faint)";

  return (
    <tr>
      {/* Factor label */}
      <td style={{ padding: "6px 12px 6px 14px", whiteSpace: "nowrap" }}>
        <span style={{ color: "var(--text)", fontSize: 12, fontWeight: 500 }}>
          {f.label}
        </span>
        <span style={{ color: "var(--faint)", fontSize: 10.5, marginLeft: 5 }}>
          ({f.ticker})
        </span>
      </td>

      {/* Beta */}
      <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: betaColor, fontSize: 12, fontWeight: f.significant ? 600 : 400 }}>
          {fmtBeta(f.beta)}
        </span>
      </td>

      {/* t-stat */}
      <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: "var(--muted)", fontSize: 11.5 }}>
          {fmtTStat(f.t_stat)}
        </span>
      </td>

      {/* p-value */}
      <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        <span
          style={{
            color:      f.significant ? "var(--positive)" : "var(--faint)",
            fontSize:   11.5,
            fontWeight: f.significant ? 600 : 400,
          }}
        >
          {fmtPValue(f.p_value)}
        </span>
      </td>

      {/* Interpretation */}
      <td style={{ padding: "6px 14px 6px 12px" }}>
        <span style={{ color: sigColor, fontSize: 11.5, lineHeight: 1.4 }}>
          {f.interpretation}
        </span>
        {f.significant && (
          <span
            style={{
              marginLeft: 6,
              fontSize: 9,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: "var(--positive)",
              border: "1px solid rgba(34,197,94,0.35)",
              borderRadius: 3,
              padding: "1px 5px",
              background: "rgba(34,197,94,0.06)",
            }}
          >
            sig
          </span>
        )}
      </td>
    </tr>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function FactorRegressionTable({
  data,
}: {
  data: FactorRegression;
}) {
  if (!data.available) {
    const reason = data.reason || "Proxy factor regression data not available.";
    return (
      <div
        style={{
          background:   "var(--surface)",
          border:       "1px solid var(--border)",
          borderRadius: 6,
          padding:      "14px 16px",
        }}
      >
        <p style={{ color: "var(--faint)", fontSize: 11.5, fontStyle: "italic", margin: 0 }}>
          {reason}
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        background:   "var(--surface)",
        border:       "1px solid var(--border)",
        borderRadius: 6,
        overflow:     "hidden",
      }}
    >
      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width:           "100%",
            borderCollapse:  "collapse",
            fontSize:        12,
          }}
        >
          <thead>
            <tr style={{ background: "var(--bg)", borderBottom: "1px solid var(--border-lt)" }}>
              {["Factor", "Beta", "t-stat", "p-value", "Interpretation"].map((h, i) => (
                <th
                  key={h}
                  style={{
                    padding:   "6px 12px",
                    textAlign:  i >= 1 && i <= 3 ? "right" : "left",
                    paddingLeft:  i === 0 ? 14 : undefined,
                    paddingRight: i === 4 ? 14 : undefined,
                    color:      "var(--faint)",
                    fontSize:   9.5,
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.factors.map((f, i) => (
              <tr
                key={f.ticker}
                style={{
                  borderBottom: i < data.factors.length - 1 ? "1px solid var(--border-lt)" : "none",
                }}
              >
                <td style={{ padding: "6px 12px 6px 14px", whiteSpace: "nowrap" }}>
                  <span style={{ color: "var(--text)", fontSize: 12, fontWeight: 500 }}>
                    {f.label}
                  </span>
                  <span style={{ color: "var(--faint)", fontSize: 10.5, marginLeft: 5 }}>
                    ({f.ticker})
                  </span>
                </td>
                <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  <span
                    style={{
                      color:      f.significant ? (f.beta > 0 ? "var(--text)" : "var(--warning)") : "var(--faint)",
                      fontSize:   12,
                      fontWeight: f.significant ? 600 : 400,
                    }}
                  >
                    {fmtBeta(f.beta)}
                  </span>
                </td>
                <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  <span style={{ color: "var(--muted)", fontSize: 11.5 }}>
                    {fmtTStat(f.t_stat)}
                  </span>
                </td>
                <td style={{ padding: "6px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  <span
                    style={{
                      color:      f.significant ? "var(--positive)" : "var(--faint)",
                      fontSize:   11.5,
                      fontWeight: f.significant ? 600 : 400,
                    }}
                  >
                    {fmtPValue(f.p_value)}
                  </span>
                </td>
                <td style={{ padding: "6px 14px 6px 12px" }}>
                  <span style={{ color: f.significant ? "var(--text)" : "var(--faint)", fontSize: 11.5 }}>
                    {f.interpretation}
                  </span>
                  {f.significant && (
                    <span
                      style={{
                        marginLeft: 6, fontSize: 9, fontWeight: 700,
                        textTransform: "uppercase", letterSpacing: "0.06em",
                        color: "var(--positive)",
                        border: "1px solid rgba(34,197,94,0.35)",
                        borderRadius: 3, padding: "1px 5px",
                        background: "rgba(34,197,94,0.06)",
                      }}
                    >
                      sig
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer stats */}
      <div
        style={{
          borderTop:  "1px solid var(--border-lt)",
          padding:    "7px 14px",
          display:    "flex",
          alignItems: "center",
          gap:        18,
          flexWrap:   "wrap",
          background: "var(--bg)",
        }}
      >
        {data.r_squared != null && (
          <span style={{ color: "var(--muted)", fontSize: 11 }}>
            R² = <strong style={{ color: "var(--text)" }}>{(data.r_squared * 100).toFixed(1)}%</strong>
          </span>
        )}
        {data.adj_r_squared != null && (
          <span style={{ color: "var(--muted)", fontSize: 11 }}>
            Adj. R² = <strong style={{ color: "var(--text)" }}>{(data.adj_r_squared * 100).toFixed(1)}%</strong>
          </span>
        )}
        {data.n_obs > 0 && (
          <span style={{ color: "var(--muted)", fontSize: 11 }}>
            N = <strong style={{ color: "var(--text)" }}>{data.n_obs.toLocaleString()}</strong>
          </span>
        )}
        {data.condition_number != null && data.condition_number > 30 && (
          <span
            style={{
              color: "var(--warning)", fontSize: 10.5,
              border: "1px solid rgba(234,179,8,0.3)", borderRadius: 3,
              padding: "1px 6px", background: "rgba(234,179,8,0.06)",
            }}
          >
            ⚠ high inter-factor correlation
          </span>
        )}
      </div>

      {/* Warnings */}
      {data.warnings && data.warnings.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border-lt)", padding: "6px 14px" }}>
          {data.warnings.map((w, i) => (
            <p key={i} style={{ color: "var(--warning)", fontSize: 11, lineHeight: 1.5, margin: "2px 0" }}>
              {w}
            </p>
          ))}
        </div>
      )}

      {/* Model note / disclaimer */}
      {data.model_note && (
        <div style={{ borderTop: "1px solid var(--border-lt)", padding: "6px 14px" }}>
          <p style={{ color: "var(--faint)", fontSize: 10.5, lineHeight: 1.5, margin: 0 }}>
            {data.model_note}
          </p>
        </div>
      )}
    </div>
  );
}

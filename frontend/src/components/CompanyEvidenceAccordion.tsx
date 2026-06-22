"use client";

import { useEffect, useState } from "react";
import { fetchEvidenceLive, type RiskEvidenceEntry, type RiskEvidenceHit } from "@/lib/api";

function isHitArray(e: RiskEvidenceEntry): e is RiskEvidenceHit[] {
  return Array.isArray(e);
}

function isPreparing(e: RiskEvidenceEntry): boolean {
  return !isHitArray(e) && /preparing/i.test((e as { message: string }).message ?? "");
}

function TickerPanel({ ticker, entry }: { ticker: string; entry: RiskEvidenceEntry }) {
  const [open, setOpen] = useState(false);
  const hits = isHitArray(entry) ? entry : null;
  const noData = !hits || hits.length === 0;
  const message = !hits ? (entry as { message: string }).message : null;

  const preparing = isPreparing(entry);
  const summary = hits && hits.length > 0
    ? `${hits.length} excerpt${hits.length !== 1 ? "s" : ""}`
    : (preparing ? "⏳ " : "") + (message ?? "No results");

  return (
    <div
      style={{
        borderBottom: "1px solid var(--border-lt)",
      }}
    >
      <button
        onClick={() => !noData && setOpen((p) => !p)}
        style={{
          width: "100%",
          background: "none",
          border: "none",
          cursor: noData ? "default" : "pointer",
          padding: "11px 0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontFamily: "inherit",
          textAlign: "left",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "var(--text)", fontSize: 12.5, fontWeight: 600 }}>{ticker}</span>
          <span style={{ color: "var(--faint)", fontSize: 11.5 }}>{summary}</span>
        </div>
        {!noData && (
          <span
            style={{
              color: "var(--faint)",
              fontSize: 10,
              display: "inline-block",
              transform: open ? "rotate(90deg)" : "none",
              transition: "transform 0.18s",
            }}
          >
            ▶
          </span>
        )}
      </button>

      {open && hits && hits.length > 0 && (
        <div style={{ paddingBottom: 12 }}>
          {hits.map((hit, i) => (
            <div
              key={hit.chunk_id}
              style={{
                background: "var(--bg)",
                borderRadius: 5,
                padding: "10px 12px",
                marginBottom: i < hits.length - 1 ? 7 : 0,
              }}
            >
              <div style={{ display: "flex", gap: 6, marginBottom: 7, flexWrap: "wrap" }}>
                <span style={{ color: "var(--faint)", fontSize: 10 }}>
                  Score {hit.score.toFixed(3)}
                </span>
                {hit.filing_date && (
                  <span style={{ color: "var(--faint)", fontSize: 10 }}>· {hit.filing_date}</span>
                )}
                <span style={{ color: "var(--faint)", fontSize: 10 }}>· {hit.source_type}</span>
              </div>
              <p style={{ color: "var(--text)", fontSize: 12, lineHeight: 1.7 }}>
                {hit.text.length > 420 ? hit.text.slice(0, 420) + "…" : hit.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CompanyEvidenceAccordion({
  evidence,
}: {
  evidence: Record<string, RiskEvidenceEntry>;
}) {
  const [live, setLive] = useState(evidence);

  // Reset whenever a new analysis arrives.
  useEffect(() => {
    setLive(evidence);
  }, [evidence]);

  // While any ticker is still "preparing" (background ingestion running), poll
  // the evidence endpoint and refresh just those entries in place — no need to
  // re-run the whole analysis. The dependency is the sorted set of preparing
  // tickers, so the interval is rebuilt only when that set actually changes and
  // stops once every ticker has resolved.
  const preparingKey = Object.entries(live)
    .filter(([, e]) => isPreparing(e))
    .map(([t]) => t)
    .sort()
    .join(",");

  useEffect(() => {
    if (!preparingKey) return;
    const tickers = preparingKey.split(",");
    const startedAt = Date.now();
    const id = setInterval(async () => {
      if (Date.now() - startedAt > 5 * 60 * 1000) {
        clearInterval(id);
        return;
      }
      try {
        const res = await fetchEvidenceLive(tickers);
        setLive((prev) => ({ ...prev, ...res.company_risk_evidence }));
      } catch {
        /* transient — keep polling */
      }
    }, 15000);
    return () => clearInterval(id);
  }, [preparingKey]);

  const tickers = Object.keys(live);

  if (tickers.length === 0) {
    return (
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        No evidence available. Ingest 10-K filings via the API to populate.
      </p>
    );
  }

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 7,
        padding: "0 18px",
      }}
    >
      {tickers.map((ticker) => (
        <TickerPanel key={ticker} ticker={ticker} entry={live[ticker]} />
      ))}
    </div>
  );
}

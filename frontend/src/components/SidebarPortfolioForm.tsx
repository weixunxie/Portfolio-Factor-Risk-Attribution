"use client";

import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import type { HoldingInput, InputMode } from "@/lib/api";

export interface PortfolioFormHandle {
  focusFirstInput: () => void;
}

interface HoldingRow {
  ticker: string;
  value: string; // semantics depend on active mode
}

type AnalyzeOpts = {
  input_mode?: InputMode;
  total_portfolio_value?: number;
  treat_unallocated_as_cash?: boolean;
};

const SAMPLE_10: HoldingRow[] = [
  { ticker: "AAPL",  value: "15" },
  { ticker: "MSFT",  value: "15" },
  { ticker: "NVDA",  value: "20" },
  { ticker: "GOOGL", value: "10" },
  { ticker: "AMZN",  value: "10" },
  { ticker: "META",  value: "10" },
  { ticker: "TSLA",  value: "10" },
  { ticker: "SPY",   value: "5"  },
  { ticker: "QQQ",   value: "3"  },
  { ticker: "TLT",   value: "2"  },
];

const MODE_LABELS: Record<InputMode, string> = {
  weights: "Weight %",
  amounts: "Dollar $",
  shares:  "Shares",
};

const MODE_PLACEHOLDER: Record<InputMode, string> = {
  weights: "0",
  amounts: "0.00",
  shares:  "0",
};

const MODE_COL_HEADER: Record<InputMode, string> = {
  weights: "Wt %",
  amounts: "Amount $",
  shares:  "Shares",
};

// ── tiny helpers ──────────────────────────────────────────────────────────────

function fmtUSD(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtPct(frac: number) {
  return `${(frac * 100).toFixed(1)}%`;
}

// ── Component ─────────────────────────────────────────────────────────────────

const SidebarPortfolioForm = forwardRef<
  PortfolioFormHandle,
  {
    onAnalyze: (h: HoldingInput[], opts?: AnalyzeOpts) => void;
    isLoading: boolean;
    onReset?: () => void;
  }
>(function SidebarPortfolioForm({ onAnalyze, isLoading, onReset }, ref) {
  const firstInputRef = useRef<HTMLInputElement>(null);

  const [mode, setMode]           = useState<InputMode>("weights");
  const [rows, setRows]           = useState<HoldingRow[]>([{ ticker: "", value: "" }]);
  const [totalValue, setTotalValue] = useState("");
  const [treatCash, setTreatCash]   = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [sampleLoaded, setSampleLoaded] = useState(false);

  useImperativeHandle(ref, () => ({
    focusFirstInput: () => firstInputRef.current?.focus(),
  }));

  // ── derived state ──────────────────────────────────────────────────────────

  const validRows = rows.filter((r) => r.ticker.trim() && parseFloat(r.value) > 0);
  const hasContent = validRows.length > 0;

  // For weights mode — check sum
  const weightSum = validRows.reduce((s, r) => s + (parseFloat(r.value) || 0), 0);
  const sumOk = mode === "weights" && hasContent && Math.abs(weightSum - 100) < 5.1;

  // For amounts mode — preview weights
  const totalEntered = validRows.reduce((s, r) => s + (parseFloat(r.value) || 0), 0);
  const tvNum = parseFloat(totalValue);
  const effectiveTotal =
    mode === "amounts" && totalValue && tvNum > 0 ? tvNum : totalEntered;

  const previewWeights: Record<string, number> =
    mode === "amounts" && effectiveTotal > 0
      ? Object.fromEntries(
          validRows.map((r) => [r.ticker, (parseFloat(r.value) || 0) / effectiveTotal])
        )
      : {};

  const unallocatedAmt =
    mode === "amounts" && totalValue && tvNum > 0 && tvNum > totalEntered
      ? tvNum - totalEntered
      : 0;

  // ── row operations ─────────────────────────────────────────────────────────

  function update(i: number, field: keyof HoldingRow, raw: string) {
    setRows((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], [field]: field === "ticker" ? raw.toUpperCase() : raw };
      return next;
    });
    setSampleLoaded(false);
    setError(null);
  }

  function addRow() {
    setRows((p) => [...p, { ticker: "", value: "" }]);
  }

  function removeRow(i: number) {
    if (rows.length === 1) { setRows([{ ticker: "", value: "" }]); return; }
    setRows((p) => p.filter((_, idx) => idx !== i));
  }

  // ── mode switch ────────────────────────────────────────────────────────────

  function switchMode(m: InputMode) {
    if (m === mode) return;
    setMode(m);
    // Clear values when switching modes to avoid semantic confusion
    setRows((prev) => prev.map((r) => ({ ticker: r.ticker, value: "" })));
    setTotalValue("");
    setTreatCash(false);
    setError(null);
    setSampleLoaded(false);
  }

  // ── submit ─────────────────────────────────────────────────────────────────

  function submit() {
    if (!validRows.length) { setError("Enter at least one holding."); return; }

    if (mode === "weights") {
      const sum = validRows.reduce((s, r) => s + (parseFloat(r.value) || 0), 0);
      if (Math.abs(sum - 100) > 5 && Math.abs(sum - 1) > 0.05) {
        setError(`Weights sum to ${sum.toFixed(1)}% — adjust to ≈ 100%.`);
        return;
      }
      setError(null);
      onAnalyze(
        validRows.map((r) => ({ ticker: r.ticker.trim(), weight: parseFloat(r.value) })),
        { input_mode: "weights" }
      );
    } else if (mode === "amounts") {
      for (const r of validRows) {
        if (parseFloat(r.value) <= 0) {
          setError(`Amount for ${r.ticker} must be positive.`);
          return;
        }
      }
      if (totalValue && tvNum > 0 && tvNum < totalEntered - 0.01) {
        setError(`Total value ($${tvNum.toLocaleString()}) is less than sum of amounts ($${totalEntered.toLocaleString()}).`);
        return;
      }
      setError(null);
      onAnalyze(
        validRows.map((r) => ({ ticker: r.ticker.trim(), amount: parseFloat(r.value) })),
        {
          input_mode: "amounts",
          total_portfolio_value: totalValue && tvNum > 0 ? tvNum : undefined,
          treat_unallocated_as_cash: unallocatedAmt > 0 ? treatCash : undefined,
        }
      );
    } else {
      // shares
      for (const r of validRows) {
        if (parseFloat(r.value) <= 0) {
          setError(`Share count for ${r.ticker} must be positive.`);
          return;
        }
      }
      setError(null);
      onAnalyze(
        validRows.map((r) => ({ ticker: r.ticker.trim(), shares: parseFloat(r.value) })),
        { input_mode: "shares" }
      );
    }
  }

  // ── sample / reset ─────────────────────────────────────────────────────────

  function loadSample() {
    switchMode("weights");
    // Re-set rows to sample after mode switch (switchMode already cleared them)
    setRows(SAMPLE_10);
    setError(null);
    setSampleLoaded(true);
  }

  function resetPortfolio() {
    setRows([{ ticker: "", value: "" }]);
    setMode("weights");
    setTotalValue("");
    setTreatCash(false);
    setError(null);
    setSampleLoaded(false);
    onReset?.();
  }

  // ── styles ─────────────────────────────────────────────────────────────────

  const tabBtn = (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: "5px 0",
    fontSize: 10.5,
    fontWeight: active ? 600 : 400,
    fontFamily: "inherit",
    cursor: "pointer",
    border: "none",
    borderRadius: 4,
    background: active ? "var(--text)" : "transparent",
    color: active ? "#fff" : "var(--muted)",
    transition: "background 0.12s, color 0.12s",
  });

  const labelStyle: React.CSSProperties = {
    color: "var(--faint)",
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  };

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div>

      {/* ── Mode selector ── */}
      <div style={{ marginBottom: 14 }}>
        <p style={{ ...labelStyle, marginBottom: 6 }}>Input mode</p>
        <div
          style={{
            display: "flex",
            gap: 2,
            background: "var(--bg)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: 2,
          }}
        >
          {(["weights", "amounts", "shares"] as InputMode[]).map((m) => (
            <button key={m} style={tabBtn(mode === m)} onClick={() => switchMode(m)} disabled={isLoading}>
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* ── Shares mode hint ── */}
      {mode === "shares" && (
        <p style={{ fontSize: 10.5, color: "var(--faint)", marginBottom: 10, lineHeight: 1.5 }}>
          Weights are calculated from market prices at analysis time.
        </p>
      )}

      {/* ── Column headers ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: mode === "amounts" && hasContent ? "1fr 72px 52px 20px" : "1fr 72px 20px",
          gap: 6,
          marginBottom: 6,
        }}
      >
        <span style={labelStyle}>Ticker</span>
        <span style={{ ...labelStyle, textAlign: "right" }}>{MODE_COL_HEADER[mode]}</span>
        {mode === "amounts" && hasContent && (
          <span style={{ ...labelStyle, textAlign: "right" }}>~Wt</span>
        )}
        <span />
      </div>

      {/* ── Holdings rows ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 10 }}>
        {rows.map((row, i) => {
          const wt = previewWeights[row.ticker.trim().toUpperCase()];
          return (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: mode === "amounts" && hasContent ? "1fr 72px 52px 20px" : "1fr 72px 20px",
                gap: 6,
                alignItems: "center",
              }}
            >
              <input
                ref={i === 0 ? firstInputRef : undefined}
                className="field-input"
                placeholder="AAPL"
                value={row.ticker}
                onChange={(e) => update(i, "ticker", e.target.value)}
                maxLength={10}
                disabled={isLoading}
              />
              <input
                className="field-input"
                style={{ textAlign: "right" }}
                placeholder={MODE_PLACEHOLDER[mode]}
                type="number"
                min="0.0001"
                step={mode === "weights" ? "0.1" : mode === "amounts" ? "100" : "1"}
                value={row.value}
                onChange={(e) => update(i, "value", e.target.value)}
                disabled={isLoading}
              />
              {mode === "amounts" && hasContent && (
                <span
                  style={{
                    textAlign: "right",
                    fontSize: 11,
                    color: wt != null ? "var(--muted)" : "var(--faint)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {wt != null && row.ticker.trim() ? fmtPct(wt) : "—"}
                </span>
              )}
              <button
                onClick={() => removeRow(i)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--faint)",
                  cursor: "pointer",
                  fontSize: 15,
                  padding: 0,
                  lineHeight: 1,
                  textAlign: "center",
                  fontFamily: "inherit",
                }}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>

      {/* ── Add row ── */}
      <button
        onClick={addRow}
        style={{
          background: "none",
          border: "none",
          color: "var(--muted)",
          fontSize: 11,
          cursor: "pointer",
          padding: 0,
          fontFamily: "inherit",
          marginBottom: 14,
          display: "block",
        }}
      >
        + Add row
      </button>

      {/* ── Amounts mode extras ── */}
      {mode === "amounts" && (
        <div
          style={{
            background: "var(--bg)",
            border: "1px solid var(--border-lt)",
            borderRadius: 6,
            padding: "10px 12px",
            marginBottom: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {/* Total portfolio value */}
          <div>
            <label style={{ ...labelStyle, display: "block", marginBottom: 4 }}>
              Total portfolio value (optional)
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>$</span>
              <input
                className="field-input"
                type="number"
                min="0"
                step="1000"
                placeholder="e.g. 100000"
                value={totalValue}
                onChange={(e) => { setTotalValue(e.target.value); setError(null); }}
                disabled={isLoading}
                style={{ flex: 1 }}
              />
            </div>
          </div>

          {/* Summary row */}
          {hasContent && (
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span style={{ color: "var(--faint)" }}>Entered</span>
              <span style={{ color: "var(--muted)", fontWeight: 500 }}>
                {fmtUSD(totalEntered)}
              </span>
            </div>
          )}

          {/* Unallocated / Cash */}
          {unallocatedAmt > 0.01 && (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                <span style={{ color: "var(--faint)" }}>Unallocated / Cash</span>
                <span style={{ color: "var(--positive)", fontWeight: 500 }}>
                  {fmtUSD(unallocatedAmt)}
                </span>
              </div>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  cursor: "pointer",
                  fontSize: 11,
                  color: "var(--muted)",
                }}
              >
                <input
                  type="checkbox"
                  checked={treatCash}
                  onChange={(e) => setTreatCash(e.target.checked)}
                  disabled={isLoading}
                  style={{ accentColor: "var(--text)", cursor: "pointer" }}
                />
                Treat unallocated as cash in analysis
              </label>
            </>
          )}
        </div>
      )}

      {/* ── Weight indicator (weights mode only) ── */}
      {mode === "weights" && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "7px 10px",
            background: "var(--bg)",
            borderRadius: 5,
            border: `1px solid ${sumOk ? "var(--border-lt)" : hasContent ? "#D9B5B5" : "var(--border-lt)"}`,
            marginBottom: 12,
          }}
        >
          <span style={{ color: "var(--faint)", fontSize: 11 }}>Total weight</span>
          <span
            style={{
              fontSize: 12.5,
              fontWeight: 600,
              color: sumOk ? "var(--positive)" : hasContent ? "var(--negative)" : "var(--faint)",
            }}
          >
            {hasContent ? `${weightSum.toFixed(1)}%` : "—"}
          </span>
        </div>
      )}

      {/* ── Validation error ── */}
      {error && (
        <p style={{ color: "var(--negative)", fontSize: 11.5, marginBottom: 10, lineHeight: 1.4 }}>
          {error}
        </p>
      )}

      {/* ── Primary button ── */}
      <button
        onClick={submit}
        disabled={isLoading}
        style={{
          width: "100%",
          background: isLoading ? "#9CA3AF" : "var(--text)",
          color: "#FFFFFF",
          border: "none",
          borderRadius: 5,
          padding: "10px 0",
          fontSize: 13,
          fontWeight: 500,
          cursor: isLoading ? "not-allowed" : "pointer",
          fontFamily: "inherit",
          letterSpacing: "0.01em",
          marginBottom: 10,
        }}
      >
        {isLoading ? "Analyzing…" : "Analyze Portfolio"}
      </button>

      {/* ── Toggle: Load sample ↔ Reset ── */}
      {sampleLoaded ? (
        <button
          onClick={resetPortfolio}
          style={{
            width: "100%",
            background: "none",
            border: "1px solid var(--border)",
            color: "var(--muted)",
            borderRadius: 5,
            padding: "9px 0",
            fontSize: 12,
            fontWeight: 400,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Reset
        </button>
      ) : (
        <button
          onClick={loadSample}
          disabled={isLoading}
          style={{
            width: "100%",
            background: "none",
            border: "1px solid var(--border)",
            color: "var(--muted)",
            borderRadius: 5,
            padding: "9px 0",
            fontSize: 12,
            fontWeight: 400,
            cursor: isLoading ? "not-allowed" : "pointer",
            fontFamily: "inherit",
          }}
        >
          Load sample portfolio
        </button>
      )}
    </div>
  );
});

export default SidebarPortfolioForm;

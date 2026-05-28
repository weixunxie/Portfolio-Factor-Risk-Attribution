"use client";

import { useState } from "react";
import { analyzePortfolio, AnalyzePortfolioResponse } from "@/lib/api";

interface HoldingRow {
  ticker: string;
  weight: string; // kept as string while typing
}

interface Props {
  onResult: (result: AnalyzePortfolioResponse) => void;
}

const DEFAULT_HOLDINGS: HoldingRow[] = [
  { ticker: "AAPL", weight: "0.25" },
  { ticker: "NVDA", weight: "0.25" },
  { ticker: "MSFT", weight: "0.25" },
  { ticker: "TSLA", weight: "0.25" },
];

export default function PortfolioInput({ onResult }: Props) {
  const [holdings, setHoldings] = useState<HoldingRow[]>(DEFAULT_HOLDINGS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalWeight = holdings.reduce((s, h) => s + (parseFloat(h.weight) || 0), 0);
  const weightOk = Math.abs(totalWeight - 1) < 0.005; // within 0.5% of 1.0

  function updateTicker(i: number, v: string) {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, ticker: v.toUpperCase() } : h)));
  }

  function updateWeight(i: number, v: string) {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, weight: v } : h)));
  }

  function addRow() {
    setHoldings((prev) => [...prev, { ticker: "", weight: "" }]);
  }

  function removeRow(i: number) {
    setHoldings((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleAnalyze() {
    setError(null);

    const parsed = holdings
      .filter((h) => h.ticker.trim() && h.weight.trim())
      .map((h) => ({ ticker: h.ticker.trim(), weight: parseFloat(h.weight) }));

    if (parsed.length === 0) {
      setError("Add at least one holding with a ticker and weight.");
      return;
    }

    const bad = parsed.find((h) => isNaN(h.weight) || h.weight <= 0 || h.weight > 1);
    if (bad) {
      setError("Each weight must be a decimal between 0 and 1 (e.g. 0.25 for 25%).");
      return;
    }

    setLoading(true);
    try {
      const result = await analyzePortfolio(parsed);
      onResult(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Portfolio Holdings</h3>
        <span
          className={`text-xs font-mono px-2 py-0.5 rounded ${
            weightOk
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-amber-50 text-amber-700 border border-amber-200"
          }`}
        >
          Total weight: {(totalWeight * 100).toFixed(1)}%{weightOk ? " ✓" : " (should be 100%)"}
        </span>
      </div>

      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wide px-1">
          <span>Ticker</span>
          <span>Weight (decimal)</span>
          <span />
        </div>
        {holdings.map((h, i) => (
          <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2 items-center">
            <input
              value={h.ticker}
              onChange={(e) => updateTicker(i, e.target.value)}
              placeholder="e.g. AAPL"
              maxLength={10}
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 uppercase"
            />
            <input
              value={h.weight}
              onChange={(e) => updateWeight(i, e.target.value)}
              placeholder="e.g. 0.25"
              inputMode="decimal"
              className="border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <button
              onClick={() => removeRow(i)}
              disabled={holdings.length <= 1}
              className="text-slate-400 hover:text-red-500 disabled:opacity-30 text-lg leading-none px-1 transition-colors"
              aria-label="Remove holding"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={addRow}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          + Add holding
        </button>
        <div className="flex-1" />
        <button
          onClick={handleAnalyze}
          disabled={loading}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          {loading ? "Analyzing…" : "Analyze Portfolio"}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}

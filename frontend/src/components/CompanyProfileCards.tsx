"use client";

import { AnalyzePortfolioResponse } from "@/lib/api";

interface Props {
  result: AnalyzePortfolioResponse;
}

function fmt(val: string, prefix = "") {
  if (!val || val === "None") return "—";
  const n = parseFloat(val);
  if (!isNaN(n) && n > 1_000_000) {
    if (n >= 1e12) return `${prefix}${(n / 1e12).toFixed(2)}T`;
    if (n >= 1e9) return `${prefix}${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `${prefix}${(n / 1e6).toFixed(2)}M`;
  }
  return val;
}

export default function CompanyProfileCards({ result }: Props) {
  if (!result.holdings.length) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-500">
          {result.total_weight_pct} allocated across {result.holdings.length} position
          {result.holdings.length !== 1 ? "s" : ""}
        </span>
        {Math.abs(result.total_weight - 1) > 0.005 && (
          <span className="text-xs text-amber-600 font-medium">
            ⚠ Weights sum to {result.total_weight_pct}, not 100%
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {result.holdings.map((h) => {
          const p = h.profile;
          return (
            <div
              key={h.ticker}
              className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-2"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="inline-block bg-blue-50 border border-blue-200 text-blue-700 text-xs font-bold px-2 py-0.5 rounded font-mono">
                    {h.ticker}
                  </span>
                  <p className="text-sm font-semibold text-slate-800 mt-1 leading-tight">
                    {p.name || h.ticker}
                  </p>
                </div>
                <span className="text-lg font-bold text-slate-700">{h.weight_pct}</span>
              </div>

              <div className="text-xs text-slate-500 space-y-0.5">
                {p.sector && (
                  <p>
                    <span className="font-medium text-slate-600">Sector:</span> {p.sector}
                  </p>
                )}
                {p.industry && (
                  <p>
                    <span className="font-medium text-slate-600">Industry:</span> {p.industry}
                  </p>
                )}
                {p.exchange && (
                  <p>
                    <span className="font-medium text-slate-600">Exchange:</span> {p.exchange}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs pt-1 border-t border-slate-100">
                <div>
                  <p className="text-slate-400">Market Cap</p>
                  <p className="font-mono text-slate-700">{fmt(p.market_cap, "$")}</p>
                </div>
                <div>
                  <p className="text-slate-400">P/E Ratio</p>
                  <p className="font-mono text-slate-700">
                    {p.pe_ratio && p.pe_ratio !== "None" ? parseFloat(p.pe_ratio).toFixed(1) : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">52-Week High</p>
                  <p className="font-mono text-slate-700">
                    {p.week_52_high && p.week_52_high !== "None" ? `$${parseFloat(p.week_52_high).toFixed(2)}` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">52-Week Low</p>
                  <p className="font-mono text-slate-700">
                    {p.week_52_low && p.week_52_low !== "None" ? `$${parseFloat(p.week_52_low).toFixed(2)}` : "—"}
                  </p>
                </div>
              </div>

              {p.source && (
                <p className="text-[10px] text-slate-300 pt-1">
                  Source: {p.source}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
        <strong>Note:</strong> {result.dynamic_risk_metrics_note}
      </div>
    </div>
  );
}

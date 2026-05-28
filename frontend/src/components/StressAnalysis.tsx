"use client";

import { useEffect, useState } from "react";
import { fetchStressSummary, StressSummaryRow } from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

function StressCard({ row }: { row: StressSummaryRow }) {
  const ret = row.portfolio_cumulative_return;
  const dd = row.portfolio_max_drawdown;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex flex-col gap-3">
      <div>
        <h3 className="font-semibold text-slate-800 text-base">{row.period}</h3>
        <p className="text-xs text-slate-400 mt-0.5">
          {row.start} — {row.end}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-50 rounded-lg px-3 py-2">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">
            Cumulative Return
          </p>
          <p className={`text-xl font-bold mt-0.5 ${ret < 0 ? "text-red-600" : "text-emerald-600"}`}>
            {pct(ret)}
          </p>
        </div>
        <div className="bg-slate-50 rounded-lg px-3 py-2">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">
            Max Drawdown
          </p>
          <p className="text-xl font-bold mt-0.5 text-red-600">{pct(dd)}</p>
        </div>
      </div>
      <div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
          Worst Contributors
        </p>
        <div className="flex gap-2">
          {[row.worst_contributor_1, row.worst_contributor_2, row.worst_contributor_3].map(
            (ticker) => (
              <span
                key={ticker}
                className="inline-block bg-red-50 border border-red-200 text-red-700 text-xs font-semibold px-2 py-0.5 rounded"
              >
                {ticker}
              </span>
            )
          )}
        </div>
      </div>
    </div>
  );
}

export default function StressAnalysis() {
  const [rows, setRows] = useState<StressSummaryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStressSummary()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="grid sm:grid-cols-2 gap-4 animate-pulse">
        <div className="bg-slate-100 rounded-xl h-44" />
        <div className="bg-slate-100 rounded-xl h-44" />
      </div>
    );

  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load stress summary: {error}
      </div>
    );

  return (
    <div className="grid sm:grid-cols-2 gap-4">
      {rows.map((row) => (
        <StressCard key={row.period} row={row} />
      ))}
    </div>
  );
}

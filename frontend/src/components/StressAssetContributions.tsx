"use client";

import { useEffect, useState } from "react";
import { fetchStressAssetContributions, StressAssetContribution } from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;

export default function StressAssetContributions() {
  const [rows, setRows] = useState<StressAssetContribution[]>([]);
  const [activePeriod, setActivePeriod] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStressAssetContributions()
      .then((data) => {
        setRows(data);
        if (data.length > 0) setActivePeriod(data[0].period);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div className="h-48 bg-slate-100 rounded-xl animate-pulse" />;

  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load stress contributions: {error}
      </div>
    );

  const periods = Array.from(new Set(rows.map((r) => r.period)));
  const filtered = rows.filter((r) => r.period === activePeriod);

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {periods.map((p) => (
          <button
            key={p}
            onClick={() => setActivePeriod(p)}
            className={`px-3 py-1 text-xs font-semibold rounded-full border transition-colors ${
              activePeriod === p
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"
            }`}
          >
            {p}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              {["Asset", "Weight", "Asset Return", "Weighted Contribution"].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-100">
            {filtered.map((row) => (
              <tr key={row.asset} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2.5 font-semibold text-slate-800">{row.asset}</td>
                <td className="px-4 py-2.5 font-mono text-slate-700">{pct(row.weight)}</td>
                <td className={`px-4 py-2.5 font-mono ${row.asset_cumulative_return < 0 ? "text-red-600" : "text-emerald-600"}`}>
                  {pct(row.asset_cumulative_return)}
                </td>
                <td className={`px-4 py-2.5 font-mono ${row.weighted_contribution < 0 ? "text-red-600" : "text-emerald-600"}`}>
                  {pct(row.weighted_contribution)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

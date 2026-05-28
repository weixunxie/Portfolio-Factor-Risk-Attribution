"use client";

import { useEffect, useState } from "react";
import { fetchRiskSummary, RiskSummaryRow } from "@/lib/api";

function fmt(metric: string, value: number): string {
  const lower = metric.toLowerCase();
  if (lower.includes("return") || lower.includes("volatility") || lower.includes("drawdown")) {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (lower.includes("ratio")) {
    return value.toFixed(2);
  }
  return value.toFixed(4);
}

function colorClass(metric: string, value: number): string {
  const lower = metric.toLowerCase();
  if (lower.includes("return")) return value >= 0 ? "text-emerald-600" : "text-red-600";
  if (lower.includes("drawdown")) return "text-red-600";
  if (lower.includes("ratio")) return value >= 1 ? "text-emerald-600" : "text-amber-600";
  return "text-slate-800";
}

export default function RiskSummaryCards() {
  const [rows, setRows] = useState<RiskSummaryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRiskSummary()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-100 rounded-xl h-24" />
        ))}
      </div>
    );

  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load risk summary: {error}
      </div>
    );

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {rows.map((row) => (
        <div
          key={row.Metric}
          className="bg-white rounded-xl border border-slate-200 px-5 py-4 shadow-sm"
        >
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide truncate">
            {row.Metric}
          </p>
          <p className={`mt-1 text-2xl font-bold ${colorClass(row.Metric, row.Value)}`}>
            {fmt(row.Metric, row.Value)}
          </p>
        </div>
      ))}
    </div>
  );
}

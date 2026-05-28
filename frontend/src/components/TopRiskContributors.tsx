"use client";

import { useEffect, useState } from "react";
import { fetchTopRiskContributors, TopRiskContributor } from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const fixed = (v: number, d = 3) => v.toFixed(d);

const COLUMNS: { key: keyof TopRiskContributor; label: string; render: (v: number | string) => string }[] = [
  { key: "", label: "Ticker", render: (v) => String(v) },
  { key: "weight", label: "Weight", render: (v) => pct(v as number) },
  { key: "annualized_volatility", label: "Ann. Volatility", render: (v) => pct(v as number) },
  { key: "weight_volatility_contribution", label: "Wt × Vol Contribution", render: (v) => pct(v as number) },
  { key: "correlation_with_portfolio", label: "Correlation w/ Portfolio", render: (v) => fixed(v as number, 2) },
  { key: "average_return_on_worst_5_days", label: "Avg Return (5 Worst Days)", render: (v) => pct(v as number) },
];

export default function TopRiskContributors() {
  const [rows, setRows] = useState<TopRiskContributor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopRiskContributors()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div className="h-40 bg-slate-100 rounded-xl animate-pulse" />;

  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Failed to load top risk contributors: {error}
      </div>
    );

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.label}
                className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-slate-50 transition-colors">
              {COLUMNS.map((col) => {
                const val = row[col.key];
                const rendered = col.render(val as number | string);
                const isNegative =
                  typeof val === "number" &&
                  val < 0 &&
                  col.key !== "correlation_with_portfolio";
                return (
                  <td
                    key={col.label}
                    className={`px-4 py-2.5 whitespace-nowrap font-mono ${
                      col.key === ""
                        ? "font-semibold text-slate-800 font-sans"
                        : isNegative
                        ? "text-red-600"
                        : "text-slate-700"
                    }`}
                  >
                    {rendered}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { queryCompanyRisk, RiskQueryHit } from "@/lib/api";

interface Props {
  tickers: string[];
  defaultQuery?: string;
}

interface TickerResult {
  ticker: string;
  hits: RiskQueryHit[];
  loading: boolean;
  error: string | null;
}

export default function DynamicRiskEvidence({
  tickers,
  defaultQuery = "key business risks revenue concentration regulatory",
}: Props) {
  const [query, setQuery] = useState(defaultQuery);
  const [activeQuery, setActiveQuery] = useState(defaultQuery);
  const [results, setResults] = useState<TickerResult[]>([]);
  const [activeTicker, setActiveTicker] = useState<string>(tickers[0] ?? "");

  useEffect(() => {
    if (!tickers.length) return;
    setActiveTicker(tickers[0]);
    runQuery(tickers[0], activeQuery);
  }, [tickers.join(",")]); // re-run when ticker list changes

  async function runQuery(ticker: string, q: string) {
    setResults((prev) => {
      const exists = prev.find((r) => r.ticker === ticker);
      if (exists) {
        return prev.map((r) =>
          r.ticker === ticker ? { ...r, loading: true, error: null } : r
        );
      }
      return [...prev, { ticker, hits: [], loading: true, error: null }];
    });

    try {
      const resp = await queryCompanyRisk(ticker, q, 5);
      setResults((prev) =>
        prev.map((r) =>
          r.ticker === ticker ? { ...r, hits: resp.results, loading: false } : r
        )
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Query failed";
      setResults((prev) =>
        prev.map((r) =>
          r.ticker === ticker ? { ...r, loading: false, error: msg } : r
        )
      );
    }
  }

  async function handleSearch() {
    setActiveQuery(query);
    for (const ticker of tickers) {
      await runQuery(ticker, query);
    }
  }

  const active = results.find((r) => r.ticker === activeTicker);

  if (!tickers.length) return null;

  return (
    <div className="space-y-4">
      {/* Query input */}
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="e.g. supply chain risk China exposure regulatory"
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <button
          onClick={handleSearch}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition-colors whitespace-nowrap"
        >
          Search
        </button>
      </div>

      {/* Ticker tabs */}
      {tickers.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {tickers.map((t) => (
            <button
              key={t}
              onClick={() => {
                setActiveTicker(t);
                if (!results.find((r) => r.ticker === t)) {
                  runQuery(t, activeQuery);
                }
              }}
              className={`px-3 py-1 text-xs font-semibold rounded-full border transition-colors ${
                activeTicker === t
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-slate-600 border-slate-300 hover:border-blue-400"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Results */}
      {active ? (
        active.loading ? (
          <div className="space-y-3 animate-pulse">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-slate-100 rounded-lg" />
            ))}
          </div>
        ) : active.error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {active.error}
            {active.error.includes("not found") || active.error.includes("500") ? (
              <p className="mt-1 text-xs text-red-500">
                Tip: run <code>POST /ingest-risk-factors/{active.ticker}</code> to index this
                ticker's risk factors first.
              </p>
            ) : null}
          </div>
        ) : active.hits.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
            No results found for <strong>{active.ticker}</strong>. The ticker may not have been
            ingested into Qdrant yet. Run{" "}
            <code className="text-xs bg-slate-100 px-1 rounded">
              POST /ingest-risk-factors/{active.ticker}
            </code>{" "}
            first.
          </div>
        ) : (
          <div className="space-y-3">
            {active.hits.map((hit, i) => (
              <div
                key={hit.chunk_id || i}
                className="bg-white rounded-lg border border-slate-200 p-4 space-y-2"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold font-mono bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded">
                      {hit.ticker}
                    </span>
                    <span className="text-xs text-slate-400">{hit.source_file}</span>
                    {hit.filing_date && (
                      <span className="text-xs text-slate-400">({hit.filing_date})</span>
                    )}
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    score: {hit.score.toFixed(3)}
                  </span>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">{hit.text}</p>
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="text-sm text-slate-400">
          Select a ticker above to view retrieved risk evidence.
        </div>
      )}
    </div>
  );
}

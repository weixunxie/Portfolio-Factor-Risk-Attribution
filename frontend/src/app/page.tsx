"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import PortfolioInput from "@/components/PortfolioInput";
import CompanyProfileCards from "@/components/CompanyProfileCards";
import DynamicRiskEvidence from "@/components/DynamicRiskEvidence";
import RiskSummaryCards from "@/components/RiskSummaryCards";
import TopRiskContributors from "@/components/TopRiskContributors";
import StressAnalysis from "@/components/StressAnalysis";
import StressAssetContributions from "@/components/StressAssetContributions";
import MarkdownSection from "@/components/MarkdownSection";
import { fetchRiskMemo, fetchCompanyRiskEvidence, AnalyzePortfolioResponse } from "@/lib/api";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-800 border-b border-slate-200 pb-2">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function DashboardPage() {
  // ── static MVP data ──────────────────────────────────────────────────────────
  const [memo, setMemo] = useState<string | null>(null);
  const [memoLoading, setMemoLoading] = useState(true);
  const [memoError, setMemoError] = useState<string | null>(null);

  const [evidence, setEvidence] = useState<string | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(true);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  // ── dynamic portfolio analysis ───────────────────────────────────────────────
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzePortfolioResponse | null>(null);

  useEffect(() => {
    fetchRiskMemo()
      .then((d) => setMemo(d.markdown))
      .catch((e) => setMemoError(`Failed to load risk memo: ${e.message}`))
      .finally(() => setMemoLoading(false));

    fetchCompanyRiskEvidence()
      .then((d) => setEvidence(d.markdown))
      .catch((e) => setEvidenceError(`Failed to load company risk evidence: ${e.message}`))
      .finally(() => setEvidenceLoading(false));
  }, []);

  const analyzedTickers = analyzeResult?.holdings.map((h) => h.ticker) ?? [];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8 space-y-10">
        <DisclaimerBanner />

        {/* ── Dynamic: Portfolio Input ─────────────────────────────────────── */}
        <Section title="Portfolio Analysis">
          <p className="text-xs text-slate-500">
            Enter your holdings below. Weights should be decimals summing to 1.0
            (e.g. 0.25 = 25%). The tool fetches company profiles and, if risk
            factors have been ingested, retrieves relevant evidence from Qdrant.
          </p>
          <PortfolioInput onResult={setAnalyzeResult} />
        </Section>

        {/* ── Dynamic: Company Profiles (shown after analysis) ─────────────── */}
        {analyzeResult && (
          <Section title="Company Profiles">
            <CompanyProfileCards result={analyzeResult} />
          </Section>
        )}

        {/* ── Dynamic: Risk Evidence (shown after analysis) ────────────────── */}
        {analyzeResult && analyzedTickers.length > 0 && (
          <Section title="Company Risk Evidence (Qdrant Semantic Search)">
            <p className="text-xs text-slate-500">
              Semantic search over ingested 10-K risk factors. Results are only
              available for tickers that have been extracted and ingested via the
              API. Run{" "}
              <code className="bg-slate-100 px-1 rounded text-xs">
                GET /sec-risk-factors/&#123;ticker&#125;
              </code>{" "}
              then{" "}
              <code className="bg-slate-100 px-1 rounded text-xs">
                POST /ingest-risk-factors/&#123;ticker&#125;
              </code>{" "}
              to populate.
            </p>
            <DynamicRiskEvidence tickers={analyzedTickers} />
          </Section>
        )}

        {/* ── Static MVP Sections ───────────────────────────────────────────── */}
        <Section title="Demo Portfolio — Risk Summary">
          <p className="text-xs text-slate-500">
            Pre-computed metrics for the fixed 10-asset demo portfolio.
          </p>
          <RiskSummaryCards />
        </Section>

        <Section title="Demo Portfolio — Top Risk Contributors">
          <p className="text-xs text-slate-500">
            Assets ranked by weight × volatility contribution.
          </p>
          <TopRiskContributors />
        </Section>

        <Section title="Demo Portfolio — Stress Period Analysis">
          <StressAnalysis />
        </Section>

        <Section title="Demo Portfolio — Stress Asset Contributions">
          <StressAssetContributions />
        </Section>

        <Section title="AI-Style Risk Memo">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-6 py-5">
            <MarkdownSection markdown={memo} loading={memoLoading} error={memoError} />
          </div>
        </Section>

        <Section title="Pre-Built Company Risk Evidence (Qdrant RAG)">
          <p className="text-xs text-slate-500">
            Evidence retrieved from the pre-indexed demo document store.
          </p>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-6 py-5">
            <MarkdownSection markdown={evidence} loading={evidenceLoading} error={evidenceError} />
          </div>
        </Section>
      </main>

      <footer className="border-t border-slate-200 bg-white mt-8">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-slate-400">
          <span>AI Investment Research &amp; Portfolio Risk Assistant</span>
          <span>Educational use only — not investment advice</span>
        </div>
      </footer>
    </div>
  );
}

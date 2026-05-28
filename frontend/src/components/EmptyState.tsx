import type { HoldingInput } from "@/lib/api";

const DEMO: HoldingInput[] = [
  { ticker: "AAPL", weight: 25 },
  { ticker: "NVDA", weight: 25 },
  { ticker: "MSFT", weight: 25 },
  { ticker: "TSLA", weight: 25 },
];

const SAMPLE_ITEMS = [
  { ticker: "AAPL", name: "Apple Inc.", weight: "25%" },
  { ticker: "NVDA", name: "NVIDIA Corp.", weight: "25%" },
  { ticker: "MSFT", name: "Microsoft Corp.", weight: "25%" },
  { ticker: "TSLA", name: "Tesla Inc.", weight: "25%" },
];

export default function EmptyState({
  onRunSample,
}: {
  onRunSample: (h: HoldingInput[], opts?: { input_mode?: "weights" | "amounts" | "shares" }) => void;
}) {
  const eyebrow: React.CSSProperties = {
    color: "var(--faint)",
    fontSize: 9.5,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    marginBottom: 12,
    display: "block",
  };

  const cardTitle: React.CSSProperties = {
    color: "var(--text)",
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 12,
  };

  return (
    <div>
      {/* Page header */}
      <div style={{ marginBottom: 20 }}>
        {/* Title row: title left, contact icons right */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
          <h1
            style={{
              color: "var(--text)",
              fontSize: 22,
              fontWeight: 600,
              lineHeight: 1.25,
            }}
          >
            Portfolio Risk Assistant
          </h1>

          {/* Author + contact icons, stacked */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10, paddingTop: 4, paddingRight: 6 }}>
            <span style={{ color: "var(--faint)", fontSize: 10.5, fontWeight: 500, letterSpacing: "0.01em" }}>
              Built by Stephanie Xie
            </span>
            <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
              {/* GitHub */}
              <a href="https://github.com/weixunxie" target="_blank" rel="noopener noreferrer"
                aria-label="GitHub profile" className="contact-icon-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.09.682-.218.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                </svg>
              </a>
              {/* LinkedIn */}
              <a href="https://www.linkedin.com/in/weixun-xie-0587202b0/" target="_blank" rel="noopener noreferrer"
                aria-label="LinkedIn profile" className="contact-icon-link">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </a>
              {/* Email */}
              <a href="mailto:weixunxie@outlook.com" aria-label="Send email" className="contact-icon-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                </svg>
              </a>
            </div>
          </div>
        </div>

        <p style={{ color: "var(--muted)", fontSize: 13.5, lineHeight: 1.65, maxWidth: 560 }}>
          Review portfolio concentration, downside exposure, stress-period behavior, and
          SEC-based company risk evidence in one workflow.
        </p>
      </div>

      {/* 2×2 workspace preview grid */}
      <div className="landing-grid">
        {/* Card 1: How it works */}
        <div className="responsive-card">
          <span style={eyebrow}>How it works</span>
          <ol
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {[
              "Enter holdings and weights in the left panel",
              "Load historical market data",
              "Calculate portfolio risk metrics",
              "Identify top risk contributors",
              "Retrieve company risk disclosures from SEC filings",
              "Generate a research-style risk summary",
            ].map((step, i) => (
              <li
                key={i}
                style={{ display: "flex", gap: 10, alignItems: "flex-start" }}
              >
                <span
                  style={{
                    color: "var(--faint)",
                    fontSize: 10.5,
                    fontWeight: 600,
                    minWidth: 16,
                    marginTop: 1,
                  }}
                >
                  {i + 1}
                </span>
                <span style={{ color: "var(--muted)", fontSize: 12.5, lineHeight: 1.55 }}>
                  {step}
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* Card 2: What you get */}
        <div className="responsive-card">
          <span style={eyebrow}>What you will get</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              {
                label: "Risk Diagnostics",
                items: "Volatility, drawdown, Sharpe ratio, VaR, and CVaR.",
              },
              {
                label: "Stress Testing",
                items: "Portfolio behavior during historical market stress periods.",
              },
              {
                label: "Company Evidence",
                items: "Relevant risk excerpts from official SEC filings.",
              },
              {
                label: "Risk Report",
                items: "A structured summary of portfolio-level and company-level risks.",
              },
            ].map(({ label, items }) => (
              <div key={label}>
                <p
                  style={{
                    color: "var(--text)",
                    fontSize: 12,
                    fontWeight: 600,
                    marginBottom: 2,
                  }}
                >
                  {label}
                </p>
                <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.5 }}>
                  {items}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Card 3: Research coverage */}
        <div className="responsive-card">
          <span style={eyebrow}>Research coverage</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {[
              { source: "Market data",      provider: "Historical prices and returns" },
              { source: "Company data",     provider: "Business profile and sector context" },
              { source: "SEC filings",      provider: "Official company risk disclosures" },
              { source: "Risk evidence",    provider: "Source-grounded excerpts" },
              { source: "Saved analyses",   provider: "Portfolio and report history" },
              { source: "Cache layer",      provider: "Faster repeat analysis" },
            ].map(({ source, provider }) => (
              <div
                key={source}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  gap: 8,
                  paddingBottom: 7,
                  borderBottom: "1px solid var(--border-lt)",
                }}
              >
                <span style={{ color: "var(--text)", fontSize: 12, fontWeight: 500 }}>
                  {source}
                </span>
                <span style={{ color: "var(--faint)", fontSize: 11.5, textAlign: "right" }}>
                  {provider}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Card 4: Sample portfolio */}
        <div className="responsive-card">
          <span style={eyebrow}>Try the sample portfolio</span>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {SAMPLE_ITEMS.map((item) => (
              <div
                key={item.ticker}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 8,
                  paddingBottom: 7,
                  borderBottom: "1px solid var(--border-lt)",
                }}
              >
                <span
                  style={{
                    color: "var(--text)",
                    fontSize: 13,
                    fontWeight: 600,
                    minWidth: 40,
                  }}
                >
                  {item.ticker}
                </span>
                <span style={{ color: "var(--muted)", fontSize: 12, flex: 1 }}>
                  {item.name}
                </span>
                <span
                  style={{
                    color: "var(--text)",
                    fontSize: 12.5,
                    fontWeight: 500,
                  }}
                >
                  {item.weight}
                </span>
              </div>
            ))}
          </div>
          <div style={{ marginTop: "auto", paddingTop: 18 }}>
            <button
              onClick={() => onRunSample(DEMO)}
              style={{
                width: "100%",
                background: "var(--text)",
                color: "#FFFFFF",
                border: "none",
                borderRadius: 5,
                padding: "10px 0",
                fontSize: 13,
                fontWeight: 500,
                cursor: "pointer",
                fontFamily: "inherit",
                letterSpacing: "0.01em",
              }}
            >
              Run sample analysis
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

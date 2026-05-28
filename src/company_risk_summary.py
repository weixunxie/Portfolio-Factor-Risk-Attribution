"""
Company-specific risk evidence summary.

Reads top risk contributors from the portfolio analysis, retrieves relevant
risk text chunks from the Qdrant vector store for the top 3 non-ETF positions,
and writes a markdown report to outputs/company_risk_evidence.md.
"""

import sys
from pathlib import Path

import pandas as pd

# Allow import from any working directory
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from qdrant_rag_pipeline import retrieve_company_risks

# ── configuration ──────────────────────────────────────────────────────────────
RISK_CONTRIBUTORS_CSV = (
    Path(__file__).parent.parent / "outputs" / "tables" / "top_risk_contributors.csv"
)
OUTPUT_FILE = Path(__file__).parent.parent / "outputs" / "company_risk_evidence.md"
ETF_TICKERS = {"SPY", "QQQ", "TLT"}   # positions to skip
TOP_N = 3                               # how many companies to include
CHUNKS_PER_COMPANY = 3                  # retrieved chunks per company
# ──────────────────────────────────────────────────────────────────────────────


# Map from ticker to a focused query that surfaces the most relevant risk text
RISK_QUERIES = {
    "NVDA": "GPU supply chain export controls AI competition revenue concentration",
    "TSLA": "EV demand competition China market autonomous driving CEO governance",
    "AAPL": "China revenue supply chain App Store regulation antitrust",
    "MSFT": "cloud AI competition cybersecurity antitrust regulatory capex",
    "AMZN": "AWS cloud AI competition antitrust regulation ecommerce margin",
    "META": "advertising revenue regulation AI competition",
    "GOOGL": "search advertising antitrust regulation AI competition",
}
DEFAULT_QUERY = "key risk factors business outlook competitive threats regulatory"


def _get_top_companies(csv_path: Path, top_n: int, exclude: set[str]) -> list[dict]:
    """Return the top_n non-ETF rows sorted by weight_volatility_contribution."""
    df = pd.read_csv(csv_path, index_col=0)
    df.index = df.index.str.upper()
    df = df[~df.index.isin(exclude)]
    df = df.sort_values("weight_volatility_contribution", ascending=False)
    top = df.head(top_n)

    companies = []
    for ticker, row in top.iterrows():
        companies.append(
            {
                "ticker": ticker,
                "weight": row.get("weight", None),
                "wv_contribution": row.get("weight_volatility_contribution", None),
            }
        )
    return companies


def _format_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.1f}%"


def build_company_risk_evidence() -> str:
    """
    Retrieve risk evidence for top risk contributors and return markdown text.
    """
    print(f"[Summary] Reading risk contributors from {RISK_CONTRIBUTORS_CSV} ...")
    companies = _get_top_companies(RISK_CONTRIBUTORS_CSV, TOP_N, ETF_TICKERS)

    if not companies:
        return "# Company-Specific Risk Evidence\n\nNo data available.\n"

    sections = ["# Company-Specific Risk Evidence\n"]
    sections.append(
        "_Retrieved from 10-K risk factors and earnings call transcripts via semantic search._\n"
    )

    for company in companies:
        ticker = company["ticker"]
        query = RISK_QUERIES.get(ticker, DEFAULT_QUERY)

        print(f"[Summary] Retrieving risk evidence for {ticker} ...")
        chunks = retrieve_company_risks(
            query=query,
            tickers=[ticker],
            top_k=CHUNKS_PER_COMPANY,
        )

        wv = _format_pct(company["wv_contribution"])
        weight = _format_pct(company["weight"])

        sections.append(f"---\n\n## {ticker}")
        sections.append(
            f"**Portfolio weight:** {weight} | "
            f"**Weight × Volatility contribution:** {wv}\n"
        )

        if not chunks:
            sections.append("_No relevant evidence found in document store._\n")
            continue

        for i, chunk in enumerate(chunks, start=1):
            sections.append(
                f"### Evidence {i} — `{chunk['source_file']}` "
                f"(similarity score: {chunk['score']})\n"
            )
            sections.append(chunk["text"].strip())
            sections.append("")  # blank line between chunks

    return "\n".join(sections) + "\n"


def main() -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    markdown = build_company_risk_evidence()

    OUTPUT_FILE.write_text(markdown, encoding="utf-8")
    print(f"[Summary] Report saved to {OUTPUT_FILE}")

    # Print a short preview
    preview_lines = markdown.splitlines()[:20]
    print("\n--- Preview (first 20 lines) ---")
    print("\n".join(preview_lines))


if __name__ == "__main__":
    main()

"""
Qdrant ingestion for company risk factor documents.

Reads extracted markdown files from:
  data/documents/{TICKER}/10k_risk_factors.md

Chunks → embeds → upserts into Qdrant Cloud.

Deterministic point IDs (UUID5) ensure that re-ingesting the same document
does not create duplicate vectors — upsert is idempotent.

Environment variables
---------------------
QDRANT_URL
QDRANT_API_KEY
QDRANT_COLLECTION_NAME

Usage
-----
python src/qdrant_ingestion.py AAPL
"""

import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

load_dotenv()

# ── paths ──────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
DOCUMENTS_DIR = _PROJECT_ROOT / "data" / "documents"
# ──────────────────────────────────────────────────────────────────────────────

# ── Qdrant configuration ──────────────────────────────────────────────────────
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None
COLLECTION_NAME = (
    os.environ.get("QDRANT_COLLECTION_NAME")
    or os.environ.get("QDRANT_COLLECTION")
    or "company_risk_documents"
)
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
VECTOR_SIZE = 384
CHUNK_SIZE_WORDS = 600    # target chunk size
CHUNK_OVERLAP_WORDS = 100  # overlap between consecutive chunks
# ──────────────────────────────────────────────────────────────────────────────

# Fixed UUID namespace — never change this; it makes point IDs deterministic
_CHUNK_NS = uuid.UUID("7e4bda4e-3f6e-4b8a-9c2d-1a5f8e3b7d9c")


# ── Qdrant helpers ─────────────────────────────────────────────────────────────

def _get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def _ensure_collection(client: QdrantClient) -> None:
    """Create the Qdrant collection if it does not already exist."""
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"[Qdrant] Created collection '{COLLECTION_NAME}'")
    else:
        print(f"[Qdrant] Using existing collection '{COLLECTION_NAME}'")


def _point_id(chunk_id: str) -> str:
    """Return a deterministic UUID string for a given chunk identifier."""
    return str(uuid.uuid5(_CHUNK_NS, chunk_id))


def ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """Create keyword payload indexes required for filtered queries on Qdrant Cloud.

    Safe to call multiple times — silently ignores already-exists errors.
    """
    for field in ("ticker", "source_type", "source_file"):
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print(f"[Qdrant] Created payload index on '{field}'")
        except Exception as exc:
            msg = str(exc).lower()
            if "already exists" in msg or "conflict" in msg:
                pass  # idempotent — index was already there
            else:
                raise


# ── Text chunking ──────────────────────────────────────────────────────────────

def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ── Markdown metadata parser ───────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse YAML-style frontmatter from a markdown string.

    Returns (metadata_dict, body_text_without_frontmatter).
    """
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("---", 3)
    if end == -1:
        return meta, text
    header = text[3:end].strip()
    for line in header.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    body = text[end + 3:].strip()
    return meta, body


# ── Public API ─────────────────────────────────────────────────────────────────

def ingest_ticker_risk_factors(ticker: str) -> dict:
    """
    Read data/documents/{TICKER}/10k_risk_factors.md, chunk, embed, and
    upsert into Qdrant Cloud.

    Uses deterministic UUID5 point IDs so re-ingesting is safe (idempotent).

    Returns
    -------
    {"success": bool, "ticker": str, "chunks_ingested": int, "error": str | None}
    """
    t = ticker.upper().strip()
    md_path = DOCUMENTS_DIR / t / "10k_risk_factors.md"

    if not md_path.exists():
        return {
            "success": False,
            "ticker": t,
            "chunks_ingested": 0,
            "error": (
                f"No risk factors file found at {md_path}. "
                f"Run GET /sec-risk-factors/{t} first to extract it from SEC EDGAR."
            ),
        }

    full_text = md_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(full_text)

    chunks = _chunk_text(body)
    if not chunks:
        return {
            "success": False,
            "ticker": t,
            "chunks_ingested": 0,
            "error": "Document body is empty after stripping frontmatter",
        }

    print(f"[Qdrant] Loading embedding model '{EMBEDDING_MODEL}' ...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"[Qdrant] Embedding {len(chunks)} chunks for {t} ...")
    embeddings = model.encode(chunks, show_progress_bar=False)

    points = [
        PointStruct(
            id=_point_id(f"{t}_10k_risk_factors_{i}"),
            vector=embedding.tolist(),
            payload={
                "ticker": t,
                "source_type": "10k_risk_factors",
                "source_file": "10k_risk_factors.md",
                "filing_date": meta.get("filing_date", ""),
                "accession_number": meta.get("accession_number", ""),
                "source_url": meta.get("source_url", ""),
                "chunk_id": f"{t}_10k_risk_factors_{i}",
                "text": chunk,
            },
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]

    client = _get_client()
    _ensure_collection(client)
    ensure_payload_indexes(client, COLLECTION_NAME)

    print(f"[Qdrant] Upserting {len(points)} vectors for {t} ...")
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"[Qdrant] Done — {len(points)} vectors upserted for {t}.")

    return {"success": True, "ticker": t, "chunks_ingested": len(points), "error": None}


def retrieve_company_risks(
    query: str,
    tickers: "list[str] | None" = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic search over company risk documents in Qdrant.

    Parameters
    ----------
    query   : natural-language query string
    tickers : optional list of ticker symbols to filter (e.g. ["AAPL", "NVDA"])
    top_k   : number of results to return

    Returns
    -------
    List of dicts: {ticker, source_file, source_type, filing_date, chunk_id, text, score}
    """
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_vector = model.encode(query).tolist()

    client = _get_client()
    ensure_payload_indexes(client, COLLECTION_NAME)

    search_filter = None
    if tickers:
        normalized = [t.upper() for t in tickers]
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="ticker",
                    match=MatchAny(any=normalized),
                )
            ]
        )

    result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )

    raw_points = result.points if hasattr(result, "points") else result

    return [
        {
            "ticker": r.payload.get("ticker", ""),
            "source_file": r.payload.get("source_file", ""),
            "source_type": r.payload.get("source_type", ""),
            "filing_date": r.payload.get("filing_date", ""),
            "accession_number": r.payload.get("accession_number", ""),
            "chunk_id": r.payload.get("chunk_id", ""),
            "text": r.payload.get("text", ""),
            "score": round(float(r.score), 4),
        }
        for r in raw_points
    ]


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    result = ingest_ticker_risk_factors(ticker_arg)
    if result["success"]:
        print(f"\n[OK] Ingested {result['chunks_ingested']} chunks for {ticker_arg}")
    else:
        print(f"\n[ERROR] {result['error']}")
        sys.exit(1)

    # Quick smoke test
    query = "supply chain manufacturing risk"
    print(f"\n[Test] Querying: '{query}' for {ticker_arg}")
    hits = retrieve_company_risks(query, tickers=[ticker_arg], top_k=3)
    if hits:
        for h in hits:
            preview = h["text"][:120].replace("\n", " ")
            print(f"  [{h['ticker']}] score={h['score']}  {preview}...")
    else:
        print("  No results returned (is the collection populated?)")

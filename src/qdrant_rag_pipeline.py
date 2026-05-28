"""
Qdrant RAG pipeline for company-specific risk documents.

Reads markdown files from data/documents/<TICKER>/, chunks them, embeds with
sentence-transformers, and stores vectors + metadata in a local Qdrant collection.
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchAny,
    MatchValue,
    NamedVector,
    QueryRequest,
)
from sentence_transformers import SentenceTransformer

load_dotenv()

# ── configuration (all secrets read from environment) ─────────────────────────
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
CHUNK_SIZE_WORDS = 650
CHUNK_OVERLAP_WORDS = 100
DOCUMENTS_DIR = Path(__file__).parent.parent / "data" / "documents"
# ──────────────────────────────────────────────────────────────────────────────


def _get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def _load_documents(documents_dir: Path) -> list[dict]:
    """Walk documents_dir and return a list of {ticker, source_file, text} dicts."""
    docs = []
    for ticker_dir in sorted(documents_dir.iterdir()):
        if not ticker_dir.is_dir():
            continue
        ticker = ticker_dir.name.upper()
        for md_file in sorted(ticker_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8").strip()
            docs.append(
                {
                    "ticker": ticker,
                    "source_file": md_file.name,
                    "text": text,
                }
            )
    return docs


def _split_into_words(text: str) -> list[str]:
    """Split text into a list of whitespace-delimited tokens."""
    return text.split()


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split text into overlapping word-based chunks.

    Each chunk is approximately `chunk_size` words; consecutive chunks share
    `overlap` words so context is preserved across boundaries.
    """
    words = _split_into_words(text)
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap  # advance by (chunk_size - overlap)
    return chunks


def _build_points(docs: list[dict], model: SentenceTransformer) -> list[PointStruct]:
    """Chunk every document, embed each chunk, and return Qdrant PointStructs."""
    points = []
    point_id = 0

    for doc in docs:
        chunks = _chunk_text(doc["text"], CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)
        texts_to_embed = chunks  # embed all chunks for this doc at once
        embeddings = model.encode(texts_to_embed, show_progress_bar=False)

        for chunk_idx, (chunk_text, vector) in enumerate(zip(chunks, embeddings)):
            payload = {
                "ticker": doc["ticker"],
                "source_file": doc["source_file"],
                "chunk_id": f"{doc['ticker']}_{doc['source_file']}_{chunk_idx}",
                "text": chunk_text,
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload=payload,
                )
            )
            point_id += 1

    return points


def build_qdrant_vector_store() -> None:
    """
    Full pipeline: load documents → chunk → embed → upload to Qdrant.

    The collection is recreated from scratch on every run so the index stays
    in sync with the markdown files.
    """
    print(f"[RAG] Loading documents from {DOCUMENTS_DIR} ...")
    docs = _load_documents(DOCUMENTS_DIR)
    if not docs:
        print("[RAG] No documents found. Aborting.")
        return
    print(f"[RAG] Loaded {len(docs)} document(s).")

    print(f"[RAG] Loading embedding model '{EMBEDDING_MODEL}' ...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("[RAG] Chunking and embedding documents ...")
    points = _build_points(docs, model)
    print(f"[RAG] Created {len(points)} chunk(s).")

    print(f"[RAG] Connecting to Qdrant at {QDRANT_URL} ...")
    client = _get_client()

    # Recreate collection so the index always reflects current documents
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        print(f"[RAG] Deleting existing collection '{COLLECTION_NAME}' ...")
        client.delete_collection(COLLECTION_NAME)

    print(f"[RAG] Creating collection '{COLLECTION_NAME}' ...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    print(f"[RAG] Uploading {len(points)} vectors ...")
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"[RAG] Done. {len(points)} vectors stored in '{COLLECTION_NAME}'.")


def retrieve_company_risks(
    query: str,
    tickers: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Semantic search over company risk documents stored in Qdrant.

    Parameters
    ----------
    query   : natural-language search string
    tickers : optional list of ticker symbols to filter results (e.g. ["NVDA", "TSLA"])
    top_k   : number of results to return

    Returns
    -------
    List of dicts with keys: ticker, source_file, chunk_id, text, score
    """
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_vector = model.encode(query).tolist()

    client = _get_client()

    # Build a payload filter if specific tickers are requested
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

    # query_points returns a QueryResponse object with a .points attribute,
    # but older builds may return the list directly — handle both.
    raw_points = result.points if hasattr(result, "points") else result

    hits = []
    for r in raw_points:
        hits.append(
            {
                "ticker": r.payload["ticker"],
                "source_file": r.payload["source_file"],
                "chunk_id": r.payload["chunk_id"],
                "text": r.payload["text"],
                "score": round(float(r.score), 4),
            }
        )
    return hits


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    build_qdrant_vector_store()

    # Quick smoke-test after building
    print("\n[RAG] Smoke test — querying: 'supply chain and geopolitical risk'")
    hits = retrieve_company_risks("supply chain and geopolitical risk", top_k=3)
    for h in hits:
        preview = h["text"][:120].replace("\n", " ")
        print(f"  [{h['ticker']}] {h['source_file']} (score={h['score']})  {preview}...")

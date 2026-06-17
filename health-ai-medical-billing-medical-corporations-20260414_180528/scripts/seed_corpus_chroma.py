#!/usr/bin/env python3
"""
Seed ChromaDB corpus and appeals collections from the 10K synthetic
document_pairs.jsonl teacher distillation corpus.

Reads denial letters into claimguard_corpus and appeal letters into
claimguard_appeals with rich metadata (payer type, denial type, CPT/ICD
codes, CARC/RARC codes, difficulty, appeal route).

Usage:
    CLAIMGUARD_EMBEDDING_BACKEND=sentence_transformer python scripts/seed_corpus_chroma.py

Environment:
    CLAIMGUARD_EMBEDDING_BACKEND  "sentence_transformer" for local semantic
                                  embeddings (default: hash)
    CLAIMGUARD_CORPUS_LIMIT       Max pairs to seed (default: all 10000)
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("seed_corpus_chroma")

# Path to the document pairs corpus
CORPUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "llm-distill"
    / "data"
    / "corpus"
    / "generated_teacher_distillation"
    / "document_pairs.jsonl"
)


def _select_provider():
    """Select embedding provider based on env var."""
    from app.services.retrieval import HashEmbeddingProvider, DEFAULT_EMBEDDING_DIMENSIONS

    backend = os.environ.get("CLAIMGUARD_EMBEDDING_BACKEND", "hash").lower()
    if backend in ("sentence_transformer", "local_semantic", "st"):
        from app.services.retrieval import SentenceTransformerEmbeddingProvider
        return SentenceTransformerEmbeddingProvider()
    return HashEmbeddingProvider(dimensions=DEFAULT_EMBEDDING_DIMENSIONS)


def _build_chunks_from_pair(record: dict) -> tuple:
    """
    Build (denial_chunk, appeal_chunk) SourceChunks from a document pair record.

    Returns (denial_chunk, appeal_chunk) — either may be None if text is missing.
    """
    from app.services.retrieval import SourceChunk

    scenario_id = record.get("scenario_id", "unknown")
    pair_id = record.get("document_pair_id", f"{scenario_id}-PAIR")
    meta = record.get("metadata", {})
    scenario = record.get("scenario", {})

    # Common metadata for both chunks
    common_meta = {
        "source_type": record.get("source_type", "synthetic"),
        "denial_type": meta.get("denial_type", ""),
        "payer_type": meta.get("payer_type", ""),
        "appeal_route": meta.get("appeal_route", ""),
        "difficulty": meta.get("difficulty", ""),
        "service_category": meta.get("service_category", ""),
        "cpt_code": meta.get("cpt_code", ""),
        "icd10_code": meta.get("icd10_code", ""),
        "carc_codes": ",".join(meta.get("carc_codes", [])),
        "rarc_codes": ",".join(meta.get("rarc_codes", [])),
        "payer_name": scenario.get("payer_name", ""),
        "state": scenario.get("state", ""),
        "phi_status": "no_phi",
        "license_status": "synthetic_review_required",
    }

    denial_text = record.get("denial_letter", "")
    appeal_text = record.get("appeal_letter", "")

    denial_chunk = None
    if denial_text and len(denial_text.strip()) > 50:
        denial_chunk = SourceChunk(
            chunk_id=f"{pair_id}-DENIAL",
            source_id=scenario_id,
            title=f"Synthetic denial: {scenario_id} ({meta.get('denial_type', 'unknown')})",
            source_type="synthetic_denial_letter",
            text=denial_text,
            jurisdiction=scenario.get("state"),
            payer_type=meta.get("payer_type"),
            phi_status="no_phi",
            license_status="synthetic_review_required",
            extra_metadata={
                **common_meta,
                "document_role": "denial_letter",
                "billed_amount": str(scenario.get("billed_amount", "")),
                "denied_amount": str(scenario.get("denied_amount", "")),
            },
        )

    appeal_chunk = None
    if appeal_text and len(appeal_text.strip()) > 50:
        appeal_chunk = SourceChunk(
            chunk_id=f"{pair_id}-APPEAL",
            source_id=scenario_id,
            title=f"Synthetic appeal draft: {scenario_id} ({meta.get('denial_type', 'unknown')})",
            source_type="synthetic_appeal_draft",
            text=appeal_text,
            jurisdiction=scenario.get("state"),
            payer_type=meta.get("payer_type"),
            phi_status="no_phi",
            license_status="synthetic_review_required",
            extra_metadata={
                **common_meta,
                "document_role": "appeal_letter",
                "appeal_draft_status": record.get("appeal_draft_status", ""),
            },
        )

    return denial_chunk, appeal_chunk


def main():
    import chromadb  # noqa: F401

    from app.services.retrieval_chroma import (
        ChromaRetrievalIndex,
        chroma_collection_stats,
        COLLECTION_CORPUS,
        COLLECTION_APPEALS,
    )

    provider = _select_provider()
    logger.info(
        "using_embedding_provider",
        extra={"model": provider.model_name, "dimensions": provider.dimensions},
    )

    # Load corpus
    if not CORPUS_PATH.exists():
        logger.error(f"Corpus not found: {CORPUS_PATH}")
        sys.exit(1)

    limit = int(os.environ.get("CLAIMGUARD_CORPUS_LIMIT", "0"))
    logger.info(f"Loading document pairs from {CORPUS_PATH} (limit={limit or 'all'})")

    records = []
    with open(CORPUS_PATH) as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            line = line.strip()
            if line:
                records.append(json.loads(line))

    logger.info(f"Loaded {len(records)} document pairs")

    # Build chunks
    denial_chunks = []
    appeal_chunks = []
    skipped = 0

    for record in records:
        denial_chunk, appeal_chunk = _build_chunks_from_pair(record)
        if denial_chunk:
            denial_chunks.append(denial_chunk)
        else:
            skipped += 1
        if appeal_chunk:
            appeal_chunks.append(appeal_chunk)

    logger.info(
        f"Built {len(denial_chunks)} denial chunks, "
        f"{len(appeal_chunks)} appeal chunks, {skipped} skipped"
    )

    # Seed corpus collection
    t0 = time.time()
    corpus_index = ChromaRetrievalIndex(
        collection_name=COLLECTION_CORPUS,
        embedding_provider=provider,
    )
    corpus_added = corpus_index.add_chunks(denial_chunks)
    corpus_time = time.time() - t0
    logger.info(f"Seeded {corpus_added} denial chunks into {COLLECTION_CORPUS} ({corpus_time:.1f}s)")

    # Seed appeals collection
    t0 = time.time()
    appeals_index = ChromaRetrievalIndex(
        collection_name=COLLECTION_APPEALS,
        embedding_provider=provider,
    )
    appeals_added = appeals_index.add_chunks(appeal_chunks)
    appeals_time = time.time() - t0
    logger.info(f"Seeded {appeals_added} appeal chunks into {COLLECTION_APPEALS} ({appeals_time:.1f}s)")

    # Stats
    stats = chroma_collection_stats()
    logger.info(f"ChromaDB stats: {stats}")

    # Smoke tests
    logger.info("Running smoke tests...")

    # Test 1: Search corpus for a denial pattern
    results = corpus_index.search("eligibility denial medicaid managed care", top_k=3)
    logger.info(f"Corpus search 'eligibility denial medicaid managed care': {len(results)} results")
    for r in results:
        logger.info(f"  [{r['score']:.4f}] {r['title'][:80]}")

    # Test 2: Search appeals for an appeal strategy
    results = appeals_index.search("appeal medical necessity prior authorization", top_k=3)
    logger.info(f"Appeals search 'appeal medical necessity prior authorization': {len(results)} results")
    for r in results:
        logger.info(f"  [{r['score']:.4f}] {r['title'][:80]}")

    # Test 3: Search by CPT code
    results = corpus_index.search("CPT 99204 office visit", top_k=3)
    logger.info(f"Corpus search 'CPT 99204 office visit': {len(results)} results")
    for r in results:
        logger.info(f"  [{r['score']:.4f}] {r['title'][:80]}")

    logger.info("Corpus seeding complete.")


if __name__ == "__main__":
    main()

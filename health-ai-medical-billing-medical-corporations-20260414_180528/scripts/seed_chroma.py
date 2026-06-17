#!/usr/bin/env python3
"""
Bootstrap ChromaDB with ClaimGuard's default appeal rule chunks.

Run once to seed the persistent vector store with CMS, DOL, Medicare,
Medicaid, and HIPAA rule chunks that power denial-workflow retrieval.

Usage:
    python -m scripts.seed_chroma
    # or
    python scripts/seed_chroma.py
"""

import logging
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("seed_chroma")


def main():
    try:
        import chromadb  # noqa: F401
    except ImportError:
        logger.error(
            "chromadb is not installed. Install it with:\n"
            "  pip install chromadb\n"
        )
        sys.exit(1)

    from app.services.retrieval_chroma import (
        chroma_collection_stats,
        seed_default_rules_to_chroma,
    )
    from app.services.retrieval import HashEmbeddingProvider, DEFAULT_EMBEDDING_DIMENSIONS

    # Use the hash embedding provider for now (works without external API)
    # Switch to PrivateSemanticEmbeddingProvider when an embedding endpoint is configured
    provider = HashEmbeddingProvider(dimensions=DEFAULT_EMBEDDING_DIMENSIONS)
    logger.info(
        "using_embedding_provider",
        extra={"model": provider.model_name, "dimensions": provider.dimensions},
    )

    # Seed default rules
    count = seed_default_rules_to_chroma(embedding_provider=provider)
    logger.info(f"Seeded {count} default rule chunks into ChromaDB")

    # Print stats
    stats = chroma_collection_stats()
    logger.info(f"ChromaDB stats: {stats}")

    # Quick smoke test
    from app.services.retrieval_chroma import ChromaRetrievalIndex

    index = ChromaRetrievalIndex(embedding_provider=provider)
    test_results = index.search("Medicare appeal deadline", top_k=3)
    logger.info(f"Smoke test: 'Medicare appeal deadline' returned {len(test_results)} results")
    for r in test_results:
        logger.info(f"  [{r['score']:.4f}] {r['title'][:60]}")

    logger.info("ChromaDB bootstrap complete.")


if __name__ == "__main__":
    main()

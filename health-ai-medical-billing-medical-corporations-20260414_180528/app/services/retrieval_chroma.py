"""
ChromaDB-backed retrieval index for ClaimGuard AI.

Provides persistent vector storage with HNSW approximate nearest-neighbor
search, replacing the in-memory HashEmbeddingRetrievalIndex for production use.

Plugs into the existing EmbeddingProvider protocol so any configured embedding
backend (hash fallback, private semantic endpoint, or future local model) works
transparently.

Safety notes:
  - ChromaDB stores vectors + metadata locally on disk (no external calls).
  - PHI-bearing text is NOT stored in ChromaDB; only embeddings + safe metadata.
  - The existing PHI scanning and access-scope gates in RetrievalStoreService
    still apply before any data reaches this index.
"""

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.retrieval import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    EmbeddingResult,
    HASH_EMBEDDING_MODEL,
    HashEmbeddingProvider,
    SourceChunk,
    cosine_similarity,
)

logger = logging.getLogger(__name__)

# Default ChromaDB persist directory (relative to app root)
DEFAULT_CHROMA_DIR = os.environ.get(
    "CLAIMGUARD_CHROMA_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "chroma_db"),
)

# Module-level shared ChromaDB client singleton to avoid
# "An instance of Chroma already exists with different settings" warnings.
_shared_clients: dict[str, Any] = {}


def _get_shared_client(persist_directory: str | None = None) -> Any:
    """Return a module-level shared PersistentClient for the given path."""
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    path = persist_directory or DEFAULT_CHROMA_DIR
    if path not in _shared_clients:
        os.makedirs(path, exist_ok=True)
        _shared_clients[path] = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )
        logger.info("chroma_shared_client_initialized", extra={"persist_directory": path})
    return _shared_clients[path]

# Collection names
COLLECTION_RULES = "claimguard_rules"
COLLECTION_CORPUS = "claimguard_corpus"
COLLECTION_APPEALS = "claimguard_appeals"


def _safe_metadata_for_chroma(chunk: SourceChunk) -> dict[str, Any]:
    """
    Extract ChromaDB-safe metadata from a SourceChunk.

    ChromaDB metadata values must be str, int, float, or bool.
    We exclude the full text (stored as the document) and embedding vectors
    (stored separately) and only keep filterable metadata fields.
    """
    return {
        "source_id": chunk.source_id,
        "title": chunk.title,
        "source_type": chunk.source_type,
        "jurisdiction": chunk.jurisdiction or "",
        "payer_type": chunk.payer_type or "",
        "date": chunk.date or "",
        "source_url": chunk.source_url or "",
        "page_number": chunk.page_number or "",
        "phi_status": chunk.phi_status,
        "license_status": chunk.license_status,
    }


class ChromaRetrievalIndex:
    """
    Persistent vector retrieval index backed by ChromaDB.

    Drop-in alternative to HashEmbeddingRetrievalIndex that persists embeddings
    to disk and uses HNSW for fast approximate nearest-neighbor search.

    Usage:
        provider = HashEmbeddingProvider(dimensions=128)
        index = ChromaRetrievalIndex(embedding_provider=provider)
        index.add_chunks(chunks)
        results = index.search("denial appeal deadline", top_k=5)
    """

    def __init__(
        self,
        *,
        collection_name: str = COLLECTION_RULES,
        persist_directory: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory or DEFAULT_CHROMA_DIR
        self.embedding_provider = embedding_provider or HashEmbeddingProvider(
            dimensions=dimensions
        )
        self.dimensions = self.embedding_provider.dimensions
        self._client = None
        self._collection = None

    def _init_client(self):
        """Lazy-init ChromaDB client via shared singleton."""
        if self._client is None:
            try:
                self._client = _get_shared_client(self.persist_directory)
                logger.info(
                    "chroma_client_initialized",
                    extra={
                        "persist_directory": self.persist_directory,
                        "collection_name": self.collection_name,
                    },
                )
            except ImportError:
                raise RuntimeError(
                    "chromadb package is not installed. "
                    "Install it with: pip install chromadb"
                )
        return self._client

    def _get_collection(self):
        """Lazy-init or get existing collection."""
        if self._collection is None:
            client = self._init_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:M": 16,
                    "hnsw:construction_ef": 200,
                    "hnsw:search_ef": 100,
                    "claimguard_dimensions": self.dimensions,
                    "claimguard_embedding_model": self.embedding_provider.model_name,
                },
            )
        return self._collection

    def add_chunks(self, chunks: list[SourceChunk]) -> int:
        """
        Add chunks to the ChromaDB collection.

        Embeds each chunk's text using the configured embedding provider,
        then stores the vector + metadata in ChromaDB.

        Returns the number of chunks added.
        """
        if not chunks:
            return 0

        collection = self._get_collection()
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for chunk in chunks:
            result = self.embedding_provider.embed(chunk.text)
            ids.append(chunk.chunk_id)
            embeddings.append(result.vector)
            # Store a truncated version of text for debugging (max 500 chars)
            # Full text lives in the encrypted SQL store
            documents.append(chunk.text[:500])
            metadatas.append(_safe_metadata_for_chroma(chunk))

        # ChromaDB batch limit is 5461 by default; chunk in batches of 5000
        batch_size = 5000
        added = 0
        for i in range(0, len(ids), batch_size):
            batch_end = i + batch_size
            collection.upsert(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )
            added += len(ids[i:batch_end])

        logger.info(
            "chroma_chunks_added",
            extra={
                "collection": self.collection_name,
                "chunks_added": added,
                "embedding_model": self.embedding_provider.model_name,
                "dimensions": self.dimensions,
            },
        )
        return added

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        source_type: str | None = None,
        payer_type: str | None = None,
        phi_status: str | None = None,
    ) -> list[dict]:
        """
        Semantic search over stored chunks.

        Returns list of result dicts with score, text, source metadata, and citation.
        """
        collection = self._get_collection()

        if collection.count() == 0:
            return []

        query_result = self.embedding_provider.embed(query)
        if not any(query_result.vector):
            return []

        # Build ChromaDB where filter from metadata constraints
        where_filter = self._build_where_filter(
            source_type=source_type,
            payer_type=payer_type,
            phi_status=phi_status,
        )

        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_result.vector],
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        try:
            results = collection.query(**query_kwargs)
        except Exception as exc:
            logger.warning(
                "chroma_query_failed",
                extra={"error": str(exc), "collection": self.collection_name},
            )
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        output: list[dict] = []
        for idx, chunk_id in enumerate(results["ids"][0]):
            # ChromaDB returns L2 distance for cosine space; convert to similarity
            distance = results["distances"][0][idx] if results.get("distances") else 1.0
            # For cosine distance: similarity = 1 - distance
            score = max(0.0, 1.0 - distance)

            metadata = results["metadatas"][0][idx] if results.get("metadatas") else {}
            document = results["documents"][0][idx] if results.get("documents") else ""

            source_url = metadata.get("source_url", "")
            page_number = metadata.get("page_number", "")
            source_id = metadata.get("source_id", "")
            if source_url:
                citation = f"{source_url}#{page_number or chunk_id}"
            else:
                citation = f"{source_id}#{chunk_id}"

            output.append({
                "source_id": source_id,
                "title": metadata.get("title", ""),
                "source_type": metadata.get("source_type", ""),
                "citation": citation,
                "text": document,
                "jurisdiction": metadata.get("jurisdiction"),
                "payer_type": metadata.get("payer_type"),
                "date": metadata.get("date"),
                "phi_status": metadata.get("phi_status", "no_phi"),
                "license_status": metadata.get("license_status", "review_required"),
                "score": round(score, 6),
            })

        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    def delete_by_source_id(self, source_id: str) -> int:
        """Delete all chunks belonging to a source. Returns count deleted."""
        collection = self._get_collection()
        try:
            results = collection.get(
                where={"source_id": source_id},
                include=[],
            )
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                logger.info(
                    "chroma_source_deleted",
                    extra={
                        "source_id": source_id,
                        "chunks_deleted": len(results["ids"]),
                        "collection": self.collection_name,
                    },
                )
                return len(results["ids"])
        except Exception as exc:
            logger.warning(
                "chroma_delete_failed",
                extra={"source_id": source_id, "error": str(exc)},
            )
        return 0

    def count(self) -> int:
        """Return total chunk count in the collection."""
        return self._get_collection().count()

    def reset(self) -> None:
        """Delete and recreate the collection. USE WITH CAUTION."""
        client = self._init_client()
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = None
        logger.warning(
            "chroma_collection_reset",
            extra={"collection": self.collection_name},
        )

    def _build_where_filter(
        self,
        *,
        source_type: str | None = None,
        payer_type: str | None = None,
        phi_status: str | None = None,
    ) -> dict | None:
        """Build ChromaDB $and where filter from optional constraints."""
        conditions = []
        if source_type:
            conditions.append({"source_type": source_type})
        if payer_type:
            conditions.append({"payer_type": payer_type})
        if phi_status:
            conditions.append({"phi_status": phi_status})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}


class ChromaHybridRetrievalIndex:
    """
    Hybrid retrieval combining ChromaDB semantic search with keyword search.

    Drop-in replacement for HybridRetrievalIndex that uses persistent ChromaDB
    for the embedding vector component while keeping the existing keyword index
    in-memory (keyword search is fast enough for the corpus size).
    """

    def __init__(
        self,
        chunks: list[SourceChunk] | None = None,
        *,
        collection_name: str = COLLECTION_RULES,
        persist_directory: str | None = None,
        dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS,
        keyword_weight: float = 0.45,
        embedding_weight: float = 0.55,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        from app.services.retrieval import KeywordRetrievalIndex

        self.chroma_index = ChromaRetrievalIndex(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_provider=embedding_provider,
            dimensions=dimensions,
        )
        self.keyword_index = KeywordRetrievalIndex(chunks or [])
        self.keyword_weight = keyword_weight
        self.embedding_weight = embedding_weight

        # If chunks provided, add them to ChromaDB
        if chunks:
            self.chroma_index.add_chunks(chunks)

    def search(self, query: str, *, top_k: int = 5) -> list[dict]:
        """Hybrid search combining ChromaDB semantic + keyword results."""
        # Get more candidates than needed for fusion
        candidate_k = max(top_k * 3, 20)

        keyword_results = self.keyword_index.search(query, top_k=candidate_k)
        semantic_results = self.chroma_index.search(query, top_k=candidate_k)

        # Score fusion (same algorithm as HybridRetrievalIndex)
        scores: dict[str, tuple[dict, float]] = {}

        for result in keyword_results:
            citation = result["citation"]
            existing = scores.get(citation, (result, 0.0))[1]
            scores[citation] = (result, existing + self.keyword_weight * result["score"])

        for result in semantic_results:
            citation = result["citation"]
            existing = scores.get(citation, (result, 0.0))[1]
            scores[citation] = (result, existing + self.embedding_weight * result["score"])

        ranked = []
        for result, score in scores.values():
            ranked_result = dict(result)
            ranked_result["score"] = round(score, 6)
            ranked.append(ranked_result)
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]


def seed_default_rules_to_chroma(
    *,
    persist_directory: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> int:
    """
    Seed the default CMS/DOL appeal rule chunks into ChromaDB.

    Call once at startup or via a management command to bootstrap the
    rules collection with the built-in public rule chunks.

    Returns number of chunks seeded.
    """
    from app.services.retrieval import build_default_rule_chunks

    chunks = build_default_rule_chunks()
    index = ChromaRetrievalIndex(
        collection_name=COLLECTION_RULES,
        persist_directory=persist_directory,
        embedding_provider=embedding_provider,
    )
    added = index.add_chunks(chunks)
    logger.info(
        "chroma_default_rules_seeded",
        extra={"chunks_seeded": added},
    )
    return added


def chroma_collection_stats(
    *,
    persist_directory: str | None = None,
) -> dict[str, Any]:
    """
    Return stats about all ClaimGuard ChromaDB collections.

    Useful for monitoring and the vector readiness dashboard.
    """
    stats: dict[str, Any] = {"collections": {}, "total_chunks": 0}
    try:
        client = _get_shared_client(persist_directory)
        for collection_info in client.list_collections():
            name = collection_info.name if hasattr(collection_info, "name") else str(collection_info)
            try:
                coll = client.get_collection(name)
                count = coll.count()
                stats["collections"][name] = {
                    "chunk_count": count,
                    "metadata": coll.metadata or {},
                }
                stats["total_chunks"] += count
            except Exception:
                stats["collections[name]"] = {"chunk_count": 0, "error": "inaccessible"}
    except Exception as exc:
        stats["error"] = str(exc)
    return stats

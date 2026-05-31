from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.core.security import EncryptionService, generate_fernet_key
from app.db.database import Base
from app.models import RetrievalSourceChunk, RetrievalSourceDocument
from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisRequest,
    RetrievalEmbeddingReindexRequest,
    RetrievalSearchRequest,
    RetrievalSourceCreateRequest,
)
from app.services.retrieval import EmbeddingResult, hash_embedding
from app.services.denial_workflow import DenialWorkflowService
from app.services.retrieval_store import RetrievalStoreError, RetrievalStoreService


SEMANTIC_SETTINGS = SimpleNamespace(
    RETRIEVAL_EMBEDDING_BACKEND="semantic",
    RETRIEVAL_EMBEDDING_MODEL="synthetic-semantic-embedding-v1",
    RETRIEVAL_EMBEDDING_MODEL_APPROVED=True,
    RETRIEVAL_VECTOR_BACKEND="pgvector",
    RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED=True,
    RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION=True,
)


class SyntheticSemanticEmbeddingProvider:
    model_name = "synthetic-semantic-embedding-v1"
    backend_name = "semantic"
    dimensions = 128

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=hash_embedding(text, dimensions=self.dimensions),
            model=self.model_name,
            backend=self.backend_name,
        )


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def store(db_session):
    encryption = EncryptionService(keys=[generate_fernet_key()], app_env="test")
    return RetrievalStoreService(db_session, encryption=encryption)


@pytest.fixture()
def semantic_store(db_session):
    encryption = EncryptionService(keys=[generate_fernet_key()], app_env="test")
    return RetrievalStoreService(
        db_session,
        encryption=encryption,
        embedding_provider=SyntheticSemanticEmbeddingProvider(),
    )


def test_create_source_encrypts_title_url_and_chunks(db_session, store):
    response = store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Plan Policy",
            source_type="plan_document",
            document_text=(
                "Synthetic policy excerpt. Prior authorization appeal evidence "
                "must include the denial notice and provider attestation."
            ),
            source_url="https://example.test/synthetic-policy",
            phi_status="deidentified",
            license_status="synthetic_internal",
            chunk_size=200,
            overlap=20,
        ),
        created_by_user_id=42,
    )

    stored_source = db_session.query(RetrievalSourceDocument).one()
    stored_chunk = db_session.query(RetrievalSourceChunk).one()

    assert response.source_id.startswith("SRC-LOCAL-")
    assert response.title == "Synthetic Plan Policy"
    assert response.chunk_count == 1
    assert response.embedding_model == "claimguard-hash-embedding-v1"
    assert response.created_by_user_id == 42
    assert "Synthetic Plan Policy" not in stored_source.title_encrypted
    assert "example.test" not in stored_source.source_url_encrypted
    assert "Prior authorization" not in stored_chunk.text_encrypted
    assert "embedding" not in stored_chunk.extra_metadata_encrypted


def test_search_decrypts_authorized_chunks(store):
    created = store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic ERISA Appeal Rule",
            source_type="public_rule",
            document_text=(
                "Synthetic source. ERISA internal appeal deadline evidence policy "
                "citation requires plan document verification."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    results = store.search(
        RetrievalSearchRequest(query="ERISA appeal deadline evidence", top_k=3)
    ).results

    assert results
    assert results[0].source_id == created.source_id
    assert results[0].title == "Synthetic ERISA Appeal Rule"
    assert "plan document verification" in results[0].text
    assert results[0].phi_status == "no_phi"


def test_embedding_search_uses_encrypted_stored_vectors(store):
    created = store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic External Review Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. external review independent medical review "
                "appeal citation deadline evidence."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    results = store.search(
        RetrievalSearchRequest(
            query="external review citation evidence",
            search_mode="embedding",
            top_k=3,
        )
    ).results

    assert results
    assert results[0].source_id == created.source_id


def test_vector_readiness_blocks_hash_fallback_until_semantic_backend_configured(store):
    store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Hash Vector Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. appeal deadline policy citation evidence "
                "for local retrieval readiness checks."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    status = store.vector_readiness()

    assert status.production_ready is False
    assert status.hash_fallback_in_use is True
    assert status.stored_embedding_models == {"claimguard-hash-embedding-v1": 1}
    assert status.sources_requiring_reindex_count == 1
    assert "semantic_embedding_backend_not_configured" in status.blockers
    assert "hash_embedding_backend_is_fallback_only" in status.blockers
    assert "embedding_model_not_approved_for_production" in status.blockers
    assert "production_vector_backend_not_configured" in status.blockers
    assert "hash_fallback_not_disabled_for_production" in status.blockers
    assert "stored_hash_embeddings_require_reindex" in status.blockers


def test_vector_readiness_passes_when_semantic_provider_indexes_chunks(
    db_session, semantic_store
):
    response = semantic_store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Semantic Vector Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. semantic vector backend readiness evidence "
                "for approved retrieval source indexing."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )
    stored_chunk = db_session.query(RetrievalSourceChunk).one()
    metadata = semantic_store._decrypt_metadata(stored_chunk.extra_metadata_encrypted)

    assert response.embedding_model == "synthetic-semantic-embedding-v1"
    assert metadata["embedding_backend"] == "semantic"
    assert metadata["embedding_dimensions"] == 128
    assert metadata["embedding_model"] == "synthetic-semantic-embedding-v1"
    assert isinstance(metadata["embedding"], list)
    assert "synthetic-semantic-embedding-v1" not in stored_chunk.extra_metadata_encrypted

    status = semantic_store.vector_readiness(settings_like=SEMANTIC_SETTINGS)

    assert status.production_ready is True
    assert status.hash_fallback_in_use is False
    assert status.embedding_backend == "semantic"
    assert status.vector_backend == "pgvector"
    assert status.semantic_backend_configured is True
    assert status.embedding_model_approved is True
    assert status.hash_fallback_disabled_for_production is True
    assert status.stored_embedding_models == {"synthetic-semantic-embedding-v1": 1}
    assert status.sources_requiring_reindex_count == 0
    assert status.blockers == []


def test_reindex_embeddings_dry_run_reports_without_metadata_write(db_session):
    encryption = EncryptionService(keys=[generate_fernet_key()], app_env="test")
    hash_store = RetrievalStoreService(db_session, encryption=encryption)
    hash_store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Dry Run Reindex Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. dry run semantic reindex evidence "
                "for appeal retrieval without writing metadata."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )
    semantic_store = RetrievalStoreService(
        db_session,
        encryption=encryption,
        embedding_provider=SyntheticSemanticEmbeddingProvider(),
    )
    stored_chunk = db_session.query(RetrievalSourceChunk).one()
    encrypted_metadata_before = stored_chunk.extra_metadata_encrypted

    result = semantic_store.reindex_embeddings(
        RetrievalEmbeddingReindexRequest(dry_run=True)
    )

    assert result.dry_run is True
    assert result.provider_backend == "semantic"
    assert result.embedding_model == "synthetic-semantic-embedding-v1"
    assert result.chunk_count == 1
    assert result.eligible_chunk_count == 1
    assert result.updated_chunk_count == 0
    assert result.skipped_chunk_count == 1
    assert result.sources_requiring_reindex_count_before == 1
    assert result.sources_requiring_reindex_count_after == 1
    assert result.stored_embedding_models_before == {"claimguard-hash-embedding-v1": 1}
    assert result.stored_embedding_models_after == {"claimguard-hash-embedding-v1": 1}
    assert result.safe_context["raw_source_text_included"] is False
    assert result.safe_context["raw_vector_values_included"] is False
    assert stored_chunk.extra_metadata_encrypted == encrypted_metadata_before


def test_reindex_embeddings_updates_hash_chunks_with_semantic_provider(db_session):
    encryption = EncryptionService(keys=[generate_fernet_key()], app_env="test")
    hash_store = RetrievalStoreService(db_session, encryption=encryption)
    hash_store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Semantic Reindex Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. semantic reindex operation should replace "
                "local hash metadata for approved retrieval source chunks."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )
    semantic_store = RetrievalStoreService(
        db_session,
        encryption=encryption,
        embedding_provider=SyntheticSemanticEmbeddingProvider(),
    )

    result = semantic_store.reindex_embeddings(
        RetrievalEmbeddingReindexRequest(dry_run=False)
    )
    stored_chunk = db_session.query(RetrievalSourceChunk).one()
    metadata = semantic_store._decrypt_metadata(stored_chunk.extra_metadata_encrypted)
    serialized_result = result.model_dump_json()

    assert result.dry_run is False
    assert result.eligible_chunk_count == 1
    assert result.updated_chunk_count == 1
    assert result.skipped_chunk_count == 0
    assert result.sources_requiring_reindex_count_before == 1
    assert result.sources_requiring_reindex_count_after == 0
    assert result.stored_embedding_models_before == {"claimguard-hash-embedding-v1": 1}
    assert result.stored_embedding_models_after == {"synthetic-semantic-embedding-v1": 1}
    assert metadata["embedding_backend"] == "semantic"
    assert metadata["embedding_dimensions"] == 128
    assert metadata["embedding_model"] == "synthetic-semantic-embedding-v1"
    assert "reindexed_at" in metadata
    assert isinstance(metadata["embedding"], list)
    assert "semantic reindex operation should replace" not in serialized_result

    status = semantic_store.vector_readiness(settings_like=SEMANTIC_SETTINGS)

    assert status.production_ready is True
    assert status.sources_requiring_reindex_count == 0
    assert status.stored_embedding_models == {"synthetic-semantic-embedding-v1": 1}


def test_reindex_embeddings_refuses_actual_hash_provider(store):
    store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Hash Reindex Refusal Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. actual reindexing with the development hash "
                "provider must remain blocked."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    with pytest.raises(RetrievalStoreError, match="development hash embedding provider"):
        store.reindex_embeddings(RetrievalEmbeddingReindexRequest(dry_run=False))


def test_embedding_search_uses_injected_semantic_provider(semantic_store):
    created = semantic_store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Semantic Search Source",
            source_type="public_rule",
            document_text=(
                "Synthetic source. semantic vector appeal deadline evidence "
                "for approved retrieval source search."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    results = semantic_store.search(
        RetrievalSearchRequest(
            query="semantic appeal deadline evidence",
            search_mode="embedding",
            top_k=3,
        )
    ).results

    assert results
    assert results[0].source_id == created.source_id


@pytest.mark.asyncio
async def test_denial_workflow_uses_persisted_retrieval_sources(db_session, store):
    created = store.create_source(
        RetrievalSourceCreateRequest(
            title="Synthetic Prior Authorization Policy",
            source_type="medical_policy",
            document_text=(
                "Synthetic source for retrieval. prior_authorization formal_internal_appeal "
                "deadline appeal evidence policy citation requires provider records, "
                "authorization proof, and a verified plan rule."
            ),
            phi_status="no_phi",
            license_status="synthetic_internal",
        )
    )

    result = await DenialWorkflowService(db=db_session, retrieval_store=store).analyze(
        DenialWorkflowAnalysisRequest(
            document_text=(
                "Synthetic denial notice. Payer: Example Health. Reference SYN-401. "
                "Reason for Denial: lack of prior authorization. The provider may appeal."
            ),
            source_document_id="synthetic-denial-401",
            use_llm=False,
        )
    )

    assert any(item.source_id == created.source_id for item in result.retrieval_citations)

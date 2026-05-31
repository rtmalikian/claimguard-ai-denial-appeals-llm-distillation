import json
import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth import ROLE_ADMIN, ROLE_BILLING_STAFF, ROLE_VIEWER
from app.core.config import settings
from app.core.security import EncryptionService, encryption_service
from app.models import AuditLog, RetrievalSourceChunk, RetrievalSourceDocument
from app.schemas.denial_workflow import (
    RetrievalAuditDashboardResponse,
    RetrievalAuditEvent,
    RetrievalEmbeddingReindexRequest,
    RetrievalEmbeddingReindexResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSourceDeleteResponse,
    RetrievalSourceGovernanceSummary,
    RetrievalSourceCreateRequest,
    RetrievalSourceResponse,
    RetrievalVectorReadinessResponse,
    RetrievedSourceSnippet,
)
from app.services.retrieval import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    HASH_EMBEDDING_MODEL,
    HashEmbeddingRetrievalIndex,
    HashEmbeddingProvider,
    HybridRetrievalIndex,
    KeywordRetrievalIndex,
    SourceChunk,
    chunk_document,
)
from app.utils.model_improvement import validate_model_improvement_opt_in
from app.utils.phi import scan_text_for_phi, validate_declared_phi_status


class RetrievalStoreError(ValueError):
    pass


ACCESS_SCOPE_OWNER = "owner"
ACCESS_SCOPE_BILLING_TEAM = "billing_team"
ACCESS_SCOPE_ADMIN_ONLY = "admin_only"
ALLOWED_ACCESS_SCOPES = {
    ACCESS_SCOPE_OWNER,
    ACCESS_SCOPE_BILLING_TEAM,
    ACCESS_SCOPE_ADMIN_ONLY,
}
RETRIEVAL_DOCUMENT_AUDIT_ACTIONS = {
    "denial_retrieval_source_created",
    "denial_retrieval_sources_listed",
    "denial_retrieval_sources_searched",
    "denial_retrieval_source_deleted",
    "denial_retrieval_embeddings_reindexed",
    "denial_retrieval_source_governance_viewed",
    "denial_retrieval_vector_readiness_viewed",
    "denial_retrieval_document_audit_dashboard_viewed",
    "denial_corpus_document_deidentified",
    "denial_corpus_document_surfaces_inspected",
    "denial_corpus_document_imported",
}
SAFE_AUDIT_DETAIL_KEYS = {
    "source_id",
    "source_type",
    "phi_status",
    "license_status",
    "access_scope",
    "retention_until",
    "deleted_at",
    "deleted_by_user_id",
    "deletion_reason",
    "chunk_count",
    "dry_run",
    "embedding_model",
    "embedding_dimensions",
    "eligible_chunk_count",
    "provider_backend",
    "embedding_model_approved",
    "document_id",
    "document_role",
    "surface_count",
    "blocking_surface_count",
    "residual_risk_score",
    "deidentification_status",
    "imported",
    "issue_count",
    "skip",
    "limit",
    "result_count",
    "query_length",
    "top_k",
    "search_mode",
    "active_count",
    "deleted_count",
    "expired_active_count",
    "embedding_backend",
    "vector_backend",
    "semantic_backend_configured",
    "production_ready",
    "hash_fallback_in_use",
    "hash_fallback_disabled_for_production",
    "sources_requiring_reindex_count",
    "sources_requiring_reindex_count_before",
    "sources_requiring_reindex_count_after",
    "source_count",
    "skipped_chunk_count",
    "updated_chunk_count",
    "warning_count",
    "blocker_count",
    "user_data_opt_in_for_model_improvement",
}
LOCAL_VECTOR_BACKENDS = {"encrypted_local_metadata", "local_encrypted_metadata", "local_metadata"}


class RetrievalStoreService:
    def __init__(
        self,
        db: Session,
        encryption: EncryptionService | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.db = db
        self.encryption = encryption or encryption_service
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()

    def create_source(
        self,
        request: RetrievalSourceCreateRequest,
        *,
        created_by_user_id: int | None = None,
    ) -> RetrievalSourceResponse:
        document_text = request.document_text.strip()
        title = request.title.strip()
        source_type = request.source_type.strip()
        if len(document_text) < 20:
            raise RetrievalStoreError("Document text is too short")
        if not title:
            raise RetrievalStoreError("Source title is required")
        if not source_type:
            raise RetrievalStoreError("Source type is required")
        if request.overlap >= request.chunk_size:
            raise RetrievalStoreError("Chunk overlap must be smaller than chunk size")
        if request.access_scope not in ALLOWED_ACCESS_SCOPES:
            raise RetrievalStoreError("Unsupported retrieval source access scope")
        phi_findings = scan_text_for_phi(document_text)
        try:
            validate_declared_phi_status(
                declared_phi_status=request.phi_status,
                findings=phi_findings,
                privacy_review_completed=request.privacy_review_completed,
                user_data_opt_in_for_model_improvement=(
                    request.user_data_opt_in_for_model_improvement
                ),
            )
        except ValueError as exc:
            raise RetrievalStoreError(str(exc)) from exc
        try:
            validate_model_improvement_opt_in(
                requested=request.user_data_opt_in_for_model_improvement,
                legal_approval_attested=(
                    request.model_improvement_legal_approval_attested
                ),
                baa_attested=request.model_improvement_baa_attested,
                consent_attested=request.model_improvement_consent_attested,
                consent_notice_version=(
                    request.model_improvement_consent_notice_version
                ),
            )
        except ValueError as exc:
            raise RetrievalStoreError(str(exc)) from exc

        source_id = f"SRC-LOCAL-{uuid.uuid4().hex[:12].upper()}"
        chunks = chunk_document(
            document_text,
            source_id=source_id,
            title=title,
            source_type=source_type,
            jurisdiction=request.jurisdiction,
            payer_type=request.payer_type,
            date=request.date,
            source_url=request.source_url,
            phi_status=request.phi_status,
            license_status=request.license_status,
            chunk_size=request.chunk_size,
            overlap=request.overlap,
        )
        if not chunks:
            raise RetrievalStoreError("No retrievable chunks were produced")

        source = RetrievalSourceDocument(
            source_id=source_id,
            title_encrypted=self.encryption.encrypt(title),
            source_type=source_type,
            jurisdiction=request.jurisdiction,
            payer_type=request.payer_type,
            source_date=request.date,
            source_url_encrypted=self._encrypt_optional(request.source_url),
            phi_status=request.phi_status,
            license_status=request.license_status,
            access_scope=request.access_scope,
            retention_until=request.retention_until,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(source)
        self.db.flush()

        for index, chunk in enumerate(chunks, start=1):
            embedding_result = self.embedding_provider.embed(chunk.text)
            source.chunks.append(
                RetrievalSourceChunk(
                    chunk_id=chunk.chunk_id,
                    chunk_index=index,
                    text_encrypted=self.encryption.encrypt(chunk.text),
                    page_number=request.page_number,
                    section_label_encrypted=self._encrypt_optional(request.section_label),
                    extra_metadata_encrypted=self.encryption.encrypt(
                        json.dumps(
                            {
                                "chunk_size": request.chunk_size,
                                "embedding": embedding_result.vector,
                                "embedding_backend": embedding_result.backend,
                                "embedding_dimensions": embedding_result.dimensions,
                                "embedding_model": embedding_result.model,
                                "overlap": request.overlap,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    ),
                )
            )

        self.db.commit()
        self.db.refresh(source)
        return self._source_response(source)

    def list_sources(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        current_user: dict | None = None,
        include_deleted: bool = False,
    ) -> list[RetrievalSourceResponse]:
        query = (
            self._visible_sources_query(
                current_user=current_user,
                include_deleted=include_deleted,
            )
            .options(joinedload(RetrievalSourceDocument.chunks))
            .order_by(RetrievalSourceDocument.created_at.desc(), RetrievalSourceDocument.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._source_response(source) for source in query.all()]

    def search(
        self,
        request: RetrievalSearchRequest,
        *,
        current_user: dict | None = None,
    ) -> RetrievalSearchResponse:
        chunks = self.load_source_chunks(
            source_type=request.source_type,
            phi_status=request.phi_status,
            current_user=current_user,
        )
        if request.search_mode == "keyword":
            index = KeywordRetrievalIndex(chunks)
        elif request.search_mode == "embedding":
            index = HashEmbeddingRetrievalIndex(
                chunks,
                embedding_provider=self.embedding_provider,
            )
        else:
            index = HybridRetrievalIndex(
                chunks,
                embedding_provider=self.embedding_provider,
            )
        results = [
            RetrievedSourceSnippet(**item)
            for item in index.search(request.query, top_k=request.top_k)
        ]
        return RetrievalSearchResponse(results=results)

    def load_source_chunks(
        self,
        *,
        source_type: str | None = None,
        phi_status: str | None = None,
        current_user: dict | None = None,
        limit: int = 500,
    ) -> list[SourceChunk]:
        query = (
            self.db.query(RetrievalSourceChunk)
            .join(RetrievalSourceDocument)
            .options(joinedload(RetrievalSourceChunk.source))
        )
        query = query.filter(RetrievalSourceDocument.deleted_at.is_(None))
        query = self._apply_access_scope(query, current_user)
        if source_type:
            query = query.filter(RetrievalSourceDocument.source_type == source_type)
        if phi_status:
            query = query.filter(RetrievalSourceDocument.phi_status == phi_status)
        query = query.order_by(RetrievalSourceChunk.id.asc()).limit(limit)

        chunks: list[SourceChunk] = []
        for stored_chunk in query.all():
            text = self._decrypt_optional(stored_chunk.text_encrypted)
            if not text:
                continue
            source = stored_chunk.source
            title = self._decrypt_optional(source.title_encrypted) or "Encrypted source"
            source_url = self._decrypt_optional(source.source_url_encrypted)
            metadata = self._decrypt_metadata(stored_chunk.extra_metadata_encrypted)
            embedding = self._metadata_embedding(metadata)
            chunks.append(
                SourceChunk(
                    chunk_id=stored_chunk.chunk_id,
                    source_id=source.source_id,
                    title=title,
                    source_type=source.source_type,
                    text=text,
                    jurisdiction=source.jurisdiction,
                    payer_type=source.payer_type,
                    date=source.source_date,
                    source_url=source_url,
                    page_number=stored_chunk.page_number,
                    phi_status=source.phi_status,
                    license_status=source.license_status,
                    extra_metadata={
                        "embedding": embedding,
                        "embedding_backend": metadata.get("embedding_backend"),
                        "embedding_dimensions": metadata.get("embedding_dimensions"),
                        "embedding_model": metadata.get("embedding_model"),
                    },
                )
            )
        return chunks

    def delete_source(
        self,
        source_id: str,
        *,
        current_user: dict | None,
        deletion_reason: str,
    ) -> RetrievalSourceDeleteResponse:
        source = (
            self._visible_sources_query(
                current_user=current_user,
                include_deleted=False,
            )
            .options(joinedload(RetrievalSourceDocument.chunks))
            .filter(RetrievalSourceDocument.source_id == source_id)
            .first()
        )
        if source is None:
            raise RetrievalStoreError("Retrieval source not found or inaccessible")
        if not self._can_delete_source(source, current_user):
            raise RetrievalStoreError("Only admins or source owners can delete retrieval sources")

        source.deleted_at = datetime.utcnow()
        source.deleted_by_user_id = self._current_user_id(current_user)
        source.deletion_reason = deletion_reason.strip()[:255]
        self.db.commit()
        self.db.refresh(source)
        return RetrievalSourceDeleteResponse(
            source_id=source.source_id,
            deleted=True,
            deleted_at=source.deleted_at or datetime.utcnow(),
            deleted_by_user_id=source.deleted_by_user_id,
            deletion_reason=source.deletion_reason or "retention_or_privacy_review",
        )

    def governance_summary(
        self,
        *,
        current_user: dict | None = None,
        include_deleted: bool = True,
    ) -> RetrievalSourceGovernanceSummary:
        sources = (
            self._visible_sources_query(
                current_user=current_user,
                include_deleted=include_deleted,
            )
            .all()
        )
        active_sources = [source for source in sources if source.deleted_at is None]
        deleted_sources = [source for source in sources if source.deleted_at is not None]
        expired_active_count = sum(1 for source in active_sources if self._is_expired(source))
        retained_without_expiration_count = sum(
            1 for source in active_sources if source.retention_until is None
        )
        return RetrievalSourceGovernanceSummary(
            active_count=len(active_sources),
            deleted_count=len(deleted_sources),
            expired_active_count=expired_active_count,
            retained_without_expiration_count=retained_without_expiration_count,
            counts_by_access_scope=self._counts(active_sources, "access_scope"),
            counts_by_phi_status=self._counts(active_sources, "phi_status"),
            counts_by_license_status=self._counts(active_sources, "license_status"),
        )

    def vector_readiness(
        self,
        *,
        settings_like=None,
    ) -> RetrievalVectorReadinessResponse:
        runtime_settings = settings_like or settings
        embedding_backend = self._settings_value(
            runtime_settings,
            "RETRIEVAL_EMBEDDING_BACKEND",
            "hash",
        ).lower()
        embedding_model = self._settings_value(
            runtime_settings,
            "RETRIEVAL_EMBEDDING_MODEL",
            HASH_EMBEDDING_MODEL,
        )
        vector_backend = self._settings_value(
            runtime_settings,
            "RETRIEVAL_VECTOR_BACKEND",
            "encrypted_local_metadata",
        ).lower()
        semantic_backend_configured = bool(
            getattr(runtime_settings, "RETRIEVAL_SEMANTIC_BACKEND_CONFIGURED", False)
        )
        embedding_model_approved = bool(
            getattr(runtime_settings, "RETRIEVAL_EMBEDDING_MODEL_APPROVED", False)
        )
        hash_fallback_disabled_for_production = bool(
            getattr(
                runtime_settings,
                "RETRIEVAL_HASH_FALLBACK_DISABLED_FOR_PRODUCTION",
                False,
            )
        )
        sources = (
            self.db.query(RetrievalSourceDocument)
            .options(joinedload(RetrievalSourceDocument.chunks))
            .filter(RetrievalSourceDocument.deleted_at.is_(None))
            .all()
        )

        stored_embedding_models: dict[str, int] = {}
        sources_requiring_reindex: set[str] = set()
        chunk_count = 0
        for source in sources:
            for chunk in source.chunks:
                chunk_count += 1
                metadata = self._decrypt_metadata(chunk.extra_metadata_encrypted)
                model_name = metadata.get("embedding_model")
                if not isinstance(model_name, str) or not model_name.strip():
                    model_name = "unknown"
                stored_embedding_models[model_name] = stored_embedding_models.get(model_name, 0) + 1
                if model_name in {"unknown", HASH_EMBEDDING_MODEL}:
                    sources_requiring_reindex.add(source.source_id)

        hash_fallback_in_use = (
            embedding_backend == "hash"
            or embedding_model == HASH_EMBEDDING_MODEL
            or any(model in {"unknown", HASH_EMBEDDING_MODEL} for model in stored_embedding_models)
        )
        blockers: list[str] = []
        warnings: list[str] = []
        if not semantic_backend_configured:
            blockers.append("semantic_embedding_backend_not_configured")
        if embedding_backend == "hash" or embedding_model == HASH_EMBEDDING_MODEL:
            blockers.append("hash_embedding_backend_is_fallback_only")
        if not embedding_model_approved:
            blockers.append("embedding_model_not_approved_for_production")
        if vector_backend in LOCAL_VECTOR_BACKENDS:
            blockers.append("production_vector_backend_not_configured")
        if not hash_fallback_disabled_for_production:
            blockers.append("hash_fallback_not_disabled_for_production")
        if sources_requiring_reindex:
            blockers.append("stored_hash_embeddings_require_reindex")
        if chunk_count == 0:
            warnings.append("no_active_retrieval_chunks_indexed")

        return RetrievalVectorReadinessResponse(
            production_ready=not blockers,
            embedding_backend=embedding_backend,
            embedding_model=embedding_model,
            embedding_model_approved=embedding_model_approved,
            vector_backend=vector_backend,
            semantic_backend_configured=semantic_backend_configured,
            hash_fallback_in_use=hash_fallback_in_use,
            hash_fallback_disabled_for_production=(
                hash_fallback_disabled_for_production
            ),
            active_source_count=len(sources),
            chunk_count=chunk_count,
            stored_embedding_models=stored_embedding_models,
            sources_requiring_reindex_count=len(sources_requiring_reindex),
            blockers=blockers,
            warnings=warnings,
            notes=[
                "Readiness is metadata-only; vector values, source text, credentials, and PHI are not returned.",
                "The local hash embedding path remains acceptable for development and tests, but it is not a production semantic backend.",
            ],
        )

    def reindex_embeddings(
        self,
        request: RetrievalEmbeddingReindexRequest,
        *,
        current_user: dict | None = None,
    ) -> RetrievalEmbeddingReindexResponse:
        provider_model = self._provider_model_name()
        provider_backend = self._provider_backend_name()
        provider_dimensions = self._provider_dimensions()
        warnings: list[str] = []
        if provider_backend == "hash" or provider_model == HASH_EMBEDDING_MODEL:
            warnings.append("hash_embedding_provider_is_development_fallback")
            if not request.dry_run:
                raise RetrievalStoreError(
                    "Refusing to reindex with the development hash embedding provider"
                )

        bounded_limit = max(1, min(request.limit, 5000))
        stored_chunks = self._active_stored_chunks(
            source_type=request.source_type,
            phi_status=request.phi_status,
            current_user=current_user,
            limit=bounded_limit,
        )
        if len(stored_chunks) == bounded_limit:
            warnings.append("limit_reached_reindex_may_be_partial")

        stored_models_before, sources_requiring_before = (
            self._stored_embedding_model_counts(stored_chunks)
        )
        source_ids = {
            stored_chunk.source.source_id
            for stored_chunk in stored_chunks
            if stored_chunk.source is not None
        }
        eligible_chunk_count = 0
        updated_chunk_count = 0
        missing_text_count = 0

        for stored_chunk in stored_chunks:
            metadata = self._decrypt_metadata(stored_chunk.extra_metadata_encrypted)
            if not self._metadata_requires_embedding_reindex(
                metadata,
                provider_model=provider_model,
                provider_backend=provider_backend,
                provider_dimensions=provider_dimensions,
            ):
                continue
            text = self._decrypt_optional(stored_chunk.text_encrypted)
            if not text:
                missing_text_count += 1
                continue
            eligible_chunk_count += 1
            if request.dry_run:
                continue

            embedding_result = self.embedding_provider.embed(text)
            updated_metadata = dict(metadata)
            updated_metadata.update(
                {
                    "embedding": embedding_result.vector,
                    "embedding_backend": embedding_result.backend,
                    "embedding_dimensions": embedding_result.dimensions,
                    "embedding_model": embedding_result.model,
                    "reindexed_at": datetime.utcnow().isoformat(),
                }
            )
            stored_chunk.extra_metadata_encrypted = self.encryption.encrypt(
                json.dumps(
                    updated_metadata,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            updated_chunk_count += 1

        if missing_text_count:
            warnings.append("chunks_with_unreadable_encrypted_text_skipped")
        if updated_chunk_count:
            self.db.commit()

        stored_models_after, sources_requiring_after = (
            self._stored_embedding_model_counts(stored_chunks)
        )
        chunk_count = len(stored_chunks)
        return RetrievalEmbeddingReindexResponse(
            dry_run=request.dry_run,
            provider_backend=provider_backend,
            embedding_model=provider_model,
            embedding_dimensions=provider_dimensions,
            source_type=request.source_type,
            phi_status=request.phi_status,
            limit=bounded_limit,
            source_count=len(source_ids),
            chunk_count=chunk_count,
            eligible_chunk_count=eligible_chunk_count,
            updated_chunk_count=updated_chunk_count,
            skipped_chunk_count=chunk_count - updated_chunk_count,
            sources_requiring_reindex_count_before=len(sources_requiring_before),
            sources_requiring_reindex_count_after=len(sources_requiring_after),
            stored_embedding_models_before=stored_models_before,
            stored_embedding_models_after=stored_models_after,
            warnings=warnings,
            safe_context={
                "raw_source_text_included": False,
                "raw_vector_values_included": False,
                "provider_endpoint_included": False,
                "phi_or_secret_values_included": False,
            },
        )

    def audit_dashboard(
        self,
        *,
        source_id: str | None = None,
        limit: int = 100,
    ) -> RetrievalAuditDashboardResponse:
        bounded_limit = max(1, min(limit, 200))
        query = (
            self.db.query(AuditLog)
            .filter(AuditLog.action.in_(RETRIEVAL_DOCUMENT_AUDIT_ACTIONS))
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(bounded_limit * 3)
        )
        events: list[RetrievalAuditEvent] = []
        counts_by_action: dict[str, int] = {}
        for audit_log in query.all():
            details = self._safe_audit_details(audit_log.details)
            if source_id and details.get("source_id") != source_id:
                continue
            counts_by_action[audit_log.action] = counts_by_action.get(audit_log.action, 0) + 1
            events.append(
                RetrievalAuditEvent(
                    id=audit_log.id,
                    action=audit_log.action,
                    user_id=audit_log.user_id,
                    timestamp=audit_log.timestamp or datetime.utcnow(),
                    details=details,
                )
            )
            if len(events) >= bounded_limit:
                break
        return RetrievalAuditDashboardResponse(
            event_count=len(events),
            source_id=source_id,
            counts_by_action=counts_by_action,
            events=events,
        )

    def _source_response(self, source: RetrievalSourceDocument) -> RetrievalSourceResponse:
        return RetrievalSourceResponse(
            id=source.id,
            source_id=source.source_id,
            title=self._decrypt_optional(source.title_encrypted) or "Encrypted source",
            source_type=source.source_type,
            jurisdiction=source.jurisdiction,
            payer_type=source.payer_type,
            date=source.source_date,
            source_url=self._decrypt_optional(source.source_url_encrypted),
            phi_status=source.phi_status,
            license_status=source.license_status,
            access_scope=source.access_scope or ACCESS_SCOPE_OWNER,
            retention_until=source.retention_until,
            deleted_at=source.deleted_at,
            deleted_by_user_id=source.deleted_by_user_id,
            deletion_reason=source.deletion_reason,
            chunk_count=len(source.chunks),
            embedding_model=self._embedding_model(source),
            created_by_user_id=source.created_by_user_id,
            created_at=source.created_at or datetime.utcnow(),
        )

    def _visible_sources_query(
        self,
        *,
        current_user: dict | None,
        include_deleted: bool,
    ):
        query = self.db.query(RetrievalSourceDocument)
        if not include_deleted:
            query = query.filter(RetrievalSourceDocument.deleted_at.is_(None))
        return self._apply_access_scope(query, current_user)

    def _apply_access_scope(self, query, current_user: dict | None):
        if current_user is None:
            return query
        role = current_user.get("role")
        user_id = self._current_user_id(current_user)
        if role == ROLE_ADMIN:
            return query
        if role == ROLE_BILLING_STAFF:
            predicates = [RetrievalSourceDocument.access_scope == ACCESS_SCOPE_BILLING_TEAM]
            if user_id is not None:
                predicates.append(
                    (
                        RetrievalSourceDocument.access_scope == ACCESS_SCOPE_OWNER
                    )
                    & (RetrievalSourceDocument.created_by_user_id == user_id)
                )
            return query.filter(or_(*predicates))
        if role == ROLE_VIEWER:
            return query.filter(RetrievalSourceDocument.access_scope == ACCESS_SCOPE_BILLING_TEAM)
        return query.filter(RetrievalSourceDocument.id == -1)

    def _can_delete_source(
        self,
        source: RetrievalSourceDocument,
        current_user: dict | None,
    ) -> bool:
        if current_user is None:
            return True
        role = current_user.get("role")
        user_id = self._current_user_id(current_user)
        if role == ROLE_ADMIN:
            return True
        return user_id is not None and source.created_by_user_id == user_id

    def _current_user_id(self, current_user: dict | None) -> int | None:
        if not isinstance(current_user, dict):
            return None
        user_id = current_user.get("id")
        return user_id if isinstance(user_id, int) else None

    def _is_expired(self, source: RetrievalSourceDocument) -> bool:
        if source.retention_until is None:
            return False
        retention_until = source.retention_until
        now = datetime.utcnow()
        if retention_until.tzinfo is not None:
            now = datetime.now(retention_until.tzinfo)
        return retention_until <= now

    def _counts(self, sources: list[RetrievalSourceDocument], field_name: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in sources:
            value = getattr(source, field_name, None) or "unknown"
            counts[str(value)] = counts.get(str(value), 0) + 1
        return counts

    def _safe_audit_details(self, details: dict | None) -> dict:
        if not isinstance(details, dict):
            return {}
        safe_details = {}
        for key in SAFE_AUDIT_DETAIL_KEYS:
            if key in details:
                safe_details[key] = details[key]
        return safe_details

    def _embedding_model(self, source: RetrievalSourceDocument) -> str | None:
        for chunk in source.chunks:
            metadata = self._decrypt_metadata(chunk.extra_metadata_encrypted)
            embedding_model = metadata.get("embedding_model")
            if isinstance(embedding_model, str):
                return embedding_model
        return None

    def _active_stored_chunks(
        self,
        *,
        source_type: str | None,
        phi_status: str | None,
        current_user: dict | None,
        limit: int,
    ) -> list[RetrievalSourceChunk]:
        query = (
            self.db.query(RetrievalSourceChunk)
            .join(RetrievalSourceDocument)
            .options(joinedload(RetrievalSourceChunk.source))
            .filter(RetrievalSourceDocument.deleted_at.is_(None))
        )
        query = self._apply_access_scope(query, current_user)
        if source_type:
            query = query.filter(RetrievalSourceDocument.source_type == source_type)
        if phi_status:
            query = query.filter(RetrievalSourceDocument.phi_status == phi_status)
        return query.order_by(RetrievalSourceChunk.id.asc()).limit(limit).all()

    def _stored_embedding_model_counts(
        self,
        stored_chunks: list[RetrievalSourceChunk],
    ) -> tuple[dict[str, int], set[str]]:
        stored_embedding_models: dict[str, int] = {}
        sources_requiring_reindex: set[str] = set()
        provider_model = self._provider_model_name()
        provider_backend = self._provider_backend_name()
        provider_dimensions = self._provider_dimensions()
        for stored_chunk in stored_chunks:
            metadata = self._decrypt_metadata(stored_chunk.extra_metadata_encrypted)
            model_name = metadata.get("embedding_model")
            if not isinstance(model_name, str) or not model_name.strip():
                model_name = "unknown"
            stored_embedding_models[model_name] = (
                stored_embedding_models.get(model_name, 0) + 1
            )
            needs_reindex = self._metadata_requires_embedding_reindex(
                metadata,
                provider_model=provider_model,
                provider_backend=provider_backend,
                provider_dimensions=provider_dimensions,
            )
            if needs_reindex and stored_chunk.source is not None:
                sources_requiring_reindex.add(stored_chunk.source.source_id)
        return stored_embedding_models, sources_requiring_reindex

    def _metadata_requires_embedding_reindex(
        self,
        metadata: dict,
        *,
        provider_model: str,
        provider_backend: str,
        provider_dimensions: int,
    ) -> bool:
        stored_embedding = metadata.get("embedding")
        stored_dimensions = metadata.get("embedding_dimensions")
        try:
            stored_dimensions = int(stored_dimensions)
        except (TypeError, ValueError):
            stored_dimensions = 0
        return (
            metadata.get("embedding_model") != provider_model
            or metadata.get("embedding_backend") != provider_backend
            or stored_dimensions != provider_dimensions
            or not isinstance(stored_embedding, list)
            or len(stored_embedding) != provider_dimensions
        )

    def _provider_model_name(self) -> str:
        value = getattr(self.embedding_provider, "model_name", None)
        return str(value).strip() if value else "unknown"

    def _provider_backend_name(self) -> str:
        value = getattr(self.embedding_provider, "backend_name", None)
        return str(value).strip().lower() if value else "unknown"

    def _provider_dimensions(self) -> int:
        value = getattr(
            self.embedding_provider,
            "dimensions",
            DEFAULT_EMBEDDING_DIMENSIONS,
        )
        try:
            dimensions = int(value)
        except (TypeError, ValueError):
            dimensions = DEFAULT_EMBEDDING_DIMENSIONS
        return dimensions if dimensions > 0 else DEFAULT_EMBEDDING_DIMENSIONS

    def _encrypt_optional(self, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return self.encryption.encrypt(value.strip())

    def _decrypt_optional(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self.encryption.decrypt(value)
        except Exception:
            return None

    def _decrypt_metadata(self, value: str | None) -> dict:
        if value is None:
            return {}
        try:
            decoded = json.loads(self.encryption.decrypt(value))
        except Exception:
            return {}
        if not isinstance(decoded, dict):
            return {}
        return decoded

    def _metadata_embedding(self, metadata: dict) -> list[float]:
        decoded = metadata.get("embedding")
        if not isinstance(decoded, list) or not decoded:
            return [0.0] * DEFAULT_EMBEDDING_DIMENSIONS
        try:
            return [float(item) for item in decoded]
        except (TypeError, ValueError):
            return [0.0] * DEFAULT_EMBEDDING_DIMENSIONS

    def _settings_value(self, settings_like, name: str, default: str) -> str:
        value = getattr(settings_like, name, default)
        if value is None:
            return default
        normalized = str(value).strip()
        return normalized or default

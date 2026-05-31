from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import ADMIN_ROLES, WRITE_ROLES, get_client_ip, require_roles
from app.db.database import get_db
from app.schemas.corpus import (
    CorpusDeidentifyRequest,
    CorpusDeidentifyResponse,
    CorpusDocumentSurfaceInspectRequest,
    CorpusDocumentSurfaceInspectResponse,
    CorpusImportRequest,
    CorpusImportResponse,
    CorpusReviewDecisionRequest,
    CorpusReviewDecisionResponse,
    CorpusReviewQueueResponse,
    CorpusStatusResponse,
    CorpusValidateRequest,
)
from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisRequest,
    DenialWorkflowAnalysisResponse,
    DenialWorkflowExportRequest,
    DenialWorkflowExportResponse,
    DenialWorkflowStudentModelStatus,
    ModelImprovementComplianceStatus,
    RetrievalAuditDashboardResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSourceCreateRequest,
    RetrievalSourceDeleteRequest,
    RetrievalSourceDeleteResponse,
    RetrievalSourceGovernanceSummary,
    RetrievalSourceResponse,
    RetrievalVectorReadinessResponse,
)
from app.services.corpus import CorpusSafetyService
from app.services.denial_workflow import DenialWorkflowService
from app.services.export import export_workflow
from app.services.retrieval import build_default_rule_chunks
from app.services.retrieval_store import RetrievalStoreError, RetrievalStoreService
from app.utils.model_improvement import model_improvement_compliance_status
from app.utils.audit import log_audit

router = APIRouter(prefix="/denial-workflow", tags=["denial-workflow"])


def _current_user_id(current_user: dict) -> int | None:
    return current_user.get("id") if isinstance(current_user, dict) else None


@router.post("/analyze", response_model=DenialWorkflowAnalysisResponse)
async def analyze_denial_workflow(
    request: Request,
    workflow_request: DenialWorkflowAnalysisRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    if not workflow_request.document_text or not workflow_request.document_text.strip():
        raise HTTPException(status_code=400, detail="Document text is required")
    if len(workflow_request.document_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Document text is too short")

    result = await DenialWorkflowService(db=db, current_user=current_user).analyze(
        workflow_request
    )
    log_audit(
        db=db,
        action="denial_workflow_analyzed",
        user_id=_current_user_id(current_user),
        details={
            "document_type": workflow_request.document_type,
            "source_document_id": workflow_request.source_document_id,
            "text_length": len(workflow_request.document_text),
            "plan_type": result.plan_type,
            "denial_type": result.denial_type,
            "recommended_route": result.recommended_route,
            "human_review_required": result.human_review_required,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/student-model/status", response_model=DenialWorkflowStudentModelStatus)
async def student_model_status(current_user: dict = Depends(require_roles(*WRITE_ROLES))):
    runtime_health = await DenialWorkflowService.student_runtime_health()
    return DenialWorkflowService.student_model_status(runtime_health=runtime_health)


@router.get(
    "/model-improvement/compliance-status",
    response_model=ModelImprovementComplianceStatus,
)
async def model_improvement_status(
    request: Request,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = ModelImprovementComplianceStatus(
        **model_improvement_compliance_status().model_dump()
    )
    log_audit(
        db=db,
        action="denial_model_improvement_compliance_status_viewed",
        user_id=_current_user_id(current_user),
        details={
            "ready": result.ready,
            "enabled": result.enabled,
            "blocker_count": len(result.blockers),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/corpus/status", response_model=CorpusStatusResponse)
async def corpus_status(
    request: Request,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().status()
    log_audit(
        db=db,
        action="denial_corpus_status_viewed",
        user_id=_current_user_id(current_user),
        details={
            "record_count": result.record_count,
            "training_eligible_count": result.training_eligible_count,
            "blocked_count": result.blocked_count,
            "missing_category_count": len(result.missing_categories),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/corpus/review-queue", response_model=CorpusReviewQueueResponse)
async def corpus_review_queue(
    request: Request,
    include_training_eligible: bool = True,
    limit: int = 100,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().review_queue(
        include_training_eligible=include_training_eligible,
        limit=limit,
    )
    log_audit(
        db=db,
        action="denial_corpus_review_queue_viewed",
        user_id=_current_user_id(current_user),
        details={
            "record_count": result.record_count,
            "queue_item_count": result.queue_item_count,
            "needs_review_count": result.needs_review_count,
            "needs_expert_determination_count": result.needs_expert_determination_count,
            "missing_pair_count": result.missing_pair_count,
            "production_candidate_count": result.production_candidate_count,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/corpus/validate", response_model=CorpusStatusResponse)
async def validate_corpus_manifest(
    request: Request,
    corpus_request: CorpusValidateRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().validate_manifest(corpus_request.records)
    log_audit(
        db=db,
        action="denial_corpus_manifest_validated",
        user_id=_current_user_id(current_user),
        details={
            "record_count": result.record_count,
            "issue_count": len(result.issues),
            "training_eligible_count": result.training_eligible_count,
            "blocked_count": result.blocked_count,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/corpus/deidentify", response_model=CorpusDeidentifyResponse)
async def deidentify_corpus_document(
    request: Request,
    deidentify_request: CorpusDeidentifyRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().deidentify(deidentify_request)
    log_audit(
        db=db,
        action="denial_corpus_document_deidentified",
        user_id=_current_user_id(current_user),
        details={
            "source_id": result.source_id,
            "document_id": result.document_id,
            "input_text_length": len(deidentify_request.document_text),
            "output_text_length": len(result.deidentified_text),
            "replacement_count": sum(item.replacement_count for item in result.replacements),
            "residual_risk_score": result.residual_risk_score,
            "human_review_required": result.human_review_required,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/corpus/inspect-document", response_model=CorpusDocumentSurfaceInspectResponse)
async def inspect_corpus_document_surfaces(
    request: Request,
    inspect_request: CorpusDocumentSurfaceInspectRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().inspect_document_surfaces(inspect_request)
    log_audit(
        db=db,
        action="denial_corpus_document_surfaces_inspected",
        user_id=_current_user_id(current_user),
        details={
            "source_id": result.source_id,
            "document_id": result.document_id,
            "document_role": result.document_role,
            "surface_count": result.surface_count,
            "blocking_surface_count": result.blocking_surface_count,
            "residual_risk_score": result.residual_risk_score,
            "deidentification_status": result.deidentification_status,
            "surface_names": [surface.surface for surface in result.surface_scans],
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/corpus/review-decision", response_model=CorpusReviewDecisionResponse)
async def apply_corpus_review_decision(
    request: Request,
    review_request: CorpusReviewDecisionRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().apply_review_decision(review_request)
    log_audit(
        db=db,
        action="denial_corpus_review_decision_applied",
        user_id=_current_user_id(current_user),
        details={
            "document_id": result.record.document_id,
            "document_role": result.record.document_role,
            "decision": review_request.decision,
            "review_method": review_request.review_method,
            "approved_for_training": result.approved_for_training,
            "blocker_count": len(result.blockers),
            "residual_risk_score": result.record.residual_risk_score,
            "reviewed_phi_finding_count": result.record.reviewed_phi_finding_count,
            "reviewed_contextual_risk_finding_count": (
                result.record.reviewed_contextual_risk_finding_count
            ),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/corpus/import-approved", response_model=CorpusImportResponse)
async def import_approved_corpus_document(
    request: Request,
    import_request: CorpusImportRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = CorpusSafetyService().import_approved(
        db,
        import_request,
        created_by_user_id=_current_user_id(current_user),
    )
    log_audit(
        db=db,
        action="denial_corpus_document_imported",
        user_id=_current_user_id(current_user),
        details={
            "document_id": import_request.record.document_id,
            "document_role": import_request.record.document_role,
            "imported": result.imported,
            "issue_count": len(result.validation.issues),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/sources", response_model=RetrievalSourceResponse)
async def create_retrieval_source(
    request: Request,
    source_request: RetrievalSourceCreateRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    try:
        result = RetrievalStoreService(db).create_source(
            source_request,
            created_by_user_id=_current_user_id(current_user),
        )
    except RetrievalStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="denial_retrieval_source_created",
        user_id=_current_user_id(current_user),
        details={
            "source_id": result.source_id,
            "source_type": result.source_type,
            "phi_status": result.phi_status,
            "license_status": result.license_status,
            "access_scope": result.access_scope,
            "retention_until": (
                result.retention_until.isoformat() if result.retention_until else None
            ),
            "user_data_opt_in_for_model_improvement": (
                source_request.user_data_opt_in_for_model_improvement
            ),
            "chunk_count": result.chunk_count,
            "embedding_model": result.embedding_model,
            "text_length": len(source_request.document_text),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/sources", response_model=list[RetrievalSourceResponse])
async def list_retrieval_sources(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = RetrievalStoreService(db).list_sources(
        skip=skip,
        limit=min(limit, 200),
        current_user=current_user,
    )
    log_audit(
        db=db,
        action="denial_retrieval_sources_listed",
        user_id=_current_user_id(current_user),
        details={"skip": skip, "limit": min(limit, 200), "result_count": len(result)},
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/sources/governance-summary", response_model=RetrievalSourceGovernanceSummary)
async def retrieval_source_governance_summary(
    request: Request,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    result = RetrievalStoreService(db).governance_summary(current_user=current_user)
    log_audit(
        db=db,
        action="denial_retrieval_source_governance_viewed",
        user_id=_current_user_id(current_user),
        details={
            "active_count": result.active_count,
            "deleted_count": result.deleted_count,
            "expired_active_count": result.expired_active_count,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/sources/vector-readiness", response_model=RetrievalVectorReadinessResponse)
async def retrieval_vector_readiness(
    request: Request,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db=Depends(get_db),
):
    result = RetrievalStoreService(db).vector_readiness()
    log_audit(
        db=db,
        action="denial_retrieval_vector_readiness_viewed",
        user_id=_current_user_id(current_user),
        details={
            "embedding_backend": result.embedding_backend,
            "vector_backend": result.vector_backend,
            "semantic_backend_configured": result.semantic_backend_configured,
            "production_ready": result.production_ready,
            "hash_fallback_in_use": result.hash_fallback_in_use,
            "chunk_count": result.chunk_count,
            "sources_requiring_reindex_count": result.sources_requiring_reindex_count,
            "blocker_count": len(result.blockers),
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/sources/{source_id}/delete", response_model=RetrievalSourceDeleteResponse)
async def delete_retrieval_source(
    source_id: str,
    request: Request,
    delete_request: RetrievalSourceDeleteRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    try:
        result = RetrievalStoreService(db).delete_source(
            source_id,
            current_user=current_user,
            deletion_reason=delete_request.deletion_reason,
        )
    except RetrievalStoreError as exc:
        status_code = 403 if "Only admins" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit(
        db=db,
        action="denial_retrieval_source_deleted",
        user_id=_current_user_id(current_user),
        details={
            "source_id": result.source_id,
            "deleted_at": result.deleted_at.isoformat(),
            "deleted_by_user_id": result.deleted_by_user_id,
            "deletion_reason": result.deletion_reason,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/sources/search", response_model=RetrievalSearchResponse)
async def search_retrieval_sources(
    request: Request,
    search_request: RetrievalSearchRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db=Depends(get_db),
):
    if not search_request.query or not search_request.query.strip():
        raise HTTPException(status_code=400, detail="Search query is required")

    result = RetrievalStoreService(db).search(search_request, current_user=current_user)
    log_audit(
        db=db,
        action="denial_retrieval_sources_searched",
        user_id=_current_user_id(current_user),
        details={
            "query_length": len(search_request.query),
            "top_k": search_request.top_k,
            "search_mode": search_request.search_mode,
            "result_count": len(result.results),
            "source_type": search_request.source_type,
            "phi_status": search_request.phi_status,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.get("/audit/retrieval-documents", response_model=RetrievalAuditDashboardResponse)
async def retrieval_document_audit_dashboard(
    request: Request,
    source_id: str | None = None,
    limit: int = 100,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db=Depends(get_db),
):
    result = RetrievalStoreService(db).audit_dashboard(
        source_id=source_id,
        limit=limit,
    )
    log_audit(
        db=db,
        action="denial_retrieval_document_audit_dashboard_viewed",
        user_id=_current_user_id(current_user),
        details={
            "source_id": source_id,
            "limit": min(max(limit, 1), 200),
            "result_count": result.event_count,
        },
        ip_address=get_client_ip(request),
    )
    return result


@router.post("/export", response_model=DenialWorkflowExportResponse)
async def export_denial_workflow(
    export_request: DenialWorkflowExportRequest,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
):
    try:
        return export_workflow(
            export_request.workflow,
            export_request.export_format,
            export_request.filename_prefix,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/source-registry")
async def source_registry(current_user: dict = Depends(require_roles(*WRITE_ROLES))):
    return {
        "sources": [
            {
                "source_id": chunk.source_id,
                "title": chunk.title,
                "source_type": chunk.source_type,
                "citation": chunk.citation(),
                "payer_type": chunk.payer_type,
                "phi_status": chunk.phi_status,
                "license_status": chunk.license_status,
            }
            for chunk in build_default_rule_chunks()
        ]
    }

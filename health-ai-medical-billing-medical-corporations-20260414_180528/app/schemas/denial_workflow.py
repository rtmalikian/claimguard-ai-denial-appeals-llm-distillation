from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SourceStatus = Literal[
    "known_from_documents",
    "inferred",
    "missing_needs_human_verification",
    "cited_rule",
]

ConfidenceLabel = Literal["low", "medium", "high"]
RetrievalSourceAccessScope = Literal["owner", "billing_team", "admin_only"]


class SourceReference(BaseModel):
    source_status: SourceStatus
    source_document_id: str | None = None
    source_page: str | None = None
    source_excerpt_ref: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    extraction_method: Literal[
        "ocr",
        "manual_entry",
        "api",
        "model_inference",
        "rule_lookup",
        "system_import",
    ] = "model_inference"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    human_verified: bool = False
    inference_path: str | None = None
    verification_note: str | None = None


class FactItem(BaseModel):
    field: str
    value: Any | None = None
    source: SourceReference


class WorkflowTask(BaseModel):
    task: str
    owner: str
    due_date: date | None = None
    source: SourceReference
    verification_status: Literal["open", "blocked", "verified"] = "open"
    reason: str | None = None


class CitedRule(BaseModel):
    rule_id: str
    summary: str
    citation: str
    source: SourceReference


class RouteEvidence(BaseModel):
    fact: str
    source: SourceReference


class RouteConsidered(BaseModel):
    route: str
    decision: Literal["selected", "not_selected", "verify_locally"]
    reason: str


class DeadlineItem(BaseModel):
    deadline_type: str
    source_stated_deadline: date | None = None
    calculated_deadline: date | None = None
    rule_source_id: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    verification_status: Literal["needs_human_verification", "verified"] = (
        "needs_human_verification"
    )
    source: SourceReference


class EvidenceGap(BaseModel):
    evidence_type: str
    description: str
    owner: str
    priority: Literal["low", "medium", "high"]
    source: SourceReference
    human_verification_required: bool = True


class AttachmentIndexItem(BaseModel):
    label: str
    description: str
    source_status: SourceStatus
    required_before_submission: bool = True


class SubmissionPlan(BaseModel):
    route: str
    required_channel: str
    proof_to_capture: list[str]
    blocker_tasks: list[str]
    source: SourceReference


class FollowUpItem(BaseModel):
    action: str
    due_date: date | None = None
    trigger: str
    source: SourceReference
    human_verification_required: bool = True


class QualityCheck(BaseModel):
    check: str
    status: Literal["pass", "warning", "blocker"]
    details: str


class PhiScanFinding(BaseModel):
    finding_type: str
    line: int
    column: int
    category: str = "identifier_like"


class PhiScanSummary(BaseModel):
    status: Literal["not_scanned", "no_findings", "findings_detected"] = "not_scanned"
    finding_count: int = 0
    finding_types: list[str] = Field(default_factory=list)
    contains_phi_or_pii_like_content: bool = False
    values_redacted: bool = True
    review_required: bool = False
    note: str = (
        "Scanner reports metadata only; matched PHI/PII-like values are not returned."
    )


class WorkflowPhaseChecklistItem(BaseModel):
    phase_id: str
    phase_name: str
    status: Literal["not_started", "in_progress", "blocked", "ready_for_human_review"]
    owner: str
    output_artifact: str
    human_verification_required: bool = True
    related_tasks: list[str] = Field(default_factory=list)
    source: SourceReference


class RetrievedSourceSnippet(BaseModel):
    source_id: str
    title: str
    source_type: str
    citation: str
    text: str
    jurisdiction: str | None = None
    payer_type: str | None = None
    date: str | None = None
    phi_status: str = "no_phi"
    license_status: str = "review_required"
    score: float = 0.0


class RetrievalSourceCreateRequest(BaseModel):
    title: str
    source_type: str
    document_text: str
    jurisdiction: str | None = None
    payer_type: str | None = None
    date: str | None = None
    source_url: str | None = None
    page_number: str | None = None
    section_label: str | None = None
    phi_status: Literal["no_phi", "contains_phi", "deidentified", "unknown"] = "unknown"
    license_status: str = "review_required"
    access_scope: RetrievalSourceAccessScope = "owner"
    retention_until: datetime | None = None
    privacy_review_completed: bool = False
    user_data_opt_in_for_model_improvement: bool = False
    model_improvement_legal_approval_attested: bool = False
    model_improvement_baa_attested: bool = False
    model_improvement_consent_attested: bool = False
    model_improvement_consent_notice_version: str | None = None
    chunk_size: int = Field(default=900, ge=200, le=3000)
    overlap: int = Field(default=120, ge=0, le=500)


class RetrievalSourceResponse(BaseModel):
    id: int
    source_id: str
    title: str
    source_type: str
    jurisdiction: str | None = None
    payer_type: str | None = None
    date: str | None = None
    source_url: str | None = None
    phi_status: str
    license_status: str
    access_scope: str = "owner"
    retention_until: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by_user_id: int | None = None
    deletion_reason: str | None = None
    chunk_count: int
    embedding_model: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime


class RetrievalSourceDeleteRequest(BaseModel):
    deletion_reason: str = Field(
        default="retention_or_privacy_review",
        min_length=3,
        max_length=255,
    )


class RetrievalSourceDeleteResponse(BaseModel):
    source_id: str
    deleted: bool
    deleted_at: datetime
    deleted_by_user_id: int | None = None
    deletion_reason: str


class RetrievalSourceGovernanceSummary(BaseModel):
    active_count: int
    deleted_count: int
    expired_active_count: int
    retained_without_expiration_count: int
    counts_by_access_scope: dict[str, int]
    counts_by_phi_status: dict[str, int]
    counts_by_license_status: dict[str, int]


class RetrievalVectorReadinessResponse(BaseModel):
    production_ready: bool
    embedding_backend: str
    embedding_model: str
    embedding_model_approved: bool = False
    vector_backend: str
    semantic_backend_configured: bool
    hash_fallback_in_use: bool
    hash_fallback_disabled_for_production: bool = False
    active_source_count: int
    chunk_count: int
    stored_embedding_models: dict[str, int]
    sources_requiring_reindex_count: int
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RetrievalEmbeddingReindexRequest(BaseModel):
    dry_run: bool = True
    source_type: str | None = None
    phi_status: Literal[
        "no_phi",
        "contains_phi",
        "deidentified",
        "unknown",
    ] | None = None
    limit: int = Field(default=500, ge=1, le=5000)


class RetrievalEmbeddingReindexResponse(BaseModel):
    dry_run: bool
    provider_backend: str
    embedding_model: str
    embedding_dimensions: int
    source_type: str | None = None
    phi_status: str | None = None
    limit: int
    source_count: int
    chunk_count: int
    eligible_chunk_count: int
    updated_chunk_count: int
    skipped_chunk_count: int
    sources_requiring_reindex_count_before: int
    sources_requiring_reindex_count_after: int
    stored_embedding_models_before: dict[str, int]
    stored_embedding_models_after: dict[str, int]
    warnings: list[str] = Field(default_factory=list)
    safe_context: dict[str, bool] = Field(default_factory=dict)
    reindexed_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievalAuditEvent(BaseModel):
    id: int
    action: str
    user_id: int | None = None
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class RetrievalAuditDashboardResponse(BaseModel):
    event_count: int
    source_id: str | None = None
    counts_by_action: dict[str, int]
    events: list[RetrievalAuditEvent]


class ModelImprovementComplianceStatus(BaseModel):
    enabled: bool
    legal_approval_confirmed: bool
    baa_confirmed: bool
    consent_notice_version: str | None = None
    approval_reference_configured: bool
    ready: bool
    blockers: list[str] = Field(default_factory=list)


class RetrievalSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=25)
    source_type: str | None = None
    phi_status: str | None = None
    search_mode: Literal["hybrid", "keyword", "embedding"] = "hybrid"


class RetrievalSearchResponse(BaseModel):
    results: list[RetrievedSourceSnippet]


class DenialWorkflowAnalysisRequest(BaseModel):
    document_text: str
    document_type: str = "denial_letter"
    source_document_id: str = "denial_letter_1"
    source_title: str = "Uploaded denial source"
    source_url: str | None = None
    phi_status: Literal["contains_phi", "deidentified", "no_phi", "unknown"] = "contains_phi"
    retrieved_sources: list[RetrievedSourceSnippet] = Field(default_factory=list)
    generate_draft: bool = True
    use_llm: bool = False


class DenialWorkflowAnalysisResponse(BaseModel):
    document_type: str
    case_summary: str
    known_from_documents: list[FactItem]
    inferred: list[FactItem]
    missing_needs_human_verification: list[WorkflowTask]
    cited_rules: list[CitedRule]
    payer_name: str | None = None
    payer_type: str = "unknown"
    plan_type: str = "unknown"
    denial_type: str = "unknown"
    recommended_route: str = "verify_plan_type"
    route_confidence: ConfidenceLabel = "low"
    route_evidence: list[RouteEvidence] = Field(default_factory=list)
    routes_considered: list[RouteConsidered] = Field(default_factory=list)
    deadline_table: list[DeadlineItem] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    provider_letter_request_checklist: list[WorkflowTask] = Field(default_factory=list)
    appeal_strategy: str
    draft_appeal_letter: str | None = None
    attachment_index: list[AttachmentIndexItem] = Field(default_factory=list)
    submission_plan: SubmissionPlan
    follow_up_plan: list[FollowUpItem] = Field(default_factory=list)
    workflow_phase_checklist: list[WorkflowPhaseChecklistItem] = Field(default_factory=list)
    quality_checks: list[QualityCheck] = Field(default_factory=list)
    phi_scan: PhiScanSummary = Field(default_factory=PhiScanSummary)
    retrieval_citations: list[RetrievedSourceSnippet] = Field(default_factory=list)
    human_review_required: bool = True
    warnings: list[str] = Field(default_factory=list)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class DenialWorkflowExportRequest(BaseModel):
    workflow: DenialWorkflowAnalysisResponse
    export_format: Literal["markdown", "docx", "pdf"] = "markdown"
    filename_prefix: str = "claimguard-denial-workflow"


class DenialWorkflowExportResponse(BaseModel):
    filename: str
    content_type: str
    encoding: Literal["utf-8", "base64"]
    content: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DenialWorkflowStudentModelStatus(BaseModel):
    provider: str
    base_url: str
    model: str
    fallback_model: str
    adapter_path: str
    adapter_path_exists: bool
    schema_contract_name: str
    acceptance_report_path: str
    readiness_report_path: str
    accepted_for_denial_workflow: bool
    acceptance_release_ready: bool | None = None
    readiness_distillation_ready: bool | None = None
    readiness_release_ready: bool | None = None
    benchmark_score_ratio: float | None = None
    warning_count: int | None = None
    blocked_count: int | None = None
    runtime_checked: bool = False
    runtime_available: bool = False
    runtime_status: str = "not_checked"
    runtime_error: str | None = None
    use_by_default: bool = False
    effective_use_by_default: bool = False
    default_cutover_ready: bool = False
    default_cutover_approved: bool = False
    default_approval_reference_configured: bool = False
    runtime_supervised: bool = False
    rollback_to_nvidia_enabled: bool = False
    default_cutover_blockers: list[str] = Field(default_factory=list)
    runtime_required_for_default: bool = False
    max_tokens: int = 1800
    enable_thinking: bool = False
    server_command: list[str] = Field(default_factory=list)
    server_command_display: str = ""
    notes: list[str] = Field(default_factory=list)

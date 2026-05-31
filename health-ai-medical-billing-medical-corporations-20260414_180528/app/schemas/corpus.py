from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.denial_workflow import PhiScanFinding, PhiScanSummary, RetrievalSourceResponse


CorpusIntakeState = Literal[
    "raw_quarantined",
    "machine_deidentified",
    "qa_failed",
    "human_review_required",
    "privacy_review_passed",
    "expert_determination_required",
    "training_eligible",
]
CorpusDocumentRole = Literal[
    "denial_letter",
    "appeal_letter",
    "appeal_response",
    "policy",
    "rule_source",
    "template",
    "other",
]
CorpusSplit = Literal["train", "valid", "test", "holdout", "none"]
CorpusPhiStatus = Literal["no_phi", "deidentified", "contains_phi", "unknown"]


class CorpusManifestRecord(BaseModel):
    source_id: str
    document_id: str
    pair_id: str | None = None
    source_type: str
    document_role: CorpusDocumentRole
    source_url_or_path: str
    checksum: str
    phi_status: CorpusPhiStatus = "unknown"
    deidentification_status: CorpusIntakeState = "raw_quarantined"
    license_status: str = "review_required"
    review_status: Literal[
        "not_reviewed",
        "privacy_review_passed",
        "expert_determination_required",
        "training_approved",
        "excluded",
    ] = "not_reviewed"
    residual_risk_score: float = Field(default=1.0, ge=0.0, le=1.0)
    training_eligible: bool = False
    split: CorpusSplit = "none"
    micro_skill_ids: list[str] = Field(default_factory=list)
    payer_type: str | None = None
    denial_type: str | None = None
    appeal_route: str | None = None
    appeal_level: str | None = None
    outcome: str | None = None
    reviewer_id: str | None = None
    review_timestamp: datetime | None = None
    review_method: str | None = None
    training_decision_note: str | None = None
    review_findings: list[str] = Field(default_factory=list)
    reviewed_phi_finding_count: int = Field(default=0, ge=0)
    reviewed_contextual_risk_finding_count: int = Field(default=0, ge=0)
    privacy_review_completed: bool = False
    license_review_completed: bool = False
    residual_risk_review_completed: bool = False
    expert_determination_completed: bool = False


class CorpusManifestIssue(BaseModel):
    document_id: str | None = None
    field: str
    code: str
    message: str


class CorpusValidateRequest(BaseModel):
    records: list[CorpusManifestRecord] = Field(default_factory=list)


class CorpusStatusResponse(BaseModel):
    manifest_path: str
    manifest_exists: bool
    record_count: int
    counts_by_deidentification_status: dict[str, int]
    counts_by_document_role: dict[str, int]
    counts_by_phi_status: dict[str, int]
    training_eligible_count: int
    blocked_count: int
    missing_categories: list[str]
    ready_for_training_export: bool
    issues: list[CorpusManifestIssue] = Field(default_factory=list)


class CorpusReviewQueueItem(BaseModel):
    source_id: str
    document_id: str
    pair_id: str | None = None
    source_type: str
    document_role: CorpusDocumentRole
    phi_status: CorpusPhiStatus
    deidentification_status: CorpusIntakeState
    license_status: str
    review_status: str
    residual_risk_score: float = Field(ge=0.0, le=1.0)
    training_eligible: bool = False
    split: CorpusSplit
    micro_skill_count: int = Field(default=0, ge=0)
    reviewer_present: bool = False
    review_timestamp_present: bool = False
    privacy_review_completed: bool = False
    license_review_completed: bool = False
    residual_risk_review_completed: bool = False
    expert_determination_completed: bool = False
    reviewed_phi_finding_count: int = Field(default=0, ge=0)
    reviewed_contextual_risk_finding_count: int = Field(default=0, ge=0)
    paired_denial_present: bool = False
    paired_appeal_present: bool = False
    ready_for_review_decision: bool = False
    ready_for_training_export: bool = False
    production_corpus_candidate: bool = False
    blockers: list[str] = Field(default_factory=list)
    next_action: str


class CorpusReviewQueueResponse(BaseModel):
    manifest_path: str
    manifest_exists: bool
    record_count: int
    queue_item_count: int
    needs_review_count: int
    needs_expert_determination_count: int
    missing_pair_count: int
    training_eligible_count: int
    production_candidate_count: int
    values_redacted: bool = True
    items: list[CorpusReviewQueueItem] = Field(default_factory=list)


class CorpusDeidentifyRequest(BaseModel):
    document_text: str
    source_id: str = "corpus_candidate"
    document_id: str = "corpus_candidate_1"
    document_role: CorpusDocumentRole = "denial_letter"


class CorpusDocumentSurfaceInspectRequest(BaseModel):
    source_id: str = "corpus_candidate"
    document_id: str = "corpus_candidate_1"
    document_role: CorpusDocumentRole = "denial_letter"
    source_filename: str | None = None
    source_mime_type: str | None = None
    visible_text: str | None = None
    hidden_text: str | None = None
    ocr_text: str | None = None
    scanned_page_texts: list[str] = Field(default_factory=list)
    header_footer_text: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    barcode_qr_text: list[str] = Field(default_factory=list)
    attachment_filenames: list[str] = Field(default_factory=list)


class CorpusContextualRiskFinding(BaseModel):
    finding_type: str
    line: int
    column: int
    severity: Literal["low", "medium", "high"]
    category: str = "contextual_reidentification_risk"
    surface: str | None = None
    review_action: str


class CorpusDocumentSurfaceScan(BaseModel):
    surface: str
    item_count: int = 0
    text_length: int = 0
    phi_scan: PhiScanSummary
    findings: list[PhiScanFinding] = Field(default_factory=list)
    contextual_risk_findings: list[CorpusContextualRiskFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CorpusDocumentSurfaceInspectResponse(BaseModel):
    source_id: str
    document_id: str
    document_role: CorpusDocumentRole
    deidentification_status: CorpusIntakeState
    residual_risk_score: float = Field(ge=0.0, le=1.0)
    human_review_required: bool = True
    training_eligible: bool = False
    values_redacted: bool = True
    surface_count: int
    blocking_surface_count: int
    contextual_risk_finding_count: int = 0
    contextual_risk_surface_count: int = 0
    surface_scans: list[CorpusDocumentSurfaceScan]
    warnings: list[str] = Field(default_factory=list)


class CorpusReplacement(BaseModel):
    placeholder: str
    finding_type: str
    replacement_count: int


class CorpusDeidentifyResponse(BaseModel):
    source_id: str
    document_id: str
    deidentified_text: str
    deidentification_status: CorpusIntakeState
    phi_scan_before: PhiScanSummary
    phi_scan_after: PhiScanSummary
    replacements: list[CorpusReplacement]
    residual_risk_score: float = Field(ge=0.0, le=1.0)
    contextual_risk_findings: list[CorpusContextualRiskFinding] = Field(default_factory=list)
    contextual_risk_finding_count: int = 0
    human_review_required: bool = True
    training_eligible: bool = False
    warnings: list[str] = Field(default_factory=list)


class CorpusImportRequest(BaseModel):
    record: CorpusManifestRecord
    document_text: str
    chunk_size: int = Field(default=900, ge=200, le=3000)
    overlap: int = Field(default=120, ge=0, le=500)


class CorpusImportResponse(BaseModel):
    imported: bool
    retrieval_source: RetrievalSourceResponse | None = None
    validation: CorpusStatusResponse


class CorpusReviewDecisionRequest(BaseModel):
    record: CorpusManifestRecord
    reviewer_id: str
    review_method: Literal[
        "privacy_review",
        "expert_determination",
        "synthetic_fixture_review",
    ]
    decision: Literal[
        "approve_for_training",
        "privacy_review_passed",
        "exclude",
    ]
    phi_status: CorpusPhiStatus | None = None
    license_status: str = "review_required"
    split: CorpusSplit = "none"
    micro_skill_ids: list[str] = Field(default_factory=list)
    residual_risk_score: float = Field(default=1.0, ge=0.0, le=1.0)
    privacy_review_completed: bool = False
    license_review_completed: bool = False
    residual_risk_review_completed: bool = False
    expert_determination_completed: bool = False
    reviewed_phi_finding_count: int = Field(default=0, ge=0)
    reviewed_contextual_risk_finding_count: int = Field(default=0, ge=0)
    review_findings: list[str] = Field(default_factory=list)
    training_decision_note: str


class CorpusReviewDecisionResponse(BaseModel):
    approved_for_training: bool
    record: CorpusManifestRecord
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: CorpusStatusResponse

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from app.schemas.corpus import CorpusDocumentSurfaceInspectResponse
from app.schemas.denial_workflow import DenialWorkflowAnalysisResponse


class ClaimDocumentGovernance(BaseModel):
    access_scope: str = "billing_team"
    retention_until: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    deleted_by_user_id: Optional[int] = None
    deletion_reason: Optional[str] = None
    created_by_user_id: Optional[int] = None
    is_retired: bool = False
    is_retention_expired: bool = False
    can_view_document: bool = False
    can_retire_document: bool = False


class ClaimDocumentResponse(BaseModel):
    claim_id: int
    filename: Optional[str] = None
    document_text: str
    governance: ClaimDocumentGovernance


class ClaimDocumentDeleteRequest(BaseModel):
    deletion_reason: str = Field(
        default="retention_or_privacy_review",
        min_length=3,
        max_length=255,
    )


class ClaimDocumentDeleteResponse(BaseModel):
    claim_id: int
    deleted: bool
    deleted_at: datetime
    deleted_by_user_id: Optional[int] = None
    deletion_reason: str


class ClaimDocumentGovernanceSummary(BaseModel):
    active_count: int
    deleted_count: int
    expired_active_count: int
    retained_without_expiration_count: int
    counts_by_access_scope: Dict[str, int]


class ClaimDocumentAuditEvent(BaseModel):
    id: int
    action: str
    user_id: Optional[int] = None
    claim_id: Optional[int] = None
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)


class ClaimDocumentAuditDashboardResponse(BaseModel):
    event_count: int
    claim_id: Optional[int] = None
    counts_by_action: Dict[str, int]
    events: List[ClaimDocumentAuditEvent]


class PatientBase(BaseModel):
    mrn: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None


class PatientCreate(PatientBase):
    pass


class PatientResponse(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ClaimBase(BaseModel):
    patient_id: int
    provider_id: int
    claim_data: Dict[str, Any]
    diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None


class ClaimCreate(ClaimBase):
    pass


class ClaimPredictionRequest(BaseModel):
    patient_id: int
    provider_id: int
    claim_data: Dict[str, Any]
    diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None


class DenialReason(BaseModel):
    reason: str
    severity: str
    code: Optional[str] = None
    driver_category: Optional[str] = None
    source_field: Optional[str] = None


class Recommendation(BaseModel):
    action: str
    description: str
    priority: str


class DocumentAnalysisRequest(BaseModel):
    document_text: Optional[str] = None
    document_type: Optional[str] = "denial_letter"


class DocumentAnalysisResponse(BaseModel):
    claim_id: Optional[int] = None
    document_type: str
    payer_name: Optional[str] = None
    denial_reason: Optional[str] = None
    denial_code: Optional[str] = None
    claim_amount: Optional[float] = None
    service_date: Optional[str] = None
    patient_name: Optional[str] = None
    policy_number: Optional[str] = None
    extracted_codes: Optional[List[str]] = None
    analysis: str
    recommendations: List[Recommendation]
    appeal_strategy: Optional[str] = None
    denial_workflow: Optional[DenialWorkflowAnalysisResponse] = None
    ocr_engine: Optional[str] = None
    ocr_model: Optional[str] = None
    ocr_pages: Optional[int] = None
    ocr_duration_ms: Optional[int] = None
    ocr_warnings: Optional[List[str]] = None
    document_surface_inspection: Optional[CorpusDocumentSurfaceInspectResponse] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ClaimPredictionResponse(BaseModel):
    claim_id: Optional[int] = None
    denial_prediction: float
    denial_confidence: float
    denial_reasons: List[DenialReason]
    recommendations: List[Recommendation]
    prediction_metadata: Dict[str, Any] = Field(default_factory=dict)
    human_review_required: bool = False
    human_review_status: str = "not_required"
    human_review_reasons: List[str] = Field(default_factory=list)
    human_review_threshold: float = 0.5
    human_review_next_action: str = "continue_standard_claim_workflow"
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ClaimSubmitRequest(BaseModel):
    patient_id: int
    provider_id: int
    claim_data: Dict[str, Any]
    diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None


class ClaimSubmitResponse(BaseModel):
    claim_id: int
    status: str
    denial_prediction: float
    denial_confidence: float
    denial_reasons: List[DenialReason]
    recommendations: List[Recommendation]
    prediction_metadata: Dict[str, Any] = Field(default_factory=dict)
    human_review_required: bool = False
    human_review_status: str = "not_required"
    human_review_reasons: List[str] = Field(default_factory=list)
    human_review_threshold: float = 0.5
    human_review_next_action: str = "continue_standard_claim_workflow"
    message: str


class ClaimStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)
    transition_reason: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional operator note. Raw note text is not written to audit logs.",
    )


class ClaimStatusUpdateResponse(BaseModel):
    claim_id: int
    previous_status: str
    status: str
    allowed_next_statuses: List[str]
    transition_allowed: bool = True
    message: str


class ClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    provider_id: int
    claim_data: Dict[str, Any]
    diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None
    submission_date: Optional[datetime] = None
    status: str
    denial_prediction: Optional[float] = None
    denial_confidence: Optional[float] = None
    deleted_at: Optional[datetime] = None
    denial_reasons: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    human_review_required: bool = False
    human_review_status: str = "not_required"
    human_review_reasons: List[str] = Field(default_factory=list)
    human_review_threshold: float = 0.5
    human_review_next_action: str = "continue_standard_claim_workflow"
    document_text: Optional[str] = None
    document_filename: Optional[str] = None
    document_governance: Optional[ClaimDocumentGovernance] = None
    document_available: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    patient: Optional[PatientResponse] = None


class BatchDocumentAnalysisRequest(BaseModel):
    documents: List[Dict[str, str]]
    document_type: Optional[str] = "denial_letter"


class BatchDocumentAnalysisResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[DocumentAnalysisResponse]


class BatchClaimUploadValidationIssue(BaseModel):
    message: str
    field: str
    error_code: str
    parser_stage: str
    severity: str
    claim_index: Optional[int] = None
    segment_index: Optional[int] = None
    segment_id: Optional[str] = None


class BatchClaimUploadServiceLine(BaseModel):
    segment_index: int
    segment_id: str
    procedure_code: Optional[str] = None
    procedure_modifiers: List[str] = Field(default_factory=list)
    charge_amount: Optional[float] = None
    unit_count: Optional[float] = None
    revenue_code: Optional[str] = None
    product_service_qualifier: Optional[str] = None
    diagnosis_pointers: List[str] = Field(default_factory=list)


class BatchClaimUploadResult(BaseModel):
    claim_index: int
    status: str
    claim_control_number: Optional[str] = None
    total_charge_amount: Optional[float] = None
    place_of_service_code: Optional[str] = None
    facility_code_qualifier: Optional[str] = None
    claim_frequency_code: Optional[str] = None
    payer_name: Optional[str] = None
    payer_identifier: Optional[str] = None
    diagnosis_codes: List[str] = Field(default_factory=list)
    procedure_codes: List[str] = Field(default_factory=list)
    service_line_count: int
    service_lines: List[BatchClaimUploadServiceLine] = Field(default_factory=list)
    validation_issues: List[BatchClaimUploadValidationIssue] = Field(default_factory=list)


class BatchClaimsUploadResponse(BaseModel):
    accepted: bool
    source_filename_present: bool
    source_file_extension: Optional[str] = None
    source_mime_type: Optional[str] = None
    segment_count: int
    claim_count: int
    valid_claim_count: int
    invalid_claim_count: int
    validation_issue_count: int
    interchange_control_number: Optional[str] = None
    group_control_number: Optional[str] = None
    transaction_control_number: Optional[str] = None
    document_surface_inspection: CorpusDocumentSurfaceInspectResponse
    claims: List[BatchClaimUploadResult]
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

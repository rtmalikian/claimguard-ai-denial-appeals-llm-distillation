from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import date, datetime


class DenialTrendData(BaseModel):
    period: str
    total_claims: int
    predicted_denials: int
    denial_rate: float
    top_reasons: List[Dict[str, Any]]


class DenialTrendResponse(BaseModel):
    trends: List[DenialTrendData]
    summary: Dict[str, Any]
    generated_at: datetime


class ClaimsByStatus(BaseModel):
    status: str
    count: int
    percentage: float


class TopDenialPatterns(BaseModel):
    pattern: str
    count: int
    percentage: float


class AnalyticsSummary(BaseModel):
    total_claims: int
    pending_claims: int
    processed_claims: int
    predicted_denial_rate: float
    claims_by_status: List[ClaimsByStatus]
    top_denial_patterns: List[TopDenialPatterns]


class PredictionAccuracyPeriod(BaseModel):
    period: str
    evaluated_claims: int
    predicted_denials: int
    actual_denials: int
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    accuracy: float
    precision: float
    recall: float
    false_positive_rate: float
    actual_denial_rate: float
    predicted_denial_rate: float


class PredictionAccuracyResponse(BaseModel):
    periods: List[PredictionAccuracyPeriod]
    summary: Dict[str, Any]
    generated_at: datetime


class AppealGenerateRequest(BaseModel):
    claim_id: int
    appeal_reason: str
    additional_context: Optional[str] = None


class AppealDeadlineTrackingItem(BaseModel):
    deadline_type: str
    source_stated_deadline: date | None = None
    calculated_deadline: date | None = None
    basis_date: date | None = None
    days_from_basis: int | None = None
    days_until_deadline: int | None = None
    rule_source_id: str | None = None
    source_status: str
    verification_status: str
    human_verification_required: bool = True
    assumptions: List[str] = Field(default_factory=list)
    safe_context: Dict[str, bool] = Field(default_factory=dict)


class AppealGenerateResponse(BaseModel):
    claim_id: int
    appeal_letter: str
    supporting_evidence: List[str]
    generated_at: datetime
    deadline_tracking: List[AppealDeadlineTrackingItem] = Field(default_factory=list)
    deadline_tracking_summary: Dict[str, Any] = Field(default_factory=dict)

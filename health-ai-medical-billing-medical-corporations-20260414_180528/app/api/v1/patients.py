import logging
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.db.database import get_db
from app.core.auth import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, get_client_ip, require_roles
from app.models import Patient
from app.schemas.claim import PatientCreate, PatientResponse
from app.utils.audit import log_audit

router = APIRouter(prefix="/patients", tags=["patients"])
logger = logging.getLogger(__name__)
PATIENT_SOFT_DELETE_REASON = "operator_requested_retention_or_privacy_review"


@dataclass(frozen=True)
class PatientDemographicIssue:
    field: str
    error_code: str
    parser_stage: str = "patient_demographic_validation"
    severity: str = "error"

    def safe_detail(self) -> dict[str, object]:
        return {
            "field": self.field,
            "error_code": self.error_code,
            "parser_stage": self.parser_stage,
            "severity": self.severity,
            "safe_context": {
                "raw_patient_data_included": False,
                "raw_field_value_included": False,
                "patient_identifier_included": False,
            },
        }


def _current_user_id(current_user: dict) -> Optional[int]:
    return current_user.get("id") if isinstance(current_user, dict) else None


def _request_ip(request: Optional[Request]) -> Optional[str]:
    return get_client_ip(request) if request is not None else None


def _active_patients_query(db: Session):
    return db.query(Patient).filter(Patient.deleted_at.is_(None))


def _patient_claims(patient: Patient) -> list:
    claims = getattr(patient, "claims", None) or []
    try:
        return list(claims)
    except TypeError:
        return []


def validate_patient_demographics(patient: PatientCreate) -> list[PatientDemographicIssue]:
    issues: list[PatientDemographicIssue] = []
    if patient.date_of_birth is not None and patient.date_of_birth > date.today():
        issues.append(
            PatientDemographicIssue(
                field="date_of_birth",
                error_code="future_date_of_birth",
            )
        )
    return issues


def _patient_demographic_error_detail(
    issues: list[PatientDemographicIssue],
) -> dict[str, object]:
    return {
        "error_code": "invalid_patient_demographics",
        "message": "Patient demographic metadata failed validation.",
        "issue_count": len(issues),
        "issues": [issue.safe_detail() for issue in issues],
        "safe_context": {
            "raw_patient_data_included": False,
            "raw_field_values_included": False,
            "patient_identifier_included": False,
        },
    }


def _raise_for_invalid_patient_demographics(
    patient: PatientCreate, *, endpoint_name: str
) -> None:
    issues = validate_patient_demographics(patient)
    if not issues:
        return

    logger.warning(
        "patient_demographic_validation_failed",
        extra={
            "patient_demographic_validation": {
                "endpoint": endpoint_name,
                "issue_count": len(issues),
                "issue_types": sorted({issue.error_code for issue in issues}),
                "date_of_birth_present": patient.date_of_birth is not None,
                "safe_context": {
                    "raw_patient_data_included": False,
                    "raw_field_values_included": False,
                    "patient_identifier_included": False,
                },
            }
        },
    )
    raise HTTPException(
        status_code=400,
        detail=_patient_demographic_error_detail(issues),
    )


@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient: PatientCreate,
    request: Request,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """Create a new patient."""
    _raise_for_invalid_patient_demographics(patient, endpoint_name="create_patient")

    existing = db.query(Patient).filter(Patient.mrn == patient.mrn).first()
    if existing:
        raise HTTPException(status_code=400, detail="Patient with this MRN already exists")

    db_patient = Patient(
        mrn=patient.mrn,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    log_audit(
        db=db,
        action="patient_created",
        user_id=_current_user_id(current_user),
        details={
            "patient_id": db_patient.id,
            "mrn_present": bool(patient.mrn),
            "date_of_birth_present": patient.date_of_birth is not None,
        },
        ip_address=_request_ip(request),
    )

    return db_patient


@router.get("/", response_model=List[PatientResponse])
async def list_patients(
    request: Request = None,
    skip: int = 0,
    limit: int = 100,
    first_name: Optional[str] = Query(None, description="Filter by first name"),
    last_name: Optional[str] = Query(None, description="Filter by last name"),
    dob: Optional[str] = Query(None, description="Filter by date of birth (YYYY-MM-DD)"),
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    """List patients with optional filtering."""
    query = _active_patients_query(db)

    if first_name:
        query = query.filter(func.lower(Patient.first_name).like(f"%{first_name.lower()}%"))

    if last_name:
        query = query.filter(func.lower(Patient.last_name).like(f"%{last_name.lower()}%"))

    if dob:
        query = query.filter(Patient.date_of_birth == dob)

    patients = query.order_by(Patient.created_at.desc()).offset(skip).limit(limit).all()
    log_audit(
        db=db,
        action="patients_listed",
        user_id=_current_user_id(current_user),
        details={
            "skip": skip,
            "limit": limit,
            "result_count": len(patients),
            "filter_count": sum(
                1 for value in [first_name, last_name, dob] if value is not None
            ),
            "first_name_filter_present": first_name is not None,
            "last_name_filter_present": last_name is not None,
            "dob_filter_present": dob is not None,
        },
        ip_address=_request_ip(request),
    )
    return patients


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: int,
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    """Get a patient by ID."""
    patient = (
        db.query(Patient)
        .filter(Patient.deleted_at.is_(None), Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    log_audit(
        db=db,
        action="patient_viewed",
        user_id=_current_user_id(current_user),
        details={"patient_id": patient_id, "lookup": "id"},
        ip_address=_request_ip(request),
    )
    return patient


@router.get("/mrn/{mrn}", response_model=PatientResponse)
async def get_patient_by_mrn(
    mrn: str,
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    """Get a patient by MRN."""
    patient = db.query(Patient).filter(Patient.deleted_at.is_(None), Patient.mrn == mrn).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    log_audit(
        db=db,
        action="patient_viewed",
        user_id=_current_user_id(current_user),
        details={
            "patient_id": patient.id,
            "lookup": "mrn",
            "mrn_present": bool(mrn),
        },
        ip_address=_request_ip(request),
    )
    return patient


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    patient: PatientCreate,
    request: Request,
    current_user: dict = Depends(require_roles(*WRITE_ROLES)),
    db: Session = Depends(get_db),
):
    """Update a patient."""
    db_patient = (
        db.query(Patient)
        .filter(Patient.deleted_at.is_(None), Patient.id == patient_id)
        .first()
    )
    if not db_patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    _raise_for_invalid_patient_demographics(patient, endpoint_name="update_patient")

    if patient.mrn != db_patient.mrn:
        existing = db.query(Patient).filter(Patient.mrn == patient.mrn).first()
        if existing:
            raise HTTPException(status_code=400, detail="MRN already in use")

    mrn_changed = patient.mrn != db_patient.mrn
    db_patient.mrn = patient.mrn
    db_patient.first_name = patient.first_name
    db_patient.last_name = patient.last_name
    db_patient.date_of_birth = patient.date_of_birth

    db.commit()
    db.refresh(db_patient)

    log_audit(
        db=db,
        action="patient_updated",
        user_id=_current_user_id(current_user),
        details={
            "patient_id": patient_id,
            "mrn_changed": mrn_changed,
            "date_of_birth_present": patient.date_of_birth is not None,
        },
        ip_address=_request_ip(request),
    )

    return db_patient


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(
    patient_id: int,
    request: Request,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Soft-delete a patient and any active associated claims."""
    patient = (
        db.query(Patient)
        .filter(Patient.deleted_at.is_(None), Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    deleted_at = datetime.utcnow()
    associated_claims = _patient_claims(patient)
    active_claim_count = 0
    for claim in associated_claims:
        if getattr(claim, "deleted_at", None) is None:
            active_claim_count += 1
            claim.deleted_at = deleted_at
            claim.deleted_by_user_id = _current_user_id(current_user)
            claim.deletion_reason = PATIENT_SOFT_DELETE_REASON

    patient.deleted_at = deleted_at
    patient.deleted_by_user_id = _current_user_id(current_user)
    patient.deletion_reason = PATIENT_SOFT_DELETE_REASON
    db.commit()

    log_audit(
        db=db,
        action="patient_deleted",
        user_id=_current_user_id(current_user),
        details={
            "patient_id": patient_id,
            "soft_deleted": True,
            "associated_claim_count": active_claim_count,
        },
        ip_address=_request_ip(request),
    )


@router.post("/{patient_id}/restore", response_model=PatientResponse)
async def restore_patient(
    patient_id: int,
    request: Request,
    current_user: dict = Depends(require_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Restore a soft-deleted patient record."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    was_deleted = patient.deleted_at is not None
    if was_deleted:
        patient.deleted_at = None
        patient.deleted_by_user_id = None
        patient.deletion_reason = None
        db.commit()
        db.refresh(patient)

    log_audit(
        db=db,
        action="patient_restored",
        user_id=_current_user_id(current_user),
        details={
            "patient_id": patient_id,
            "was_deleted": was_deleted,
            "associated_claims_restored": False,
        },
        ip_address=_request_ip(request),
    )
    return patient

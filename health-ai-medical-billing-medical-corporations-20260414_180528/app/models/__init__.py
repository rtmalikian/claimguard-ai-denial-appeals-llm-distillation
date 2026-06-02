from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Text,
    ForeignKey,
    JSON,
    Date,
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.db.database import Base
from app.services.claim_state import CANONICAL_CLAIM_STATUSES, CLAIM_STATUS_PENDING
from app.utils.healthcare_codes import is_valid_npi, normalize_healthcare_code


CLAIM_STATUS_CHECK_NAME = "ck_claims_status_canonical"
CLAIM_STATUS_CHECK_SQL = (
    "status IN ("
    + ", ".join(repr(status) for status in CANONICAL_CLAIM_STATUSES)
    + ")"
)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    mrn = Column(String(50), unique=True, index=True, nullable=False)
    first_name = Column(String(100), index=True, nullable=True)
    last_name = Column(String(100), index=True, nullable=True)
    date_of_birth = Column(Date, nullable=True, index=True)
    demographics_encrypted = Column(Text, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id = Column(Integer, nullable=True, index=True)
    deletion_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    claims = relationship("Claim", back_populates="patient")


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    npi = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    specialty = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    claims = relationship("Claim", back_populates="provider")

    @validates("npi")
    def validate_npi(self, key: str, value: object) -> str:
        normalized_npi = normalize_healthcare_code(value)
        if not is_valid_npi(normalized_npi):
            raise ValueError("provider_npi_failed_check_digit_validation")
        return normalized_npi


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="viewer", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(CLAIM_STATUS_CHECK_SQL, name=CLAIM_STATUS_CHECK_NAME),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    claim_data = Column(JSON, nullable=False)
    diagnosis_codes = Column(JSON, nullable=True)
    procedure_codes = Column(JSON, nullable=True)
    submission_date = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(50), default=CLAIM_STATUS_PENDING, nullable=False, index=True)
    denial_prediction = Column(Float, nullable=True, index=True)
    denial_confidence = Column(Float, nullable=True)
    denial_reasons = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id = Column(Integer, nullable=True, index=True)
    deletion_reason = Column(String(255), nullable=True)
    document_text = Column(Text, nullable=True)
    document_filename = Column(String(255), nullable=True)
    document_access_scope = Column(String(32), nullable=False, default="billing_team", index=True)
    document_retention_until = Column(DateTime(timezone=True), nullable=True, index=True)
    document_deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    document_deleted_by_user_id = Column(Integer, nullable=True, index=True)
    document_deletion_reason = Column(String(255), nullable=True)
    document_created_by_user_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient", back_populates="claims")
    provider = relationship("Provider", back_populates="claims")
    audit_logs = relationship("AuditLog", back_populates="claim")


class DenialPattern(Base):
    __tablename__ = "denial_patterns"

    id = Column(Integer, primary_key=True, index=True)
    icd_code = Column(String(20), index=True, nullable=True)
    cpt_code = Column(String(20), index=True, nullable=True)
    payer_id = Column(String(50), index=True, nullable=True)
    denial_rate = Column(Float, default=0.0)
    common_reasons = Column(JSON, nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RetrievalSourceDocument(Base):
    __tablename__ = "retrieval_source_documents"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(64), unique=True, nullable=False, index=True)
    title_encrypted = Column(Text, nullable=False)
    source_type = Column(String(64), nullable=False, index=True)
    jurisdiction = Column(String(64), nullable=True, index=True)
    payer_type = Column(String(64), nullable=True, index=True)
    source_date = Column(String(32), nullable=True, index=True)
    source_url_encrypted = Column(Text, nullable=True)
    phi_status = Column(String(32), nullable=False, default="unknown", index=True)
    license_status = Column(String(64), nullable=False, default="review_required", index=True)
    access_scope = Column(String(32), nullable=False, default="owner", index=True)
    retention_until = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by_user_id = Column(Integer, nullable=True, index=True)
    deletion_reason = Column(String(255), nullable=True)
    created_by_user_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    chunks = relationship(
        "RetrievalSourceChunk",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class RetrievalSourceChunk(Base):
    __tablename__ = "retrieval_source_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String(96), unique=True, nullable=False, index=True)
    source_document_id = Column(
        Integer,
        ForeignKey("retrieval_source_documents.id"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False, index=True)
    text_encrypted = Column(Text, nullable=False)
    page_number = Column(String(32), nullable=True)
    section_label_encrypted = Column(Text, nullable=True)
    extra_metadata_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source = relationship("RetrievalSourceDocument", back_populates="chunks")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    claim = relationship("Claim", back_populates="audit_logs")

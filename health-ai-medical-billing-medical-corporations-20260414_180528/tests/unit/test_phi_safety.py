import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import EncryptionService, generate_fernet_key
from app.db.database import Base
from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisRequest,
    RetrievalSourceCreateRequest,
)
from app.services.denial_workflow import DenialWorkflowService
from app.services.retrieval_store import RetrievalStoreError, RetrievalStoreService
from app.utils.phi import scan_text_for_phi, serialize_phi_findings


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


def test_phi_scanner_returns_metadata_without_values():
    text = (
        "Synthetic denial notice\n"
        "Patient: Sample Person\n"
        "Member ID: SYN-77777\n"
        "Contact: 555-010-9999\n"
    )

    serialized = serialize_phi_findings(scan_text_for_phi(text))
    payload = json.dumps(serialized)

    assert {item["finding_type"] for item in serialized} >= {
        "patient_name_label",
        "member_id_label",
        "phone_like",
    }
    assert "Sample Person" not in payload
    assert "SYN-77777" not in payload
    assert "555-010-9999" not in payload


@pytest.mark.asyncio
async def test_denial_workflow_adds_phi_review_gate_without_echoing_values():
    text = (
        "Synthetic denial notice\n"
        "Payer: Example Health\n"
        "Claim Number: SYN-9001\n"
        "Member ID: SYN-MEMBER-1\n"
        "Reason for Denial: missing documentation."
    )

    result = await DenialWorkflowService().analyze(
        DenialWorkflowAnalysisRequest(document_text=text, source_document_id="synthetic-phi-1")
    )
    phi_payload = json.dumps(result.phi_scan.model_dump(mode="json"))

    assert result.phi_scan.status == "findings_detected"
    assert result.phi_scan.review_required is True
    assert result.model_metadata["phi_scan"]["values_redacted"] is True
    assert any(
        task.task == "Verify minimum necessary PHI scope before export or submission"
        for task in result.missing_needs_human_verification
    )
    assert any(
        check.check == "phi_minimum_necessary_review" and check.status == "blocker"
        for check in result.quality_checks
    )
    assert "SYN-9001" not in phi_payload
    assert "SYN-MEMBER-1" not in phi_payload


def test_retrieval_source_rejects_no_phi_declaration_when_findings_exist(store):
    with pytest.raises(RetrievalStoreError) as exc_info:
        store.create_source(
            RetrievalSourceCreateRequest(
                title="Synthetic Source With Identifier Label",
                source_type="plan_document",
                document_text=(
                    "Synthetic source text with Claim Number: SYN-777 and enough "
                    "additional words to pass chunking and length checks."
                ),
                phi_status="no_phi",
                license_status="synthetic_internal",
            )
        )

    assert "cannot be declared no_phi" in str(exc_info.value)


def test_retrieval_source_requires_review_for_deidentified_findings(store):
    with pytest.raises(RetrievalStoreError) as exc_info:
        store.create_source(
            RetrievalSourceCreateRequest(
                title="Synthetic Deidentified Source",
                source_type="plan_document",
                document_text=(
                    "Synthetic source text with Member ID: SYN-MEMBER and enough "
                    "additional words to pass chunking and length checks."
                ),
                phi_status="deidentified",
                license_status="synthetic_internal",
            )
        )

    assert "deidentified sources require privacy review" in str(exc_info.value)

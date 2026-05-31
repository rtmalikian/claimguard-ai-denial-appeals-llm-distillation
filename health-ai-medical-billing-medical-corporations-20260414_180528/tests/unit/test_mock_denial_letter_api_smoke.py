import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
from app.models import Claim
from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisResponse,
    SourceReference,
    SubmissionPlan,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_CORPUS_DIR = (
    REPO_ROOT / "llm-distill" / "data" / "corpus" / "generated_synthetic_pairs"
)
VISUAL_MANIFEST_PATH = GENERATED_CORPUS_DIR / "visual_manifest_synthetic_900.json"
API_UPLOAD_SAMPLE_SIZE = 12


def _visual_manifest_records() -> list[dict]:
    payload = json.loads(VISUAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    return payload["records"]


def _denial_records() -> list[dict]:
    return [
        record
        for record in _visual_manifest_records()
        if record["document_role"] == "denial_letter"
    ]


def _representative_denial_records() -> list[dict]:
    records_by_layout = {}
    for record in _denial_records():
        records_by_layout.setdefault(record["layout_profile"], record)
    selected = [records_by_layout[key] for key in sorted(records_by_layout)]
    assert len(selected) == API_UPLOAD_SAMPLE_SIZE
    return selected


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _billing_headers() -> dict[str, str]:
    token = create_access_token(
        {
            "sub": "7",
            "email": "billing.example.test",
            "role": "billing_staff",
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _analysis_result(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        document_type="denial_letter",
        payer_name=f"Example Plan {index}",
        denial_reason="Synthetic denial rationale requires human appeal review.",
        denial_code=f"SYN{index:02d}",
        claim_amount=float(400 + index),
        service_date=None,
        patient_name=None,
        policy_number=None,
        extracted_codes=["99213"],
        analysis='{"summary": "Synthetic API smoke analysis", "appeal_strength": "moderate"}',
        recommendations=[],
        appeal_strategy="Draft appeal for human review; not filing-ready.",
        analyzed_at=datetime(2026, 1, index, 12, 0, 0),
    )


def _workflow_response(index: int) -> DenialWorkflowAnalysisResponse:
    source = SourceReference(
        source_status="known_from_documents",
        source_document_id=f"synthetic-api-smoke-{index}",
        extraction_method="api",
        confidence=0.9,
        human_verified=False,
    )
    return DenialWorkflowAnalysisResponse(
        document_type="denial_letter",
        case_summary="Synthetic denial letter API smoke case.",
        known_from_documents=[],
        inferred=[],
        missing_needs_human_verification=[],
        cited_rules=[],
        payer_name=f"Example Plan {index}",
        appeal_strategy="Prepare a draft appeal for human review.",
        submission_plan=SubmissionPlan(
            route="internal_appeal",
            required_channel="verify_locally",
            proof_to_capture=["human reviewer approval"],
            blocker_tasks=["verify no PHI before filing"],
            source=source,
        ),
        human_review_required=True,
        warnings=[],
    )


def test_generated_mock_denial_and_appeal_corpus_has_documented_variation():
    records = _visual_manifest_records()
    denial_records = [
        record for record in records if record["document_role"] == "denial_letter"
    ]
    appeal_records = [
        record for record in records if record["document_role"] == "appeal_letter"
    ]

    assert len(records) == 1800
    assert len(denial_records) == 900
    assert len(appeal_records) == 900
    assert {record["split"] for record in records} == {"train", "valid", "test"}
    assert len({record["font_family"] for record in records}) == 8
    assert len({record["layout_profile"] for record in records}) == 12
    assert len({record["typography_profile"] for record in records}) == 8
    assert max(record["word_count"] for record in records) - min(
        record["word_count"] for record in records
    ) >= 50

    for record in records:
        assert record["synthetic_only"] is True
        assert record["real_claim_data_used"] is False
        assert record["real_patient_data_used"] is False
        assert (REPO_ROOT / record["source_text_path"]).exists()
        assert (REPO_ROOT / record["rendered_html_path"]).exists()


def test_representative_rendered_denial_letters_feed_upload_api_without_phi(
    db_session,
):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    upload_records = _representative_denial_records()

    async def fake_analyze_document(*args, **kwargs):
        document_text = kwargs["document_text"]
        document_type = kwargs["document_type"]
        assert document_type == "denial_letter"
        assert "Synthetic visual profile" in document_text
        assert "font-family:" in document_text
        return _analysis_result(fake_analyze_document.call_count)

    fake_analyze_document.call_count = 0

    async def counted_analyze_document(*args, **kwargs):
        fake_analyze_document.call_count += 1
        return await fake_analyze_document(*args, **kwargs)

    async def fake_denial_workflow(*args, **kwargs):
        assert kwargs["document_type"] == "denial_letter"
        assert "Synthetic visual profile" in kwargs["document_text"]
        return _workflow_response(fake_denial_workflow.call_count)

    fake_denial_workflow.call_count = 0

    async def counted_denial_workflow(**kwargs):
        fake_denial_workflow.call_count += 1
        return await fake_denial_workflow(**kwargs)

    try:
        with patch(
            "app.api.v1.claims.DocumentAnalysisService.analyze_document",
            new=AsyncMock(side_effect=counted_analyze_document),
        ), patch(
            "app.api.v1.claims._build_denial_workflow",
            new=AsyncMock(side_effect=counted_denial_workflow),
        ):
            for record in upload_records:
                letter_text = (REPO_ROOT / record["rendered_html_path"]).read_text(
                    encoding="utf-8"
                )
                filename = f"{record['document_id'].lower()}-rendered.txt"
                response = client.post(
                    "/api/v1/claims/upload-document",
                    headers=_billing_headers(),
                    files={
                        "file": (
                            filename,
                            letter_text.encode("utf-8"),
                            "text/plain",
                        )
                    },
                )

                assert response.status_code == 200
                body = response.json()
                assert body["document_type"] == "denial_letter"
                assert body["claim_id"] is not None
                assert body["document_surface_inspection"]["values_redacted"] is True
                assert body["document_surface_inspection"]["surface_count"] >= 1
                assert body["document_surface_inspection"]["surface_scans"]
                assert "SYN-CASE-" not in response.text
                assert "[PATIENT_" not in response.text
                assert filename not in response.text

        claims = db_session.query(Claim).order_by(Claim.id).all()
        assert fake_analyze_document.call_count == len(upload_records)
        assert fake_denial_workflow.call_count == len(upload_records)
        assert len(claims) == len(upload_records)
        assert {claim.document_access_scope for claim in claims} == {"billing_team"}
        assert all("Synthetic visual profile" in claim.document_text for claim in claims)
    finally:
        app.dependency_overrides.clear()

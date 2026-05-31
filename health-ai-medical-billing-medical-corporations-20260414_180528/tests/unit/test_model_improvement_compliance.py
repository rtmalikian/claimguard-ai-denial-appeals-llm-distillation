import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import EncryptionService, generate_fernet_key
from app.db.database import Base
from app.schemas.corpus import CorpusImportRequest, CorpusManifestRecord
from app.schemas.denial_workflow import RetrievalSourceCreateRequest
from app.services.corpus import CorpusSafetyService
from app.services.retrieval_store import RetrievalStoreError, RetrievalStoreService
from app.utils.model_improvement import model_improvement_compliance_status


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


def _synthetic_source_request(**overrides) -> RetrievalSourceCreateRequest:
    payload = {
        "title": "Synthetic Reviewed Source",
        "source_type": "synthetic_policy",
        "document_text": (
            "Synthetic no-PHI source for model improvement compliance tests. "
            "Appeal routing evidence is fully deidentified and reviewable."
        ),
        "phi_status": "no_phi",
        "license_status": "synthetic_internal",
    }
    payload.update(overrides)
    return RetrievalSourceCreateRequest(**payload)


def _enable_model_improvement(monkeypatch):
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED", True)
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED", True)
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED", True)
    monkeypatch.setattr(
        settings,
        "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION",
        "synthetic-consent-v1",
    )
    monkeypatch.setattr(
        settings,
        "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE",
        "synthetic-approval-reference",
    )


def test_model_improvement_status_defaults_to_blocked(monkeypatch):
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED", False)
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_LEGAL_APPROVED", False)
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_BAA_CONFIRMED", False)
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_CONSENT_NOTICE_VERSION", "")
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_APPROVAL_REFERENCE", "")

    status = model_improvement_compliance_status()

    assert status.ready is False
    assert "user_data_model_improvement_disabled" in status.blockers
    assert "legal_approval_missing" in status.blockers
    assert "baa_confirmation_missing" in status.blockers
    assert "consent_notice_version_missing" in status.blockers
    assert "approval_reference_missing" in status.blockers


def test_model_improvement_opt_in_is_blocked_until_legal_baa_and_consent_ready(
    monkeypatch,
    store,
):
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED", False)

    with pytest.raises(RetrievalStoreError) as exc_info:
        store.create_source(
            _synthetic_source_request(
                user_data_opt_in_for_model_improvement=True,
                model_improvement_legal_approval_attested=True,
                model_improvement_baa_attested=True,
                model_improvement_consent_attested=True,
                model_improvement_consent_notice_version="synthetic-consent-v1",
            )
        )

    assert "disabled pending legal, BAA, and consent readiness" in str(exc_info.value)


def test_model_improvement_opt_in_requires_request_attestations(monkeypatch, store):
    _enable_model_improvement(monkeypatch)

    with pytest.raises(RetrievalStoreError) as exc_info:
        store.create_source(
            _synthetic_source_request(
                user_data_opt_in_for_model_improvement=True,
                model_improvement_legal_approval_attested=True,
                model_improvement_baa_attested=True,
                model_improvement_consent_attested=False,
                model_improvement_consent_notice_version="synthetic-consent-v1",
            )
        )

    assert "requires consent attestation" in str(exc_info.value)


def test_model_improvement_opt_in_succeeds_when_all_gates_are_attested(
    monkeypatch,
    store,
):
    _enable_model_improvement(monkeypatch)

    created = store.create_source(
        _synthetic_source_request(
            user_data_opt_in_for_model_improvement=True,
            model_improvement_legal_approval_attested=True,
            model_improvement_baa_attested=True,
            model_improvement_consent_attested=True,
            model_improvement_consent_notice_version="synthetic-consent-v1",
        )
    )

    assert created.source_id.startswith("SRC-LOCAL-")


def test_approved_corpus_import_does_not_auto_opt_in_user_data(monkeypatch, db_session):
    monkeypatch.setattr(settings, "USER_DATA_MODEL_IMPROVEMENT_ENABLED", False)
    record = CorpusManifestRecord(
        source_id="SRC-SYN-COMPLIANCE",
        document_id="DOC-SYN-COMPLIANCE",
        pair_id="PAIR-SYN-COMPLIANCE",
        source_type="synthetic_internal",
        document_role="denial_letter",
        source_url_or_path="synthetic://compliance",
        checksum="sha256:synthetic-compliance",
        phi_status="deidentified",
        deidentification_status="training_eligible",
        license_status="synthetic_allowed",
        review_status="privacy_review_passed",
        residual_risk_score=0.0,
        training_eligible=True,
        split="train",
        micro_skill_ids=[f"MS{index:02d}" for index in range(1, 13)],
    )

    result = CorpusSafetyService().import_approved(
        db_session,
        CorpusImportRequest(
            record=record,
            document_text=(
                "Synthetic deidentified denial example using placeholders only. "
                "Appeal route evidence is present for training export tests."
            ),
        ),
        created_by_user_id=9,
    )

    assert result.imported is True
    assert result.retrieval_source is not None

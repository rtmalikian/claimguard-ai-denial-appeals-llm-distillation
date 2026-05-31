import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.schemas.corpus import (
    CorpusDeidentifyRequest,
    CorpusImportRequest,
    CorpusManifestRecord,
    CorpusReviewDecisionRequest,
)
from app.services.corpus import CorpusSafetyService


def _training_record(document_id: str, role: str, pair_id: str = "PAIR-1") -> CorpusManifestRecord:
    return CorpusManifestRecord(
        source_id=f"SRC-{document_id}",
        document_id=document_id,
        pair_id=pair_id,
        source_type="synthetic_internal",
        document_role=role,  # type: ignore[arg-type]
        source_url_or_path=f"synthetic://{document_id}",
        checksum=f"sha256:{document_id}",
        phi_status="deidentified",
        deidentification_status="training_eligible",
        license_status="synthetic_allowed",
        review_status="privacy_review_passed",
        residual_risk_score=0.0,
        training_eligible=True,
        split="train",
        micro_skill_ids=[f"MS{index:02d}" for index in range(1, 13)],
        reviewer_id="privacy-reviewer-synthetic",
        review_method="synthetic_fixture",
    )


def test_deidentify_replaces_identifier_values_with_placeholders():
    result = CorpusSafetyService().deidentify(
        CorpusDeidentifyRequest(
            document_text=(
                "Patient: Sample Person\n"
                "Member ID: SYN-MEMBER-123\n"
                "Claim Number: SYN-CLAIM-456\n"
                "Authorization: SYN-AUTH-789\n"
                "DOB: 01/02/1970\n"
                "Contact: 555-010-1111\n"
                "Email: sample.person@example.test\n"
            ),
            source_id="SRC-SYN-DEID",
            document_id="DOC-SYN-DEID",
        )
    )

    assert "[PATIENT_1]" in result.deidentified_text
    assert "[MEMBER_ID_1]" in result.deidentified_text
    assert "[CLAIM_ID_1]" in result.deidentified_text
    assert "[AUTH_ID_1]" in result.deidentified_text
    assert "[DATE_BIRTH_1]" in result.deidentified_text
    assert "[PHONE_1]" in result.deidentified_text
    assert "[EMAIL_1]" in result.deidentified_text
    assert "Sample Person" not in result.deidentified_text
    assert "SYN-MEMBER-123" not in result.deidentified_text
    assert "sample.person@example.test" not in result.deidentified_text
    assert result.training_eligible is False
    assert result.human_review_required is True


def test_deidentify_contextual_rare_facts_require_expert_determination():
    result = CorpusSafetyService().deidentify(
        CorpusDeidentifyRequest(
            document_text=(
                "The appeal narrative describes a 92-year-old beneficiary in a small town. "
                "The service involved an ultra-rare custom implant and a $125000 charge."
            ),
            source_id="SRC-CONTEXT",
            document_id="DOC-CONTEXT",
        )
    )

    finding_types = {finding.finding_type for finding in result.contextual_risk_findings}

    assert result.deidentification_status == "expert_determination_required"
    assert result.contextual_risk_finding_count >= 4
    assert result.residual_risk_score > 0.2
    assert result.training_eligible is False
    assert result.human_review_required is True
    assert {
        "age_over_89",
        "small_geography_or_unique_provider",
        "rare_condition_or_device",
        "unusual_dollar_amount",
    }.issubset(finding_types)
    assert any("expert determination" in warning for warning in result.warnings)


def test_manifest_blocks_raw_training_eligible_record():
    record = _training_record("DOC-BLOCKED", "denial_letter")
    record.deidentification_status = "raw_quarantined"
    record.phi_status = "contains_phi"
    record.review_status = "not_reviewed"
    record.residual_risk_score = 0.9

    status = CorpusSafetyService().validate_manifest([record])

    issue_codes = {issue.code for issue in status.issues}
    assert "training_phi_status_blocked" in issue_codes
    assert "training_deidentification_status_blocked" in issue_codes
    assert "training_review_blocked" in issue_codes
    assert "training_residual_risk_blocked" in issue_codes
    assert status.ready_for_training_export is False


def test_manifest_requires_paired_denial_and_appeal_roles():
    denial = _training_record("DOC-DENIAL", "denial_letter")
    appeal = _training_record("DOC-APPEAL", "appeal_letter")

    status = CorpusSafetyService().validate_manifest([denial, appeal])

    assert status.training_eligible_count == 2
    assert status.blocked_count == 0
    assert "paired_denial_appeal_examples" not in status.missing_categories
    assert status.ready_for_training_export is True


def test_import_approved_corpus_document_uses_encrypted_retrieval_store():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        record = _training_record("DOC-IMPORT", "denial_letter")
        result = CorpusSafetyService().import_approved(
            session,
            CorpusImportRequest(
                record=record,
                document_text=(
                    "Synthetic deidentified denial example. Member ID: [MEMBER_ID_1]. "
                    "Claim Number: [CLAIM_ID_1]. Appeal route evidence is present."
                ),
            ),
            created_by_user_id=7,
        )

        assert result.imported is True
        assert result.retrieval_source is not None
        assert result.retrieval_source.source_type == "corpus_denial_letter"
        assert result.retrieval_source.phi_status == "deidentified"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_review_decision_blocks_training_without_required_reviews():
    record = _training_record("DOC-REVIEW-BLOCK", "denial_letter")
    record.training_eligible = False
    record.deidentification_status = "machine_deidentified"
    record.review_status = "not_reviewed"
    record.split = "none"

    result = CorpusSafetyService().apply_review_decision(
        CorpusReviewDecisionRequest(
            record=record,
            reviewer_id="privacy-reviewer-synthetic",
            review_method="privacy_review",
            decision="approve_for_training",
            phi_status="deidentified",
            license_status="synthetic_allowed",
            split="train",
            micro_skill_ids=[f"MS{index:02d}" for index in range(1, 13)],
            residual_risk_score=0.0,
            training_decision_note="Synthetic reviewer noted no raw values in the metadata packet.",
        )
    )

    assert result.approved_for_training is False
    assert result.record.training_eligible is False
    assert "privacy_review_not_completed" in result.blockers
    assert "license_review_not_completed" in result.blockers
    assert "residual_risk_review_not_completed" in result.blockers


def test_review_decision_approves_training_when_all_gates_pass():
    record = _training_record("DOC-REVIEW-APPROVE", "appeal_letter")
    record.training_eligible = False
    record.deidentification_status = "machine_deidentified"
    record.review_status = "not_reviewed"
    record.split = "none"
    record.micro_skill_ids = []

    result = CorpusSafetyService().apply_review_decision(
        CorpusReviewDecisionRequest(
            record=record,
            reviewer_id="privacy-reviewer-synthetic",
            review_method="privacy_review",
            decision="approve_for_training",
            phi_status="deidentified",
            license_status="synthetic_allowed",
            split="valid",
            micro_skill_ids=[f"MS{index:02d}" for index in range(1, 13)],
            residual_risk_score=0.0,
            privacy_review_completed=True,
            license_review_completed=True,
            residual_risk_review_completed=True,
            training_decision_note="Synthetic review confirms metadata-only approval for local training export.",
            review_findings=["No unresolved scanner findings in reviewed metadata."],
        )
    )

    assert result.approved_for_training is True
    assert result.blockers == []
    assert result.record.training_eligible is True
    assert result.record.review_status == "training_approved"
    assert result.record.deidentification_status == "training_eligible"
    assert result.record.split == "valid"
    assert result.record.privacy_review_completed is True
    assert result.record.license_review_completed is True
    assert result.record.residual_risk_review_completed is True
    assert result.validation.issues == []


def test_review_decision_requires_expert_determination_for_contextual_risk():
    record = _training_record("DOC-REVIEW-EXPERT", "denial_letter")
    record.training_eligible = False
    record.deidentification_status = "expert_determination_required"
    record.review_status = "expert_determination_required"
    record.split = "none"

    result = CorpusSafetyService().apply_review_decision(
        CorpusReviewDecisionRequest(
            record=record,
            reviewer_id="expert-reviewer-synthetic",
            review_method="privacy_review",
            decision="approve_for_training",
            phi_status="deidentified",
            license_status="synthetic_allowed",
            split="test",
            micro_skill_ids=[f"MS{index:02d}" for index in range(1, 13)],
            residual_risk_score=0.0,
            privacy_review_completed=True,
            license_review_completed=True,
            residual_risk_review_completed=True,
            reviewed_contextual_risk_finding_count=1,
            training_decision_note="Synthetic contextual risk reviewed but expert gate remains open.",
        )
    )

    assert result.approved_for_training is False
    assert result.record.training_eligible is False
    assert result.record.deidentification_status == "expert_determination_required"
    assert "expert_determination_required" in result.blockers


def test_review_decision_excludes_record_without_training_eligibility():
    record = _training_record("DOC-REVIEW-EXCLUDE", "denial_letter")
    result = CorpusSafetyService().apply_review_decision(
        CorpusReviewDecisionRequest(
            record=record,
            reviewer_id="privacy-reviewer-synthetic",
            review_method="privacy_review",
            decision="exclude",
            phi_status="deidentified",
            license_status="review_required",
            residual_risk_score=0.5,
            training_decision_note="Synthetic reviewer excluded the record from model training.",
            review_findings=["Excluded for unresolved review metadata."],
        )
    )

    assert result.approved_for_training is False
    assert result.record.training_eligible is False
    assert result.record.review_status == "excluded"
    assert result.record.deidentification_status == "qa_failed"
    assert result.record.split == "none"


def test_review_queue_summarizes_manifest_metadata_without_source_locations(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    candidate = CorpusManifestRecord(
        source_id="SRC-QUEUE-DENIAL",
        document_id="DOC-QUEUE-DENIAL",
        pair_id="PAIR-QUEUE",
        source_type="real_deidentified_pair",
        document_role="denial_letter",
        source_url_or_path="quarantine/private/raw-denial-file.txt",
        checksum="sha256:queue-denial",
        phi_status="deidentified",
        deidentification_status="machine_deidentified",
        license_status="reviewed_allowed",
        review_status="not_reviewed",
        residual_risk_score=0.1,
        training_eligible=False,
        split="none",
        micro_skill_ids=[],
    )
    manifest_path.write_text(
        json.dumps({"records": [candidate.model_dump(mode="json")]}),
        encoding="utf-8",
    )

    result = CorpusSafetyService(manifest_path=manifest_path).review_queue()

    assert result.values_redacted is True
    assert result.record_count == 1
    assert result.queue_item_count == 1
    assert result.needs_review_count == 1
    assert result.missing_pair_count == 1
    item = result.items[0]
    assert not hasattr(item, "source_url_or_path")
    assert not hasattr(item, "checksum")
    assert item.ready_for_review_decision is True
    assert item.production_corpus_candidate is True
    assert "privacy_review_required_after_machine_deidentification" in item.blockers
    assert "paired_denial_appeal_record_missing" in item.blockers
    assert item.next_action == "add_missing_denial_or_appeal_pair_record"


def test_review_queue_marks_complete_production_pair_export_ready(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    review_timestamp = datetime(2026, 5, 30, 18, 30, tzinfo=timezone.utc)
    records = []
    for role in ("denial_letter", "appeal_letter"):
        records.append(
            CorpusManifestRecord(
                source_id=f"SRC-QUEUE-{role}",
                document_id=f"DOC-QUEUE-{role}",
                pair_id="PAIR-QUEUE-PROD",
                source_type="real_deidentified_pair",
                document_role=role,  # type: ignore[arg-type]
                source_url_or_path=f"reviewed/{role}.txt",
                checksum=f"sha256:{role}",
                phi_status="deidentified",
                deidentification_status="training_eligible",
                license_status="reviewed_allowed",
                review_status="training_approved",
                residual_risk_score=0.0,
                training_eligible=True,
                split="train",
                micro_skill_ids=["MS01"],
                reviewer_id="privacy-reviewer-synthetic",
                review_timestamp=review_timestamp,
                review_method="privacy_review",
                training_decision_note="Synthetic test metadata confirms training approval.",
            )
        )
    manifest_path.write_text(
        json.dumps({"records": [record.model_dump(mode="json") for record in records]}),
        encoding="utf-8",
    )

    result = CorpusSafetyService(manifest_path=manifest_path).review_queue()

    assert result.training_eligible_count == 2
    assert result.production_candidate_count == 2
    assert result.missing_pair_count == 0
    assert {item.ready_for_training_export for item in result.items} == {True}
    assert {item.production_corpus_candidate for item in result.items} == {True}
    assert {tuple(item.blockers) for item in result.items} == {()}
    assert {
        item.next_action for item in result.items
    } == {"ready_for_production_corpus_export_review"}

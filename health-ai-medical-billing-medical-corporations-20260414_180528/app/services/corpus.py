import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import RetrievalSourceChunk, RetrievalSourceDocument  # noqa: F401
from app.schemas.corpus import (
    CorpusContextualRiskFinding,
    CorpusDeidentifyRequest,
    CorpusDeidentifyResponse,
    CorpusDocumentSurfaceInspectRequest,
    CorpusDocumentSurfaceInspectResponse,
    CorpusDocumentSurfaceScan,
    CorpusImportRequest,
    CorpusImportResponse,
    CorpusManifestIssue,
    CorpusManifestRecord,
    CorpusReplacement,
    CorpusReviewDecisionRequest,
    CorpusReviewDecisionResponse,
    CorpusReviewQueueItem,
    CorpusReviewQueueResponse,
    CorpusStatusResponse,
)
from app.schemas.denial_workflow import PhiScanSummary, RetrievalSourceCreateRequest
from app.utils.phi import phi_scan_summary, scan_text_for_phi, serialize_phi_findings


OUTER_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = OUTER_ROOT / "llm-distill" / "data" / "corpus" / "manifest.json"
MAX_TRAINING_RESIDUAL_RISK = 0.2
REQUIRED_ROLES = {"denial_letter", "appeal_letter"}
PRODUCTION_PAIR_SOURCE_TYPES = {
    "approved_public_denial_appeal_pair",
    "public_government_deidentified_pair",
    "public_government_denial_appeal_pair",
    "real_deidentified_pair",
    "real_world_deidentified_pair",
}
TRAINING_LICENSE_BLOCKLIST = {"review_required", "unknown", "prohibited"}


DEIDENTIFICATION_PATTERNS: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "patient_name",
        "[PATIENT_1]",
        re.compile(r"(\b(?:patient|member)\s*(?:name)?\s*:\s*)([^\n\r]+)", re.IGNORECASE),
        r"\1[PATIENT_1]",
    ),
    (
        "member_id",
        "[MEMBER_ID_1]",
        re.compile(
            r"(\b(?:member id|subscriber id|policy number|policy #|member #)\s*[:#-]?\s*)([A-Z0-9-]+)",
            re.IGNORECASE,
        ),
        r"\1[MEMBER_ID_1]",
    ),
    (
        "claim_id",
        "[CLAIM_ID_1]",
        re.compile(r"(\b(?:claim number|claim #|ICN|DCN)\s*[:#-]?\s*)([A-Z0-9-]+)", re.IGNORECASE),
        r"\1[CLAIM_ID_1]",
    ),
    (
        "auth_id",
        "[AUTH_ID_1]",
        re.compile(r"(\b(?:authorization|auth number|prior auth)\s*[:#-]?\s*)([A-Z0-9-]+)", re.IGNORECASE),
        r"\1[AUTH_ID_1]",
    ),
    (
        "date_of_birth",
        "[DATE_BIRTH_1]",
        re.compile(
            r"(\b(?:DOB|date of birth)\s*[:#-]?\s*)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        r"\1[DATE_BIRTH_1]",
    ),
    (
        "date_of_service",
        "[DATE_SERVICE_1]",
        re.compile(
            r"(\b(?:date of service|service date|DOS)\s*[:#-]?\s*)(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        r"\1[DATE_SERVICE_1]",
    ),
    (
        "phone",
        "[PHONE_1]",
        re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        "[PHONE_1]",
    ),
    (
        "email",
        "[EMAIL_1]",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        "[EMAIL_1]",
    ),
    (
        "ssn",
        "[SSN_1]",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN_1]",
    ),
    (
        "street_address",
        "[ADDRESS_1]",
        re.compile(
            r"\b\d{2,6}\s+[A-Z0-9][A-Z0-9.'-]*(?:\s+[A-Z0-9][A-Z0-9.'-]*){0,4}\s+"
            r"(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd)\b",
            re.IGNORECASE,
        ),
        "[ADDRESS_1]",
    ),
]

CONTEXTUAL_RISK_PATTERNS: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "age_over_89",
        "high",
        re.compile(
            r"\b(?:(?:age|aged)\s*[:#-]?\s*(?:9[0-9]|1[0-2][0-9])|"
            r"(?:9[0-9]|1[0-2][0-9])[-\s]?year[-\s]?old)\b",
            re.IGNORECASE,
        ),
        "Generalize age above 89 before any training eligibility decision.",
    ),
    (
        "rare_condition_or_device",
        "medium",
        re.compile(
            r"\b(?:rare|ultra-rare|orphan disease|experimental implant|"
            r"custom implant|one-of-a-kind|transplant complication)\b",
            re.IGNORECASE,
        ),
        "Review rare clinical/device facts for re-identification risk.",
    ),
    (
        "small_geography_or_unique_provider",
        "medium",
        re.compile(
            r"\b(?:small town|rural county|frontier county|only specialist|"
            r"sole provider|single provider|local news)\b",
            re.IGNORECASE,
        ),
        "Generalize geography/provider uniqueness before training use.",
    ),
    (
        "exact_unlabeled_timeline",
        "medium",
        re.compile(
            r"\b(?:on|from|through|between|after|before)\s+"
            r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b",
            re.IGNORECASE,
        ),
        "Generalize exact dates or timeline facts before training use.",
    ),
    (
        "unusual_dollar_amount",
        "low",
        re.compile(r"\$\s?\d{5,}(?:\.\d{2})?\b"),
        "Review unusual dollar amounts as possible quasi-identifiers.",
    ),
    (
        "public_uniqueness",
        "high",
        re.compile(
            r"\b(?:news report|media coverage|publicly reported|lawsuit|"
            r"public fundraiser|court filing)\b",
            re.IGNORECASE,
        ),
        "Exclude or expert-review facts tied to public records before training use.",
    ),
]
CONTEXTUAL_RISK_WEIGHTS = {"low": 0.08, "medium": 0.16, "high": 0.25}


class CorpusSafetyService:
    def __init__(self, manifest_path: Path | None = None):
        self.manifest_path = manifest_path or DEFAULT_MANIFEST_PATH

    def status(self) -> CorpusStatusResponse:
        return self.validate_manifest(self._load_manifest_records(), manifest_exists=self.manifest_path.exists())

    def review_queue(
        self,
        *,
        include_training_eligible: bool = True,
        limit: int = 100,
    ) -> CorpusReviewQueueResponse:
        records = self._load_manifest_records()
        pair_roles: dict[str, set[str]] = {}
        for record in records:
            if record.pair_id and record.document_role in REQUIRED_ROLES:
                pair_roles.setdefault(record.pair_id, set()).add(record.document_role)

        items = [
            self._review_queue_item(record, pair_roles)
            for record in records
            if include_training_eligible or not record.training_eligible
        ][: max(1, min(limit, 500))]

        return CorpusReviewQueueResponse(
            manifest_path=str(self.manifest_path),
            manifest_exists=self.manifest_path.exists(),
            record_count=len(records),
            queue_item_count=len(items),
            needs_review_count=sum(1 for item in items if not item.ready_for_training_export),
            needs_expert_determination_count=sum(
                1
                for item in items
                if (
                    item.deidentification_status == "expert_determination_required"
                    or item.reviewed_contextual_risk_finding_count > 0
                )
                and not item.expert_determination_completed
            ),
            missing_pair_count=sum(
                1
                for item in items
                if item.document_role in REQUIRED_ROLES
                and not (item.paired_denial_present and item.paired_appeal_present)
            ),
            training_eligible_count=sum(1 for item in items if item.training_eligible),
            production_candidate_count=sum(1 for item in items if item.production_corpus_candidate),
            items=items,
        )

    def validate_manifest(
        self,
        records: Iterable[CorpusManifestRecord],
        *,
        manifest_exists: bool = True,
        enforce_pair_completeness: bool = True,
    ) -> CorpusStatusResponse:
        record_list = list(records)
        issues: list[CorpusManifestIssue] = []
        seen_document_ids: set[str] = set()
        pair_roles: dict[str, set[str]] = {}

        for record in record_list:
            if record.document_id in seen_document_ids:
                issues.append(
                    self._issue(record, "document_id", "duplicate_document_id", "Document IDs must be unique.")
                )
            seen_document_ids.add(record.document_id)
            if record.pair_id:
                pair_roles.setdefault(record.pair_id, set()).add(record.document_role)
            issues.extend(self._record_issues(record))

        if enforce_pair_completeness:
            for pair_id, roles in pair_roles.items():
                if not {"denial_letter", "appeal_letter"}.issubset(roles):
                    issues.append(
                        CorpusManifestIssue(
                            document_id=None,
                            field="pair_id",
                            code="incomplete_denial_appeal_pair",
                            message=f"Pair {pair_id} must include denial_letter and appeal_letter records.",
                        )
                    )

        role_counts = Counter(record.document_role for record in record_list)
        status_counts = Counter(record.deidentification_status for record in record_list)
        phi_counts = Counter(record.phi_status for record in record_list)
        missing_categories = self._missing_categories(record_list, role_counts)
        training_eligible_count = sum(1 for record in record_list if record.training_eligible)
        blocked_count = len([issue for issue in issues if issue.code.startswith("training_")])

        return CorpusStatusResponse(
            manifest_path=str(self.manifest_path),
            manifest_exists=manifest_exists,
            record_count=len(record_list),
            counts_by_deidentification_status=dict(status_counts),
            counts_by_document_role=dict(role_counts),
            counts_by_phi_status=dict(phi_counts),
            training_eligible_count=training_eligible_count,
            blocked_count=blocked_count,
            missing_categories=missing_categories,
            ready_for_training_export=(
                training_eligible_count > 0 and not blocked_count and not missing_categories
            ),
            issues=issues,
        )

    def deidentify(self, request: CorpusDeidentifyRequest) -> CorpusDeidentifyResponse:
        text = request.document_text
        before_findings = scan_text_for_phi(text)
        replacements: list[CorpusReplacement] = []
        deidentified = text
        for finding_type, placeholder, pattern, replacement in DEIDENTIFICATION_PATTERNS:
            deidentified, count = pattern.subn(replacement, deidentified)
            if count:
                replacements.append(
                    CorpusReplacement(
                        placeholder=placeholder,
                        finding_type=finding_type,
                        replacement_count=count,
                    )
                )

        after_findings = scan_text_for_phi(deidentified)
        contextual_risk_findings = self._contextual_risk_findings(deidentified)
        residual_risk_score = self._residual_risk_score(
            deidentified,
            after_findings,
            contextual_risk_findings,
        )
        warnings = [
            "Machine de-identification output requires Raphael/privacy review before training eligibility.",
        ]
        if after_findings:
            warnings.append(
                "Metadata-only scan still found PHI/PII-like labels or patterns after replacement."
            )
        if contextual_risk_findings:
            warnings.append(
                "Local contextual review found rare or unique facts that require expert determination."
            )
        if residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            warnings.append("Residual risk score exceeds training eligibility threshold.")

        if contextual_risk_findings or residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            deidentification_status = "expert_determination_required"
        elif after_findings:
            deidentification_status = "human_review_required"
        else:
            deidentification_status = "machine_deidentified"

        return CorpusDeidentifyResponse(
            source_id=request.source_id,
            document_id=request.document_id,
            deidentified_text=deidentified,
            deidentification_status=deidentification_status,
            phi_scan_before=PhiScanSummary(**phi_scan_summary(before_findings)),
            phi_scan_after=PhiScanSummary(**phi_scan_summary(after_findings)),
            replacements=replacements,
            residual_risk_score=residual_risk_score,
            contextual_risk_findings=contextual_risk_findings,
            contextual_risk_finding_count=len(contextual_risk_findings),
            human_review_required=True,
            training_eligible=False,
            warnings=warnings,
        )

    def inspect_document_surfaces(
        self,
        request: CorpusDocumentSurfaceInspectRequest,
    ) -> CorpusDocumentSurfaceInspectResponse:
        surface_inputs = self._document_surface_inputs(request)
        surface_scans: list[CorpusDocumentSurfaceScan] = []
        warnings = [
            "Document-surface inspection is metadata-only and does not return matched values.",
            "Machine inspection output requires Raphael/privacy review before training eligibility.",
        ]
        if not surface_inputs:
            warnings.append("No document surfaces were supplied for inspection.")
        if request.source_mime_type and "pdf" in request.source_mime_type.lower():
            if not request.hidden_text:
                warnings.append("PDF hidden text was not supplied for inspection.")
            if not request.ocr_text and not request.scanned_page_texts:
                warnings.append("PDF OCR/scanned page text was not supplied for inspection.")
            if not request.metadata:
                warnings.append("PDF metadata was not supplied for inspection.")

        all_findings = []
        all_contextual_risk_findings: list[CorpusContextualRiskFinding] = []
        for surface, text, item_count in surface_inputs:
            findings = scan_text_for_phi(text)
            all_findings.extend(findings)
            contextual_risk_findings = self._contextual_risk_findings(text, surface=surface)
            all_contextual_risk_findings.extend(contextual_risk_findings)
            surface_warnings = []
            if findings:
                surface_warnings.append(
                    f"{surface} has PHI/PII-like findings; matched values are redacted."
                )
            if contextual_risk_findings:
                surface_warnings.append(
                    f"{surface} has contextual re-identification risk findings; values are redacted."
                )
            surface_scans.append(
                CorpusDocumentSurfaceScan(
                    surface=surface,
                    item_count=item_count,
                    text_length=len(text),
                    phi_scan=PhiScanSummary(**phi_scan_summary(findings)),
                    findings=serialize_phi_findings(findings),
                    contextual_risk_findings=contextual_risk_findings,
                    warnings=surface_warnings,
                )
            )

        residual_risk_score = self._residual_risk_score(
            "\n".join(text for _, text, _ in surface_inputs),
            all_findings,
            all_contextual_risk_findings,
        )
        blocking_surface_count = sum(
            1 for surface in surface_scans if surface.phi_scan.finding_count > 0
        )
        contextual_risk_surface_count = len(
            {
                finding.surface
                for finding in all_contextual_risk_findings
                if finding.surface is not None
            }
        )
        if all_contextual_risk_findings:
            warnings.append(
                "Local contextual review found rare or unique facts that require expert determination."
            )
        if residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            warnings.append("Residual risk score exceeds training eligibility threshold.")
        if blocking_surface_count:
            status = "qa_failed"
        elif all_contextual_risk_findings or residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            status = "expert_determination_required"
        else:
            status = "machine_deidentified"
        return CorpusDocumentSurfaceInspectResponse(
            source_id=request.source_id,
            document_id=request.document_id,
            document_role=request.document_role,
            deidentification_status=status,
            residual_risk_score=residual_risk_score,
            human_review_required=True,
            training_eligible=False,
            values_redacted=True,
            surface_count=len(surface_scans),
            blocking_surface_count=blocking_surface_count,
            contextual_risk_finding_count=len(all_contextual_risk_findings),
            contextual_risk_surface_count=contextual_risk_surface_count,
            surface_scans=surface_scans,
            warnings=warnings,
        )

    def import_approved(
        self,
        db: Session,
        request: CorpusImportRequest,
        *,
        created_by_user_id: int | None = None,
    ) -> CorpusImportResponse:
        from app.services.retrieval_store import RetrievalStoreService

        validation = self.validate_manifest(
            [request.record],
            enforce_pair_completeness=False,
        )
        if validation.issues or not request.record.training_eligible:
            return CorpusImportResponse(imported=False, validation=validation)

        retrieval_source = RetrievalStoreService(db).create_source(
            RetrievalSourceCreateRequest(
                title=f"{request.record.document_role}:{request.record.document_id}",
                source_type=f"corpus_{request.record.document_role}",
                document_text=request.document_text,
                source_url=request.record.source_url_or_path,
                phi_status=request.record.phi_status,
                license_status=request.record.license_status,
                privacy_review_completed=True,
                user_data_opt_in_for_model_improvement=False,
                chunk_size=request.chunk_size,
                overlap=request.overlap,
            ),
            created_by_user_id=created_by_user_id,
        )
        return CorpusImportResponse(
            imported=True,
            retrieval_source=retrieval_source,
            validation=validation,
        )

    def apply_review_decision(
        self,
        request: CorpusReviewDecisionRequest,
    ) -> CorpusReviewDecisionResponse:
        blockers = self._review_decision_blockers(request)
        warnings = [
            "Review decisions store metadata only; raw document text and matched values are not accepted.",
            "Approved records still require paired denial/appeal coverage before corpus SFT export.",
        ]
        needs_expert_determination = self._review_needs_expert_determination(request)
        reviewed_phi_status = request.phi_status or request.record.phi_status
        approved_for_training = request.decision == "approve_for_training" and not blockers

        if request.decision == "exclude":
            review_status = "excluded"
            deidentification_status = "qa_failed"
            split = "none"
            micro_skill_ids: list[str] = []
            training_eligible = False
        elif approved_for_training:
            review_status = "training_approved"
            deidentification_status = "training_eligible"
            split = request.split
            micro_skill_ids = request.micro_skill_ids
            training_eligible = True
        else:
            review_status = (
                "privacy_review_passed"
                if request.privacy_review_completed
                else request.record.review_status
            )
            deidentification_status = (
                "expert_determination_required"
                if needs_expert_determination and not request.expert_determination_completed
                else "privacy_review_passed"
                if request.privacy_review_completed
                else "human_review_required"
            )
            split = "none"
            micro_skill_ids = request.micro_skill_ids if request.decision == "privacy_review_passed" else []
            training_eligible = False

        updated_record = request.record.model_copy(
            update={
                "phi_status": reviewed_phi_status,
                "deidentification_status": deidentification_status,
                "license_status": request.license_status,
                "review_status": review_status,
                "residual_risk_score": request.residual_risk_score,
                "training_eligible": training_eligible,
                "split": split,
                "micro_skill_ids": micro_skill_ids,
                "reviewer_id": request.reviewer_id.strip() or None,
                "review_timestamp": datetime.now(timezone.utc),
                "review_method": request.review_method,
                "training_decision_note": request.training_decision_note.strip() or None,
                "review_findings": [item.strip() for item in request.review_findings if item.strip()],
                "reviewed_phi_finding_count": request.reviewed_phi_finding_count,
                "reviewed_contextual_risk_finding_count": (
                    request.reviewed_contextual_risk_finding_count
                ),
                "privacy_review_completed": request.privacy_review_completed,
                "license_review_completed": request.license_review_completed,
                "residual_risk_review_completed": request.residual_risk_review_completed,
                "expert_determination_completed": request.expert_determination_completed,
            }
        )
        validation = self.validate_manifest(
            [updated_record],
            enforce_pair_completeness=False,
        )
        if training_eligible and validation.issues:
            blockers.extend(
                f"manifest_validation:{issue.code}" for issue in validation.issues
            )
            updated_record = updated_record.model_copy(
                update={
                    "training_eligible": False,
                    "deidentification_status": "privacy_review_passed",
                    "review_status": "privacy_review_passed",
                    "split": "none",
                }
            )
            validation = self.validate_manifest(
                [updated_record],
                enforce_pair_completeness=False,
            )
            approved_for_training = False

        return CorpusReviewDecisionResponse(
            approved_for_training=approved_for_training,
            record=updated_record,
            blockers=blockers,
            warnings=warnings,
            validation=validation,
        )

    def _load_manifest_records(self) -> list[CorpusManifestRecord]:
        if not self.manifest_path.exists():
            return []
        try:
            decoded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw_records = decoded.get("records") if isinstance(decoded, dict) else decoded
        if not isinstance(raw_records, list):
            return []
        records: list[CorpusManifestRecord] = []
        for item in raw_records:
            try:
                records.append(CorpusManifestRecord.model_validate(item))
            except Exception:
                continue
        return records

    def _document_surface_inputs(
        self,
        request: CorpusDocumentSurfaceInspectRequest,
    ) -> list[tuple[str, str, int]]:
        surfaces: list[tuple[str, str, int]] = []

        def add(surface: str, text: str | None, item_count: int = 1) -> None:
            if text and text.strip():
                surfaces.append((surface, text.strip(), item_count))

        add("source_filename", request.source_filename)
        add("visible_text", request.visible_text)
        add("hidden_text", request.hidden_text)
        add("ocr_text", request.ocr_text)
        for index, page_text in enumerate(request.scanned_page_texts, start=1):
            add(f"scanned_page_text_{index}", page_text)
        add("header_footer_text", request.header_footer_text)
        if request.metadata:
            metadata_text = "\n".join(
                f"{key}: {value}" for key, value in sorted(request.metadata.items())
            )
            add("metadata", metadata_text, len(request.metadata))
        if request.barcode_qr_text:
            add("barcode_qr_text", "\n".join(request.barcode_qr_text), len(request.barcode_qr_text))
        if request.attachment_filenames:
            add(
                "attachment_filenames",
                "\n".join(request.attachment_filenames),
                len(request.attachment_filenames),
            )
        if not request.header_footer_text:
            inferred = self._infer_header_footer_text(
                [
                    request.visible_text,
                    request.hidden_text,
                    request.ocr_text,
                    *request.scanned_page_texts,
                ]
            )
            add("inferred_header_footer_text", inferred)
        return surfaces

    def _infer_header_footer_text(self, texts: list[str | None]) -> str:
        header_footer_lines: list[str] = []
        for text in texts:
            if not text:
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:
                continue
            header_footer_lines.extend(lines[:2])
            if len(lines) > 2:
                header_footer_lines.extend(lines[-2:])
        return "\n".join(header_footer_lines)

    def _record_issues(self, record: CorpusManifestRecord) -> list[CorpusManifestIssue]:
        issues: list[CorpusManifestIssue] = []
        if not record.checksum:
            issues.append(self._issue(record, "checksum", "missing_checksum", "Checksum is required."))
        if record.training_eligible:
            if record.phi_status not in {"no_phi", "deidentified"}:
                issues.append(
                    self._issue(
                        record,
                        "phi_status",
                        "training_phi_status_blocked",
                        "Training records must be no_phi or deidentified.",
                    )
                )
            if record.deidentification_status != "training_eligible":
                issues.append(
                    self._issue(
                        record,
                        "deidentification_status",
                        "training_deidentification_status_blocked",
                        "Training records must have deidentification_status=training_eligible.",
                    )
                )
            if record.review_status not in {"privacy_review_passed", "training_approved"}:
                issues.append(
                    self._issue(
                        record,
                        "review_status",
                        "training_review_blocked",
                        "Training records require privacy review or training approval.",
                    )
                )
            if record.license_status in {"review_required", "unknown", "prohibited"}:
                issues.append(
                    self._issue(
                        record,
                        "license_status",
                        "training_license_blocked",
                        "Training records require reviewed, allowed license status.",
                    )
                )
            if record.residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
                issues.append(
                    self._issue(
                        record,
                        "residual_risk_score",
                        "training_residual_risk_blocked",
                        "Residual risk is too high for training eligibility.",
                    )
                )
            if record.split == "none":
                issues.append(
                    self._issue(record, "split", "training_split_missing", "Training split is required.")
                )
            if not record.micro_skill_ids:
                issues.append(
                    self._issue(
                        record,
                        "micro_skill_ids",
                        "training_micro_skill_coverage_missing",
                        "At least one denial_skill micro-skill ID is required.",
                    )
                )
        elif record.deidentification_status == "raw_quarantined" and record.training_eligible:
            issues.append(
                self._issue(
                    record,
                    "training_eligible",
                    "raw_training_blocked",
                    "Raw quarantined records cannot be training eligible.",
                )
                )
        return issues

    def _review_queue_item(
        self,
        record: CorpusManifestRecord,
        pair_roles: dict[str, set[str]],
    ) -> CorpusReviewQueueItem:
        roles = pair_roles.get(record.pair_id or "", set())
        paired_denial_present = "denial_letter" in roles
        paired_appeal_present = "appeal_letter" in roles
        manifest_validation = self.validate_manifest(
            [record],
            enforce_pair_completeness=False,
        )
        ready_for_training_export = record.training_eligible and not manifest_validation.issues
        blockers = self._review_queue_blockers(
            record,
            paired_denial_present=paired_denial_present,
            paired_appeal_present=paired_appeal_present,
            manifest_validation=manifest_validation,
        )
        return CorpusReviewQueueItem(
            source_id=record.source_id,
            document_id=record.document_id,
            pair_id=record.pair_id,
            source_type=record.source_type,
            document_role=record.document_role,
            phi_status=record.phi_status,
            deidentification_status=record.deidentification_status,
            license_status=record.license_status,
            review_status=record.review_status,
            residual_risk_score=record.residual_risk_score,
            training_eligible=record.training_eligible,
            split=record.split,
            micro_skill_count=len(record.micro_skill_ids),
            reviewer_present=bool(record.reviewer_id),
            review_timestamp_present=record.review_timestamp is not None,
            privacy_review_completed=record.privacy_review_completed,
            license_review_completed=record.license_review_completed,
            residual_risk_review_completed=record.residual_risk_review_completed,
            expert_determination_completed=record.expert_determination_completed,
            reviewed_phi_finding_count=record.reviewed_phi_finding_count,
            reviewed_contextual_risk_finding_count=record.reviewed_contextual_risk_finding_count,
            paired_denial_present=paired_denial_present,
            paired_appeal_present=paired_appeal_present,
            ready_for_review_decision=self._ready_for_review_decision(record),
            ready_for_training_export=ready_for_training_export,
            production_corpus_candidate=record.source_type in PRODUCTION_PAIR_SOURCE_TYPES,
            blockers=blockers,
            next_action=self._review_queue_next_action(record, blockers, ready_for_training_export),
        )

    def _review_queue_blockers(
        self,
        record: CorpusManifestRecord,
        *,
        paired_denial_present: bool,
        paired_appeal_present: bool,
        manifest_validation: CorpusStatusResponse,
    ) -> list[str]:
        blockers = [f"manifest_validation:{issue.code}" for issue in manifest_validation.issues]
        if record.document_role not in REQUIRED_ROLES:
            blockers.append("document_role_not_denial_or_appeal_pair")
        elif not (paired_denial_present and paired_appeal_present):
            blockers.append("paired_denial_appeal_record_missing")
        if record.source_type not in PRODUCTION_PAIR_SOURCE_TYPES:
            blockers.append("source_type_not_production_denial_appeal_pair")
        if record.phi_status not in {"no_phi", "deidentified"}:
            blockers.append("phi_status_not_training_safe")
        if record.deidentification_status in {"raw_quarantined", "human_review_required", "qa_failed"}:
            blockers.append(f"deidentification_status:{record.deidentification_status}")
        if (
            record.deidentification_status == "machine_deidentified"
            and record.review_status not in {"privacy_review_passed", "training_approved"}
        ):
            blockers.append("privacy_review_required_after_machine_deidentification")
        if (
            record.deidentification_status == "expert_determination_required"
            and not record.expert_determination_completed
        ):
            blockers.append("expert_determination_required")
        if record.license_status in TRAINING_LICENSE_BLOCKLIST:
            blockers.append("license_status_not_training_allowed")
        if record.review_status not in {"privacy_review_passed", "training_approved"}:
            blockers.append("review_status_not_training_approved")
        if record.residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            blockers.append("residual_risk_exceeds_training_threshold")
        if record.document_role in REQUIRED_ROLES:
            if record.split not in {"train", "valid", "test"}:
                blockers.append("training_split_missing")
            if not record.micro_skill_ids:
                blockers.append("micro_skill_ids_required")
        if not record.reviewer_id or record.review_timestamp is None:
            blockers.append("manual_review_metadata_missing")
        return sorted(set(blockers))

    def _ready_for_review_decision(self, record: CorpusManifestRecord) -> bool:
        return (
            record.document_role in REQUIRED_ROLES
            and record.phi_status in {"no_phi", "deidentified"}
            and record.deidentification_status
            in {"machine_deidentified", "privacy_review_passed", "expert_determination_required"}
            and record.license_status not in {"prohibited"}
            and record.review_status != "excluded"
            and record.residual_risk_score <= 1.0
        )

    def _review_queue_next_action(
        self,
        record: CorpusManifestRecord,
        blockers: list[str],
        ready_for_training_export: bool,
    ) -> str:
        if ready_for_training_export and record.source_type in PRODUCTION_PAIR_SOURCE_TYPES:
            return "ready_for_production_corpus_export_review"
        if ready_for_training_export:
            return "keep_as_guarded_nonproduction_training_evidence"
        if record.document_role not in REQUIRED_ROLES:
            return "retain_as_reference_or_add_paired_denial_appeal_records"
        if any(blocker.startswith("deidentification_status:raw_quarantined") for blocker in blockers):
            return "run_surface_inspection_and_machine_deidentification"
        if "expert_determination_required" in blockers:
            return "complete_expert_determination_before_training_approval"
        if "license_status_not_training_allowed" in blockers:
            return "complete_license_review_before_training_approval"
        if "paired_denial_appeal_record_missing" in blockers:
            return "add_missing_denial_or_appeal_pair_record"
        if "source_type_not_production_denial_appeal_pair" in blockers:
            return "classify_or_collect_approved_production_pair_source"
        return "apply_metadata_only_review_decision_before_import_or_export"

    def _review_decision_blockers(
        self,
        request: CorpusReviewDecisionRequest,
    ) -> list[str]:
        blockers: list[str] = []
        if not request.reviewer_id.strip():
            blockers.append("reviewer_id_required")
        if not request.training_decision_note.strip():
            blockers.append("training_decision_note_required")
        review_metadata = "\n".join([request.training_decision_note, *request.review_findings])
        if scan_text_for_phi(review_metadata):
            blockers.append("review_metadata_contains_phi_or_pii_like_pattern")

        if request.decision == "exclude":
            return blockers

        if not request.privacy_review_completed:
            blockers.append("privacy_review_not_completed")
        if request.decision == "privacy_review_passed":
            return blockers

        reviewed_phi_status = request.phi_status or request.record.phi_status
        if reviewed_phi_status not in {"no_phi", "deidentified"}:
            blockers.append("reviewed_phi_status_not_training_safe")
        if not request.license_review_completed:
            blockers.append("license_review_not_completed")
        if request.license_status in {"review_required", "unknown", "prohibited"}:
            blockers.append("license_status_not_training_allowed")
        if not request.residual_risk_review_completed:
            blockers.append("residual_risk_review_not_completed")
        if request.residual_risk_score > MAX_TRAINING_RESIDUAL_RISK:
            blockers.append("residual_risk_exceeds_training_threshold")
        if request.split not in {"train", "valid", "test"}:
            blockers.append("training_split_must_be_train_valid_or_test")
        if not request.micro_skill_ids:
            blockers.append("micro_skill_ids_required_for_training")
        if self._review_needs_expert_determination(request) and not request.expert_determination_completed:
            blockers.append("expert_determination_required")
        return blockers

    def _review_needs_expert_determination(
        self,
        request: CorpusReviewDecisionRequest,
    ) -> bool:
        return (
            request.record.deidentification_status == "expert_determination_required"
            or request.record.review_status == "expert_determination_required"
            or request.reviewed_contextual_risk_finding_count > 0
            or request.record.reviewed_contextual_risk_finding_count > 0
        )

    def _missing_categories(
        self,
        records: list[CorpusManifestRecord],
        role_counts: Counter,
    ) -> list[str]:
        missing = [role for role in sorted(REQUIRED_ROLES) if not role_counts.get(role)]
        paired_ids = {
            record.pair_id
            for record in records
            if record.pair_id and record.document_role in REQUIRED_ROLES
        }
        if not paired_ids:
            missing.append("paired_denial_appeal_examples")
        covered_skills = {
            skill_id
            for record in records
            if record.training_eligible
            for skill_id in record.micro_skill_ids
        }
        for skill_id in [f"MS{index:02d}" for index in range(1, 13)]:
            if skill_id not in covered_skills:
                missing.append(skill_id)
        return missing

    def _contextual_risk_findings(
        self,
        text: str,
        *,
        surface: str | None = None,
    ) -> list[CorpusContextualRiskFinding]:
        findings: list[CorpusContextualRiskFinding] = []
        if not text:
            return findings
        for line_number, line in enumerate(text.splitlines(), start=1):
            for finding_type, severity, pattern, review_action in CONTEXTUAL_RISK_PATTERNS:
                for match in pattern.finditer(line):
                    findings.append(
                        CorpusContextualRiskFinding(
                            finding_type=finding_type,
                            line=line_number,
                            column=match.start() + 1,
                            severity=severity,  # type: ignore[arg-type]
                            surface=surface,
                            review_action=review_action,
                        )
                    )
        return findings

    def _residual_risk_score(
        self,
        text: str,
        after_findings: list,
        contextual_risk_findings: list[CorpusContextualRiskFinding] | None = None,
    ) -> float:
        risk = min(0.6, len(after_findings) * 0.08)
        contextual_findings = (
            contextual_risk_findings
            if contextual_risk_findings is not None
            else self._contextual_risk_findings(text)
        )
        contextual_risk = sum(
            CONTEXTUAL_RISK_WEIGHTS.get(finding.severity, 0.08)
            for finding in contextual_findings
        )
        risk += min(0.5, contextual_risk)
        return min(1.0, round(risk, 3))

    def _issue(
        self,
        record: CorpusManifestRecord,
        field: str,
        code: str,
        message: str,
    ) -> CorpusManifestIssue:
        return CorpusManifestIssue(
            document_id=record.document_id,
            field=field,
            code=code,
            message=message,
        )

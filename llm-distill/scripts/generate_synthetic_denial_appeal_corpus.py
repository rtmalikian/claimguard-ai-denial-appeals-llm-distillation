#!/usr/bin/env python3
"""Generate a large synthetic denial/appeal corpus with no real PHI."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
DISTILL_DIR = REPO_ROOT / "llm-distill"
DEFAULT_PAIR_COUNT = 900
MIN_REQUESTED_PAIR_COUNT = 800
MAX_REQUESTED_PAIR_COUNT = 1000
DEFAULT_OUTPUT_DIR = DISTILL_DIR / "data" / "corpus" / "generated_synthetic_pairs"
REQUIRED_MICRO_SKILLS = [f"MS{index:02d}" for index in range(1, 13)]
REVIEW_TIMESTAMP = "2026-05-30T16:24:00-07:00"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_phi_scan import scan_text  # noqa: E402
from report_output_sanitizer import write_sanitized_report_json  # noqa: E402


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


PAYER_PROFILES = [
    ("Aster Health Plan", "commercial", "formal_internal_appeal"),
    ("Northstar Care Alliance", "medicare_advantage", "plan_reconsideration"),
    ("Clearwater Managed Care", "medicaid_managed_care", "managed_care_appeal"),
    ("Summit Benefit Administrators", "erisa_self_funded", "erisa_internal_appeal"),
    ("Harbor Marketplace Health", "marketplace", "marketplace_internal_appeal"),
    ("CivicCare Advantage", "medicare_advantage", "plan_reconsideration"),
    ("Oakline Community Health", "medicaid_managed_care", "managed_care_appeal"),
    ("Blue Harbor Administrators", "commercial", "formal_internal_appeal"),
]

PROVIDER_GROUPS = [
    "Riverbend Orthopedic Group",
    "Lakeside Imaging Associates",
    "Cedar Valley Therapy",
    "Northgate Surgical Center",
    "Pinecrest Cardiology",
    "Westhaven Digestive Health",
    "MetroCare Physical Medicine",
    "Summit Neurology Clinic",
    "BrightPath Pediatrics",
    "Harborview Oncology Center",
]

SERVICE_LINES = [
    ("outpatient MRI lumbar spine", "72148", "radiology"),
    ("physical therapy re-evaluation", "97164", "therapy"),
    ("ambulatory surgery facility service", "29881", "surgery"),
    ("office evaluation and management visit", "99214", "professional"),
    ("cardiac stress imaging component", "78452", "cardiology"),
    ("home health skilled nursing visit", "G0299", "home_health"),
    ("infusion administration encounter", "96365", "infusion"),
    ("sleep study technical component", "95810", "diagnostic_testing"),
    ("wound care debridement service", "11042", "wound_care"),
    ("behavioral health therapy session", "90837", "behavioral_health"),
]

DENIAL_TYPES = [
    ("prior_authorization_missing", "authorization evidence was not located in the submitted packet"),
    ("medical_necessity", "submitted notes did not establish the plan criteria for the requested level of care"),
    ("coding_modifier_mismatch", "the billed procedure and modifier combination needs coding review"),
    ("timely_filing", "the payer system marked the submission window as unresolved"),
    ("coordination_of_benefits", "other coverage information must be reconciled before payment review"),
    ("eligibility", "coverage eligibility could not be confirmed for the service window"),
    ("experimental_investigational", "the plan classified the requested service as investigational pending evidence review"),
    ("documentation_support", "required documentation was missing or incomplete"),
    ("out_of_network", "network status was not supported by the submitted materials"),
    ("duplicate_service", "the payer system detected a potentially duplicate service line"),
]

DENIAL_FORMATS = [
    "formal_letter",
    "eob_summary",
    "portal_message",
    "utilization_review_notice",
    "fax_cover_summary",
    "medicare_reconsideration_notice",
    "medicaid_managed_care_notice",
    "employer_plan_adverse_benefit_notice",
]

APPEAL_FORMATS = [
    "provider_formal_letter",
    "clinical_reconsideration_packet",
    "corrected_claim_cover_letter",
    "portal_appeal_message",
    "medical_records_index",
    "timely_filing_rebuttal",
    "network_exception_appeal",
    "coding_review_appeal",
]

LAYOUT_PROFILES = [
    "single_column_letterhead",
    "two_column_eob_summary",
    "portal_card_stack",
    "dense_utilization_review_notice",
    "fax_cover_plus_body",
    "tabbed_reconsideration_notice",
    "bullet_heavy_managed_care_notice",
    "employer_plan_memo",
    "records_index_packet",
    "short_portal_update",
    "long_form_adverse_benefit_notice",
    "corrected_claim_cover_layout",
]

TYPOGRAPHY_PROFILES = [
    "serif_notice_body",
    "sans_serif_portal_body",
    "monospace_fax_extract",
    "condensed_table_labels",
    "large_print_accessible_notice",
    "small_footer_legal_notice",
    "mixed_heading_body_hierarchy",
    "plain_text_eob_export",
]

LENGTH_PROFILES = [
    ("compact", 0),
    ("standard", 1),
    ("expanded", 2),
    ("long_review_packet", 3),
    ("table_heavy", 2),
    ("short_portal", 0),
]


@dataclass(frozen=True)
class SyntheticCase:
    index: int
    pair_id: str
    split: str
    payer_name: str
    payer_type: str
    appeal_route: str
    provider_group: str
    service_name: str
    procedure_code: str
    service_category: str
    denial_type: str
    denial_rationale: str
    denial_format: str
    appeal_format: str
    case_reference: str
    coverage_reference: str
    auth_placeholder: str
    patient_placeholder: str
    service_window: str
    amount: str
    appeal_level: str
    layout_profile: str
    typography_profile: str
    length_profile: str
    extra_section_count: int


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_source_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def split_for_index(index: int, pair_count: int) -> str:
    train_cutoff = int(pair_count * 0.8)
    valid_cutoff = train_cutoff + int(pair_count * 0.1)
    if index <= train_cutoff:
        return "train"
    if index <= valid_cutoff:
        return "valid"
    return "test"


def synthetic_case(index: int, pair_count: int) -> SyntheticCase:
    payer_name, payer_type, appeal_route = PAYER_PROFILES[(index - 1) % len(PAYER_PROFILES)]
    provider_group = PROVIDER_GROUPS[(index * 3) % len(PROVIDER_GROUPS)]
    service_name, procedure_code, service_category = SERVICE_LINES[(index * 5) % len(SERVICE_LINES)]
    denial_type, denial_rationale = DENIAL_TYPES[(index * 7) % len(DENIAL_TYPES)]
    amount = f"${475 + ((index * 137) % 9800):,.2f}"
    return SyntheticCase(
        index=index,
        pair_id=f"PAIR-SYN-LARGE-{index:04d}",
        split=split_for_index(index, pair_count),
        payer_name=payer_name,
        payer_type=payer_type,
        appeal_route=appeal_route,
        provider_group=provider_group,
        service_name=service_name,
        procedure_code=procedure_code,
        service_category=service_category,
        denial_type=denial_type,
        denial_rationale=denial_rationale,
        denial_format=DENIAL_FORMATS[(index * 11) % len(DENIAL_FORMATS)],
        appeal_format=APPEAL_FORMATS[(index * 13) % len(APPEAL_FORMATS)],
        case_reference=f"SYN-CASE-{index:04d}",
        coverage_reference=f"SYN-COVERAGE-{(index * 17) % 10000:04d}",
        auth_placeholder=f"[AUTH_{index:04d}]",
        patient_placeholder=f"[PATIENT_{index:04d}]",
        service_window=f"2026-Q{((index - 1) % 4) + 1}",
        amount=amount,
        appeal_level="first_level" if index % 9 else "second_level",
        layout_profile=LAYOUT_PROFILES[(index * 19) % len(LAYOUT_PROFILES)],
        typography_profile=TYPOGRAPHY_PROFILES[(index * 23) % len(TYPOGRAPHY_PROFILES)],
        length_profile=LENGTH_PROFILES[(index * 29) % len(LENGTH_PROFILES)][0],
        extra_section_count=LENGTH_PROFILES[(index * 29) % len(LENGTH_PROFILES)][1],
    )


def format_profile_block(case: SyntheticCase, role: str) -> str:
    return (
        "Synthetic formatting profile\n"
        f"- Corpus role: {role}\n"
        f"- Layout profile: {case.layout_profile}\n"
        f"- Typography profile: {case.typography_profile}\n"
        f"- Length profile: {case.length_profile}\n"
        f"- Format family: {case.denial_format if role == 'denial_letter' else case.appeal_format}\n"
        "- Rendering note: source text is kept plain UTF-8 for PHI scanning; "
        "font and layout profile names document the intended stress-test rendering style.\n"
    )


def denial_extra_sections(case: SyntheticCase) -> list[str]:
    sections = [
        (
            "Source packet review\n"
            f"The review queue could not confirm that {case.provider_group} supplied all plan-required "
            f"support for {case.service_name}. Staff should compare the service category, code, "
            "and submitted record summary before preparing any appeal response."
        ),
        (
            "Service-line table\n"
            f"| Field | Synthetic value |\n|---|---|\n| Service category | {case.service_category} |\n"
            f"| Procedure code | {case.procedure_code} |\n| Review amount | {case.amount} |\n"
            f"| Route metadata | {case.appeal_route} |"
        ),
        (
            "Document consistency note\n"
            "This synthetic notice contains no personal identifiers, contact routes, account references, "
            "addresses, exact calendar details, or raw document metadata. It is designed to test whether "
            "the model keeps denial facts separate from appeal recommendations."
        ),
        (
            "Reviewer action list\n"
            "- Verify the current payer rule before citing it.\n"
            "- Confirm the appeal channel and representative authority.\n"
            "- Use only minimum necessary placeholders in any training response.\n"
            "- Keep any generated appeal draft marked for human review."
        ),
    ]
    start = case.index % len(sections)
    rotated = sections[start:] + sections[:start]
    return rotated[: case.extra_section_count]


def appeal_extra_sections(case: SyntheticCase) -> list[str]:
    sections = [
        (
            "Source index for reviewer\n"
            f"1. Synthetic denial notice {case.case_reference}.\n"
            f"2. Coding rationale for procedure code {case.procedure_code}.\n"
            "3. Placeholder record summary with no real person or claim information.\n"
            "4. Payer-specific rule source to be verified outside this training fixture."
        ),
        (
            "Quality-control checklist\n"
            "- Confirm the draft remains conditional and source-grounded.\n"
            "- Remove any unsupported clinical, legal, deadline, or citation language.\n"
            "- Verify attachments and signature authority before real-world use.\n"
            "- Preserve only minimum necessary placeholder information."
        ),
        (
            "Alternative short portal wording\n"
            f"Please reconsider synthetic case {case.case_reference}. The provider staff reviewer "
            f"will attach support for {case.service_name} after validating payer-specific requirements. "
            "This portal wording is not filing-ready until the record is verified."
        ),
        (
            "Appeal rationale table\n"
            f"| Topic | Synthetic review point |\n|---|---|\n| Denial type | {case.denial_type} |\n"
            f"| Service | {case.service_name} |\n| Route | {case.appeal_route} |\n"
            "| Human gate | Verify facts, deadline, authority, and PHI scope |"
        ),
    ]
    start = (case.index * 2) % len(sections)
    rotated = sections[start:] + sections[:start]
    return rotated[: case.extra_section_count]


def render_denial(case: SyntheticCase) -> str:
    common = {
        "header": (
            f"Training synthetic corpus pair {case.pair_id}.\n\n"
            f"{case.payer_name}\n"
            f"Synthetic adverse benefit determination\n"
            f"Case reference {case.case_reference}\n"
            f"Coverage reference {case.coverage_reference}\n"
            f"{format_profile_block(case, 'denial_letter')}"
        ),
        "service": (
            f"Synthetic member placeholder {case.patient_placeholder}; provider group "
            f"{case.provider_group}; service window {case.service_window}; "
            f"service reviewed {case.service_name}; procedure code {case.procedure_code}; "
            f"billed amount {case.amount}."
        ),
        "reason": (
            f"Determination rationale: {case.denial_rationale}. "
            "This synthetic notice is for model training only and is not connected to any real person."
        ),
        "next": (
            f"Recommended route metadata: {case.appeal_route}. "
            "The provider may submit a draft_for_human_review appeal packet with source documents, "
            "coding rationale, and minimum necessary placeholders."
        ),
    }
    templates = {
        "formal_letter": (
            "{header}\nDear Provider Staff,\n\n"
            "{service}\n\n{reason}\n\n{next}\n\n"
            "No final deadline is asserted in this synthetic example; local plan documents must be verified."
        ),
        "eob_summary": (
            "{header}\nExplanation summary\n- Review status: denied\n- Service category: "
            f"{case.service_category}\n- {common['service']}\n- {common['reason']}\n"
            "- Action: reconcile coding, coverage, and documentation before appeal submission.\n"
            "- Human review required before any real-world use."
        ),
        "portal_message": (
            "{header}\nPortal status update\n\n"
            "Status: denied pending provider review\n"
            f"Summary: {common['service']}\n"
            f"Why this requires action: {common['reason']}\n"
            f"Suggested channel: {case.appeal_route}; verify channel before filing."
        ),
        "utilization_review_notice": (
            "{header}\nUtilization review outcome\n\n"
            f"Clinical/service topic: {case.service_name}.\n"
            f"Administrative context: {common['service']}\n"
            f"Review finding: {common['reason']}\n"
            "A reviewer should compare the submitted packet against current plan criteria."
        ),
        "fax_cover_summary": (
            "{header}\nFax-style synthetic summary\n\n"
            f"Line 1: {common['service']}\n"
            f"Line 2: Denial type {case.denial_type}.\n"
            f"Line 3: {common['reason']}\n"
            "Line 4: Attach verified records only; do not add real identifiers."
        ),
        "medicare_reconsideration_notice": (
            "{header}\nPlan reconsideration training notice\n\n"
            f"{common['service']}\n\n"
            f"{common['reason']}\n\n"
            "Use this example to train route selection and evidence-gap detection, not to assert Medicare rules."
        ),
        "medicaid_managed_care_notice": (
            "{header}\nManaged care training notice\n\n"
            f"{common['service']}\n\n"
            f"{common['reason']}\n\n"
            "The synthetic appeal should preserve source-grounding and request plan-specific review."
        ),
        "employer_plan_adverse_benefit_notice": (
            "{header}\nEmployer plan adverse benefit training notice\n\n"
            f"{common['service']}\n\n"
            f"{common['reason']}\n\n"
            "The draft response must ask staff to verify plan documents and representative authority."
        ),
    }
    base = templates[case.denial_format].format(**common).strip()
    extras = denial_extra_sections(case)
    if extras:
        base = base + "\n\n" + "\n\n".join(extras)
    return base + "\n"


def render_appeal(case: SyntheticCase) -> str:
    evidence_lines = [
        f"- Verify the denial rationale for {case.denial_type}.",
        f"- Attach source-grounded records for {case.service_name}.",
        f"- Confirm code {case.procedure_code} and any modifier logic before submission.",
        f"- Keep placeholders {case.patient_placeholder}, {case.auth_placeholder}, and {case.coverage_reference} synthetic.",
    ]
    common = {
        "header": (
            "Draft for human review.\n"
            "draft_for_human_review\n"
            f"Synthetic corpus pair {case.pair_id}.\n\n"
            f"{case.provider_group}\n"
            f"Synthetic appeal draft for case reference {case.case_reference}\n"
            f"Route metadata {case.appeal_route}; appeal level {case.appeal_level}\n"
            f"{format_profile_block(case, 'appeal_letter')}"
        ),
        "opening": (
            f"This supervised training draft responds to {case.payer_name}'s synthetic denial "
            f"for {case.service_name} in service window {case.service_window}."
        ),
        "position": (
            f"The provider staff reviewer should request reconsideration because {case.denial_rationale}. "
            "The packet should connect each assertion to the denial notice, source record, or coding rationale."
        ),
        "evidence": "\n".join(evidence_lines),
        "close": (
            "Before any real-world use, verify payer channel, current deadline, authority, attachments, "
            "clinical statements, coding facts, and minimum necessary PHI scope. "
            "This synthetic draft is not filing-ready."
        ),
    }
    templates = {
        "provider_formal_letter": (
            "{header}\nTo Appeals Review Staff,\n\n{opening}\n\n{position}\n\n"
            "Evidence checklist:\n{evidence}\n\nRequested action: review and reprocess if the verified record supports coverage.\n\n{close}"
        ),
        "clinical_reconsideration_packet": (
            "{header}\nClinical reconsideration outline\n\n1. Case context: {opening}\n"
            "2. Source-grounded position: {position}\n3. Evidence checklist:\n{evidence}\n\n{close}"
        ),
        "corrected_claim_cover_letter": (
            "{header}\nCorrected claim cover draft\n\n{opening}\n\n"
            "Correction focus: reconcile service line, procedure code, authorization placeholder, and payer edit.\n"
            "{position}\n\n{evidence}\n\n{close}"
        ),
        "portal_appeal_message": (
            "{header}\nPortal message draft\n\nSummary: {opening}\n\n"
            "Appeal basis: {position}\n\nEvidence to attach:\n{evidence}\n\n{close}"
        ),
        "medical_records_index": (
            "{header}\nRecords index plus appeal narrative\n\n{opening}\n\n{position}\n\n"
            "Records index:\n{evidence}\n\n{close}"
        ),
        "timely_filing_rebuttal": (
            "{header}\nTimely filing rebuttal draft\n\n{opening}\n\n"
            "The reviewer should verify receipt proof, payer portal status, and allowed submission window.\n"
            "{position}\n\n{evidence}\n\n{close}"
        ),
        "network_exception_appeal": (
            "{header}\nNetwork review draft\n\n{opening}\n\n"
            "The reviewer should verify network status, referral pathway, and any continuity-of-care facts.\n"
            "{position}\n\n{evidence}\n\n{close}"
        ),
        "coding_review_appeal": (
            "{header}\nCoding review appeal draft\n\n{opening}\n\n"
            "The reviewer should verify code selection, modifier support, bundling edits, and payer policy.\n"
            "{position}\n\n{evidence}\n\n{close}"
        ),
    }
    base = templates[case.appeal_format].format(**common).strip()
    extras = appeal_extra_sections(case)
    if extras:
        base = base + "\n\n" + "\n\n".join(extras)
    return base + "\n"


def manifest_record(
    *,
    case: SyntheticCase,
    role: str,
    source_path: str,
    text: str,
) -> dict[str, Any]:
    suffix = "DENIAL" if role == "denial_letter" else "APPEAL"
    return {
        "source_id": f"SRC-SYN-LARGE-{case.index:04d}-{suffix}",
        "document_id": f"DOC-SYN-LARGE-{case.index:04d}-{suffix}",
        "pair_id": case.pair_id,
        "source_type": "synthetic_deidentified_pair",
        "document_role": role,
        "source_url_or_path": source_path,
        "checksum": sha256_text(text),
        "phi_status": "no_phi",
        "deidentification_status": "training_eligible",
        "license_status": "synthetic_allowed",
        "review_status": "training_approved",
        "residual_risk_score": 0.0,
        "training_eligible": True,
        "split": case.split,
        "micro_skill_ids": REQUIRED_MICRO_SKILLS,
        "payer_type": case.payer_type,
        "denial_type": case.denial_type,
        "appeal_route": case.appeal_route,
        "appeal_level": case.appeal_level,
        "outcome": "drafted_appeal" if role == "appeal_letter" else "denied",
        "format_profile": case.denial_format if role == "denial_letter" else case.appeal_format,
        "layout_profile": case.layout_profile,
        "typography_profile": case.typography_profile,
        "length_profile": case.length_profile,
        "reviewer_id": "synthetic_large_scale_generator",
        "review_timestamp": REVIEW_TIMESTAMP,
        "review_method": "deterministic_synthetic_no_phi_generation",
        "training_decision_note": (
            "Synthetic no-PHI fixture generated for guarded ClaimGuard training. "
            "Not sourced from real patients, claims, denial letters, payer records, or user uploads."
        ),
    }


def validate_generated_text(path: Path, text: str) -> list[dict[str, Any]]:
    return scan_text(path, text)


def generated_readme(pair_count: int) -> str:
    return f"""# Generated Synthetic Denial/Appeal Corpus

ClaimGuard AI is architected by Raphael Malikian.

This directory contains {pair_count} synthetic denial/appeal pairs, or {pair_count * 2}
plain-text letters, generated for local ClaimGuard model-training experiments.

Safety and format rules:

- Every document is fictitious and generated locally from deterministic templates.
- No real patients, claim IDs, member IDs, contact details, credentials, payer records,
  user-uploaded files, or production documents were used.
- Denial letters follow the existing corpus style: each begins as a training
  synthetic corpus pair, describes a payer denial scenario, avoids direct
  identifiers, and names the reviewer action.
- Appeal letters follow the existing corpus style: each is marked
  `draft_for_human_review`, stays conditional, and requires source, deadline,
  authority, clinical, coding, and PHI-scope verification.
- Each file includes a Synthetic formatting profile with layout, typography,
  format-family, and length-profile metadata.
- The `rendered_html/` companions apply actual CSS font stacks and layout
  wrappers for the same no-PHI letter text, so visual/OCR-style stress tests
  can exercise different document fonts and page layouts without changing the
  plain UTF-8 training source.
- Use `manifest_synthetic_{pair_count}.json` plus `generation_report.json` as the
  source of truth for checksums, split counts, coverage, and PHI-scan status.
- Use `visual_manifest_synthetic_{pair_count}.json` plus
  `visual_render_report.json` as the source of truth for rendered HTML
  checksums, font-family coverage, layout coverage, and visual rendering
  PHI-scan status.
"""


def generate_corpus(
    *,
    pair_count: int,
    output_dir: Path,
    manifest_path: Path | None = None,
    report_path: Path | None = None,
    enforce_requested_range: bool = True,
) -> dict[str, Any]:
    if enforce_requested_range and not (
        MIN_REQUESTED_PAIR_COUNT <= pair_count <= MAX_REQUESTED_PAIR_COUNT
    ):
        raise ValueError("pair_count must be between 800 and 1000 for this corpus request")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")

    manifest_path = manifest_path or output_dir / f"manifest_synthetic_{pair_count}.json"
    report_path = report_path or output_dir / "generation_report.json"
    readme_path = output_dir / "README.md"
    letters_dir = output_dir / "letters"
    records: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    counts = {
        "split": {},
        "payer_type": {},
        "denial_type": {},
        "denial_format": {},
        "appeal_format": {},
        "layout_profile": {},
        "typography_profile": {},
        "length_profile": {},
    }

    for index in range(1, pair_count + 1):
        case = synthetic_case(index, pair_count)
        denial_text = render_denial(case)
        appeal_text = render_appeal(case)
        split_dir = letters_dir / case.split
        denial_path = split_dir / f"{case.pair_id.lower()}_denial.txt"
        appeal_path = split_dir / f"{case.pair_id.lower()}_appeal.txt"
        split_dir.mkdir(parents=True, exist_ok=True)
        denial_path.write_text(denial_text, encoding="utf-8")
        appeal_path.write_text(appeal_text, encoding="utf-8")
        findings.extend(validate_generated_text(denial_path, denial_text))
        findings.extend(validate_generated_text(appeal_path, appeal_text))
        records.append(
            manifest_record(
                case=case,
                role="denial_letter",
                source_path=manifest_source_path(denial_path),
                text=denial_text,
            )
        )
        records.append(
            manifest_record(
                case=case,
                role="appeal_letter",
                source_path=manifest_source_path(appeal_path),
                text=appeal_text,
            )
        )
        for key, value in [
            ("split", case.split),
            ("payer_type", case.payer_type),
            ("denial_type", case.denial_type),
            ("denial_format", case.denial_format),
            ("appeal_format", case.appeal_format),
            ("layout_profile", case.layout_profile),
            ("typography_profile", case.typography_profile),
            ("length_profile", case.length_profile),
        ]:
            counts[key][value] = counts[key].get(value, 0) + 1

    manifest = {
        "version": f"synthetic-large-{pair_count}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": "llm-distill/scripts/generate_synthetic_denial_appeal_corpus.py",
        "records": records,
    }
    report = {
        "artifact": "synthetic_denial_appeal_corpus",
        "pair_count": pair_count,
        "letter_count": pair_count * 2,
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "readme_path": str(readme_path),
        "counts": counts,
        "phi_scan": {
            "finding_count": len(findings),
            "findings": findings,
            "values_redacted": True,
        },
        "safety": {
            "synthetic_only": True,
            "real_patient_data_used": False,
            "real_claim_data_used": False,
            "external_model_calls_made": False,
            "uses_placeholders_for_member_and_patient_context": True,
            "training_allowed_only_after_export_gates": True,
        },
        "notes": [
            "Fictitious payer and provider organization names are synthetic.",
            "Patient, authorization, and coverage context uses placeholders rather than real identifiers.",
            "The generated appeal letters remain draft_for_human_review.",
            "Each text file includes a synthetic formatting profile documenting intended layout, typography, format family, and length variation.",
            "Font variation is represented as metadata so the training corpus remains plain text and PHI-scannable.",
        ],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if path_is_within(report_path, REPO_ROOT):
        write_sanitized_report_json(report_path, report, REPO_ROOT)
    else:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.write_text(generated_readme(pair_count), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-count", type=int, default=DEFAULT_PAIR_COUNT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    report = generate_corpus(
        pair_count=args.pair_count,
        output_dir=args.output_dir,
        manifest_path=args.manifest,
        report_path=args.report,
    )
    print(
        "wrote synthetic denial/appeal corpus to "
        f"{args.output_dir} "
        f"(pairs={report['pair_count']}, letters={report['letter_count']}, "
        f"phi_findings={report['phi_scan']['finding_count']})"
    )
    return 1 if report["phi_scan"]["finding_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare synthetic ClaimGuard records for teacher labeling and student SFT."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.schemas.denial_workflow import DenialWorkflowAnalysisRequest  # noqa: E402
from app.services.denial_workflow import DenialWorkflowService  # noqa: E402
from run_phi_scan import scan_text  # noqa: E402


SYSTEM_PROMPT = (
    "You are a ClaimGuard denial workflow assistant. Return compact JSON only. "
    "Do not provide legal advice, medical advice, fabricated deadlines, "
    "fabricated citations, or filing-ready language. Mark all drafts as "
    "draft_for_human_review."
)

REQUIRED_OUTPUT_KEYS = [
    "case_summary",
    "known_from_documents",
    "inferred",
    "missing_needs_human_verification",
    "cited_rules",
    "plan_type",
    "denial_type",
    "recommended_route",
    "deadline_table",
    "evidence_gaps",
    "draft_sections",
    "follow_up_plan",
    "human_review_required",
    "warnings",
]

REQUIRED_MICRO_SKILLS = [f"MS{index:02d}" for index in range(1, 13)]
COMMON_MICRO_SKILLS = ["MS01", "MS02", "MS03", "MS06", "MS08", "MS09", "MS10", "MS11"]
FAMILY_MICRO_SKILLS = {
    "urgent_pre_service": ["MS05"],
    "self_funded_erisa_medical_necessity": ["MS05"],
    "medicare_ffs_redetermination": ["MS05"],
    "medicare_advantage_pre_service": ["MS05"],
    "medicaid_managed_care_service_reduction": ["MS05"],
    "coding_modifier_corrected_claim": ["MS07"],
    "provider_authority_missing": ["MS04"],
    "upheld_final_adverse_response": ["MS12"],
}
FAMILY_RED_TEAM_TAGS = {
    "urgent_pre_service": ["urgent_routing_failure", "unsupported_urgency"],
    "self_funded_erisa_medical_necessity": ["wrong_plan_path", "deadline_conflict"],
    "medicare_advantage_pre_service": ["wrong_payer_path", "urgent_routing_failure"],
    "medicaid_managed_care_service_reduction": ["medicaid_continuation_missed"],
    "coding_modifier_corrected_claim": ["corrected_claim_vs_appeal"],
    "commercial_out_of_network": ["external_review_premature"],
    "provider_authority_missing": ["missing_authority", "filing_ready_block"],
    "upheld_final_adverse_response": ["outcome_analysis", "next_level_deadline"],
}
LABEL_REPLACEMENTS = [
    (re.compile(r"member id\b", re.IGNORECASE), "member identifier"),
    (re.compile(r"subscriber id\b", re.IGNORECASE), "subscriber identifier"),
    (re.compile(r"policy number\b", re.IGNORECASE), "policy identifier"),
    (re.compile(r"claim number\b", re.IGNORECASE), "case reference"),
    (re.compile(r"claim #\b", re.IGNORECASE), "case reference"),
    (re.compile(r"ICN\b"), "internal control reference"),
    (re.compile(r"DCN\b"), "document control reference"),
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if "scenario_id" not in record:
                raise ValueError(f"{path}:{line_number}: missing scenario_id")
            if not record.get("input", {}).get("document_text"):
                raise ValueError(f"{path}:{line_number}: missing input.document_text")
            records.append(record)
    return records


def compact_output(response: Any) -> dict[str, Any]:
    response_data = response.model_dump(mode="json")
    draft = response_data.get("draft_appeal_letter")
    return {
        "case_summary": response_data["case_summary"],
        "known_from_documents": response_data["known_from_documents"],
        "inferred": response_data["inferred"],
        "missing_needs_human_verification": response_data["missing_needs_human_verification"],
        "cited_rules": response_data["cited_rules"],
        "plan_type": response_data["plan_type"],
        "denial_type": response_data["denial_type"],
        "recommended_route": response_data["recommended_route"],
        "route_confidence": response_data["route_confidence"],
        "route_evidence": response_data["route_evidence"],
        "routes_considered": response_data["routes_considered"],
        "deadline_table": response_data["deadline_table"],
        "evidence_gaps": response_data["evidence_gaps"],
        "appeal_strategy": response_data["appeal_strategy"],
        "draft_sections": [
            {
                "section_id": "appeal_letter",
                "draft_status": "draft_for_human_review",
                "body": draft,
            }
        ]
        if draft
        else [],
        "attachment_index": response_data["attachment_index"],
        "submission_plan": response_data["submission_plan"],
        "follow_up_plan": response_data["follow_up_plan"],
        "quality_checks": response_data["quality_checks"],
        "human_review_required": response_data["human_review_required"],
        "warnings": response_data["warnings"],
    }


def sanitize_phi_like_labels(value: Any) -> Any:
    if isinstance(value, str):
        output = value
        for pattern, replacement in LABEL_REPLACEMENTS:
            output = pattern.sub(replacement, output)
        return output
    if isinstance(value, list):
        return [sanitize_phi_like_labels(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_phi_like_labels(item) for key, item in value.items()}
    return value


def micro_skills_for(scenario: dict[str, Any]) -> list[str]:
    family = scenario.get("scenario_family", "")
    return sorted(set(COMMON_MICRO_SKILLS + FAMILY_MICRO_SKILLS.get(family, [])))


def red_team_tags_for(scenario: dict[str, Any]) -> list[str]:
    family = scenario.get("scenario_family", "")
    expected = scenario.get("expected_output", {})
    tags = list(FAMILY_RED_TEAM_TAGS.get(family, []))
    if expected.get("human_review_required") is True:
        tags.append("human_review_gate")
    if "must_not_include" in expected:
        tags.append("unsafe_phrase_suppression")
    return sorted(set(tags))


def source_snippets(response: Any) -> list[dict[str, Any]]:
    snippets = []
    for snippet in response.retrieval_citations:
        data = snippet.model_dump(mode="json")
        phi_status = data.get("phi_status", "no_phi")
        license_status = data.get("license_status", "review_required")
        if str(data["source_id"]).startswith("synthetic-"):
            phi_status = "no_phi"
            license_status = "synthetic_internal_seed"
        snippets.append(
            {
                "source_id": data["source_id"],
                "title": data["title"],
                "source_type": data["source_type"],
                "citation": data["citation"],
                "text": data["text"],
                "jurisdiction": data.get("jurisdiction"),
                "payer_type": data.get("payer_type"),
                "date": data.get("date"),
                "phi_status": phi_status,
                "license_status": license_status,
            }
        )
    return snippets


def user_prompt(scenario: dict[str, Any], snippets: list[dict[str, Any]]) -> str:
    payload = {
        "task": "Produce the ClaimGuard denial workflow JSON for this synthetic case.",
        "required_output_keys": REQUIRED_OUTPUT_KEYS,
        "rules": [
            "Use null or unknown when a fact is missing.",
            "Do not invent deadlines, plan language, policy citations, or clinical facts.",
            "Every draft must stay marked draft_for_human_review.",
            "Use only minimum necessary synthetic case details.",
        ],
        "document": {
            "document_id": f"synthetic-{scenario['scenario_id'].lower()}",
            "document_type": "denial_letter",
            "text": scenario["input"]["document_text"],
        },
        "available_source_snippets": snippets,
        "gold_behavior_constraints": scenario.get("expected_output", {}),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_supervised_record(
    scenario: dict[str, Any],
    response: Any,
    split: str,
    label_source: str,
) -> dict[str, Any]:
    example_id = f"cg-{scenario['scenario_id'].lower()}-{scenario['scenario_family']}"
    snippets = source_snippets(response)
    expected_output = compact_output(response)
    prompt = user_prompt(scenario, snippets)
    return sanitize_phi_like_labels(
        {
            "example_id": example_id,
            "dataset_split": split,
            "task": "end_to_end_denial_workflow",
            "micro_skill_ids": micro_skills_for(scenario),
            "source_policy": {
                "data_tier": "synthetic",
                "phi_status": "no_phi",
                "license_status": "synthetic_internal_seed",
                "user_phi_allowed": False,
            },
            "input": {
                "documents": [
                    {
                        "document_id": f"synthetic-{scenario['scenario_id'].lower()}",
                        "document_type": "denial_letter",
                        "text": scenario["input"]["document_text"],
                    }
                ],
                "known_case_facts": {},
                "retrieved_supporting_source_snippets": snippets,
            },
            "expected_output": expected_output,
            "teacher_label": {
                "label_source": label_source,
                "teacher_model": None,
                "teacher_review_status": "pending_large_teacher_review",
                "human_review_required": True,
            },
            "sft_messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": json.dumps(expected_output, sort_keys=True)},
            ],
            "quality_gates": {
                "draft_for_human_review_present": any(
                    section.get("draft_status") == "draft_for_human_review"
                    for section in expected_output["draft_sections"]
                ),
                "human_review_required": expected_output["human_review_required"] is True,
                "has_source_status_groups": all(
                    key in expected_output
                    for key in [
                        "known_from_documents",
                        "inferred",
                        "missing_needs_human_verification",
                        "cited_rules",
                    ]
                ),
                "has_quality_checks": bool(expected_output["quality_checks"]),
            },
            "red_team_tags": red_team_tags_for(scenario),
        }
    )


def build_teacher_request(
    scenario: dict[str, Any],
    response: Any,
    teacher_model: str,
) -> dict[str, Any]:
    snippets = source_snippets(response)
    return sanitize_phi_like_labels(
        {
            "custom_id": f"teacher-label-{scenario['scenario_id'].lower()}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": teacher_model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            SYSTEM_PROMPT
                            + " You are producing a teacher label for a smaller student model. "
                            "Use the ClaimGuard output contract exactly."
                        ),
                    },
                    {"role": "user", "content": user_prompt(scenario, snippets)},
                ],
                "response_format": {"type": "json_object"},
            },
        }
    )


async def analyze_scenarios(scenarios: list[dict[str, Any]]) -> list[tuple[dict[str, Any], Any]]:
    service = DenialWorkflowService()
    analyzed = []
    for scenario in scenarios:
        response = await service.analyze(
            DenialWorkflowAnalysisRequest(
                document_text=scenario["input"]["document_text"],
                source_document_id=f"synthetic-{scenario['scenario_id'].lower()}",
                source_title=f"Synthetic distillation scenario {scenario['scenario_id']}",
                generate_draft=True,
                use_llm=False,
            )
        )
        analyzed.append((scenario, response))
    return analyzed


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def assert_no_phi(path: Path) -> None:
    findings = scan_text(path, path.read_text(encoding="utf-8"))
    if findings:
        summary = Counter(finding["finding_type"] for finding in findings)
        raise ValueError(f"{path} has PHI/PII-like findings: {dict(summary)}")


def write_dataset_card(path: Path, records: list[dict[str, Any]], teacher_requests: int) -> None:
    split_counts = Counter(record["dataset_split"] for record in records)
    skill_counts = Counter(skill for record in records for skill in record["micro_skill_ids"])
    missing_skills = [
        skill_id for skill_id in REQUIRED_MICRO_SKILLS if skill_counts.get(skill_id, 0) <= 0
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# ClaimGuard Synthetic Distillation Dataset Card",
                "",
                "Architected by Raphael Malikian <rtmalikian@gmail.com>.",
                "",
                "## Purpose",
                "",
                "This seed dataset prepares ClaimGuard denial-processing and appeal-drafting records for a smaller local student model. It is not a production training corpus and is not a substitute for reviewed teacher labels.",
                "",
                "## Data Status",
                "",
                "- Data tier: synthetic.",
                "- PHI status: no PHI intended; run `llm-distill/scripts/run_phi_scan.py` before use.",
                "- Label source: deterministic ClaimGuard workflow seed pending large-teacher or human review.",
                "- User-uploaded PHI: not allowed.",
                "- Runtime target: MLX/MLX-LM student model path from `llm-distill/llm-distill-plan.md`.",
                "",
                "## Counts",
                "",
                f"- Supervised seed records: {len(records)}.",
                f"- Teacher request records: {teacher_requests}.",
                f"- Splits: {dict(sorted(split_counts.items()))}.",
                f"- Micro-skill coverage: {dict(sorted(skill_counts.items()))}.",
                f"- Required micro-skills: {REQUIRED_MICRO_SKILLS}.",
                f"- Missing required micro-skills: {missing_skills}.",
                "",
                "## Intended Use",
                "",
                "Use these records to dry-run SFT formatting, teacher-label review, JSON validation, and regression scoring. Do not treat them as final teacher-labeled training data until a compliant teacher model or human reviewer has approved labels.",
                "",
                "## Exclusions",
                "",
                "Do not add real denial letters, user-uploaded documents, private claims, credentials, local model weights, or raw PHI to this dataset path.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=REPO_ROOT / "llm-distill" / "evals" / "cases" / "gold_scenarios.jsonl",
    )
    parser.add_argument(
        "--supervised-output",
        type=Path,
        default=REPO_ROOT
        / "llm-distill"
        / "data"
        / "distillation"
        / "seed_synthetic_supervised.jsonl",
    )
    parser.add_argument(
        "--teacher-request-output",
        type=Path,
        default=REPO_ROOT
        / "llm-distill"
        / "data"
        / "distillation"
        / "teacher_label_requests.jsonl",
    )
    parser.add_argument(
        "--dataset-card-output",
        type=Path,
        default=REPO_ROOT / "llm-distill" / "data" / "distillation" / "dataset_card.md",
    )
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test", "red_team"])
    parser.add_argument("--teacher-model", default="TEACHER_MODEL_TO_BE_SET_BY_OPERATOR")
    parser.add_argument(
        "--label-source",
        default="deterministic_claim_guard_workflow_seed",
        choices=["deterministic_claim_guard_workflow_seed", "large_teacher_reviewed", "human_reviewed"],
    )
    parser.add_argument("--skip-phi-scan", action="store_true")
    args = parser.parse_args()

    scenarios = load_jsonl(args.cases)
    analyzed = asyncio.run(analyze_scenarios(scenarios))
    supervised_records = [
        build_supervised_record(scenario, response, args.split, args.label_source)
        for scenario, response in analyzed
    ]
    teacher_requests = [
        build_teacher_request(scenario, response, args.teacher_model)
        for scenario, response in analyzed
    ]

    write_jsonl(args.supervised_output, supervised_records)
    write_jsonl(args.teacher_request_output, teacher_requests)
    write_dataset_card(args.dataset_card_output, supervised_records, len(teacher_requests))

    if not args.skip_phi_scan:
        for output_path in [args.supervised_output, args.teacher_request_output]:
            assert_no_phi(output_path)

    print(
        "wrote "
        f"{len(supervised_records)} supervised records, "
        f"{len(teacher_requests)} teacher requests, and dataset card"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import re
from typing import Any


PROMPT_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|bypass|override)\b.{0,80}"
            r"\b(previous|prior|above|system|developer|instruction|instructions|prompt|rules)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(you are now|act as|pretend to be|new role|system message)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(api key|authorization header|password|token|secret|credentials?)\b.{0,80}"
            r"\b(show|print|return|reveal|exfiltrate|send)\b|"
            r"\b(show|print|return|reveal|exfiltrate|send)\b.{0,80}"
            r"\b(api key|authorization header|password|token|secret|credentials?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "tool_or_network_request",
        re.compile(
            r"\b(call|invoke|use|open|fetch|post to)\b.{0,60}"
            r"\b(tool|browser|shell|terminal|python|webhook|http endpoint|url)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "output_override",
        re.compile(
            r"\b(return|respond|output)\b.{0,80}\b(only|instead|exactly)\b|"
            r"\bdo not\b.{0,80}\b(json|audit|human review|review|guardrail)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)

HALLUCINATION_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "approval_or_payment_guarantee",
        re.compile(
            r"\b(guarantee approval|guaranteed approval|will be approved|"
            r"must approve|must pay|100\s*%|100 percent|certain to win)(?=\W|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "submission_without_review",
        re.compile(
            r"\b(ready to file|submit immediately|no human review needed|"
            r"human review not required|without human review)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "unsupported_deadline_certainty",
        re.compile(
            r"\b(deadline is final|exact filing deadline|definitive deadline)\b",
            re.IGNORECASE,
        ),
    ),
)


def inspect_ai_input(text: str) -> dict[str, Any]:
    categories: list[str] = []
    for category, pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text or ""):
            categories.append(category)
    categories = sorted(set(categories))
    return {
        "prompt_injection_detected": bool(categories),
        "prompt_injection_categories": categories,
        "prompt_injection_finding_count": len(categories),
        "document_treated_as_untrusted": True,
        "safe_context": {
            "raw_document_text_included": False,
            "matched_value_included": False,
            "credentials_included": False,
        },
    }


def detect_hallucination_risks(text: str) -> list[str]:
    risks: list[str] = []
    for risk, pattern in HALLUCINATION_RISK_PATTERNS:
        if pattern.search(text or ""):
            risks.append(risk)
    return sorted(set(risks))


def build_document_analysis_fallback(
    extracted: dict[str, Any],
    *,
    fallback_reason: str,
    prompt_injection_detected: bool,
    prompt_injection_categories: list[str],
) -> str:
    priority_actions = [
        "Verify payer instructions, deadline, appeal route, and representative authority from source documents.",
        "Gather supporting records and payer policy evidence before drafting or submission.",
        "Keep any appeal draft marked draft_for_human_review until QA is complete.",
    ]
    if extracted.get("denial_code"):
        priority_actions.insert(0, "Research the denial code against payer policy and remittance guidance.")
    if extracted.get("procedure_codes"):
        priority_actions.insert(0, "Verify procedure, diagnosis, modifier, and service-line coding accuracy.")

    payload = {
        "summary": (
            "Deterministic fallback analysis generated from extracted fields because "
            "provider model analysis was unavailable or unsafe."
        ),
        "key_issues": _fallback_key_issues(extracted),
        "appeal_strength": "requires_human_review",
        "priority_actions": priority_actions[:5],
        "estimated_success_rate": "not_estimated_requires_human_review",
        "human_review_required": True,
        "filing_ready": False,
        "ai_guardrails": _guardrail_payload(
            fallback_used=True,
            fallback_reason=fallback_reason,
            prompt_injection_detected=prompt_injection_detected,
            prompt_injection_categories=prompt_injection_categories,
            hallucination_risk_categories=[],
        ),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def apply_document_analysis_guardrails(
    analysis: str,
    *,
    fallback_used: bool,
    fallback_reason: str | None,
    prompt_injection_detected: bool,
    prompt_injection_categories: list[str],
) -> str:
    payload = _json_object_from_text(analysis)
    if not isinstance(payload, dict):
        payload = {
            "summary": (analysis or "Analysis unavailable.")[:500],
            "key_issues": [],
            "appeal_strength": "requires_human_review",
            "priority_actions": [
                "Verify denial rationale, appeal route, deadlines, and supporting evidence before action."
            ],
            "estimated_success_rate": "not_estimated_requires_human_review",
        }

    hallucination_risks = detect_hallucination_risks(json.dumps(payload, sort_keys=True))
    if hallucination_risks:
        payload["estimated_success_rate"] = "not_estimated_requires_human_review"
        payload["appeal_strength"] = payload.get("appeal_strength") or "requires_human_review"

    guardrail_warnings = list(payload.get("guardrail_warnings") or [])
    if prompt_injection_detected:
        guardrail_warnings.append(
            "Prompt-injection-like instructions were detected in the source document and treated as untrusted text."
        )
    if fallback_used:
        guardrail_warnings.append(
            "Provider model analysis was unavailable; deterministic fallback output is not filing-ready."
        )
    if hallucination_risks:
        guardrail_warnings.append(
            "Unsupported approval, deadline, payment, or no-review language was detected and requires human QA."
        )
    if guardrail_warnings:
        payload["guardrail_warnings"] = sorted(set(str(item) for item in guardrail_warnings))

    payload["human_review_required"] = True
    payload["filing_ready"] = False
    payload["ai_guardrails"] = _guardrail_payload(
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        prompt_injection_detected=prompt_injection_detected,
        prompt_injection_categories=prompt_injection_categories,
        hallucination_risk_categories=hallucination_risks,
    )
    return json.dumps(payload, indent=2, sort_keys=True)


def _fallback_key_issues(extracted: dict[str, Any]) -> list[str]:
    issues = []
    if extracted.get("denial_code"):
        issues.append("denial_code_requires_policy_review")
    if extracted.get("denial_reason"):
        issues.append("payer_rationale_requires_source_verification")
    if extracted.get("procedure_codes"):
        issues.append("service_line_coding_requires_verification")
    if not issues:
        issues.append("denial_document_requires_human_review")
    return issues


def _guardrail_payload(
    *,
    fallback_used: bool,
    fallback_reason: str | None,
    prompt_injection_detected: bool,
    prompt_injection_categories: list[str],
    hallucination_risk_categories: list[str],
) -> dict[str, Any]:
    return {
        "prompt_injection_guardrail_active": True,
        "prompt_injection_detected": prompt_injection_detected,
        "prompt_injection_categories": sorted(set(prompt_injection_categories)),
        "hallucination_guardrail_active": True,
        "hallucination_risk_detected": bool(hallucination_risk_categories),
        "hallucination_risk_categories": sorted(set(hallucination_risk_categories)),
        "deterministic_fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "human_review_required": True,
        "filing_ready": False,
        "safe_context": {
            "raw_document_text_included": False,
            "matched_value_included": False,
            "credentials_included": False,
        },
    }


def _json_object_from_text(text: str) -> Any:
    if not isinstance(text, str):
        return None
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        return None
    return None

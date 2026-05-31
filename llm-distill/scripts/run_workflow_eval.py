#!/usr/bin/env python3
"""Run offline denial-workflow baseline evaluation on synthetic gold scenarios."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "health-ai-medical-billing-medical-corporations-20260414_180528"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.schemas.denial_workflow import DenialWorkflowAnalysisRequest  # noqa: E402
from app.services.denial_workflow import DenialWorkflowService  # noqa: E402


@dataclass
class ScenarioResult:
    scenario_id: str
    score: float
    max_score: float
    checks: dict[str, bool]
    expected: dict[str, Any]
    actual: dict[str, Any]
    missing_terms: list[str]
    forbidden_terms_found: list[str]

    @property
    def passed(self) -> bool:
        return self.score == self.max_score and not self.forbidden_terms_found

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "passed": self.passed,
            "score": self.score,
            "max_score": self.max_score,
            "score_ratio": round(self.score / self.max_score, 4) if self.max_score else 0.0,
            "checks": self.checks,
            "expected": self.expected,
            "actual": self.actual,
            "missing_terms": self.missing_terms,
            "forbidden_terms_found": self.forbidden_terms_found,
        }


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


def output_text(result: Any) -> str:
    return json.dumps(result, default=str, sort_keys=True).lower()


def normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", value.lower())).strip()


def contains_term(text: str, term: str) -> bool:
    normalized_text = normalize_for_match(text)
    normalized_term = normalize_for_match(term)
    return normalized_term in normalized_text or term.lower() in text


def evaluate_response(scenario: dict[str, Any], response: Any) -> ScenarioResult:
    expected = scenario.get("expected_output", {})
    actual = {
        "denial_type": response.denial_type,
        "recommended_route": response.recommended_route,
        "human_review_required": response.human_review_required,
        "route_confidence": response.route_confidence,
        "known_fact_count": len(response.known_from_documents),
        "retrieval_citation_count": len(response.retrieval_citations),
        "quality_check_count": len(response.quality_checks),
        "warning_count": len(response.warnings),
    }
    checks: dict[str, bool] = {}
    score = 0.0
    max_score = 0.0

    if "recommended_route" in expected:
        max_score += 2.0
        checks["route_match"] = response.recommended_route == expected["recommended_route"]
        if checks["route_match"]:
            score += 2.0
    if "denial_type" in expected:
        max_score += 1.5
        checks["denial_type_match"] = response.denial_type == expected["denial_type"]
        if checks["denial_type_match"]:
            score += 1.5
    if expected.get("human_review_required") is True:
        max_score += 1.0
        checks["human_review_required"] = response.human_review_required is True
        if checks["human_review_required"]:
            score += 1.0

    serialized = output_text(response.model_dump())
    required_terms = expected.get("must_include", [])
    missing_terms = [term for term in required_terms if not contains_term(serialized, term)]
    if required_terms:
        max_score += float(len(required_terms))
        score += float(len(required_terms) - len(missing_terms))
        checks["required_terms_present"] = not missing_terms

    forbidden_terms = expected.get("must_not_include", [])
    forbidden_terms_found = [term for term in forbidden_terms if contains_term(serialized, term)]
    if forbidden_terms:
        max_score += float(len(forbidden_terms))
        score += float(len(forbidden_terms) - len(forbidden_terms_found))
        checks["forbidden_terms_absent"] = not forbidden_terms_found

    max_score += 2.0
    checks["draft_marked_for_review"] = "draft_for_human_review" in (response.draft_appeal_letter or "")
    checks["quality_checks_present"] = bool(response.quality_checks)
    if checks["draft_marked_for_review"]:
        score += 1.0
    if checks["quality_checks_present"]:
        score += 1.0

    return ScenarioResult(
        scenario_id=scenario["scenario_id"],
        score=score,
        max_score=max_score,
        checks=checks,
        expected=expected,
        actual=actual,
        missing_terms=missing_terms,
        forbidden_terms_found=forbidden_terms_found,
    )


async def evaluate_scenarios(scenarios: list[dict[str, Any]]) -> list[ScenarioResult]:
    service = DenialWorkflowService()
    results = []
    for scenario in scenarios:
        response = await service.analyze(
            DenialWorkflowAnalysisRequest(
                document_text=scenario["input"]["document_text"],
                source_document_id=f"gold-{scenario['scenario_id'].lower()}",
                source_title=f"Synthetic gold scenario {scenario['scenario_id']}",
                generate_draft=True,
                use_llm=False,
            )
        )
        results.append(evaluate_response(scenario, response))
    return results


def summarize(results: list[ScenarioResult]) -> dict[str, Any]:
    total_score = sum(result.score for result in results)
    max_score = sum(result.max_score for result in results)
    return {
        "scenario_count": len(results),
        "passed_count": sum(1 for result in results if result.passed),
        "total_score": round(total_score, 4),
        "max_score": round(max_score, 4),
        "score_ratio": round(total_score / max_score, 4) if max_score else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=REPO_ROOT / "llm-distill" / "evals" / "cases" / "gold_scenarios.jsonl",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-under", type=float)
    args = parser.parse_args()

    scenarios = load_jsonl(args.cases)
    results = asyncio.run(evaluate_scenarios(scenarios))
    payload = {
        "summary": summarize(results),
        "results": [result.to_dict() for result in results],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote workflow eval results to {args.output}")
    else:
        print(json.dumps(payload, indent=2))

    if args.fail_under is not None and payload["summary"]["score_ratio"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

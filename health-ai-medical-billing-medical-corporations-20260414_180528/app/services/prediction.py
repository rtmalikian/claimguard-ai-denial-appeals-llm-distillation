import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import DenialPattern
from app.schemas.claim import ClaimPredictionRequest, DenialReason, Recommendation
from app.services.contract_rates import ContractRateFinding, evaluate_contract_rates
from app.services.nvidia import nvidia_service
from app.services.prediction_fairness import (
    annotate_denial_reason_driver,
    build_prediction_metadata as build_prediction_metadata_payload,
)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if (
                self.last_failure_time
                and (datetime.utcnow() - self.last_failure_time).total_seconds() > self.timeout
            ):
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            elif self.state == "closed":
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.utcnow()
            if self.failures >= self.failure_threshold:
                self.state = "open"
            raise e


circuit_breaker = CircuitBreaker()


llm_service = nvidia_service


class PredictionService:
    SYSTEM_PROMPT = """You are a medical billing expert analyzing claims for potential denials.
Analyze the claim data and identify specific issues that could lead to claim denial.
Provide detailed reasons and actionable recommendations.
Focus on: coding errors, missing documentation, policy violations, bundling issues, medical necessity."""

    def __init__(self, db: Session):
        self.db = db
        self.llm = llm_service

    async def predict_denial(
        self, request: ClaimPredictionRequest
    ) -> tuple[float, float, List[DenialReason], List[Recommendation]]:
        denial_reasons = []
        recommendations = []
        pattern_reasons = self._check_denial_patterns(
            request.diagnosis_codes or [], request.procedure_codes or []
        )
        denial_reasons.extend(pattern_reasons)
        contract_findings = evaluate_contract_rates(
            request.claim_data,
            request.procedure_codes or [],
        )
        denial_reasons.extend(self._contract_findings_to_denial_reasons(contract_findings))
        recommendations.extend(self._contract_findings_to_recommendations(contract_findings))
        ai_analysis = await self._analyze_with_ai(request)
        denial_reasons.extend(ai_analysis.get("reasons", []))
        recommendations.extend(ai_analysis.get("recommendations", []))
        if not denial_reasons:
            denial_reasons.append(
                DenialReason(reason="No obvious denial indicators found", severity="low")
            )
            recommendations.append(
                Recommendation(
                    action="Submit claim as normal",
                    description="Claim appears properly documented",
                    priority="low",
                )
            )
        denial_reasons = [
            annotate_denial_reason_driver(reason) for reason in denial_reasons
        ]
        denial_prediction = min(
            1.0,
            len(denial_reasons) * 0.2 + sum(0.2 for r in denial_reasons if r.severity == "high"),
        )
        denial_confidence = 0.65 + (len(denial_reasons) * 0.05)
        return (
            denial_prediction,
            min(denial_confidence, 0.95),
            denial_reasons,
            recommendations,
        )

    def build_prediction_metadata(
        self,
        request: ClaimPredictionRequest,
        reasons: List[DenialReason],
        recommendations: List[Recommendation],
    ) -> Dict[str, Any]:
        return build_prediction_metadata_payload(
            claim_data=request.claim_data,
            reasons=reasons,
            recommendations=recommendations,
        )

    def _check_denial_patterns(
        self, diagnosis_codes: List[str], procedure_codes: List[str]
    ) -> List[DenialReason]:
        reasons = []
        patterns = (
            self.db.query(DenialPattern)
            .filter(
                (DenialPattern.icd_code.in_(diagnosis_codes))
                | (DenialPattern.cpt_code.in_(procedure_codes))
            )
            .all()
        )
        for pattern in patterns:
            if pattern.denial_rate and pattern.denial_rate > 0.3:
                reasons.append(
                    DenialReason(
                        reason=f"Known high-risk pattern: {pattern.icd_code or pattern.cpt_code}",
                        severity="high" if pattern.denial_rate > 0.6 else "medium",
                        code=pattern.icd_code or pattern.cpt_code,
                    )
                )
                if pattern.common_reasons:
                    for reason in pattern.common_reasons[:2]:
                        reasons.append(
                            DenialReason(
                                reason=reason,
                                severity="medium",
                                code=pattern.icd_code or pattern.cpt_code,
                            )
                        )
        return reasons

    def _contract_findings_to_denial_reasons(
        self, findings: List[ContractRateFinding]
    ) -> List[DenialReason]:
        reasons = []
        for finding in findings:
            reasons.append(
                DenialReason(
                    reason=finding.description,
                    severity=finding.severity,
                    code=(
                        "CO-45"
                        if finding.finding_type == "charge_exceeds_contract_rate"
                        else "CHARGE-MASTER"
                    ),
                )
            )
        return reasons

    def _contract_findings_to_recommendations(
        self, findings: List[ContractRateFinding]
    ) -> List[Recommendation]:
        recommendations = []
        for finding in findings:
            action = (
                "Review contract rate and allowed amount"
                if finding.finding_type == "charge_exceeds_contract_rate"
                else "Review charge master amount"
            )
            recommendations.append(
                Recommendation(
                    action=action,
                    description=finding.recommendation,
                    priority=finding.severity,
                )
            )
        return recommendations

    async def _analyze_with_ai(self, request: ClaimPredictionRequest) -> Dict[str, Any]:
        claim_info = json.dumps(request.claim_data, indent=2)
        prompt = f"""Analyze this medical claim for potential denial risks:

Claim Data:
{claim_info}

Diagnosis Codes: {request.diagnosis_codes or "None"}
Procedure Codes: {request.procedure_codes or "None"}

Provide a JSON response with:
{{
  "reasons": [
    {{"reason": "specific issue", "severity": "high/medium/low", "code": "relevant code"}}
  ],
  "recommendations": [
    {{"action": "specific action", "description": "description", "priority": "high/medium/low"}}
  ]
}}
"""
        try:
            response = await self.llm.generate(
                prompt,
                self.SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1024,
            )
            return self._parse_ai_response(response)
        except Exception:
            return {
                "reasons": [],
                "recommendations": [
                    Recommendation(
                        action="Manual review recommended",
                        description="AI analysis unavailable - please review manually",
                        priority="high",
                    )
                ],
            }

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        try:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "reasons": [DenialReason(**r) for r in data.get("reasons", [])],
                    "recommendations": [
                        Recommendation(**r) for r in data.get("recommendations", [])
                    ],
                }
        except Exception:
            pass
        return {"reasons": [], "recommendations": []}

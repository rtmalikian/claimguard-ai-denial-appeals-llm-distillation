from typing import Any, Iterable

from app.schemas.claim import DenialReason, Recommendation


PREDICTION_HIGH_RISK_THRESHOLD = 0.5
PREDICTION_THRESHOLD_VERSION = "claim_denial_human_review_threshold_v1"
DEMOGRAPHIC_PARITY_DISPARITY_THRESHOLD = 0.10
MIN_FAIRNESS_GROUP_SIZE = 2

FAIRNESS_MONITORED_DEMOGRAPHIC_KEYS = {
    "age_band",
    "age_group",
    "disability_status",
    "ethnicity",
    "gender",
    "language",
    "race",
    "sex",
}


def monitored_demographic_keys_present(claim_data: dict[str, Any] | None) -> list[str]:
    if not isinstance(claim_data, dict):
        return []
    return sorted(
        key for key in claim_data.keys() if key in FAIRNESS_MONITORED_DEMOGRAPHIC_KEYS
    )


def driver_category_for_denial_reason(reason: DenialReason) -> str:
    code = str(reason.code or "").upper()
    text = str(reason.reason or "").lower()
    if code in {"CO-45", "CHARGE-MASTER"}:
        return "contract_or_charge_rate"
    if "known high-risk pattern" in text:
        return "diagnosis_procedure_pattern"
    if "documentation" in text:
        return "documentation_gap"
    if "authorization" in text:
        return "authorization_gap"
    if "medical necessity" in text:
        return "medical_necessity_review"
    if "timely" in text or "deadline" in text:
        return "timeliness_or_deadline"
    if "ai analysis unavailable" in text:
        return "model_availability_fallback"
    if "no obvious denial indicators" in text:
        return "no_obvious_denial_indicator"
    return "policy_or_model_analysis"


def source_field_for_driver_category(driver_category: str) -> str:
    if driver_category == "contract_or_charge_rate":
        return "claim_data.contract_rate_fields"
    if driver_category == "diagnosis_procedure_pattern":
        return "diagnosis_codes_or_procedure_codes"
    if driver_category == "documentation_gap":
        return "claim_data.documentation_presence"
    if driver_category == "authorization_gap":
        return "claim_data.authorization_metadata"
    if driver_category == "medical_necessity_review":
        return "diagnosis_codes_or_procedure_codes"
    if driver_category == "timeliness_or_deadline":
        return "claim_data.date_metadata"
    if driver_category == "model_availability_fallback":
        return "prediction_service.ai_provider_status"
    return "claim_data_or_policy_context"


def annotate_denial_reason_driver(reason: DenialReason) -> DenialReason:
    driver_category = driver_category_for_denial_reason(reason)
    return reason.model_copy(
        update={
            "driver_category": driver_category,
            "source_field": source_field_for_driver_category(driver_category),
        }
    )


def feature_driver_categories(reasons: Iterable[DenialReason]) -> list[str]:
    return sorted(
        {
            str(reason.driver_category or driver_category_for_denial_reason(reason))
            for reason in reasons
        }
    )


def threshold_metadata() -> dict[str, Any]:
    return {
        "threshold_version": PREDICTION_THRESHOLD_VERSION,
        "high_risk_threshold": PREDICTION_HIGH_RISK_THRESHOLD,
        "threshold_use": "human_review_routing_only",
        "auto_denial_threshold": False,
        "requires_human_review_above_threshold": True,
        "raw_claim_values_included": False,
    }


def prediction_fairness_metadata(
    *,
    claim_data: dict[str, Any] | None,
    reasons: list[DenialReason],
) -> dict[str, Any]:
    demographic_keys = monitored_demographic_keys_present(claim_data)
    return {
        "fairness_monitoring_enabled": True,
        "demographic_parity_metric_available": True,
        "demographic_parity_status": "requires_batch_evaluation",
        "demographic_attribute_key_count": len(demographic_keys),
        "demographic_attribute_keys_present": demographic_keys,
        "demographic_attribute_values_included": False,
        "raw_claim_values_included": False,
        "feature_driver_categories": feature_driver_categories(reasons),
    }


def build_prediction_metadata(
    *,
    claim_data: dict[str, Any] | None,
    reasons: list[DenialReason],
    recommendations: list[Recommendation],
) -> dict[str, Any]:
    return {
        "threshold": threshold_metadata(),
        "fairness": prediction_fairness_metadata(
            claim_data=claim_data,
            reasons=reasons,
        ),
        "explainability": {
            "feature_driver_categories": feature_driver_categories(reasons),
            "reason_count": len(reasons),
            "recommendation_count": len(recommendations),
            "raw_reason_text_included": False,
            "raw_recommendation_text_included": False,
            "raw_claim_values_included": False,
        },
    }


def evaluate_demographic_parity(
    records: list[dict[str, Any]],
    *,
    group_key: str,
    prediction_key: str = "denial_prediction",
    positive_threshold: float = PREDICTION_HIGH_RISK_THRESHOLD,
    disparity_threshold: float = DEMOGRAPHIC_PARITY_DISPARITY_THRESHOLD,
    min_group_size: int = MIN_FAIRNESS_GROUP_SIZE,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, int]] = {}
    evaluated_record_count = 0
    for record in records:
        if not isinstance(record, dict) or group_key not in record:
            continue
        try:
            prediction = float(record[prediction_key])
        except (KeyError, TypeError, ValueError):
            continue
        group_token = str(record[group_key])
        if group_token not in grouped:
            grouped[group_token] = {"record_count": 0, "positive_count": 0}
        grouped[group_token]["record_count"] += 1
        grouped[group_token]["positive_count"] += int(prediction > positive_threshold)
        evaluated_record_count += 1

    eligible_groups = [
        stats for _, stats in sorted(grouped.items()) if stats["record_count"] >= min_group_size
    ]
    group_rates = [
        stats["positive_count"] / stats["record_count"] for stats in eligible_groups
    ]
    max_disparity = max(group_rates) - min(group_rates) if len(group_rates) >= 2 else 0.0
    status = "insufficient_data"
    if len(group_rates) >= 2:
        status = (
            "needs_human_fairness_review"
            if max_disparity > disparity_threshold
            else "pass"
        )

    return {
        "metric": "demographic_parity_difference",
        "status": status,
        "record_count": len(records),
        "evaluated_record_count": evaluated_record_count,
        "group_count": len(grouped),
        "eligible_group_count": len(eligible_groups),
        "positive_threshold": positive_threshold,
        "disparity_threshold": disparity_threshold,
        "max_positive_rate_disparity": round(max_disparity, 3),
        "groups": [
            {
                "group_index": index + 1,
                "record_count": stats["record_count"],
                "positive_count": stats["positive_count"],
                "positive_rate": round(
                    stats["positive_count"] / stats["record_count"],
                    3,
                ),
            }
            for index, stats in enumerate(eligible_groups)
        ],
        "raw_group_values_included": False,
        "raw_claim_values_included": False,
    }

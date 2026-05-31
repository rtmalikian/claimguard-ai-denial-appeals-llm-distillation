from app.schemas.claim import DenialReason, Recommendation
from app.services.prediction_fairness import (
    annotate_denial_reason_driver,
    build_prediction_metadata,
    evaluate_demographic_parity,
)


def test_prediction_metadata_redacts_demographic_values_and_documents_threshold():
    reason = annotate_denial_reason_driver(
        DenialReason(
            reason="Known high-risk pattern: synthetic code",
            severity="high",
            code="Z00.00",
        )
    )

    metadata = build_prediction_metadata(
        claim_data={
            "race": "synthetic_group_a",
            "language": "synthetic_language_group",
            "amount": 100,
        },
        reasons=[reason],
        recommendations=[
            Recommendation(
                action="Review supporting documentation",
                description="Synthetic recommendation",
                priority="high",
            )
        ],
    )

    assert metadata["threshold"]["high_risk_threshold"] == 0.5
    assert metadata["threshold"]["threshold_use"] == "human_review_routing_only"
    assert metadata["threshold"]["auto_denial_threshold"] is False
    assert metadata["fairness"]["demographic_parity_metric_available"] is True
    assert metadata["fairness"]["demographic_attribute_keys_present"] == [
        "language",
        "race",
    ]
    assert metadata["fairness"]["demographic_attribute_values_included"] is False
    assert metadata["explainability"]["feature_driver_categories"] == [
        "diagnosis_procedure_pattern"
    ]
    assert reason.driver_category == "diagnosis_procedure_pattern"
    assert reason.source_field == "diagnosis_codes_or_procedure_codes"
    assert "synthetic_group_a" not in str(metadata)
    assert "synthetic_language_group" not in str(metadata)


def test_demographic_parity_metric_uses_group_indexes_not_group_values():
    records = [
        {"race": "synthetic_group_a", "denial_prediction": 0.9},
        {"race": "synthetic_group_a", "denial_prediction": 0.8},
        {"race": "synthetic_group_b", "denial_prediction": 0.1},
        {"race": "synthetic_group_b", "denial_prediction": 0.2},
    ]

    result = evaluate_demographic_parity(
        records,
        group_key="race",
        min_group_size=2,
        disparity_threshold=0.1,
    )

    assert result["metric"] == "demographic_parity_difference"
    assert result["status"] == "needs_human_fairness_review"
    assert result["group_count"] == 2
    assert result["eligible_group_count"] == 2
    assert result["max_positive_rate_disparity"] == 1.0
    assert result["raw_group_values_included"] is False
    assert result["raw_claim_values_included"] is False
    assert {group["group_index"] for group in result["groups"]} == {1, 2}
    assert "synthetic_group_a" not in str(result)
    assert "synthetic_group_b" not in str(result)


def test_demographic_parity_metric_requires_enough_groups():
    result = evaluate_demographic_parity(
        [{"race": "synthetic_group_a", "denial_prediction": 0.9}],
        group_key="race",
        min_group_size=2,
    )

    assert result["status"] == "insufficient_data"
    assert result["eligible_group_count"] == 0
    assert result["groups"] == []

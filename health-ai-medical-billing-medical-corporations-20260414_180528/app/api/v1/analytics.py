from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.core.auth import READ_ROLES, get_client_ip, require_roles
from app.schemas.analytics import (
    DenialTrendResponse,
    DenialTrendData,
    AnalyticsSummary,
    ClaimsByStatus,
    PredictionAccuracyPeriod,
    PredictionAccuracyResponse,
    TopDenialPatterns,
)
from app.models import Claim, DenialPattern
from app.utils.audit import log_audit
from datetime import datetime, timedelta

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _current_user_id(current_user: dict) -> int | None:
    return current_user.get("id") if isinstance(current_user, dict) else None


def _request_ip(request: Request | None) -> str | None:
    return get_client_ip(request) if request is not None else None


FINAL_DENIED_STATUSES = {
    "denied",
    "appealed",
    "appeal_pending",
    "appeal_submitted",
    "rejected",
}
FINAL_APPROVED_STATUSES = {
    "approved",
    "paid",
    "accepted",
    "clean",
    "not_denied",
}


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def _prediction_value(claim: Claim) -> float | None:
    value = getattr(claim, "denial_prediction", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _final_denial_outcome(status: str | None) -> bool | None:
    normalized = (status or "").strip().lower()
    if normalized in FINAL_DENIED_STATUSES:
        return True
    if normalized in FINAL_APPROVED_STATUSES:
        return False
    return None


def _claim_event_time(claim: Claim) -> datetime | None:
    return _naive_utc(getattr(claim, "submission_date", None)) or _naive_utc(
        getattr(claim, "created_at", None)
    )


def _empty_accuracy_period(period: str) -> PredictionAccuracyPeriod:
    return PredictionAccuracyPeriod(
        period=period,
        evaluated_claims=0,
        predicted_denials=0,
        actual_denials=0,
        true_positives=0,
        true_negatives=0,
        false_positives=0,
        false_negatives=0,
        accuracy=0.0,
        precision=0.0,
        recall=0.0,
        false_positive_rate=0.0,
        actual_denial_rate=0.0,
        predicted_denial_rate=0.0,
    )


def _accuracy_period(period: str, claims: list[Claim], threshold: float) -> PredictionAccuracyPeriod:
    counts = {
        "true_positives": 0,
        "true_negatives": 0,
        "false_positives": 0,
        "false_negatives": 0,
    }
    evaluated = 0
    predicted_denials = 0
    actual_denials = 0

    for claim in claims:
        prediction = _prediction_value(claim)
        actual_denied = _final_denial_outcome(getattr(claim, "status", None))
        if prediction is None or actual_denied is None:
            continue

        evaluated += 1
        predicted_denied = prediction >= threshold
        predicted_denials += 1 if predicted_denied else 0
        actual_denials += 1 if actual_denied else 0

        if predicted_denied and actual_denied:
            counts["true_positives"] += 1
        elif predicted_denied and not actual_denied:
            counts["false_positives"] += 1
        elif not predicted_denied and actual_denied:
            counts["false_negatives"] += 1
        else:
            counts["true_negatives"] += 1

    if evaluated == 0:
        return _empty_accuracy_period(period)

    true_positives = counts["true_positives"]
    true_negatives = counts["true_negatives"]
    false_positives = counts["false_positives"]
    false_negatives = counts["false_negatives"]

    return PredictionAccuracyPeriod(
        period=period,
        evaluated_claims=evaluated,
        predicted_denials=predicted_denials,
        actual_denials=actual_denials,
        true_positives=true_positives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        accuracy=_safe_ratio(true_positives + true_negatives, evaluated),
        precision=_safe_ratio(true_positives, true_positives + false_positives),
        recall=_safe_ratio(true_positives, true_positives + false_negatives),
        false_positive_rate=_safe_ratio(false_positives, false_positives + true_negatives),
        actual_denial_rate=_safe_ratio(actual_denials, evaluated),
        predicted_denial_rate=_safe_ratio(predicted_denials, evaluated),
    )


def _prediction_accuracy_report(
    claims: list[Claim],
    *,
    days: int,
    bucket_days: int,
    threshold: float,
    generated_at: datetime,
) -> tuple[list[PredictionAccuracyPeriod], dict]:
    start_date = generated_at - timedelta(days=days)
    periods: list[PredictionAccuracyPeriod] = []
    current_start = start_date

    while current_start < generated_at:
        current_end = min(current_start + timedelta(days=bucket_days), generated_at)
        period_claims = [
            claim
            for claim in claims
            if (event_time := _claim_event_time(claim)) is not None
            and current_start <= event_time < current_end
        ]
        period_label = f"{current_start.date().isoformat()} to {current_end.date().isoformat()}"
        periods.append(_accuracy_period(period_label, period_claims, threshold))
        current_start = current_end

    overall = _accuracy_period("overall", claims, threshold)
    total_claims = len(claims)
    evaluated_claims = overall.evaluated_claims
    summary = {
        "days": days,
        "bucket_days": bucket_days,
        "prediction_threshold": threshold,
        "total_claims_in_window": total_claims,
        "evaluated_claims": evaluated_claims,
        "excluded_claims": total_claims - evaluated_claims,
        "final_denied_statuses": sorted(FINAL_DENIED_STATUSES),
        "final_approved_statuses": sorted(FINAL_APPROVED_STATUSES),
        "accuracy": overall.accuracy,
        "precision": overall.precision,
        "recall": overall.recall,
        "false_positive_rate": overall.false_positive_rate,
        "actual_denial_rate": overall.actual_denial_rate,
        "predicted_denial_rate": overall.predicted_denial_rate,
    }
    return periods, summary


@router.get("/denial-trends", response_model=DenialTrendResponse)
async def get_denial_trends(
    request: Request = None,
    days: int = 30,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    start_date = datetime.utcnow() - timedelta(days=days)

    claims = db.query(Claim).filter(Claim.created_at >= start_date).all()

    trends = []
    periods = ["Week 1", "Week 2", "Week 3", "Week 4"] if days >= 28 else ["Period"]
    period_days = days // len(periods) if days >= 28 else days

    for i, period in enumerate(periods):
        period_start = start_date + timedelta(days=i * period_days)
        period_end = period_start + timedelta(days=period_days)
        period_claims = [
            c
            for c in claims
            if c.created_at
            and period_start.replace(tzinfo=None)
            <= c.created_at.replace(tzinfo=None)
            < period_end.replace(tzinfo=None)
        ]
        total = len(period_claims)
        predicted_denials = len(
            [c for c in period_claims if c.denial_prediction and c.denial_prediction > 0.5]
        )

        all_reasons = []
        for c in period_claims:
            if c.denial_reasons:
                all_reasons.extend(c.denial_reasons)

        top_reasons = []
        if all_reasons:
            reason_counts = {}
            for r in all_reasons:
                reason = r.get("reason", "Unknown") if isinstance(r, dict) else "Unknown"
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:5]
            top_reasons = [{"reason": r[0], "count": r[1]} for r in top_reasons]

        trends.append(
            DenialTrendData(
                period=period,
                total_claims=total,
                predicted_denials=predicted_denials,
                denial_rate=predicted_denials / total if total > 0 else 0.0,
                top_reasons=top_reasons,
            )
        )

    total_claims = len(claims)
    pending = len([c for c in claims if c.status == "pending"])
    processed = total_claims - pending
    predicted_denial_rate = (
        sum(c.denial_prediction or 0 for c in claims) / total_claims if total_claims > 0 else 0
    )

    summary = {
        "total_claims": total_claims,
        "pending_claims": pending,
        "processed_claims": processed,
        "predicted_denial_rate": round(predicted_denial_rate, 2),
    }

    log_audit(
        db=db,
        action="analytics_denial_trends_viewed",
        user_id=_current_user_id(current_user),
        details={
            "days": days,
            "total_claims": total_claims,
            "period_count": len(trends),
            "predicted_denial_rate": round(predicted_denial_rate, 2),
        },
        ip_address=_request_ip(request),
    )
    return DenialTrendResponse(trends=trends, summary=summary, generated_at=datetime.utcnow())


@router.get("/prediction-accuracy", response_model=PredictionAccuracyResponse)
async def get_prediction_accuracy(
    request: Request = None,
    days: int = Query(default=90, ge=1, le=3650),
    bucket_days: int = Query(default=30, ge=1, le=365),
    threshold: float = Query(default=0.5, ge=0.0, le=1.0),
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    generated_at = datetime.utcnow()
    start_date = generated_at - timedelta(days=days)
    claims = (
        db.query(Claim)
        .filter(Claim.created_at >= start_date)
        .all()
    )
    periods, summary = _prediction_accuracy_report(
        claims,
        days=days,
        bucket_days=min(bucket_days, days),
        threshold=threshold,
        generated_at=generated_at,
    )

    log_audit(
        db=db,
        action="analytics_prediction_accuracy_viewed",
        user_id=_current_user_id(current_user),
        details={
            "days": days,
            "bucket_days": min(bucket_days, days),
            "prediction_threshold": threshold,
            "total_claims_in_window": summary["total_claims_in_window"],
            "evaluated_claims": summary["evaluated_claims"],
            "excluded_claims": summary["excluded_claims"],
            "period_count": len(periods),
            "accuracy": summary["accuracy"],
        },
        ip_address=_request_ip(request),
    )
    return PredictionAccuracyResponse(
        periods=periods,
        summary=summary,
        generated_at=generated_at,
    )


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    request: Request = None,
    current_user: dict = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db),
):
    total = db.query(func.count(Claim.id)).scalar()
    pending = db.query(func.count(Claim.id)).filter(Claim.status == "pending").scalar()
    processed = db.query(func.count(Claim.id)).filter(Claim.status == "submitted").scalar()

    claims = db.query(Claim).all()
    predicted_rate = sum(c.denial_prediction or 0 for c in claims) / total if total > 0 else 0

    status_counts = {}
    for claim in claims:
        status_counts[claim.status] = status_counts.get(claim.status, 0) + 1

    claims_by_status = [
        ClaimsByStatus(status=s, count=c, percentage=round(c / total * 100, 1) if total > 0 else 0)
        for s, c in status_counts.items()
    ]

    pattern_data = (
        db.query(DenialPattern).order_by(DenialPattern.denial_rate.desc()).limit(10).all()
    )
    top_denial_patterns = [
        TopDenialPatterns(
            pattern=f"{p.icd_code or ''} / {p.cpt_code or ''}",
            count=int(p.denial_rate * 100),
            percentage=round(p.denial_rate * 100, 1),
        )
        for p in pattern_data
    ]

    log_audit(
        db=db,
        action="analytics_summary_viewed",
        user_id=_current_user_id(current_user),
        details={
            "total_claims": total or 0,
            "pending_claims": pending or 0,
            "processed_claims": processed or 0,
            "status_count": len(status_counts),
            "top_denial_pattern_count": len(top_denial_patterns),
        },
        ip_address=_request_ip(request),
    )
    return AnalyticsSummary(
        total_claims=total or 0,
        pending_claims=pending or 0,
        processed_claims=processed or 0,
        predicted_denial_rate=round(predicted_rate, 2),
        claims_by_status=claims_by_status,
        top_denial_patterns=top_denial_patterns,
    )

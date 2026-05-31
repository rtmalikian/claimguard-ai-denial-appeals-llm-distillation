from typing import Any


CLAIM_STATUS_DRAFT = "draft"
CLAIM_STATUS_PENDING = "pending"
CLAIM_STATUS_SUBMITTED = "submitted"
CLAIM_STATUS_DENIED = "denied"
CLAIM_STATUS_APPEALED = "appealed"
CLAIM_STATUS_PAID = "paid"
CLAIM_STATUS_PARTIALLY_PAID = "partially_paid"
CLAIM_STATUS_WRITE_OFF = "write_off"

CANONICAL_CLAIM_STATUSES = (
    CLAIM_STATUS_DRAFT,
    CLAIM_STATUS_PENDING,
    CLAIM_STATUS_SUBMITTED,
    CLAIM_STATUS_DENIED,
    CLAIM_STATUS_APPEALED,
    CLAIM_STATUS_PAID,
    CLAIM_STATUS_PARTIALLY_PAID,
    CLAIM_STATUS_WRITE_OFF,
)

LEGACY_READABLE_CLAIM_STATUSES = (
    "analyzed",
    "accepted",
    "approved",
    "appeal_pending",
    "appeal_submitted",
    "clean",
    "not_denied",
    "rejected",
)

CLAIM_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    CLAIM_STATUS_DRAFT: (
        CLAIM_STATUS_PENDING,
        CLAIM_STATUS_SUBMITTED,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_PENDING: (
        CLAIM_STATUS_SUBMITTED,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_SUBMITTED: (
        CLAIM_STATUS_DENIED,
        CLAIM_STATUS_PAID,
        CLAIM_STATUS_PARTIALLY_PAID,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_DENIED: (
        CLAIM_STATUS_APPEALED,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_APPEALED: (
        CLAIM_STATUS_DENIED,
        CLAIM_STATUS_PAID,
        CLAIM_STATUS_PARTIALLY_PAID,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_PARTIALLY_PAID: (
        CLAIM_STATUS_APPEALED,
        CLAIM_STATUS_PAID,
        CLAIM_STATUS_WRITE_OFF,
    ),
    CLAIM_STATUS_PAID: (),
    CLAIM_STATUS_WRITE_OFF: (),
}

LEGACY_STATUS_TRANSITION_ALIASES = {
    "analyzed": CLAIM_STATUS_DRAFT,
    "accepted": CLAIM_STATUS_PAID,
    "approved": CLAIM_STATUS_PAID,
    "appeal_pending": CLAIM_STATUS_APPEALED,
    "appeal_submitted": CLAIM_STATUS_APPEALED,
    "clean": CLAIM_STATUS_PAID,
    "not_denied": CLAIM_STATUS_PAID,
    "rejected": CLAIM_STATUS_DENIED,
}


def normalize_claim_status(status: Any) -> str:
    return str(status or "").strip().lower()


def is_canonical_claim_status(status: Any) -> bool:
    return normalize_claim_status(status) in CANONICAL_CLAIM_STATUSES


def is_readable_claim_status(status: Any) -> bool:
    normalized = normalize_claim_status(status)
    return normalized in CANONICAL_CLAIM_STATUSES or normalized in LEGACY_READABLE_CLAIM_STATUSES


def claim_status_for_transition(status: Any) -> str:
    normalized = normalize_claim_status(status)
    return LEGACY_STATUS_TRANSITION_ALIASES.get(normalized, normalized)


def allowed_next_claim_statuses(status: Any) -> tuple[str, ...]:
    return CLAIM_STATUS_TRANSITIONS.get(claim_status_for_transition(status), ())


def validate_claim_status_transition(current_status: Any, requested_status: Any) -> tuple[bool, list[str]]:
    requested = normalize_claim_status(requested_status)
    if requested not in CANONICAL_CLAIM_STATUSES:
        return False, ["requested_status_is_not_canonical"]

    current = claim_status_for_transition(current_status)
    if current not in CANONICAL_CLAIM_STATUSES:
        return False, ["current_status_is_not_supported"]

    if current == requested:
        return True, []

    allowed_next = allowed_next_claim_statuses(current)
    if requested not in allowed_next:
        return False, ["transition_not_allowed"]

    return True, []

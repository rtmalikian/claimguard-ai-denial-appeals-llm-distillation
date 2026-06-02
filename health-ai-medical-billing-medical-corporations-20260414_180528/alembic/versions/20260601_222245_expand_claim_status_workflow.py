"""expand claim status workflow

Revision ID: 20260601_222245
Revises: 20260531_033507
Create Date: 2026-06-01 22:22:45
"""

from alembic import op


revision = "20260601_222245"
down_revision = "20260531_033507"
branch_labels = None
depends_on = None


CLAIM_STATUS_CHECK_NAME = "ck_claims_status_canonical"
EXPANDED_CLAIM_STATUSES = (
    "draft",
    "pending",
    "scrubbing",
    "submitted",
    "accepted",
    "in_review",
    "denied",
    "appealed",
    "appeal_approved",
    "appeal_denied",
    "paid",
    "partially_paid",
    "write_off",
    "timely_filing",
)
PREVIOUS_CLAIM_STATUSES = (
    "draft",
    "pending",
    "submitted",
    "denied",
    "appealed",
    "paid",
    "partially_paid",
    "write_off",
)
EXPANDED_CLAIM_STATUS_CHECK_SQL = (
    "status IN ("
    + ", ".join(repr(status) for status in EXPANDED_CLAIM_STATUSES)
    + ")"
)
PREVIOUS_CLAIM_STATUS_CHECK_SQL = (
    "status IN ("
    + ", ".join(repr(status) for status in PREVIOUS_CLAIM_STATUSES)
    + ")"
)
DOWNGRADE_STATUS_ALIASES = {
    "scrubbing": "pending",
    "accepted": "submitted",
    "in_review": "submitted",
    "appeal_approved": "paid",
    "appeal_denied": "denied",
    "timely_filing": "denied",
}


def upgrade() -> None:
    op.drop_constraint(CLAIM_STATUS_CHECK_NAME, "claims", type_="check")
    op.create_check_constraint(
        CLAIM_STATUS_CHECK_NAME,
        "claims",
        EXPANDED_CLAIM_STATUS_CHECK_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(CLAIM_STATUS_CHECK_NAME, "claims", type_="check")
    for expanded_status, previous_status in DOWNGRADE_STATUS_ALIASES.items():
        op.execute(
            "UPDATE claims "
            f"SET status = '{previous_status}' "
            f"WHERE status = '{expanded_status}'"
        )
    op.create_check_constraint(
        CLAIM_STATUS_CHECK_NAME,
        "claims",
        PREVIOUS_CLAIM_STATUS_CHECK_SQL,
    )

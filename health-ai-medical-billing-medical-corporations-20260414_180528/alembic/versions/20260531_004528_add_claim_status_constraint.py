"""add claim status constraint

Revision ID: 20260531_004528
Revises: 20260530_120221
Create Date: 2026-05-31 00:45:28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260531_004528"
down_revision = "20260530_120221"
branch_labels = None
depends_on = None


CANONICAL_CLAIM_STATUSES = (
    "draft",
    "pending",
    "submitted",
    "denied",
    "appealed",
    "paid",
    "partially_paid",
    "write_off",
)
CLAIM_STATUS_CHECK_NAME = "ck_claims_status_canonical"
CLAIM_STATUS_CHECK_SQL = (
    "status IN ("
    + ", ".join(repr(status) for status in CANONICAL_CLAIM_STATUSES)
    + ")"
)
LEGACY_STATUS_ALIASES = {
    "analyzed": "draft",
    "accepted": "paid",
    "approved": "paid",
    "appeal_pending": "appealed",
    "appeal_submitted": "appealed",
    "clean": "paid",
    "not_denied": "paid",
    "rejected": "denied",
}


def upgrade() -> None:
    op.execute("UPDATE claims SET status = lower(trim(status)) WHERE status IS NOT NULL")
    op.execute("UPDATE claims SET status = 'pending' WHERE status IS NULL OR status = ''")
    for legacy_status, canonical_status in LEGACY_STATUS_ALIASES.items():
        op.execute(
            "UPDATE claims "
            f"SET status = '{canonical_status}' "
            f"WHERE status = '{legacy_status}'"
        )

    op.alter_column(
        "claims",
        "status",
        existing_type=sa.String(length=50),
        nullable=False,
    )
    op.create_check_constraint(
        CLAIM_STATUS_CHECK_NAME,
        "claims",
        CLAIM_STATUS_CHECK_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(CLAIM_STATUS_CHECK_NAME, "claims", type_="check")
    op.alter_column(
        "claims",
        "status",
        existing_type=sa.String(length=50),
        nullable=True,
    )

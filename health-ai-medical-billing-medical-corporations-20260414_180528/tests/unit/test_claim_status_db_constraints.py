from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models import Claim, CLAIM_STATUS_CHECK_NAME, CLAIM_STATUS_CHECK_SQL
from app.services.claim_state import CANONICAL_CLAIM_STATUSES, CLAIM_STATUS_PENDING


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260531_004528_add_claim_status_constraint.py"
)


def test_claim_model_declares_canonical_status_check_constraint():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in Claim.__table__.constraints
        if constraint.name
    }

    assert Claim.__table__.c.status.nullable is False
    assert Claim.__table__.c.status.default.arg == CLAIM_STATUS_PENDING
    assert constraints[CLAIM_STATUS_CHECK_NAME] == CLAIM_STATUS_CHECK_SQL
    for status in CANONICAL_CLAIM_STATUSES:
        assert repr(status) in constraints[CLAIM_STATUS_CHECK_NAME]


def test_claim_status_check_constraint_blocks_noncanonical_status():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    session.execute(
        Claim.__table__.insert().values(
            patient_id=1,
            provider_id=1,
            claim_data={"synthetic": True},
            status="draft",
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
        session.execute(
            Claim.__table__.insert().values(
                patient_id=1,
                provider_id=1,
                claim_data={"synthetic": True},
                status="approved",
            )
        )


def test_claim_status_migration_normalizes_legacy_statuses_before_constraint():
    migration_text = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'down_revision = "20260530_120221"' in migration_text
    assert f'CLAIM_STATUS_CHECK_NAME = "{CLAIM_STATUS_CHECK_NAME}"' in migration_text
    assert "op.create_check_constraint(" in migration_text
    assert "op.drop_constraint(" in migration_text
    assert "op.alter_column(" in migration_text
    assert '"analyzed": "draft"' in migration_text
    assert '"approved": "paid"' in migration_text
    for status in CANONICAL_CLAIM_STATUSES:
        assert f'"{status}"' in migration_text

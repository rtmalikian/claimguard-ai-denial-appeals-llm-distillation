from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import EncryptionService, generate_fernet_key
from app.db.database import Base
from app.models import AuditLog, RetrievalSourceChunk, RetrievalSourceDocument
from app.schemas.denial_workflow import (
    DenialWorkflowAnalysisRequest,
    RetrievalSearchRequest,
    RetrievalSourceCreateRequest,
)
from app.services.denial_workflow import DenialWorkflowService
from app.services.retrieval_store import RetrievalStoreError, RetrievalStoreService


ADMIN_USER = {"id": 1, "role": "admin"}
BILLING_USER = {"id": 10, "role": "billing_staff"}
OTHER_BILLING_USER = {"id": 20, "role": "billing_staff"}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def store(db_session):
    encryption = EncryptionService(keys=[generate_fernet_key()], app_env="test")
    return RetrievalStoreService(db_session, encryption=encryption)


def _source_request(
    title: str,
    phrase: str,
    *,
    access_scope: str = "owner",
    retention_until: datetime | None = None,
) -> RetrievalSourceCreateRequest:
    return RetrievalSourceCreateRequest(
        title=title,
        source_type="synthetic_policy",
        document_text=(
            f"Synthetic governance source for testing. {phrase} "
            "Appeal evidence should stay source-grounded and reviewable."
        ),
        phi_status="no_phi",
        license_status="synthetic_internal",
        access_scope=access_scope,
        retention_until=retention_until,
        chunk_size=200,
        overlap=20,
    )


def test_role_scoped_source_listing_and_search(store):
    owner_source = store.create_source(
        _source_request("Synthetic Owner Source", "owner-only modifier evidence"),
        created_by_user_id=BILLING_USER["id"],
    )
    team_source = store.create_source(
        _source_request(
            "Synthetic Team Source",
            "team-shared appeal evidence",
            access_scope="billing_team",
        ),
        created_by_user_id=OTHER_BILLING_USER["id"],
    )
    admin_source = store.create_source(
        _source_request(
            "Synthetic Admin Source",
            "admin-restricted appeal evidence",
            access_scope="admin_only",
        ),
        created_by_user_id=ADMIN_USER["id"],
    )

    billing_sources = store.list_sources(current_user=BILLING_USER)
    billing_source_ids = {source.source_id for source in billing_sources}

    assert owner_source.source_id in billing_source_ids
    assert team_source.source_id in billing_source_ids
    assert admin_source.source_id not in billing_source_ids

    billing_results = store.search(
        RetrievalSearchRequest(query="admin-restricted", top_k=5),
        current_user=BILLING_USER,
    ).results
    assert all(result.source_id != admin_source.source_id for result in billing_results)

    admin_source_ids = {
        source.source_id for source in store.list_sources(current_user=ADMIN_USER)
    }
    assert {owner_source.source_id, team_source.source_id, admin_source.source_id}.issubset(
        admin_source_ids
    )


def test_soft_delete_excludes_source_from_list_search_and_reports_retention(store, db_session):
    expired_source = store.create_source(
        _source_request(
            "Synthetic Expired Owner Source",
            "expired retention appeal pathway evidence",
            retention_until=datetime.utcnow() - timedelta(days=1),
        ),
        created_by_user_id=BILLING_USER["id"],
    )
    summary_before_delete = store.governance_summary(current_user=BILLING_USER)
    assert summary_before_delete.active_count == 1
    assert summary_before_delete.expired_active_count == 1

    delete_result = store.delete_source(
        expired_source.source_id,
        current_user=BILLING_USER,
        deletion_reason="synthetic retention test deletion",
    )

    assert delete_result.deleted is True
    assert delete_result.deleted_by_user_id == BILLING_USER["id"]
    assert delete_result.deletion_reason == "synthetic retention test deletion"

    listed_ids = {
        source.source_id for source in store.list_sources(current_user=BILLING_USER)
    }
    assert expired_source.source_id not in listed_ids

    search_results = store.search(
        RetrievalSearchRequest(query="expired retention", top_k=5),
        current_user=BILLING_USER,
    ).results
    assert all(result.source_id != expired_source.source_id for result in search_results)

    summary_after_delete = store.governance_summary(current_user=BILLING_USER)
    assert summary_after_delete.active_count == 0
    assert summary_after_delete.deleted_count == 1

    stored_source = db_session.query(RetrievalSourceDocument).one()
    stored_chunks = db_session.query(RetrievalSourceChunk).all()
    assert stored_source.deleted_at is not None
    assert stored_chunks


def test_only_admin_or_owner_can_delete_source(store):
    created = store.create_source(
        _source_request(
            "Synthetic Shared Owner Source",
            "shared source deletion permissions",
            access_scope="billing_team",
        ),
        created_by_user_id=OTHER_BILLING_USER["id"],
    )

    with pytest.raises(RetrievalStoreError, match="Only admins"):
        store.delete_source(
            created.source_id,
            current_user=BILLING_USER,
            deletion_reason="synthetic unauthorized deletion attempt",
        )

    admin_delete = store.delete_source(
        created.source_id,
        current_user=ADMIN_USER,
        deletion_reason="synthetic admin retention deletion",
    )
    assert admin_delete.deleted is True


@pytest.mark.asyncio
async def test_denial_workflow_retrieval_respects_current_user_scope(db_session, store):
    hidden = store.create_source(
        _source_request(
            "Synthetic Hidden Admin Rule",
            "admin-only rare route evidence",
            access_scope="admin_only",
        ),
        created_by_user_id=ADMIN_USER["id"],
    )
    visible = store.create_source(
        _source_request(
            "Synthetic Visible Team Rule",
            "team-visible appeal route evidence",
            access_scope="billing_team",
        ),
        created_by_user_id=ADMIN_USER["id"],
    )

    result = await DenialWorkflowService(
        db=db_session,
        retrieval_store=store,
        current_user=BILLING_USER,
    ).analyze(
        DenialWorkflowAnalysisRequest(
            document_text=(
                "Synthetic denial notice. Payer: Example Health. "
                "Reason for Denial: missing documentation. The provider may appeal."
            ),
            source_document_id="synthetic-governance-denial",
            use_llm=False,
        )
    )

    citation_ids = {item.source_id for item in result.retrieval_citations}
    assert hidden.source_id not in citation_ids
    assert visible.source_id in citation_ids


def test_audit_dashboard_returns_only_safe_document_event_details(store, db_session):
    db_session.add(
        AuditLog(
            user_id=ADMIN_USER["id"],
            action="denial_retrieval_source_created",
            details={
                "source_id": "SRC-LOCAL-SAFEAUDIT",
                "source_type": "synthetic_policy",
                "phi_status": "no_phi",
                "document_text": "do not surface source text",
                "matched_value": "redacted synthetic placeholder",
            },
            timestamp=datetime.utcnow(),
        )
    )
    db_session.commit()

    dashboard = store.audit_dashboard(source_id="SRC-LOCAL-SAFEAUDIT")

    assert dashboard.event_count == 1
    assert dashboard.events[0].details == {
        "source_id": "SRC-LOCAL-SAFEAUDIT",
        "source_type": "synthetic_policy",
        "phi_status": "no_phi",
    }

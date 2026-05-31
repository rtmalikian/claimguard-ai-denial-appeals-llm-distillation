import pytest
from unittest.mock import MagicMock, patch
from app.utils.audit import log_audit, sanitize_audit_details


class TestAuditLogging:
    def test_log_audit_creates_record(self):
        mock_db = MagicMock()

        log_audit(
            db=mock_db,
            action="document_analyzed",
            user_id=1,
            claim_id=5,
            details={"model": "qwen2.5"},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_audit_without_claim(self):
        mock_db = MagicMock()

        log_audit(
            db=mock_db,
            action="user_login",
            user_id=1,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_audit_redacts_sensitive_details(self):
        mock_db = MagicMock()

        log_audit(
            db=mock_db,
            action="document_uploaded",
            user_id=2,
            claim_id=10,
            details={
                "filename": "test.pdf",
                "mrn": "SYNTH-MRN-123",
                "document_text": "Member ID: SYN-MEMBER-001 should never be logged",
                "size": 1024,
                "type": "application/pdf",
            },
        )

        mock_db.add.assert_called_once()
        call_args = mock_db.add.call_args[0][0]
        assert call_args.details["filename"]["redacted"] is True
        assert call_args.details["mrn"]["redacted"] is True
        assert call_args.details["document_text"]["redacted"] is True
        assert call_args.details["document_text"]["phi_finding_count"] == 1
        assert call_args.details["size"] == 1024
        assert "SYN-MEMBER-001" not in str(call_args.details)

    def test_sanitize_audit_details_redacts_phi_like_safe_key_values(self):
        details = sanitize_audit_details(
            {
                "note": "Reach the synthetic payer at 555-555-0199.",
                "claim_id": 123,
            }
        )

        assert details["note"]["redacted"] is True
        assert details["note"]["phi_finding_count"] == 1
        assert details["claim_id"] == 123
        assert "555-555-0199" not in str(details)

    def test_log_audit_with_ip_address(self):
        mock_db = MagicMock()

        log_audit(
            db=mock_db,
            action="claim_viewed",
            user_id=1,
            claim_id=3,
            ip_address="192.168.1.1",
        )

        mock_db.add.assert_called_once()
        call_args = mock_db.add.call_args[0][0]
        assert call_args.ip_address == "192.168.1.1"

    def test_log_audit_returns_audit_log(self):
        mock_db = MagicMock()

        result = log_audit(
            db=mock_db,
            action="api_access",
            user_id=1,
        )

        mock_db.add.assert_called_once()
        assert result.action == "api_access"
        assert result.user_id == 1

import logging

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


class TestClaimsDocumentAnalysis:
    def test_parse_document_ai_analysis_logs_safe_metadata_for_invalid_json(self, caplog):
        from app.api.v1.claims import _parse_document_ai_analysis

        with caplog.at_level(logging.WARNING, logger="app.api.v1.claims"):
            result = _parse_document_ai_analysis(
                '{"summary": "Synthetic analysis",}',
                processing_stage="unit_test_analysis_parse",
            )

        assert result["summary"] == '{"summary": "Synthetic analysis",}'
        parse_error = caplog.records[-1].document_analysis_parse_error
        assert parse_error["error_code"] == "invalid_analysis_json"
        assert parse_error["processing_stage"] == "unit_test_analysis_parse"
        assert parse_error["analysis_present"] is True
        assert parse_error["safe_context"] == {
            "raw_analysis_included": False,
            "raw_document_text_included": False,
            "matched_value_included": False,
        }
        assert "raw_analysis" not in parse_error

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    @patch("app.api.v1.claims.get_db")
    async def test_analyze_document_success(self, mock_get_db, mock_analyze, mock_log):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_result = MagicMock()
        mock_result.document_type = "denial_letter"
        mock_result.payer_name = "Aetna"
        mock_result.denial_reason = "Missing info"
        mock_result.denial_code = "CO16"
        mock_result.claim_amount = 500.0
        mock_result.service_date = "01/15/2024"
        mock_result.patient_name = "John Doe"
        mock_result.policy_number = "ABC-123"
        mock_result.extracted_codes = ["99213"]
        mock_result.analysis = '{"summary": "Test analysis", "appeal_strength": "moderate"}'
        mock_result.recommendations = []
        mock_result.appeal_strategy = "Submit appeal"
        mock_result.analyzed_at = datetime.utcnow()

        mock_analyze.return_value = mock_result

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        def set_claim_id(claim):
            claim.id = 1

        mock_db.refresh = MagicMock(side_effect=set_claim_id)

        from app.api.v1.claims import analyze_document
        from app.schemas.claim import DocumentAnalysisRequest
        from fastapi import Request

        mock_request = MagicMock(spec=Request)

        doc_request = DocumentAnalysisRequest(
            document_text="Denial letter text here with enough characters to pass validation"
        )

        result = await analyze_document(request=mock_request, doc_request=doc_request, db=mock_db)

        assert result.document_type == "denial_letter"

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    @patch("app.api.v1.claims.get_db")
    async def test_analyze_document_creates_claim(self, mock_get_db, mock_analyze, mock_log):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_result = MagicMock()
        mock_result.document_type = "denial_letter"
        mock_result.payer_name = "BCBS"
        mock_result.denial_reason = None
        mock_result.denial_code = None
        mock_result.claim_amount = None
        mock_result.service_date = None
        mock_result.patient_name = None
        mock_result.policy_number = None
        mock_result.extracted_codes = []
        mock_result.analysis = "Analysis text"
        mock_result.recommendations = []
        mock_result.appeal_strategy = None
        mock_result.analyzed_at = datetime.utcnow()

        mock_analyze.return_value = mock_result

        added_claim = None

        def capture_claim(claim):
            nonlocal added_claim
            added_claim = claim
            claim.id = 1

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=capture_claim)

        from app.api.v1.claims import analyze_document
        from app.schemas.claim import DocumentAnalysisRequest
        from fastapi import Request

        mock_request = MagicMock(spec=Request)

        doc_request = DocumentAnalysisRequest(
            document_text="This is a denial letter with enough text to pass validation"
        )

        result = await analyze_document(request=mock_request, doc_request=doc_request, db=mock_db)

        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        assert added_claim is not None


class TestClaimsUploadDocument:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.log_audit")
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    @patch("app.api.v1.claims.get_db")
    async def test_upload_text_file(self, mock_get_db, mock_analyze, mock_log):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_result = MagicMock()
        mock_result.document_type = "denial_letter"
        mock_result.payer_name = "Aetna"
        mock_result.denial_reason = "Test"
        mock_result.denial_code = "CO16"
        mock_result.claim_amount = 100.0
        mock_result.service_date = None
        mock_result.patient_name = None
        mock_result.policy_number = None
        mock_result.extracted_codes = []
        mock_result.analysis = "Test analysis"
        mock_result.recommendations = []
        mock_result.appeal_strategy = None
        mock_result.analyzed_at = datetime.utcnow()

        mock_analyze.return_value = mock_result

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

        from app.api.v1.claims import upload_document
        from fastapi import UploadFile

        file_content = b"This is denial letter content for testing purposes"
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "denial.txt"
        mock_file.size = len(file_content)
        mock_file.read = AsyncMock(return_value=file_content)

        result = await upload_document(file=mock_file, db=mock_db)

        assert result.payer_name == "Aetna"
        mock_db.add.assert_called()
        mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file_before_processing(self):
        from app.api.v1.claims import CLAIM_DOCUMENT_UPLOAD_MAX_BYTES, upload_document
        from fastapi import HTTPException, UploadFile

        large_content = b"x" * (CLAIM_DOCUMENT_UPLOAD_MAX_BYTES + 1)
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-large-denial.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=large_content)

        with patch("app.utils.file_processing.FileProcessor.process_file") as mock_process, \
            patch("app.api.v1.claims.DocumentAnalysisService.analyze_document") as mock_analyze, \
            patch("app.api.v1.claims.log_audit") as mock_log:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        assert detail["error_code"] == "file_too_large"
        assert detail["processing_stage"] == "file_validation"
        assert detail["source_filename_present"] is True
        assert detail["source_file_extension"] == ".pdf"
        assert detail["source_mime_type"] == "application/pdf"
        assert detail["content_length"] == CLAIM_DOCUMENT_UPLOAD_MAX_BYTES + 1
        assert detail["max_upload_size_bytes"] == CLAIM_DOCUMENT_UPLOAD_MAX_BYTES
        assert detail["safe_context"] == {
            "upload_surface": "claim_document_upload",
            "raw_filename_included": False,
            "raw_document_text_included": False,
            "raw_file_bytes_included": False,
            "raw_pdf_parser_error_included": False,
            "raw_exception_message_included": False,
        }
        assert "synthetic-large-denial.pdf" not in str(detail)
        mock_file.read.assert_awaited_once_with(CLAIM_DOCUMENT_UPLOAD_MAX_BYTES + 1)
        mock_process.assert_not_called()
        mock_analyze.assert_not_called()
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_disguised_inner_extension_before_read(self):
        from app.api.v1.claims import upload_document
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-denial.php.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"synthetic denial text")

        with patch("app.utils.file_processing.FileProcessor.process_file") as mock_process, \
            patch("app.api.v1.claims.DocumentAnalysisService.analyze_document") as mock_analyze, \
            patch("app.api.v1.claims.log_audit") as mock_log:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "suspicious_extension_chain"
        assert detail["processing_stage"] == "file_validation"
        assert detail["source_filename_present"] is True
        assert detail["source_file_extension"] == ".txt"
        assert detail["source_mime_type"] == "text/plain"
        assert detail["safe_context"]["inner_extension_chain_checked"] is True
        assert detail["safe_context"]["raw_filename_included"] is False
        assert detail["safe_context"]["raw_document_text_included"] is False
        assert "synthetic-denial.php.txt" not in str(detail)
        mock_file.read.assert_not_awaited()
        mock_process.assert_not_called()
        mock_analyze.assert_not_called()
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_empty_file_before_processing(self):
        from app.api.v1.claims import upload_document
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-empty-denial.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"")

        with patch("app.utils.file_processing.FileProcessor.process_file") as mock_process:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error_code"] == "empty_file"
        assert exc_info.value.detail["processing_stage"] == "file_validation"
        assert exc_info.value.detail["content_length"] == 0
        assert "synthetic-empty-denial.txt" not in str(exc_info.value.detail)
        mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_file_processing_failure_with_safe_metadata(self):
        from app.api.v1.claims import CLAIM_DOCUMENT_UPLOAD_MAX_BYTES, upload_document
        from app.utils.file_processing import FileProcessingError
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-image-denial.png"
        mock_file.content_type = "image/png"
        mock_file.read = AsyncMock(return_value=b"not-real-image-bytes")

        with patch(
            "app.utils.file_processing.FileProcessor.process_file",
            side_effect=FileProcessingError("synthetic processor failure"),
        ) as mock_process, patch(
            "app.api.v1.claims.DocumentAnalysisService.analyze_document"
        ) as mock_analyze:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "file_processing_failed"
        assert detail["processing_stage"] == "file_processing"
        assert detail["source_file_extension"] == ".png"
        assert detail["source_mime_type"] == "image/png"
        assert detail["content_length"] == len(b"not-real-image-bytes")
        assert detail["max_upload_size_bytes"] == CLAIM_DOCUMENT_UPLOAD_MAX_BYTES
        assert detail["exception_type"] == "FileProcessingError"
        assert detail["safe_context"]["raw_exception_message_included"] is False
        assert detail["safe_context"]["raw_file_bytes_included"] is False
        assert "synthetic-image-denial.png" not in str(detail)
        assert "synthetic processor failure" not in str(detail)
        mock_process.assert_called_once()
        mock_analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_processed_file_too_large_with_safe_metadata(self):
        from app.api.v1.claims import CLAIM_DOCUMENT_UPLOAD_MAX_BYTES, upload_document
        from app.utils.file_processing import ProcessedFile
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-large-after-processing.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"synthetic denial letter text")
        processed_file = ProcessedFile(
            content=b"synthetic denial letter text",
            original_filename="synthetic-large-after-processing.txt",
            processed_filename="synthetic-large-after-processing.txt",
            file_type="text/plain",
            original_size=len(b"synthetic denial letter text"),
            processed_size=CLAIM_DOCUMENT_UPLOAD_MAX_BYTES + 1,
            was_resized=False,
            was_converted=False,
        )

        with patch(
            "app.utils.file_processing.FileProcessor.process_file",
            return_value=processed_file,
        ), patch("app.api.v1.claims.DocumentAnalysisService.analyze_document") as mock_analyze:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "processed_file_too_large"
        assert detail["processing_stage"] == "file_processing"
        assert detail["processed_size_bytes"] == CLAIM_DOCUMENT_UPLOAD_MAX_BYTES + 1
        assert detail["safe_context"]["raw_filename_included"] is False
        assert "synthetic-large-after-processing.txt" not in str(detail)
        mock_analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_unreadable_pdf_with_safe_metadata(self):
        from app.api.v1.claims import upload_document
        from app.utils.file_processing import ProcessedFile
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-broken-denial.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"not a valid pdf")
        processed_file = ProcessedFile(
            content=b"not a valid pdf",
            original_filename="synthetic-broken-denial.pdf",
            processed_filename="synthetic-broken-denial.pdf",
            file_type="application/pdf",
            original_size=len(b"not a valid pdf"),
            processed_size=len(b"not a valid pdf"),
            was_resized=False,
            was_converted=False,
        )

        with patch(
            "app.utils.file_processing.FileProcessor.process_file",
            return_value=processed_file,
        ), patch("app.api.v1.claims.DocumentAnalysisService.analyze_document") as mock_analyze:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "pdf_text_extraction_failed"
        assert detail["processing_stage"] == "text_extraction"
        assert detail["source_mime_type"] == "application/pdf"
        assert detail["exception_type"]
        assert detail["safe_context"]["raw_pdf_parser_error_included"] is False
        assert detail["safe_context"]["raw_exception_message_included"] is False
        assert "synthetic-broken-denial.pdf" not in str(detail)
        assert "not a valid pdf" not in str(detail)
        mock_analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_rejects_empty_text_extraction_with_safe_metadata(self):
        from app.api.v1.claims import upload_document
        from app.utils.file_processing import ProcessedFile
        from fastapi import HTTPException, UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "synthetic-blank-denial.txt"
        mock_file.content_type = "text/plain"
        mock_file.read = AsyncMock(return_value=b"   \n\t")
        processed_file = ProcessedFile(
            content=b"   \n\t",
            original_filename="synthetic-blank-denial.txt",
            processed_filename="synthetic-blank-denial.txt",
            file_type="text/plain",
            original_size=len(b"   \n\t"),
            processed_size=len(b"   \n\t"),
            was_resized=False,
            was_converted=False,
        )

        with patch(
            "app.utils.file_processing.FileProcessor.process_file",
            return_value=processed_file,
        ), patch("app.api.v1.claims.DocumentAnalysisService.analyze_document") as mock_analyze:
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, db=MagicMock())

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 400
        assert detail["error_code"] == "text_extraction_empty"
        assert detail["processing_stage"] == "text_extraction"
        assert detail["text_length"] == 0
        assert detail["processed_size_bytes"] == len(b"   \n\t")
        assert detail["safe_context"]["raw_document_text_included"] is False
        assert "synthetic-blank-denial.txt" not in str(detail)
        mock_analyze.assert_not_called()


class TestClaimsBatchAnalysis:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    @patch("app.api.v1.claims.get_db")
    async def test_batch_analyze_all_success(self, mock_get_db, mock_analyze):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_result = MagicMock()
        mock_result.document_type = "denial_letter"
        mock_result.payer_name = "BCBS"
        mock_result.denial_reason = None
        mock_result.denial_code = None
        mock_result.claim_amount = None
        mock_result.service_date = None
        mock_result.patient_name = None
        mock_result.policy_number = None
        mock_result.extracted_codes = []
        mock_result.analysis = "Test"
        mock_result.recommendations = []
        mock_result.appeal_strategy = None
        mock_result.analyzed_at = datetime.utcnow()

        mock_analyze.return_value = mock_result

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

        from app.api.v1.claims import analyze_documents_batch
        from app.schemas.claim import BatchDocumentAnalysisRequest

        request = BatchDocumentAnalysisRequest(
            documents=[
                {"document_text": "Document 1 with enough text for validation"},
                {"document_text": "Document 2 with enough text for validation"},
                {"document_text": "Document 3 with enough text for validation"},
            ]
        )

        result = await analyze_documents_batch(request=request, db=mock_db)

        assert result.total == 3
        assert result.successful == 3
        assert result.failed == 0

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    @patch("app.api.v1.claims.get_db")
    async def test_batch_analyze_partial_failure(self, mock_get_db, mock_analyze):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_result = MagicMock()
        mock_result.document_type = "denial_letter"
        mock_result.payer_name = "BCBS"
        mock_result.denial_reason = None
        mock_result.denial_code = None
        mock_result.claim_amount = None
        mock_result.service_date = None
        mock_result.patient_name = None
        mock_result.policy_number = None
        mock_result.extracted_codes = []
        mock_result.analysis = "Test"
        mock_result.recommendations = []
        mock_result.appeal_strategy = None
        mock_result.analyzed_at = datetime.utcnow()

        mock_analyze.return_value = mock_result
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

        from app.api.v1.claims import analyze_documents_batch
        from app.schemas.claim import BatchDocumentAnalysisRequest

        request = BatchDocumentAnalysisRequest(
            documents=[
                {"document_text": "Valid document with enough text"},
                {"document_text": "Short"},
            ]
        )

        result = await analyze_documents_batch(request=request, db=mock_db)

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_batch_analyze_logs_short_document_safe_failure_metadata(self, caplog):
        from app.api.v1.claims import analyze_documents_batch
        from app.schemas.claim import BatchDocumentAnalysisRequest

        mock_db = MagicMock()
        request = BatchDocumentAnalysisRequest(
            documents=[{"document_text": "Short"}],
        )

        with caplog.at_level(logging.WARNING, logger="app.api.v1.claims"):
            result = await analyze_documents_batch(request=request, db=mock_db)

        failure_logs = [
            record.document_batch_analysis_error
            for record in caplog.records
            if hasattr(record, "document_batch_analysis_error")
        ]
        assert result.total == 1
        assert result.successful == 0
        assert result.failed == 1
        assert len(failure_logs) == 1
        failure = failure_logs[0]
        assert failure["error_code"] == "document_text_too_short"
        assert failure["processing_stage"] == "document_validation"
        assert failure["document_index"] == 0
        assert failure["document_text_present"] is True
        assert failure["document_text_length"] == 5
        assert failure["safe_context"] == {
            "upload_surface": "batch_document_analysis",
            "raw_document_text_included": False,
            "raw_exception_message_included": False,
            "raw_prompt_included": False,
            "raw_model_response_included": False,
        }
        assert "Short" not in str(failure)

    @pytest.mark.asyncio
    @patch("app.api.v1.claims.DocumentAnalysisService.analyze_document")
    async def test_batch_analyze_logs_exception_safe_failure_metadata(
        self, mock_analyze, caplog
    ):
        from app.api.v1.claims import analyze_documents_batch
        from app.schemas.claim import BatchDocumentAnalysisRequest

        mock_db = MagicMock()
        mock_analyze.side_effect = RuntimeError("synthetic model failure text")
        request = BatchDocumentAnalysisRequest(
            documents=[
                {
                    "document_text": (
                        "Synthetic denial letter with enough text for validation"
                    )
                }
            ],
        )

        with caplog.at_level(logging.WARNING, logger="app.api.v1.claims"):
            result = await analyze_documents_batch(request=request, db=mock_db)

        failure_logs = [
            record.document_batch_analysis_error
            for record in caplog.records
            if hasattr(record, "document_batch_analysis_error")
        ]
        assert result.total == 1
        assert result.successful == 0
        assert result.failed == 1
        assert len(failure_logs) == 1
        failure = failure_logs[0]
        assert failure["error_code"] == "document_analysis_failed"
        assert failure["processing_stage"] == "document_analysis"
        assert failure["document_index"] == 0
        assert failure["exception_type"] == "RuntimeError"
        assert failure["safe_context"]["raw_exception_message_included"] is False
        assert failure["safe_context"]["raw_model_response_included"] is False
        assert "synthetic model failure text" not in str(failure)
        assert "Synthetic denial letter" not in str(failure)


class TestClaimsSubmit:
    @pytest.mark.asyncio
    @patch("app.api.v1.claims.get_db")
    @patch("app.services.prediction.PredictionService.predict_denial", new_callable=AsyncMock)
    async def test_submit_claim_with_codes(self, mock_predict, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_predict.return_value = (0.4, 0.8, [], [])

        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock(side_effect=lambda x: setattr(x, "id", 1))

        from app.api.v1.claims import submit_claim
        from app.schemas.claim import ClaimSubmitRequest

        request = ClaimSubmitRequest(
            patient_id=1,
            provider_id=1,
            claim_data={
                "amount": 500,
                "payer_name": "Synthetic Health Plan",
                "subscriber_id": "SYN-SUB-001",
                "service_date": "2026-01-15",
            },
            diagnosis_codes=["Z00.00"],
            procedure_codes=["99213"],
        )

        result = await submit_claim(request=request, db=mock_db)

        assert result.claim_id == 1
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

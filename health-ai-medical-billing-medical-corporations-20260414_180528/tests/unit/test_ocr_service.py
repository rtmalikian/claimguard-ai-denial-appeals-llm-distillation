import io

import pytest
from PIL import Image

from app.services.ocr import OcrResult, OcrService, OcrServiceError
from app.services.nvidia import NvidiaServiceError


def make_png(size=(120, 60)) -> bytes:
    image = Image.new("RGB", size, color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class TestOcrResult:
    def test_metadata(self):
        result = OcrResult(
            text="Denial Code: CO16",
            engine="nvidia_nemotron_parse",
            model="nvidia/nemotron-parse",
            pages=2,
            duration_ms=123,
            warnings=["synthetic warning"],
        )

        assert result.metadata() == {
            "engine": "nvidia_nemotron_parse",
            "model": "nvidia/nemotron-parse",
            "pages": 2,
            "duration_ms": 123,
            "warnings": ["synthetic warning"],
        }


class TestOcrService:
    @pytest.mark.asyncio
    async def test_extract_text_from_image_bytes(self, monkeypatch):
        service = OcrService()

        async def fake_ocr_png_bytes(png_bytes, source_filename, page_number):
            assert source_filename == "synthetic-denial.png"
            assert page_number is None
            assert png_bytes.startswith(b"\x89PNG")
            return "Payer: Synthetic Health\nDenial Code: CO16"

        monkeypatch.setattr(service, "_ocr_png_bytes", fake_ocr_png_bytes)

        result = await service.extract_text_from_image_bytes(
            make_png(),
            "synthetic-denial.png",
        )

        assert result.text == "Payer: Synthetic Health\nDenial Code: CO16"
        assert result.engine == "nvidia_nemotron_parse"
        assert result.model == "nvidia/nemotron-parse"
        assert result.pages == 1

    @pytest.mark.asyncio
    async def test_ocr_png_bytes_success(self, monkeypatch):
        async def fake_transcribe_image(**kwargs):
            assert kwargs["mime_type"] == "image/png"
            return "Claim Amount: $123.45"

        monkeypatch.setattr(
            "app.services.ocr.nvidia_service.transcribe_image",
            fake_transcribe_image,
        )

        text = await OcrService()._ocr_png_bytes(make_png(), "synthetic.png", None)

        assert text == "Claim Amount: $123.45"

    @pytest.mark.asyncio
    async def test_ocr_png_bytes_missing_api_key(self, monkeypatch):
        async def fake_transcribe_image(**kwargs):
            raise NvidiaServiceError(
                "NVIDIA_API_KEY is not configured.",
                "nvidia_api_key_missing",
                status_code=503,
            )

        monkeypatch.setattr(
            "app.services.ocr.nvidia_service.transcribe_image",
            fake_transcribe_image,
        )

        with pytest.raises(OcrServiceError) as exc:
            await OcrService()._ocr_png_bytes(make_png(), "synthetic.png", None)

        assert exc.value.error_type == "nvidia_api_key_missing"
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_ocr_png_bytes_unavailable(self, monkeypatch):
        async def fake_transcribe_image(**kwargs):
            raise NvidiaServiceError(
                "NVIDIA NIM is unavailable.",
                "nvidia_unavailable",
                status_code=503,
            )

        monkeypatch.setattr(
            "app.services.ocr.nvidia_service.transcribe_image",
            fake_transcribe_image,
        )

        with pytest.raises(OcrServiceError) as exc:
            await OcrService()._ocr_png_bytes(make_png(), "synthetic.png", None)

        assert exc.value.error_type == "nvidia_unavailable"
        assert exc.value.to_detail()["model"] == "nvidia/nemotron-parse"

    @pytest.mark.asyncio
    async def test_ocr_png_bytes_empty_response(self, monkeypatch):
        async def fake_transcribe_image(**kwargs):
            return "   "

        monkeypatch.setattr(
            "app.services.ocr.nvidia_service.transcribe_image",
            fake_transcribe_image,
        )

        with pytest.raises(OcrServiceError) as exc:
            await OcrService()._ocr_png_bytes(make_png(), "synthetic.png", None)

        assert exc.value.error_type == "ocr_empty_response"
        assert exc.value.status_code == 400

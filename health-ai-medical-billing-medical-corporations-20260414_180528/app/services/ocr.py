import asyncio
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps

from app.core.config import settings
from app.services.nvidia import NvidiaServiceError, nvidia_service

logger = logging.getLogger(__name__)


class OcrServiceError(Exception):
    def __init__(self, message: str, error_type: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.status_code = status_code

    def to_detail(self) -> dict[str, str]:
        return {
            "error": self.error_type,
            "message": self.message,
            "engine": settings.OCR_ENGINE,
            "model": settings.NVIDIA_OCR_MODEL,
        }


@dataclass
class OcrResult:
    text: str
    engine: str
    model: str
    pages: int = 1
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "model": self.model,
            "pages": self.pages,
            "duration_ms": self.duration_ms,
            "warnings": self.warnings,
        }


class OcrService:
    _semaphore = asyncio.Semaphore(1)

    OCR_PROMPT = (
        "Extract all visible text from this medical insurance denial document. "
        "Preserve line breaks, tables, payer names, claim identifiers, dates, dollar amounts, "
        "CPT/HCPCS codes, ICD-10 codes, CARC/RARC codes, policy numbers, and authorization "
        "references exactly as printed. Do not summarize. Do not infer missing words. Use "
        "[illegible] for unreadable text."
    )

    def __init__(self):
        self.model = settings.NVIDIA_OCR_MODEL
        self.timeout = settings.OCR_TIMEOUT
        self.max_pages = settings.OCR_MAX_PAGES
        self.render_dpi = settings.OCR_RENDER_DPI
        self.max_dimension = settings.OCR_MAX_DIMENSION

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "ok" if nvidia_service.api_key else "missing_api_key",
            "engine": settings.OCR_ENGINE,
            "model": self.model,
            "provider": "nvidia_nim",
            "base_url": nvidia_service.base_url,
        }

    async def extract_text_from_image_bytes(
        self,
        image_bytes: bytes,
        source_filename: str,
        page_number: int | None = None,
    ) -> OcrResult:
        start = time.perf_counter()
        png_bytes = self._prepare_image_for_ocr(image_bytes)
        text = await self._ocr_png_bytes(png_bytes, source_filename, page_number)
        duration_ms = int((time.perf_counter() - start) * 1000)
        return OcrResult(
            text=text,
            engine=settings.OCR_ENGINE,
            model=self.model,
            pages=1,
            duration_ms=duration_ms,
        )

    async def extract_text_from_pdf_scan(self, pdf_bytes: bytes, source_filename: str) -> OcrResult:
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:
            raise OcrServiceError(
                "Scanned PDF OCR requires pypdfium2 to render pages.",
                "ocr_pdf_renderer_missing",
                status_code=503,
            ) from exc

        start = time.perf_counter()
        try:
            pdf = pdfium.PdfDocument(pdf_bytes)
            page_count = len(pdf)
        except Exception as exc:
            self._log_failure(source_filename, None, "ocr_pdf_render_failed", exc)
            raise OcrServiceError(
                "Could not render scanned PDF for OCR.",
                "ocr_pdf_render_failed",
                status_code=400,
            ) from exc

        if page_count > self.max_pages:
            raise OcrServiceError(
                f"Scanned PDF has {page_count} pages; OCR limit is {self.max_pages} pages.",
                "ocr_pdf_page_limit_exceeded",
                status_code=400,
            )

        page_texts: list[str] = []
        for page_index in range(page_count):
            try:
                page = pdf[page_index]
                bitmap = page.render(scale=self.render_dpi / 72)
                pil_image = bitmap.to_pil()
                output = io.BytesIO()
                self._resize_image(pil_image).save(output, format="PNG", optimize=True)
            except Exception as exc:
                self._log_failure(
                    source_filename, page_index + 1, "ocr_pdf_page_render_failed", exc
                )
                raise OcrServiceError(
                    f"Could not render PDF page {page_index + 1} for OCR.",
                    "ocr_pdf_page_render_failed",
                    status_code=400,
                ) from exc

            page_text = await self._ocr_png_bytes(output.getvalue(), source_filename, page_index + 1)
            page_texts.append(f"--- Page {page_index + 1} ---\n{page_text.strip()}")

        duration_ms = int((time.perf_counter() - start) * 1000)
        return OcrResult(
            text="\n\n".join(page_texts).strip(),
            engine=settings.OCR_ENGINE,
            model=self.model,
            pages=page_count,
            duration_ms=duration_ms,
        )

    def _prepare_image_for_ocr(self, image_bytes: bytes) -> bytes:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image)
            output = io.BytesIO()
            self._resize_image(image).save(output, format="PNG", optimize=True)
            return output.getvalue()
        except Exception as exc:
            raise OcrServiceError(
                "Could not prepare image for OCR.",
                "ocr_image_prepare_failed",
                status_code=400,
            ) from exc

    def _resize_image(self, image: Image.Image) -> Image.Image:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        width, height = image.size
        largest = max(width, height)
        if largest <= self.max_dimension:
            return image
        scale = self.max_dimension / largest
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        return image.resize(new_size, Image.Resampling.LANCZOS)

    async def _ocr_png_bytes(
        self,
        png_bytes: bytes,
        source_filename: str,
        page_number: int | None,
    ) -> str:
        try:
            async with self._semaphore:
                text = await nvidia_service.transcribe_image(
                    image_bytes=png_bytes,
                    mime_type="image/png",
                    prompt=self.OCR_PROMPT,
                    timeout=self.timeout,
                )
        except NvidiaServiceError as exc:
            self._log_failure(source_filename, page_number, exc.error_type, exc)
            raise OcrServiceError(
                exc.message,
                exc.error_type,
                status_code=exc.status_code,
            ) from exc
        except Exception as exc:
            self._log_failure(source_filename, page_number, "ocr_request_failed", exc)
            raise OcrServiceError(
                "NVIDIA OCR request failed.",
                "ocr_request_failed",
                status_code=503,
            ) from exc

        text = text.strip()
        if not text:
            raise OcrServiceError(
                "NVIDIA OCR returned no extracted text.",
                "ocr_empty_response",
                status_code=400,
            )
        return text

    def _log_failure(
        self,
        source_filename: str,
        page_number: int | None,
        error_type: str,
        exc: Exception,
    ) -> None:
        logger.error(
            "ocr_failure",
            extra={
                "ocr_error": {
                    "filename": source_filename,
                    "page_number": page_number,
                    "engine": settings.OCR_ENGINE,
                    "model": self.model,
                    "error_type": error_type,
                    "exception_type": type(exc).__name__,
                }
            },
        )

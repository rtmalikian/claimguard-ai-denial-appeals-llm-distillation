"""
File processing utility for handling uploads.
Supports image resizing, compression, and format conversion.
"""

import io
import logging
import warnings
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessedFile:
    content: bytes
    original_filename: str
    processed_filename: str
    file_type: str
    original_size: int
    processed_size: int
    was_resized: bool
    was_converted: bool


class FileProcessingError(Exception):
    """Raised when file processing fails."""

    pass


class FileProcessor:
    """Handles file processing operations including resize, compress, and convert."""

    MAX_DIMENSION = 4096
    MAX_IMAGE_PIXELS = 50_000_000
    MAX_FILE_SIZE_MB = 10
    JPEG_QUALITY = 85
    PNG_COMPRESSION = 6

    SUPPORTED_IMAGE_TYPES = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }

    SUPPORTED_DOCUMENT_TYPES = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".denial": "text/plain",
    }

    @classmethod
    def get_file_type(cls, filename: str) -> Optional[str]:
        """Detect file type from filename extension."""
        if not filename:
            return None
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        return f".{ext}"

    @classmethod
    def is_supported_type(cls, filename: str) -> bool:
        """Check if file type is supported."""
        file_type = cls.get_file_type(filename)
        if not file_type:
            return False
        return file_type in cls.SUPPORTED_IMAGE_TYPES or file_type in cls.SUPPORTED_DOCUMENT_TYPES

    @classmethod
    def get_mime_type(cls, filename: str) -> str:
        """Get MIME type from filename."""
        file_type = cls.get_file_type(filename)
        if not file_type:
            return "application/octet-stream"
        return cls.SUPPORTED_IMAGE_TYPES.get(
            file_type, cls.SUPPORTED_DOCUMENT_TYPES.get(file_type, "application/octet-stream")
        )

    @classmethod
    def _open_image_safely(cls, file_bytes: bytes):
        from PIL import Image

        previous_max_pixels = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = cls.MAX_IMAGE_PIXELS
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                img = Image.open(io.BytesIO(file_bytes))
                width, height = img.size
                pixel_count = int(width) * int(height)
                if pixel_count > cls.MAX_IMAGE_PIXELS:
                    img.close()
                    raise FileProcessingError("Image pixel count exceeds safety limit")
                return img
        finally:
            Image.MAX_IMAGE_PIXELS = previous_max_pixels

    @classmethod
    def process_image(
        cls,
        file_bytes: bytes,
        original_filename: str,
        max_size_mb: int = None,
        max_dimension: int = None,
        target_format: str = "JPEG",
    ) -> ProcessedFile:
        """
        Process an image file: resize if needed, compress, optionally convert format.

        Args:
            file_bytes: Raw file bytes
            original_filename: Original filename
            max_size_mb: Maximum file size in MB (default: 10)
            max_dimension: Maximum dimension in pixels (default: 4096)
            target_format: Target format (JPEG, PNG)

        Returns:
            ProcessedFile with processed content and metadata
        """
        if max_size_mb is None:
            max_size_mb = cls.MAX_FILE_SIZE_MB
        if max_dimension is None:
            max_dimension = cls.MAX_DIMENSION

        max_size_bytes = max_size_mb * 1024 * 1024
        original_size = len(file_bytes)
        was_resized = False
        was_converted = False
        processed_filename = original_filename

        try:
            from PIL import Image

            img = cls._open_image_safely(file_bytes)

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            original_width, original_height = img.size

            needs_resize = (
                original_width > max_dimension
                or original_height > max_dimension
                or original_size > max_size_bytes
            )

            if needs_resize:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                was_resized = True

            output = io.BytesIO()

            if target_format.upper() == "JPEG":
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(
                    output,
                    format="JPEG",
                    quality=cls.JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                if not processed_filename.lower().endswith((".jpg", ".jpeg")):
                    base_name = (
                        processed_filename.rsplit(".", 1)[0]
                        if "." in processed_filename
                        else processed_filename
                    )
                    processed_filename = f"{base_name}.jpg"
                    was_converted = True

            elif target_format.upper() == "PNG":
                img.save(
                    output,
                    format="PNG",
                    optimize=True,
                    compress_level=cls.PNG_COMPRESSION,
                )
                if not processed_filename.lower().endswith(".png"):
                    base_name = (
                        processed_filename.rsplit(".", 1)[0]
                        if "." in processed_filename
                        else processed_filename
                    )
                    processed_filename = f"{base_name}.png"
                    was_converted = True

            processed_bytes = output.getvalue()

            current_size = len(processed_bytes)
            quality = cls.JPEG_QUALITY

            while current_size > max_size_bytes and quality > 30:
                quality -= 10
                output = io.BytesIO()
                img.save(
                    output,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )
                processed_bytes = output.getvalue()
                current_size = len(processed_bytes)

            if current_size > max_size_bytes:
                scale = (max_size_bytes / current_size) ** 0.5
                new_width = int(original_width * scale)
                new_height = int(original_height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                img.save(
                    output,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                )
                processed_bytes = output.getvalue()
                was_resized = True

            return ProcessedFile(
                content=processed_bytes,
                original_filename=original_filename,
                processed_filename=processed_filename,
                file_type=cls.get_mime_type(processed_filename),
                original_size=original_size,
                processed_size=len(processed_bytes),
                was_resized=was_resized,
                was_converted=was_converted,
            )

        except ImportError:
            logger.warning("Pillow not installed, skipping image processing")
            return ProcessedFile(
                content=file_bytes,
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type=cls.get_mime_type(original_filename),
                original_size=original_size,
                processed_size=original_size,
                was_resized=False,
                was_converted=False,
            )
        except FileProcessingError:
            raise
        except Exception as e:
            logger.error(
                "Image processing failed",
                extra={
                    "file_processing_error": {
                        "stage": "image_processing",
                        "exception_type": type(e).__name__,
                        "raw_filename_included": False,
                        "raw_file_bytes_included": False,
                        "raw_exception_message_included": False,
                    },
                },
            )
            raise FileProcessingError("Failed to process image safely")

    @classmethod
    def compress_pdf(
        cls,
        file_bytes: bytes,
        original_filename: str,
        max_size_mb: int = None,
    ) -> ProcessedFile:
        """
        Compress PDF if it exceeds size limit.

        Args:
            file_bytes: Raw file bytes
            original_filename: Original filename
            max_size_mb: Maximum file size in MB

        Returns:
            ProcessedFile with processed content and metadata
        """
        if max_size_mb is None:
            max_size_mb = cls.MAX_FILE_SIZE_MB

        original_size = len(file_bytes)
        max_size_bytes = max_size_mb * 1024 * 1024

        if original_size <= max_size_bytes:
            return ProcessedFile(
                content=file_bytes,
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type="application/pdf",
                original_size=original_size,
                processed_size=original_size,
                was_resized=False,
                was_converted=False,
            )

        try:
            from pypdf import PdfReader, PdfWriter

            reader = PdfReader(io.BytesIO(file_bytes))
            writer = PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            writer.optimize_resources()
            output = io.BytesIO()
            writer.write(output)

            compressed_bytes = output.getvalue()

            compression_ratio = original_size / len(compressed_bytes)
            logger.info(f"PDF compression ratio: {compression_ratio:.2f}x")

            return ProcessedFile(
                content=compressed_bytes,
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type="application/pdf",
                original_size=original_size,
                processed_size=len(compressed_bytes),
                was_resized=True,
                was_converted=False,
            )

        except ImportError:
            logger.warning("pypdf not installed, skipping PDF compression")
            return ProcessedFile(
                content=file_bytes,
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type="application/pdf",
                original_size=original_size,
                processed_size=original_size,
                was_resized=False,
                was_converted=False,
            )
        except Exception as e:
            logger.error(f"PDF compression failed: {e}")
            raise FileProcessingError(f"Failed to compress PDF: {e}")

    @classmethod
    def process_file(
        cls,
        file_bytes: bytes,
        filename: str,
        max_size_mb: int = None,
    ) -> ProcessedFile:
        """
        Process any supported file type.

        Args:
            file_bytes: Raw file bytes
            filename: Filename for type detection
            max_size_mb: Maximum file size in MB

        Returns:
            ProcessedFile with processed content and metadata
        """
        file_type = cls.get_file_type(filename)

        if file_type in cls.SUPPORTED_IMAGE_TYPES:
            return cls.process_image(
                file_bytes,
                filename,
                max_size_mb=max_size_mb,
                target_format="JPEG",
            )
        elif file_type == ".pdf":
            return cls.compress_pdf(
                file_bytes,
                filename,
                max_size_mb=max_size_mb,
            )
        else:
            original_size = len(file_bytes)
            return ProcessedFile(
                content=file_bytes,
                original_filename=filename,
                processed_filename=filename,
                file_type=cls.get_mime_type(filename),
                original_size=original_size,
                processed_size=original_size,
                was_resized=False,
                was_converted=False,
            )


def get_file_info(filename: str, file_size: int) -> dict:
    """Get formatted file information."""
    from app.utils.format import format_file_size

    file_type = FileProcessor.get_file_type(filename)
    mime_type = FileProcessor.get_mime_type(filename)

    return {
        "filename": filename,
        "file_type": file_type,
        "mime_type": mime_type,
        "size_bytes": file_size,
        "size_formatted": format_file_size(file_size),
        "is_supported": FileProcessor.is_supported_type(filename),
    }

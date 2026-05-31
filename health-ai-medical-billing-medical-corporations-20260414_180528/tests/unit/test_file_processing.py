import pytest
from unittest.mock import MagicMock, patch
import io


class TestFileProcessor:
    def test_get_file_type_pdf(self):
        from app.utils.file_processing import FileProcessor

        file_type = FileProcessor.get_file_type("document.pdf")
        assert file_type == ".pdf"

    def test_get_file_type_jpeg(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.get_file_type("photo.jpg") == ".jpg"
        assert FileProcessor.get_file_type("photo.jpeg") == ".jpeg"

    def test_get_file_type_png(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.get_file_type("image.png") == ".png"

    def test_tiff_is_supported_for_ocr_uploads(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.is_supported_type("denial-scan.tif") is True
        assert FileProcessor.is_supported_type("denial-scan.tiff") is True
        assert FileProcessor.get_mime_type("denial-scan.tif") == "image/tiff"
        assert FileProcessor.get_mime_type("denial-scan.tiff") == "image/tiff"

    def test_get_file_type_none(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.get_file_type("") is None
        assert FileProcessor.get_file_type(None) is None

    def test_is_supported_type(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.is_supported_type("doc.pdf") is True
        assert FileProcessor.is_supported_type("doc.txt") is True
        assert FileProcessor.is_supported_type("photo.jpg") is True
        assert FileProcessor.is_supported_type("photo.png") is True
        assert FileProcessor.is_supported_type("file.exe") is False

    def test_get_mime_type(self):
        from app.utils.file_processing import FileProcessor

        assert FileProcessor.get_mime_type("doc.pdf") == "application/pdf"
        assert FileProcessor.get_mime_type("photo.jpg") == "image/jpeg"
        assert FileProcessor.get_mime_type("photo.png") == "image/png"
        assert FileProcessor.get_mime_type("doc.txt") == "text/plain"


class TestFileProcessingWithMock:
    def test_process_text_file(self):
        from app.utils.file_processing import FileProcessor

        test_bytes = b"plain text content"
        result = FileProcessor.process_file(
            file_bytes=test_bytes,
            filename="test.txt",
        )

        assert result.content == test_bytes
        assert result.original_filename == "test.txt"
        assert result.file_type == "text/plain"


class TestProcessedFile:
    def test_processed_file_dataclass(self):
        from app.utils.file_processing import ProcessedFile

        pf = ProcessedFile(
            content=b"file content",
            original_filename="original.pdf",
            processed_filename="processed.jpg",
            file_type="image/jpeg",
            original_size=1000,
            processed_size=800,
            was_resized=True,
            was_converted=True,
        )

        assert pf.original_filename == "original.pdf"
        assert pf.processed_filename == "processed.jpg"
        assert pf.was_resized is True
        assert pf.was_converted is True
        assert pf.processed_size < pf.original_size


class TestFileProcessingErrors:
    def test_file_processing_error(self):
        from app.utils.file_processing import FileProcessingError

        error = FileProcessingError("Test error message")
        assert str(error) == "Test error message"

    def test_process_image_rejects_excessive_pixel_count_before_decode(self):
        Image = pytest.importorskip("PIL.Image")
        from app.utils.file_processing import FileProcessingError, FileProcessor

        original_max_pixels = Image.MAX_IMAGE_PIXELS
        oversized_image = MagicMock()
        oversized_image.size = (FileProcessor.MAX_IMAGE_PIXELS + 1, 1)
        oversized_image.mode = "RGB"

        with patch("PIL.Image.open", return_value=oversized_image):
            with pytest.raises(FileProcessingError) as exc_info:
                FileProcessor.process_image(
                    file_bytes=b"synthetic image header",
                    original_filename="synthetic-large-scan.png",
                )

        assert "pixel count exceeds safety limit" in str(exc_info.value)
        assert Image.MAX_IMAGE_PIXELS == original_max_pixels
        oversized_image.close.assert_called_once()
        oversized_image.convert.assert_not_called()
        oversized_image.thumbnail.assert_not_called()

    def test_process_file_no_pillow(self):
        from app.utils.file_processing import FileProcessor

        test_bytes = b"some file content"
        result = FileProcessor.process_file(
            file_bytes=test_bytes,
            filename="test.txt",
        )

        assert result.content == test_bytes
        assert result.was_resized is False


class TestFormatFileSize:
    def test_format_bytes(self):
        from app.utils.format import format_file_size

        assert format_file_size(500) == "500 B"
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"

    def test_format_kilobytes(self):
        from app.utils.format import format_file_size

        assert format_file_size(1024 * 10) == "10.0 KB"
        assert format_file_size(1024 * 100) == "100.0 KB"

    def test_format_megabytes(self):
        from app.utils.format import format_file_size

        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 5) == "5.0 MB"

    def test_format_gigabytes(self):
        from app.utils.format import format_file_size

        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"


class TestTruncateText:
    def test_truncate_short_text(self):
        from app.utils.format import truncate_text

        text = "Short"
        result = truncate_text(text, max_length=100)
        assert result == "Short"

    def test_truncate_long_text(self):
        from app.utils.format import truncate_text

        text = "A" * 200
        result = truncate_text(text, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_custom_suffix(self):
        from app.utils.format import truncate_text

        text = "A" * 200
        result = truncate_text(text, max_length=50, suffix="...")
        assert result.endswith("...")


class TestFormatCurrency:
    def test_format_usd(self):
        from app.utils.format import format_currency

        assert format_currency(100.00) == "$100.00"
        assert format_currency(1234.56) == "$1,234.56"
        assert format_currency(0.99) == "$0.99"


class TestFormatPercentage:
    def test_format_percentage(self):
        from app.utils.format import format_percentage

        assert format_percentage(0.75) == "75.0%"
        assert format_percentage(0.5) == "50.0%"
        assert format_percentage(1.0) == "100.0%"

    def test_format_percentage_decimals(self):
        from app.utils.format import format_percentage

        assert format_percentage(0.333, decimals=2) == "33.30%"

"""Service for extracting text content from uploaded documents."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles text extraction from various document types."""

    def extract_text(self, file_path: str, mime_type: str) -> str:
        """
        Extract text content from a file based on its MIME type.

        Supports:
        - PDF: via PyMuPDF (fitz) with OCR fallback via pytesseract
        - Images: OCR via pytesseract
        - Plain text: direct read

        Args:
            file_path: Path to the file on disk.
            mime_type: MIME type of the file.

        Returns:
            Extracted text as a string.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if mime_type == "application/pdf":
            return self._extract_from_pdf(file_path)
        elif mime_type.startswith("image/"):
            return self._extract_from_image(file_path)
        elif mime_type.startswith("text/"):
            return self._extract_from_text(file_path)
        else:
            raise ValueError(f"Unsupported MIME type for text extraction: {mime_type}")

    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from a PDF file using PyMuPDF, with OCR fallback."""
        import fitz  # PyMuPDF

        text_parts: list[str] = []

        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc):
                page_text = page.get_text("text")

                if page_text.strip():
                    text_parts.append(page_text.strip())
                else:
                    # OCR fallback for scanned pages
                    logger.info(f"Page {page_num + 1} has no text, attempting OCR...")
                    ocr_text = self._ocr_pdf_page(page)
                    if ocr_text:
                        text_parts.append(ocr_text)

            doc.close()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

        return "\n\n".join(text_parts)

    def _ocr_pdf_page(self, page) -> str:
        """Run OCR on a single PDF page rendered as an image."""
        try:
            import pytesseract
            from PIL import Image
            import io

            # Render page to a pixmap at 300 DPI
            mat = __import__("fitz").Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))

            return pytesseract.image_to_string(image).strip()
        except ImportError:
            logger.warning("pytesseract not installed; skipping OCR fallback.")
            return ""
        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""

    def _extract_from_image(self, file_path: str) -> str:
        """Extract text from an image file using pytesseract OCR."""
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except ImportError:
            logger.error("pytesseract or Pillow not installed.")
            raise
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            raise

    def _extract_from_text(self, file_path: str) -> str:
        """Read text directly from a plain text file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except UnicodeDecodeError:
            # Fallback to latin-1 if UTF-8 fails
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read().strip()

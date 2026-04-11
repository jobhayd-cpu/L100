from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Supported file extensions
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
TEXT_EXTENSIONS = {".txt"}


def compute_sha256(file_path: str) -> str:
    safe_path = os.path.realpath(os.path.abspath(file_path))
    h = hashlib.sha256()
    with open(safe_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_folder(folder_path: str) -> List[str]:
    """Return list of PDF and image file paths found in folder_path (recursive)."""
    safe_folder = os.path.realpath(os.path.abspath(folder_path))
    found = []
    for root, _dirs, files in os.walk(safe_folder, followlinks=False):
        for fname in sorted(files):
            ext = Path(fname).suffix.lower()
            if ext in PDF_EXTENSIONS | IMAGE_EXTENSIONS | TEXT_EXTENSIONS:
                full_path = os.path.join(root, fname)
                # Ensure the resolved path is still within the base folder
                if os.path.realpath(full_path).startswith(safe_folder):
                    found.append(full_path)
    return found


def extract_pdf_text(file_path: str) -> List[Tuple[int, str, bool]]:
    """
    Extract text from a PDF file page by page.
    Returns list of (page_number_1based, text, is_ocr).
    Uses native extraction first; if a page yields <50 chars, marks for OCR.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf not installed")
        return []

    pages = []
    try:
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            pages.append((i, text, False))
    except Exception as exc:
        logger.warning("pypdf failed for %s: %s", file_path, exc)

    return pages


def render_pdf_page_to_image(file_path: str, page_number: int):
    """
    Render a single PDF page (1-based) to a PIL Image using pypdfium2.
    Returns PIL.Image or None.
    """
    try:
        import pypdfium2 as pdfium
        from PIL import Image
        import io

        pdf = pdfium.PdfDocument(file_path)
        # pypdfium2 uses 0-based index
        page = pdf[page_number - 1]
        bitmap = page.render(scale=2.0)  # 2x scale for better OCR
        pil_image = bitmap.to_pil()
        pdf.close()
        return pil_image
    except Exception as exc:
        logger.warning("pypdfium2 render failed for %s page %d: %s", file_path, page_number, exc)
        return None


def ocr_image(image, lang: str = "spa") -> Tuple[str, float]:
    """
    Run Tesseract OCR on a PIL image.
    Returns (text, confidence_0_to_100).
    """
    try:
        import pytesseract
        from app.config import get_settings

        settings = get_settings()
        if settings.tesseract_cmd and settings.tesseract_cmd != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

        data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )
        text = pytesseract.image_to_string(image, lang=lang)
        confidences = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
        avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.0
        return text.strip(), avg_conf
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return "", 0.0


def load_image_file(file_path: str):
    """Load an image file as PIL Image."""
    try:
        from PIL import Image
        return Image.open(file_path).convert("RGB")
    except Exception as exc:
        logger.warning("Failed to load image %s: %s", file_path, exc)
        return None


def extract_text_file(file_path: str) -> List[Tuple[int, str, bool]]:
    """
    Read a plain-text file and split it into logical pages of ~3 000 chars each.
    Returns list of (page_number_1based, text, is_ocr=False).
    """
    PAGE_CHARS = 3000
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as exc:
        logger.warning("Failed to read text file %s: %s", file_path, exc)
        return []

    pages = []
    for i, start in enumerate(range(0, max(len(content), 1), PAGE_CHARS), start=1):
        chunk = content[start : start + PAGE_CHARS].strip()
        if chunk:
            pages.append((i, chunk, False))
    return pages


def extract_pages(
    file_path: str,
    ocr_lang: str = "spa",
    ocr_threshold: int = 50,
) -> List[Tuple[int, str, bool, Optional[float]]]:
    """
    Extract all pages from a PDF, image, or plain-text file.
    Returns list of (page_number_1based, text, is_ocr, ocr_confidence).
    For scanned pages (text < ocr_threshold chars), falls back to OCR.
    For image files, always uses OCR.
    For .txt files, splits into logical pages of ~3 000 chars.
    """
    ext = Path(file_path).suffix.lower()
    results = []

    if ext in TEXT_EXTENSIONS:
        for page_num, text, is_ocr in extract_text_file(file_path):
            results.append((page_num, text, is_ocr, None))
        return results

    if ext in IMAGE_EXTENSIONS:
        img = load_image_file(file_path)
        if img:
            text, conf = ocr_image(img, lang=ocr_lang)
            results.append((1, text, True, conf))
        return results

    # PDF
    native_pages = extract_pdf_text(file_path)
    for page_num, text, _ in native_pages:
        if len(text) >= ocr_threshold:
            results.append((page_num, text, False, None))
        else:
            # Try OCR for this page
            img = render_pdf_page_to_image(file_path, page_num)
            if img is not None:
                ocr_text, conf = ocr_image(img, lang=ocr_lang)
                if len(ocr_text) > len(text):
                    results.append((page_num, ocr_text, True, conf))
                else:
                    results.append((page_num, text, False, None))
            else:
                results.append((page_num, text, False, None))

    return results

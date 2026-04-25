"""
Document Ingestor
-----------------
Parses and chunks documents from various formats (PDF, Markdown, DOCX, plain text).
Each chunk is stored with metadata: source filename, page number, chunk index.

Scanned-PDF support:
    Pages that yield no selectable text are rendered at high DPI and processed
    with Tesseract OCR (via pytesseract).  The ``ocr`` metadata flag lets
    downstream consumers know how the text was obtained.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF
import docx
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Optional OCR dependencies – gracefully degrade if not installed
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OCR helper
# ---------------------------------------------------------------------------

def _ocr_page(page: fitz.Page, dpi: int = 300) -> str:
    """Render a PyMuPDF page to a PIL image and run Tesseract OCR on it.

    Args:
        page: A ``fitz.Page`` object.
        dpi:  Resolution for rendering.  300 is a good balance between
              quality and speed; increase for very small text.

    Returns:
        Extracted text as a string (may be empty if OCR finds nothing).
    """
    if not OCR_AVAILABLE:
        logger.warning(
            "pytesseract or Pillow is not installed – OCR skipped. "
            "Install them with: pip install pytesseract Pillow"
        )
        return ""

    try:
        zoom = dpi / 72  # 72 is the default PDF resolution
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text: str = pytesseract.image_to_string(img)
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        logger.warning(
            "Tesseract OCR engine is not installed or not found on PATH. "
            "Scanned pages will be skipped. Install Tesseract from: "
            "https://github.com/UB-Mannheim/tesseract/wiki (Windows) "
            "or run 'sudo apt install tesseract-ocr' (Linux)."
        )
        return ""
    except Exception as exc:
        logger.warning(
            "OCR failed for page: %s – skipping. Error: %s",
            getattr(page, 'number', '?'),
            exc,
        )
        return ""


def load_pdf(filepath: str) -> List[Dict[str, Any]]:
    """Extract text from a PDF, falling back to OCR for scanned pages."""
    doc = fitz.open(filepath)
    pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text").strip()
        used_ocr = False

        # Fallback: if no selectable text, try OCR
        if not text:
            if OCR_AVAILABLE:
                logger.info(
                    "Page %d of '%s' has no selectable text – running OCR…",
                    page_num + 1,
                    Path(filepath).name,
                )
                text = _ocr_page(page)
                used_ocr = True
            else:
                logger.warning(
                    "Page %d of '%s' appears scanned but pytesseract/Pillow "
                    "are not installed – skipping.",
                    page_num + 1,
                    Path(filepath).name,
                )

        if text:
            pages.append({
                "content": text,
                "metadata": {
                    "source": Path(filepath).name,
                    "page": page_num + 1,
                    "filetype": "pdf",
                    "ocr": used_ocr,
                }
            })
    doc.close()
    return pages


def load_markdown(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return [{"content": content, "metadata": {"source": Path(filepath).name, "page": 1, "filetype": "markdown"}}]


def load_docx(filepath: str) -> List[Dict[str, Any]]:
    doc = docx.Document(filepath)
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return [{"content": text, "metadata": {"source": Path(filepath).name, "page": 1, "filetype": "docx"}}]


def load_txt(filepath: str) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return [{"content": content, "metadata": {"source": Path(filepath).name, "page": 1, "filetype": "txt"}}]


LOADERS = {".pdf": load_pdf, ".md": load_markdown, ".markdown": load_markdown, ".docx": load_docx, ".txt": load_txt}


def load_document(filepath: str) -> List[Dict[str, Any]]:
    ext = Path(filepath).suffix.lower()
    loader = LOADERS.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: {ext}")
    return loader(filepath)


def chunk_documents(docs: List[Dict[str, Any]], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Dict[str, Any]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for doc in docs:
        splits = splitter.split_text(doc["content"])
        for i, split in enumerate(splits):
            chunks.append({"content": split, "metadata": {**doc["metadata"], "chunk_index": i}})
    return chunks


def ingest_directory(directory: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[Dict[str, Any]]:
    all_chunks = []
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            ext = Path(filepath).suffix.lower()
            if ext in LOADERS:
                print(f"  Loading: {filename}")
                try:
                    docs = load_document(filepath)
                    chunks = chunk_documents(docs, chunk_size, chunk_overlap)
                    all_chunks.extend(chunks)
                    print(f"    -> {len(chunks)} chunks")
                except Exception as e:
                    print(f"    Failed: {e}")
    return all_chunks

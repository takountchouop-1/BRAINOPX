"""
rule_parser.py

Extracts plain text from rules files and user input files.

Supported formats:
    - .txt   → plain UTF-8 / latin-1 text
    - .pdf   → PDF text (requires the `pypdf` package)
    - .docx  → Office Open XML (requires the `python-docx` package)
    - .doc   → legacy Word (fallback: return the binary as readable-ish text)
    - .xlsx  → Excel cell text (optional convenience, via openpyxl)

Any file type is allowed; unsupported binary types degrade to a best-effort
read of the raw bytes.
"""
import os

from fastapi import HTTPException, status

# ── Optional imports (graceful degradation if a package is missing) ─────────
try:
    import pypdf
except Exception:  # pragma: no cover - environment dependent
    pypdf = None

try:
    import docx  # python-docx
except Exception:  # pragma: no cover - environment dependent
    docx = None

try:
    import openpyxl
except Exception:  # pragma: no cover - environment dependent
    openpyxl = None

MAX_CHARS = 60_000  # safety cap for AI context windows


def extract_text(file_path: str) -> str:
    """
    Extract plain text from any supported rules/input file.

    Raises:
        HTTPException(400) if the file can't be read.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found on server.",
        )

    try:
        if ext == ".txt":
            text = _read_txt(file_path)
        elif ext == ".pdf":
            text = _read_pdf(file_path)
        elif ext == ".docx":
            text = _read_docx(file_path)
        elif ext == ".doc":
            text = _read_doc(file_path)
        elif ext in (".xlsx", ".xls"):
            text = _read_excel(file_path)
        else:
            text = _read_raw(file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not extract text from file: {e}",
        )

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text was found in the file.",
        )

    # Cap length so we never blow past the model context window.
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...[truncated]"

    return text


def _read_txt(path: str) -> str:
    for encoding in ("utf-8", "latin-1", "utf-16"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    # Final fallback
    with open(path, "r", encoding="latin-1") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    if pypdf is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Reading PDF files requires the 'pypdf' package. "
                "Install it with: pip install pypdf"
            ),
        )
    reader = pypdf.PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _read_docx(path: str) -> str:
    if docx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Reading .docx files requires the 'python-docx' package. "
                "Install it with: pip install python-docx"
            ),
        )
    document = docx.Document(path)
    parts = [p.text for p in document.paragraphs if p.text.strip()]

    # Also include text inside tables
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def _read_doc(path: str) -> str:
    # Legacy .doc is a binary OLE format. Best-effort: extract readable strings.
    with open(path, "rb") as f:
        data = f.read()

    # Try UTF-16-LE text extraction (common in older .doc files)
    try:
        text = data.decode("utf-16-le", errors="ignore")
        cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
        if len(cleaned.strip()) > 50:
            return cleaned
    except Exception:
        pass

    # Fallback: printable ASCII/UTF-8 chunks
    return "".join(ch for ch in data.decode("latin-1", errors="ignore") if ch.isprintable() or ch in "\n\r\t")


def _read_excel(path: str) -> str:
    if openpyxl is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reading Excel files requires the 'openpyxl' package.",
        )
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines = []
    for sheet in workbook.worksheets:
        lines.append(f"=== Sheet: {sheet.title} ===")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    workbook.close()
    return "\n".join(lines)


def _read_raw(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return "".join(ch for ch in data.decode("latin-1", errors="ignore") if ch.isprintable() or ch in "\n\r\t")


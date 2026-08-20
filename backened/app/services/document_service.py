"""
document_service.py

Builds downloadable PDF/Word reports from an assistant conversation.

Uses a small markdown-lite block parser — bold spans, numbered/bulleted
lists, and '#'/'##'/'###' headings — mirroring the frontend's
parseAssistantBlocks (components/ChatMessage.jsx), extended with heading
support so a structured report the assistant produces renders with real
heading hierarchy instead of literal '#' characters.
"""
import io
import re
from typing import Any, Dict, List, Tuple
from xml.sax.saxutils import escape as xml_escape

import docx
from docx.shared import Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# Caps so a very long conversation can't produce a pathologically large export.
MAX_TURNS = 40
MAX_TOTAL_CHARS = 40_000

BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


# ============================================================
# MARKDOWN-LITE BLOCK PARSER
# ============================================================

def parse_blocks(text: str) -> List[Dict[str, Any]]:
    """
    Splits message text into blocks: headings (h1/h2/h3), numbered/bulleted
    lists, and paragraphs.
    """
    lines = str(text or "").split("\n")
    blocks: List[Dict[str, Any]] = []
    current_list: Dict[str, Any] | None = None

    def flush_list():
        nonlocal current_list
        if current_list:
            blocks.append(current_list)
            current_list = None

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_list()
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            flush_list()
            level = len(heading.group(1))
            blocks.append({"type": f"h{level}", "text": heading.group(2).strip()})
            continue

        numbered = re.match(r"^\d+[.)]\s+(.*)$", line)
        if numbered:
            if not current_list or current_list["type"] != "ol":
                flush_list()
                current_list = {"type": "ol", "items": []}
            current_list["items"].append(numbered.group(1))
            continue

        bulleted = re.match(r"^[-•]\s+(.*)$", line)
        if bulleted:
            if not current_list or current_list["type"] != "ul":
                flush_list()
                current_list = {"type": "ul", "items": []}
            current_list["items"].append(bulleted.group(1))
            continue

        flush_list()
        blocks.append({"type": "p", "text": line})

    flush_list()
    return blocks


def _bold_runs(text: str) -> List[Tuple[str, bool]]:
    """Splits text on **bold** markers into (text, is_bold) runs."""
    runs: List[Tuple[str, bool]] = []
    pos = 0
    for match in BOLD_RE.finditer(text):
        if match.start() > pos:
            runs.append((text[pos:match.start()], False))
        runs.append((match.group(1), True))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], False))
    return runs or [("", False)]


# ============================================================
# TRANSCRIPT PREP
# ============================================================

def _trim_turns(
    turns: List[Tuple[str, str, str]],
) -> Tuple[List[Tuple[str, str, str]], bool]:
    """Caps a conversation transcript so exports can't grow unbounded."""

    trimmed = turns[-MAX_TURNS:] if len(turns) > MAX_TURNS else list(turns)

    total = 0
    kept: List[Tuple[str, str, str]] = []
    for turn in reversed(trimmed):
        total += len(turn[2])
        if total > MAX_TOTAL_CHARS and kept:
            break
        kept.append(turn)
    kept.reverse()

    omitted = len(turns) - len(kept)
    return kept, omitted > 0


# ============================================================
# DOCX
# ============================================================

def build_docx(title: str, turns: List[Tuple[str, str, str]]) -> bytes:
    """turns: list of (speaker_label, timestamp_str, content)."""

    turns, trimmed = _trim_turns(turns)

    document = docx.Document()
    document.add_heading(title, level=1)

    if trimmed:
        note = document.add_paragraph()
        note.add_run("(earlier messages omitted for length)").italic = True

    for speaker, timestamp, content in turns:
        heading = document.add_heading(level=2)
        run = heading.add_run(speaker + (f" — {timestamp}" if timestamp else ""))
        run.font.size = Pt(13)

        for block in parse_blocks(content):
            _write_docx_block(document, block)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _write_docx_block(document, block: Dict[str, Any]) -> None:
    block_type = block["type"]

    if block_type in ("h1", "h2", "h3"):
        # Offset so a block heading nests visually under the turn heading (level 2).
        level = min(int(block_type[1]) + 1, 4)
        document.add_heading(block["text"], level=level)
        return

    if block_type in ("ul", "ol"):
        style = "List Bullet" if block_type == "ul" else "List Number"
        for item in block["items"]:
            paragraph = document.add_paragraph(style=style)
            _write_docx_runs(paragraph, item)
        return

    paragraph = document.add_paragraph()
    _write_docx_runs(paragraph, block["text"])


def _write_docx_runs(paragraph, text: str) -> None:
    for run_text, bold in _bold_runs(text):
        if not run_text:
            continue
        run = paragraph.add_run(run_text)
        run.bold = bold


# ============================================================
# PDF
# ============================================================

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("BxTitle", parent=_STYLES["Title"], spaceAfter=14)
_TURN_STYLE = ParagraphStyle(
    "BxTurn", parent=_STYLES["Heading2"], spaceBefore=14, spaceAfter=6
)
_H_STYLES = {
    "h1": ParagraphStyle("BxH1", parent=_STYLES["Heading2"], spaceBefore=8, spaceAfter=4),
    "h2": ParagraphStyle("BxH2", parent=_STYLES["Heading3"], spaceBefore=6, spaceAfter=4),
    "h3": ParagraphStyle("BxH3", parent=_STYLES["Heading4"], spaceBefore=6, spaceAfter=4),
}
_BODY_STYLE = ParagraphStyle("BxBody", parent=_STYLES["BodyText"], spaceAfter=6, leading=15)
_NOTE_STYLE = ParagraphStyle(
    "BxNote", parent=_STYLES["BodyText"], textColor=colors.HexColor("#666666")
)


def _pdf_markup(text: str) -> str:
    """
    Escapes text for reportlab's Paragraph mini-XML, then re-wraps **bold**
    spans as real <b> tags. Escaping must happen before wrapping — otherwise
    a message containing a literal '<' or '&' (e.g. "<foo@bar.com>") crashes
    the PDF build, since Paragraph parses its input as a small XML grammar.
    """
    parts = []
    for run_text, bold in _bold_runs(text):
        escaped = xml_escape(run_text)
        parts.append(f"<b>{escaped}</b>" if bold else escaped)
    return "".join(parts)


def build_pdf(title: str, turns: List[Tuple[str, str, str]]) -> bytes:
    turns, trimmed = _trim_turns(turns)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: List[Any] = [Paragraph(xml_escape(title), _TITLE_STYLE)]

    if trimmed:
        story.append(Paragraph("(earlier messages omitted for length)", _NOTE_STYLE))
        story.append(Spacer(1, 8))

    for speaker, timestamp, content in turns:
        label = xml_escape(speaker + (f" — {timestamp}" if timestamp else ""))
        story.append(Paragraph(label, _TURN_STYLE))

        for block in parse_blocks(content):
            story.extend(_pdf_flowables(block))

    doc.build(story)
    return buffer.getvalue()


def _pdf_flowables(block: Dict[str, Any]) -> List[Any]:
    block_type = block["type"]

    if block_type in _H_STYLES:
        return [Paragraph(_pdf_markup(block["text"]), _H_STYLES[block_type])]

    if block_type in ("ul", "ol"):
        items = [
            ListItem(Paragraph(_pdf_markup(item), _BODY_STYLE)) for item in block["items"]
        ]
        bullet_type = "bullet" if block_type == "ul" else "1"
        return [ListFlowable(items, bulletType=bullet_type, leftIndent=18)]

    return [Paragraph(_pdf_markup(block["text"]), _BODY_STYLE)]

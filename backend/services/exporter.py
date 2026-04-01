"""Export notes and transcripts to Markdown and PDF."""
import io
import textwrap
from datetime import datetime
from typing import Optional

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from models.schemas import Notes, Transcript


# ── Markdown ──────────────────────────────────────────────────────────────────

def export_markdown(notes: Notes, transcript: Optional[Transcript] = None) -> str:
    lines = []

    lines.append(f"# {notes.title}")
    lines.append(f"*Generated: {notes.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*\n")

    lines.append("## Summary\n")
    lines.append(notes.summary + "\n")

    if notes.action_items:
        lines.append("## Action Items\n")
        for item in notes.action_items:
            lines.append(f"- {item}")
        lines.append("")

    if notes.key_timestamps:
        lines.append("## Key Timestamps\n")
        for kts in notes.key_timestamps:
            lines.append(f"- **{kts.formatted}** — {kts.label}: {kts.description}")
        lines.append("")

    for section in notes.sections:
        lines.append(f"## {section.heading}\n")
        if section.start_time is not None:
            m, s = divmod(int(section.start_time), 60)
            h, m2 = divmod(m, 60)
            ts = f"{h:02d}:{m2:02d}:{s:02d}" if h else f"{m2:02d}:{s:02d}"
            lines.append(f"*Starts at {ts}*\n")
        lines.append(section.content + "\n")

    if transcript:
        lines.append("---\n")
        lines.append("## Full Transcript\n")
        for seg in transcript.segments:
            lines.append(f"**{seg.timestamp}** {seg.text}")
        lines.append("")

    return "\n".join(lines)


# ── PDF ───────────────────────────────────────────────────────────────────────

class NotesPDF(FPDF):
    def __init__(self, title: str):
        super().__init__()
        self._doc_title = title
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        self.set_margins(20, 20, 20)

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, self._doc_title[:80], align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(200, 200, 200)
        self.line(20, self.get_y(), self.w - 20, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def h1(self, text: str):
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 10, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def h2(self, text: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(50, 80, 160)
        self.multi_cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(50, 80, 160)
        self.line(20, self.get_y(), self.w - 20, self.get_y())
        self.ln(3)

    def body(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        # Strip basic markdown formatting for PDF
        clean = _strip_markdown(text)
        self.multi_cell(0, 6, clean, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(50, 50, 50)
        clean = _strip_markdown(text)
        self.cell(6, 6, "\u2022", new_x=XPos.RIGHT)
        self.multi_cell(0, 6, clean, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def timestamp_row(self, ts: str, label: str, desc: str):
        self.set_font("Courier", "B", 9)
        self.set_text_color(30, 130, 100)
        self.cell(22, 6, ts, new_x=XPos.RIGHT)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(40, 40, 40)
        self.cell(50, 6, label[:40], new_x=XPos.RIGHT)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 6, desc, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def meta(self, text: str):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)


def export_pdf(notes: Notes, transcript: Optional[Transcript] = None) -> bytes:
    pdf = NotesPDF(title=notes.title)

    # Title
    pdf.h1(notes.title)
    pdf.meta(f"Generated: {notes.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    pdf.ln(2)

    # Summary
    pdf.h2("Summary")
    pdf.body(notes.summary)

    # Action Items
    if notes.action_items:
        pdf.h2("Action Items")
        for item in notes.action_items:
            pdf.bullet(item)

    # Key Timestamps
    if notes.key_timestamps:
        pdf.h2("Key Timestamps")
        for kts in notes.key_timestamps:
            pdf.timestamp_row(kts.formatted, kts.label, kts.description)

    # Sections
    for section in notes.sections:
        pdf.h2(section.heading)
        if section.start_time is not None:
            m, s = divmod(int(section.start_time), 60)
            h, m2 = divmod(m, 60)
            ts = f"{h:02d}:{m2:02d}:{s:02d}" if h else f"{m2:02d}:{s:02d}"
            pdf.meta(f"Starts at {ts}")
        # Render content line by line (handle bullet lists)
        for line in section.content.split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(2)
            elif line.startswith("- ") or line.startswith("* "):
                pdf.bullet(line[2:])
            else:
                pdf.body(line)

    # Transcript (optional)
    if transcript:
        pdf.add_page()
        pdf.h2("Full Transcript")
        for seg in transcript.segments:
            pdf.set_font("Courier", "B", 8)
            pdf.set_text_color(80, 120, 180)
            pdf.cell(18, 5, seg.timestamp, new_x=XPos.RIGHT)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, seg.text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def _strip_markdown(text: str) -> str:
    """Remove common markdown syntax for plain PDF rendering."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)         # italic
    text = re.sub(r"`(.+?)`", r"\1", text)            # inline code
    text = re.sub(r"#{1,6}\s*", "", text)             # headings
    return text

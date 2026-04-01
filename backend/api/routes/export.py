"""Export notes and transcript to Markdown or PDF."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, PlainTextResponse

import session_store
from services.exporter import export_markdown, export_pdf

router = APIRouter()


@router.get("/{session_id}/export")
def export(
    session_id: str,
    format: str = Query("markdown", pattern="^(markdown|pdf)$"),
    include_transcript: bool = Query(False),
):
    """Export notes as 'markdown' or 'pdf'."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.notes:
        raise HTTPException(400, "Notes not generated yet — call POST /{session_id}/notes first")

    transcript = session.transcript if include_transcript else None
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in session.title)[:60]

    if format == "pdf":
        data = export_pdf(session.notes, transcript)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )

    # Markdown
    md = export_markdown(session.notes, transcript)
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )

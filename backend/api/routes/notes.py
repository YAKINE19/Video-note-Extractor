"""Notes generation endpoint."""
import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks

import session_store
from models.schemas import Notes, NotesRequest, SessionStatus
from services.summarizer import generate_notes

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate(session_id: str, request: NotesRequest):
    session = session_store.get_session(session_id)
    if not session or not session.transcript:
        return
    try:
        notes = generate_notes(
            full_text=session.transcript.full_text,
            title=session.title,
            session_id=session_id,
            model=request.model,
        )
        session_store.save_notes(session_id, notes)
        logger.info("Notes generated for session %s", session_id)
    except Exception as exc:
        logger.exception("Notes generation failed for session %s", session_id)


@router.post("/{session_id}/notes", response_model=Notes, status_code=202)
async def generate_notes_endpoint(
    session_id: str,
    request: NotesRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger async notes generation for a session."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != SessionStatus.READY:
        raise HTTPException(400, f"Session not ready (status: {session.status})")
    if not session.transcript:
        raise HTTPException(400, "No transcript available")

    background_tasks.add_task(_generate, session_id, request)
    # Return a placeholder; client should poll GET /{session_id}
    return Notes(
        session_id=session_id,
        title=session.title,
        summary="Generating…",
        sections=[],
        key_timestamps=[],
        action_items=[],
    )


@router.get("/{session_id}/notes", response_model=Notes)
def get_notes(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if not session.notes:
        raise HTTPException(404, "Notes not yet generated")
    return session.notes

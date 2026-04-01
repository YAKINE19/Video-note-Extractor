"""Session management: create, list, get, delete."""
import os
import asyncio
import logging
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

import session_store
from models.schemas import (
    SessionCreate, SessionStatus, SessionSummary,
    YouTubeRequest, Transcript,
)
from services.audio_extractor import extract_from_youtube, extract_from_video, get_video_duration
from services.transcriber import transcribe_audio
from services.rag_service import index_transcript
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Background pipeline ───────────────────────────────────────────────────────

def _run_pipeline(session_id: str, source_type: str, source_path: str, whisper_model: str | None):
    """Full extraction + transcription pipeline (runs in a thread)."""
    try:
        # 1. Extract audio
        session_store.update_status(session_id, SessionStatus.EXTRACTING)
        if source_type == "youtube":
            audio_path, _ = extract_from_youtube(source_path, session_id)
        else:
            audio_path = extract_from_video(source_path, session_id)

        # 2. Transcribe
        session_store.update_status(session_id, SessionStatus.TRANSCRIBING)
        segments, full_text, language = transcribe_audio(audio_path, whisper_model)
        duration = get_video_duration(audio_path)

        transcript = Transcript(
            session_id=session_id,
            segments=segments,
            full_text=full_text,
            language=language,
            duration=duration,
        )
        session_store.save_transcript(session_id, transcript)

        # 3. Index in ChromaDB
        index_transcript(session_id, segments)

        session_store.update_status(session_id, SessionStatus.READY)
        logger.info("Pipeline complete for session %s", session_id)

    except Exception as exc:
        logger.exception("Pipeline failed for session %s", session_id)
        session_store.update_status(session_id, SessionStatus.FAILED, str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=SessionCreate, status_code=202)
async def create_youtube_session(
    payload: YouTubeRequest,
    background_tasks: BackgroundTasks,
):
    """Start processing a YouTube URL."""
    session = session_store.create_session(
        title=payload.url,   # will be updated with real title later
        source=payload.url,
    )
    background_tasks.add_task(
        _run_pipeline,
        session.session_id,
        "youtube",
        payload.url,
        payload.whisper_model,
    )
    return session


@router.post("/upload", response_model=SessionCreate, status_code=202)
async def create_upload_session(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    whisper_model: str = Form(None),
):
    """Upload a video file and start processing."""
    ext = os.path.splitext(file.filename)[-1].lower()
    allowed = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".mp3", ".wav", ".m4a"}
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    session = session_store.create_session(title=file.filename, source=file.filename)
    save_path = os.path.join(settings.upload_dir, f"{session.session_id}{ext}")

    # Save upload synchronously before returning
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    background_tasks.add_task(
        _run_pipeline,
        session.session_id,
        "file",
        save_path,
        whisper_model,
    )
    return session


@router.get("", response_model=List[SessionSummary])
def list_sessions():
    return [
        SessionSummary(
            session_id=s.session_id,
            title=s.title,
            source=s.source,
            status=s.status,
            created_at=s.created_at,
            has_transcript=s.transcript is not None,
            has_notes=s.notes is not None,
        )
        for s in session_store.list_sessions()
    ]


@router.get("/{session_id}", response_model=SessionCreate)
def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str):
    from services.rag_service import delete_session_index
    delete_session_index(session_id)
    if not session_store.delete_session(session_id):
        raise HTTPException(404, "Session not found")

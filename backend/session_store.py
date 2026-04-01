"""In-memory session store with thread-safe operations.

In production, replace with Redis or a database backend.
"""
import threading
from datetime import datetime
from typing import Dict, Optional
from uuid import uuid4

from models.schemas import SessionCreate, SessionStatus, Transcript, Notes


_lock = threading.Lock()
_sessions: Dict[str, SessionCreate] = {}


def create_session(title: str, source: str) -> SessionCreate:
    session = SessionCreate(
        session_id=str(uuid4()),
        title=title,
        source=source,
        status=SessionStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    with _lock:
        _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Optional[SessionCreate]:
    with _lock:
        return _sessions.get(session_id)


def list_sessions() -> list[SessionCreate]:
    with _lock:
        return sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)


def update_status(session_id: str, status: SessionStatus, error: str | None = None) -> None:
    with _lock:
        session = _sessions.get(session_id)
        if session:
            session.status = status
            if error is not None:
                session.error = error


def save_transcript(session_id: str, transcript: Transcript) -> None:
    with _lock:
        session = _sessions.get(session_id)
        if session:
            session.transcript = transcript


def save_notes(session_id: str, notes: Notes) -> None:
    with _lock:
        session = _sessions.get(session_id)
        if session:
            session.notes = notes


def delete_session(session_id: str) -> bool:
    with _lock:
        return _sessions.pop(session_id, None) is not None

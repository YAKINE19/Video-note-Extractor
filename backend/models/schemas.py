from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime


class SessionStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    READY = "ready"
    FAILED = "failed"


# ── Requests ──────────────────────────────────────────────────────────────────

class YouTubeRequest(BaseModel):
    url: str
    whisper_model: Optional[str] = None   # override global default


class NotesRequest(BaseModel):
    # Optionally override the Ollama model for this request
    model: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None           # optionally override Ollama model


# ── Transcript ─────────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    index: int
    start: float      # seconds
    end: float        # seconds
    text: str

    @property
    def timestamp(self) -> str:
        def fmt(s: float) -> str:
            m, sec = divmod(int(s), 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        return fmt(self.start)


class Transcript(BaseModel):
    session_id: str
    segments: List[TranscriptSegment]
    full_text: str
    language: Optional[str] = None
    duration: Optional[float] = None   # seconds


# ── Notes ──────────────────────────────────────────────────────────────────────

class NoteSection(BaseModel):
    heading: str
    content: str
    start_time: Optional[float] = None   # seconds
    end_time: Optional[float] = None


class KeyTimestamp(BaseModel):
    time: float        # seconds
    label: str
    description: str

    @property
    def formatted(self) -> str:
        m, s = divmod(int(self.time), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class Notes(BaseModel):
    session_id: str
    title: str
    summary: str
    sections: List[NoteSection]
    key_timestamps: List[KeyTimestamp]
    action_items: List[str]
    generated_at: datetime = datetime.utcnow()


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatSource(BaseModel):
    text: str
    start: float
    end: float
    timestamp: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource]


# ── Session ───────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    session_id: str
    title: str
    source: str        # URL or filename
    status: SessionStatus
    created_at: datetime
    error: Optional[str] = None
    transcript: Optional[Transcript] = None
    notes: Optional[Notes] = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    source: str
    status: SessionStatus
    created_at: datetime
    has_transcript: bool
    has_notes: bool

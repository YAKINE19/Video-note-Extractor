"""Speech-to-text transcription.

Local mode  (no GROQ_API_KEY): openai-whisper runs on your machine
Cloud mode  (GROQ_API_KEY set): Groq Whisper API (free, whisper-large-v3-turbo)
"""
import logging
from typing import List

from config import settings
from models.schemas import TranscriptSegment

logger = logging.getLogger(__name__)

# ── Local Whisper cache ────────────────────────────────────────────────────────
_whisper_model = None
_loaded_model_name: str | None = None


def transcribe_audio(
    audio_path: str,
    whisper_model: str | None = None,
) -> tuple[List[TranscriptSegment], str, str]:
    """Transcribe an audio file.

    Returns (segments, full_text, language).
    Automatically chooses Groq API or local Whisper based on config.
    """
    if settings.use_groq:
        return _transcribe_groq(audio_path)
    return _transcribe_local(audio_path, whisper_model or settings.whisper_model)


# ── Groq (cloud) ──────────────────────────────────────────────────────────────

def _transcribe_groq(audio_path: str) -> tuple:
    """Transcribe using Groq's free Whisper API (no GPU, no torch)."""
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(audio_path.split("/")[-1], f),
            model=settings.groq_whisper_model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    raw_segs = getattr(response, "segments", []) or []
    segments = _parse_segments(raw_segs)
    full_text = (getattr(response, "text", "") or "").strip()
    language = getattr(response, "language", "en") or "en"

    logger.info("Groq Whisper: %d segments, language=%s", len(segments), language)
    return segments, full_text, language


# ── Local Whisper ─────────────────────────────────────────────────────────────

def _transcribe_local(audio_path: str, model_name: str) -> tuple:
    """Transcribe using a local Whisper model (requires torch)."""
    global _whisper_model, _loaded_model_name

    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "openai-whisper is not installed. Either install it "
            "(pip install openai-whisper) or set GROQ_API_KEY to use the "
            "cloud Whisper API instead."
        )

    if _whisper_model is None or _loaded_model_name != model_name:
        logger.info("Loading local Whisper model: %s", model_name)
        _whisper_model = whisper.load_model(model_name)
        _loaded_model_name = model_name

    result = _whisper_model.transcribe(audio_path, verbose=False, word_timestamps=False)

    segments = _parse_segments(result.get("segments", []))
    full_text = result.get("text", "").strip()
    language = result.get("language", "en")

    logger.info("Local Whisper: %d segments, language=%s", len(segments), language)
    return segments, full_text, language


# ── Shared ────────────────────────────────────────────────────────────────────

def _parse_segments(raw: list) -> List[TranscriptSegment]:
    segments = []
    for i, seg in enumerate(raw):
        if isinstance(seg, dict):
            start, end, text = seg.get("start", 0.0), seg.get("end", 0.0), seg.get("text", "").strip()
        else:
            start, end, text = (
                getattr(seg, "start", 0.0),
                getattr(seg, "end", 0.0),
                getattr(seg, "text", "").strip(),
            )
        if text:
            segments.append(TranscriptSegment(index=i, start=start, end=end, text=text))
    return segments
